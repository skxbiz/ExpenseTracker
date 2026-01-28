# services/edit_service_fastapi.py

from services.firebase_db import firebase_service
import joblib
from typing import Optional, Dict

class EditService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def fetch_transaction(self, txn_id: str) -> Optional[Dict]:
        """Fetch a single transaction by ID"""
        try:
            txn = firebase_service.get_transaction(txn_id, self.user_id)
            return txn
        except Exception as e:
            print(f"Error fetching transaction: {e}")
            return None

    def update_transaction(self, txn_id: str, description: str, amount: float, category: str, sub_category: str) -> bool:
        """Update a transaction"""
        try:
            update_data = {
                'description': description,
                'amount': amount,
                'category': category,
                'sub_category': sub_category
            }
            
            success = firebase_service.update_transaction(txn_id, update_data, self.user_id)
            
            if success:
                # Update ML model with new label
                new_label = f"{category}|{sub_category}"
                try:
                    v, m, c = joblib.load("money_ai_model.pkl")
                    if new_label not in c:
                        c = list(c) + [new_label]
                    X_new = v.transform([description])
                    m.partial_fit(X_new, [new_label], classes=c)
                    joblib.dump((v, m, c), "money_ai_model.pkl")
                except Exception as ml_e:
                    print(f"Warning: Could not update ML model: {ml_e}")
            
            return success
            
        except Exception as e:
            print(f"Error updating transaction: {e}")
            return False