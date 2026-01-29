# services/firebase_db.py

from dotenv import load_dotenv
load_dotenv()


import os
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import HTTPException, status

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.api_core.datetime_helpers import DatetimeWithNanoseconds
from google.cloud.firestore_v1 import FieldFilter


def _convert_firestore_data(data: dict) -> dict:
    """Convert Firestore timestamp objects to standard datetime strings for JSON serialization."""
    result = {}
    for key, value in data.items():
        if isinstance(value, DatetimeWithNanoseconds):
            result[key] = value.isoformat()
        elif isinstance(value, dict):
            result[key] = _convert_firestore_data(value)
        elif isinstance(value, list):
            result[key] = [
                _convert_firestore_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


class FirebaseService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    # def __init__(self):
    #     if self._initialized:
    #         return

    #     try:
    #         # ---------- Load credentials ----------
    #         if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    #             cred = credentials.Certificate(
    #                 os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    #             )

    #         elif os.environ.get("FIREBASE_CONFIG"):
    #             firebase_config = json.loads(os.environ.get("FIREBASE_CONFIG"))
    #             cred = credentials.Certificate(firebase_config)

    #         else:
    #             # Production environment - must use environment variables
    #             raise ValueError("No Firebase credentials found. Please set GOOGLE_APPLICATION_CREDENTIALS or FIREBASE_CONFIG environment variable in Render dashboard.")

    #         if not firebase_admin._apps:
    #             firebase_admin.initialize_app(cred)

    #         self.db = firestore.client()
    #         self._initialized = True
    #         print("✅ Firebase initialized successfully")

    #     except Exception as e:
    #         print(f"❌ Firebase initialization failed: {e}")
    #         raise HTTPException(
    #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #             detail="Firebase initialization failed",
    #         )

    
    def __init__(self):
        if self._initialized:
            return

        try:
            firebase_config = {
                "type": os.getenv("FIREBASE_TYPE"),
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
                "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
                "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
                "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
            }

            missing = [k for k, v in firebase_config.items() if not v]
            if missing:
                raise ValueError(f"Missing Firebase env vars: {missing}")

            cred = credentials.Certificate(firebase_config)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)

            self.db = firestore.client()
            self._initialized = True
            print("✅ Firebase initialized successfully using .env variables")

        except Exception as e:
            print(f"❌ Firebase initialization failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firebase initialization failed",
            )



    # ---------------- USERS ----------------

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        try:
            query = (
                self.db.collection("users")
                .where(filter=FieldFilter("username", "==", username))
                .limit(1)
            )

            for doc in query.stream():
                data = doc.to_dict()
                data["id"] = doc.id
                return data

            return None

        except Exception as e:
            print(f"Error fetching user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch user",
            )

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc_ref = self.db.collection("users").document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                return data
            
            return None

        except Exception as e:
            print(f"Error fetching user by ID: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch user",
            )

    def create_user(self, username: str, password_hash: str) -> str:
        try:
            doc_ref = self.db.collection("users").document()
            doc_ref.set({
                "username": username,
                "password": password_hash,
                "created_at": datetime.utcnow(),
            })
            return doc_ref.id

        except Exception as e:
            print(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

    # ---------------- TRANSACTIONS ----------------

    def get_transaction(self, txn_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            ref = self.db.collection("transactions").document(txn_id)
            doc = ref.get()

            if not doc.exists:
                return None

            data = doc.to_dict()
            data = _convert_firestore_data(data)
            if data.get("user_id") != user_id:
                return None

            data["id"] = doc.id
            return data

        except Exception as e:
            print(f"Error fetching transaction: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch transaction",
            )

    def get_transactions(self, user_id: str, filters: Dict = None) -> List[Dict[str, Any]]:
        try:
            query = self.db.collection("transactions").where(
                filter=FieldFilter("user_id", "==", user_id)
            )

            if filters:
                if filters.get("category"):
                    query = query.where(filter=FieldFilter("category", "==", filters["category"]))

                if filters.get("sub_category") and filters["sub_category"].lower() != "all":
                    query = query.where(
                        filter=FieldFilter("sub_category", "==", filters["sub_category"])
                    )

                # Handle date range filtering
                if filters.get("start_date"):
                    start_date_value = filters["start_date"]
                    # Handle both string and datetime objects
                    if isinstance(start_date_value, str):
                        start_datetime = datetime.fromisoformat(start_date_value.replace('Z', '+00:00'))
                    else:
                        start_datetime = start_date_value
                    query = query.where(filter=FieldFilter("date_time", ">=", start_datetime))
                
                if filters.get("end_date"):
                    end_date_value = filters["end_date"]
                    # Handle both string and datetime objects
                    if isinstance(end_date_value, str):
                        end_datetime = datetime.fromisoformat(end_date_value.replace('Z', '+00:00'))
                    else:
                        end_datetime = end_date_value
                    query = query.where(filter=FieldFilter("date_time", "<", end_datetime))

            query = query.order_by(
                "date_time", direction=firestore.Query.DESCENDING
            )

            transactions = []
            for doc in query.stream():
                data = doc.to_dict()
                data = _convert_firestore_data(data)
                data["id"] = doc.id
                transactions.append(data)

            # Python-side search
            if filters and filters.get("search"):
                term = filters["search"].lower()
                transactions = [
                    t for t in transactions
                    if term in t.get("description", "").lower()
                    or term in t.get("category", "").lower()
                    or term in t.get("sub_category", "").lower()
                ]

            return transactions

        except Exception as e:
            print(f"Error fetching transactions: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch transactions",
            )

    def create_transaction(self, data: Dict[str, Any]) -> str:
        try:
            ref = self.db.collection("transactions").document()
            data["created_at"] = datetime.utcnow()
            ref.set(data)
            return ref.id

        except Exception as e:
            print(f"Error creating transaction: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create transaction",
            )

    def update_transaction(self, txn_id: str, update_data: Dict[str, Any], user_id: str) -> bool:
        try:
            ref = self.db.collection("transactions").document(txn_id)
            doc = ref.get()

            if not doc.exists:
                return False

            data = doc.to_dict()
            data = _convert_firestore_data(data)
            if data.get("user_id") != user_id:
                return False

            update_data["updated_at"] = datetime.utcnow()
            ref.update(update_data)
            return True

        except Exception as e:
            print(f"Error updating transaction: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update transaction",
            )

    def delete_transaction(self, txn_id: str, user_id: str) -> bool:
        try:
            ref = self.db.collection("transactions").document(txn_id)
            doc = ref.get()

            if not doc.exists:
                return False

            doc_data = doc.to_dict()
            doc_data = _convert_firestore_data(doc_data)
            if doc_data.get("user_id") != user_id:
                return False

            ref.delete()
            return True

        except Exception as e:
            print(f"Error deleting transaction: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete transaction",
            )

    # ---------------- PASSWORD MANAGER ----------------

    def list_passwords(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            query = (
                self.db.collection("passwords")
                .where(filter=FieldFilter("user_id", "==", user_id))
            )

            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data = _convert_firestore_data(data)
                data["id"] = doc.id
                results.append(data)

            # Sort by date_time in descending order after fetching
            results.sort(key=lambda x: x.get('date_time', ''), reverse=True)

            return results

        except Exception as e:
            print(f"Error fetching passwords: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch passwords",
            )

    def create_password(self, data: Dict[str, Any]) -> str:
        try:
            ref = self.db.collection("passwords").document()
            data["date_time"] = datetime.utcnow()
            ref.set(data)
            return ref.id

        except Exception as e:
            print(f"Error creating password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create password",
            )

    def search_passwords(
        self, user_id: str, category: str = None, username: str = None
    ) -> List[Dict[str, Any]]:
        try:
            query = self.db.collection("passwords").where(
                filter=FieldFilter("user_id", "==", user_id)
            )

            if category:
                query = query.where(filter=FieldFilter("category", "==", category))
            if username:
                query = query.where(filter=FieldFilter("username", "==", username))

            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data = _convert_firestore_data(data)
                data["id"] = doc.id
                results.append(data)

            # Sort by date_time in descending order after fetching
            results.sort(key=lambda x: x.get('date_time', ''), reverse=True)

            return results

        except Exception as e:
            print(f"Error searching passwords: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to search passwords",
            )

    def get_passwords(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            query = (
                self.db.collection("passwords")
                .where(filter=FieldFilter("user_id", "==", user_id))
            )

            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data = _convert_firestore_data(data)
                data["id"] = doc.id
                results.append(data)

            # Sort by date_time in descending order after fetching
            results.sort(key=lambda x: x.get('date_time', ''), reverse=True)

            return results

        except Exception as e:
            print(f"Error fetching passwords: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch passwords",
            )

    def delete_password(self, password_id: str) -> bool:
        try:
            ref = self.db.collection("passwords").document(password_id)
            doc = ref.get()

            if not doc.exists:
                return False
            
            ref.delete()
            return True

        except Exception as e:
            print(f"Error deleting password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete password",
            )

    def update_password(self, password_id: str, data: Dict[str, Any]) -> bool:
        try:
            ref = self.db.collection("passwords").document(password_id)
            doc = ref.get()

            if not doc.exists:
                return False
            
            # Update only the provided fields
            update_data = {}
            if 'category' in data:
                update_data['category'] = data['category']
            if 'username' in data:
                update_data['username'] = data['username']
            if 'password' in data:
                update_data['password'] = data['password']
            
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                ref.update(update_data)
            
            return True

        except Exception as e:
            print(f"Error updating password: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password",
            )


# Global instance
firebase_service = FirebaseService()
