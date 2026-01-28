# services/subcategory_service_fastapi.py

from services.firebase_db import firebase_service
from typing import List, Dict

class SubcategoryService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def fetch_transactions_by_subcategory(self, category: str, sub_category: str) -> List[Dict]:
        """Fetch transactions by category and subcategory"""
        try:
            filters = {
                'category': category,
                'sub_category': sub_category
            }
            
            transactions = firebase_service.get_transactions(self.user_id, filters)
            
            # Sort by date_time descending (newest first)
            transactions.sort(key=lambda x: x.get('date_time', ''), reverse=True)
            
            return transactions
            
        except Exception as e:
            print(f"Error fetching transactions by subcategory: {e}")
            return []