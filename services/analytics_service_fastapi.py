# services/analytics_service_fastapi.py

from services.firebase_db import firebase_service
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Tuple

class AnalyticsService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def fetch_analytics(self) -> Tuple[Dict, List[Dict], List[Dict], List[Dict]]:
        """Fetch analytics data for expenses, income, savings, and transfers"""
        try:
            now = datetime.now()
            start_of_month = datetime(now.year, now.month, 1)
            next_month = start_of_month + relativedelta(months=1)
            
            # Get all transactions for the user
            transactions = firebase_service.get_transactions(self.user_id)
            
            # Filter transactions by date range for current month
            current_month_transactions = [
                txn for txn in transactions
                if start_of_month.isoformat() <= txn.get('date_time', '') < next_month.isoformat()
            ]
            
            # Expenses: sum per day
            expenses_data = {}
            expense_transactions = [txn for txn in current_month_transactions if txn.get('category') == 'Expenses']
            
            # Group by date (assuming date_time is in ISO format)
            daily_expenses = {}
            for txn in expense_transactions:
                try:
                    # Extract date part from datetime string
                    date_str = txn.get('date_time', '').split('T')[0]  # YYYY-MM-DD format
                    amount = float(txn.get('amount', 0))
                    if date_str in daily_expenses:
                        daily_expenses[date_str] += amount
                    else:
                        daily_expenses[date_str] = amount
                except (ValueError, IndexError):
                    continue
            
            expenses_data = daily_expenses
            
            # Income: sum per month
            income_transactions = [txn for txn in transactions if txn.get('category') == 'Income']
            monthly_income = self._group_by_month(income_transactions)
            income_rows = [{'month': month, 'total': total} for month, total in monthly_income.items()]
            
            # Savings/Investments: sum per month
            savings_transactions = [txn for txn in transactions if txn.get('category') == 'Savings / Investments']
            monthly_savings = self._group_by_month(savings_transactions)
            savings_rows = [{'month': month, 'total': total} for month, total in monthly_savings.items()]
            
            # Usne-Pasne: sent vs received per month
            transfer_transactions = [txn for txn in transactions if txn.get('category') == 'Usne-Pasne']
            monthly_transfers = {}
            
            for txn in transfer_transactions:
                try:
                    month_str = txn.get('date_time', '').split('-')[0] + '-' + txn.get('date_time', '').split('-')[1]  # YYYY-MM
                    amount = float(txn.get('amount', 0))
                    sub_category = txn.get('sub_category', '')
                    
                    if month_str not in monthly_transfers:
                        monthly_transfers[month_str] = {'sent': 0, 'received': 0}
                    
                    if sub_category == 'Money Sent':
                        monthly_transfers[month_str]['sent'] += amount
                    elif sub_category == 'Money Received':
                        monthly_transfers[month_str]['received'] += amount
                except (ValueError, IndexError):
                    continue
            
            up_rows = [
                {'month': month, 'sent': data['sent'], 'received': data['received']} 
                for month, data in monthly_transfers.items()
            ]
            
            return expenses_data, income_rows, savings_rows, up_rows
            
        except Exception as e:
            print(f"Error in fetch_analytics: {e}")
            return {}, [], [], []

    def _group_by_month(self, transactions: List[Dict]) -> Dict[str, float]:
        """Helper method to group transactions by month and sum amounts"""
        monthly_data = {}
        
        for txn in transactions:
            try:
                # Extract month from date_time (YYYY-MM format)
                month_str = txn.get('date_time', '').split('-')[0] + '-' + txn.get('date_time', '').split('-')[1]
                amount = float(txn.get('amount', 0))
                
                if month_str in monthly_data:
                    monthly_data[month_str] += amount
                else:
                    monthly_data[month_str] = amount
            except (ValueError, IndexError):
                continue
                
        return monthly_data