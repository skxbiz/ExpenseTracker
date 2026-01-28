from services.firebase_db import firebase_service
from services.utils_fastapi import CATEGORIES
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Tuple

class DashboardService:
    def __init__(self, user_id: str, month_filter: str = None):
        self.user_id = user_id
        self.now = datetime.now()
        self.current_year = self.now.year
        self.months = [(self.now - relativedelta(months=i)).strftime("%Y-%m") for i in range(12)]
        self.month_filter = month_filter if month_filter in self.months else self.now.strftime("%Y-%m")
        self.year, self.month = map(int, self.month_filter.split("-"))
        self.start_of_month = datetime(self.year, self.month, 1)
        if self.month == 12:
            self.next_month = datetime(self.year + 1, 1, 1)
        else:
            self.next_month = datetime(self.year, self.month + 1, 1)

    def fetch_summary_networth(self) -> Tuple[Dict, Dict, float]:
        """Fetch summary data and networth for the dashboard"""
        try:
            # Get transactions for the current month filter
            print("Fetching transactions for user:", self.user_id)
            filters = {
                'start_date': self.start_of_month,
                'end_date': self.next_month
            }
        
            print("Filters:", filters)
            transactions = firebase_service.get_transactions(self.user_id, filters)
            print("Transactions:", transactions)
            
            # Group transactions by category and sub_category
            category_data = {}
            for txn in transactions:
                category = txn.get('category', 'Unknown')
                sub_category = txn.get('sub_category', 'Unknown')
                amount = float(txn.get('amount', 0))
                
                if category not in category_data:
                    category_data[category] = {}
                if sub_category not in category_data[category]:
                    category_data[category][sub_category] = 0
                # Sum amounts for same category and subcategory
                category_data[category][sub_category] += amount
            
            # Convert to the format expected by prepare_summary
            data = []
            for category, subcats in category_data.items():
                for sub_category, total in subcats.items():
                    data.append({
                        'category': category,
                        'sub_category': sub_category,
                        'total': total
                    })
            
            # Calculate networth for the current year
            year_start = datetime(self.current_year, 1, 1)
            year_end = datetime(self.current_year + 1, 1, 1)
            
            year_filters = {
                'start_date': year_start.isoformat(),
                'end_date': year_end.isoformat()
            }
            year_transactions = firebase_service.get_transactions(self.user_id, year_filters)
            
            networth = sum(float(txn.get('amount', 0)) for txn in year_transactions)
            
            summary, totals = self.prepare_summary(data)
            return summary, totals, networth
            
        except Exception as e:
            print(f"Error in fetch_summary_networth: {e}")
            # Return empty data on error
            summary = {cat: [{"sub_category": sub, "amount": 0} for sub in subs] for cat, subs in CATEGORIES.items()}
            totals = {cat: 0 for cat in CATEGORIES.keys()}
            return summary, totals, 0

    def prepare_summary(self, data: List[Dict]) -> Tuple[Dict, Dict]:
        """Prepare summary data grouped by categories and subcategories"""
        # Initialize summary with all known categories and subcategories set to 0
        summary = {cat: [{"sub_category": sub, "amount": 0} for sub in subs] for cat, subs in CATEGORIES.items()}
        
        for row in data:
            cat = row.get("category", "")
            sub = row.get("sub_category", "")
            amt = row.get("total", 0)
            
            # If the category exists in our predefined categories, update the specific subcategory
            if cat and cat in CATEGORIES:
                # Find the subcategory in the predefined list and update its amount
                for item in summary[cat]:
                    if item["sub_category"] == sub:
                        item["amount"] = amt
                        break  # Found and updated, move to next row
            # If it's an unknown category, we can add it but it won't appear in the template
            # since the template only iterates over predefined CATEGORIES
        
        totals = {cat: sum(x["amount"] for x in summary[cat]) for cat in CATEGORIES}
        return summary, totals

    def get_context(self) -> Dict:
        """Get the complete context for the dashboard template"""
        summary, totals, networth = self.fetch_summary_networth()
        return {
            "summary": summary,
            "totals": totals,
            "networth": networth,
            "months": self.months,
            "month_filter": self.month_filter
        }