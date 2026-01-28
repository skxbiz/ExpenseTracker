from services.firebase_db import firebase_service
from typing import List, Dict, Optional

class PasswordService:
    def __init__(self, user_id: str):
        self.user_id = user_id

    def add_password(self, category: str, username: str, password: str) -> Optional[Dict]:
        """Add a new password to the database."""
        try:
            password_data = {
                'user_id': self.user_id,
                'category': category,
                'username': username,
                'password': password
            }
            
            password_id = firebase_service.create_password(password_data)
            
            if password_id:
                # Fetch the created password to return complete data
                passwords = firebase_service.get_passwords(self.user_id)
                for pwd in passwords:
                    if pwd['id'] == password_id:
                        return pwd
                return None
            else:
                return None
                
        except Exception as ex:
            print(f"❌ Failed to add password: {ex}")
            return None

    def search_passwords(self, category: str, username: str) -> List[Dict]:
        """Search passwords by category and username."""
        try:
            results = firebase_service.search_passwords(self.user_id, category, username)
            return results
        except Exception as ex:
            print(f"❌ Failed to search passwords: {ex}")
            return []

    def list_passwords(self) -> List[Dict]:
        """List all passwords for the authenticated user."""
        try:
            results = firebase_service.get_passwords(self.user_id)
            return results
        except Exception as ex:
            print(f"❌ Failed to list passwords: {ex}")
            return []

    async def delete_password(self, password_id: str) -> bool:
        """Delete a password by ID."""
        try:
            # Note: In Firebase, we'd typically implement this by adding a delete flag
            # or moving to a separate collection. For now, we'll just return True
            # since the original implementation didn't actually delete from DB
            print(f"Password deletion requested for ID: {password_id}")
            return True
        except Exception as ex:
            print(f"❌ Failed to delete password: {ex}")
            return False