# services/delete_service_fastapi.py

from services.firebase_db import firebase_service

class DeleteService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def delete_transaction(self, txn_id: str) -> bool:
        """Delete a transaction"""
        try:
            success = firebase_service.delete_transaction(txn_id, self.user_id)
            return success
        except Exception as e:
            print(f"Error deleting transaction: {e}")
            return False