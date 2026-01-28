# services/add_service_fastapi.py
from services.firebase_db import firebase_service
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import List, Dict

class AddService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def fetch_current_month_txns(self) -> List[Dict]:
        """Fetch transactions for the current month"""
        try:
            now = datetime.now()
            start_month = datetime(now.year, now.month, 1)
            next_month = start_month + relativedelta(months=1)
            
            filters = {
                'start_date': start_month.isoformat(),
                'end_date': next_month.isoformat()
            }
            
            transactions = firebase_service.get_transactions(self.user_id, filters)
            
            # Sort by date_time ascending (oldest first)
            transactions.sort(key=lambda x: x.get('date_time', ''))
            
            return transactions
            
        except Exception as e:
            print(f"Error fetching current month transactions: {e}")
            return []