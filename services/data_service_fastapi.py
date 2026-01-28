from services.firebase_db import firebase_service
from services.utils_fastapi import CATEGORIES
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Tuple

class DataService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def fetch(self, sub_category: str, month_filter: str, search: str) -> Tuple[List[Dict], List[Dict], List[str], str]:
        """Fetch transactions with filtering and search"""
        try:
            now = datetime.now()
            months = [(now - relativedelta(months=i)).strftime("%Y-%m") for i in range(12)]
            
            if not month_filter or month_filter not in months:
                month_filter = now.strftime("%Y-%m")

            year, month = map(int, month_filter.split("-"))
            start_of_month = datetime(year, month, 1)
            next_month = datetime(year, month+1, 1) if month < 12 else datetime(year+1, 1, 1)

            # Prepare filters
            filters = {
                'start_date': start_of_month,
                'end_date': next_month
            }

            
            # Add sub_category filter if not "all"
            if sub_category.lower() != "all":
                filters['sub_category'] = sub_category
            
            # Add search term
            if search:
                filters['search'] = search

            # Fetch transactions
            txns = firebase_service.get_transactions(self.user_id, filters)
            
            # Create subcategory list
            subcat_list = [{"category": cat, "sub_category": sub} for cat, subs in CATEGORIES.items() for sub in subs]
            
            return txns, subcat_list, months, month_filter
            
        except Exception as e:
            print(f"Error in data service fetch: {e}")
            subcat_list = [{"category": cat, "sub_category": sub} for cat, subs in CATEGORIES.items() for sub in subs]
            months = [(datetime.now() - relativedelta(months=i)).strftime("%Y-%m") for i in range(12)]
            return [], subcat_list, months, datetime.now().strftime("%Y-%m")