from services.firebase_db import firebase_service
from services.password_utils import hash_password, encrypt_password, decrypt_password
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
                'password': encrypt_password(password)
            }
            
            password_id = firebase_service.create_password(password_data)
            
            if password_id:
                # Fetch the created password to return complete data
                passwords = firebase_service.get_passwords(self.user_id)
                for pwd in passwords:
                    if pwd['id'] == password_id:
                        # Decrypt the password before returning
                        if 'password' in pwd:
                            try:
                                pwd['password'] = decrypt_password(pwd['password'])
                            except Exception as e:
                                # If decryption fails, it might be a plain text password
                                # or an incorrectly encrypted one, so we'll leave it as is
                                print(f"Decryption failed for password ID {pwd.get('id', 'unknown')}: {e}")
                                # For backwards compatibility, if decryption fails, 
                                # we'll assume it's already plain text
                                pass  # Keep the original value
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
            # Decrypt passwords before returning
            for pwd in results:
                if 'password' in pwd:
                    try:
                        pwd['password'] = decrypt_password(pwd['password'])
                    except Exception as e:
                        # If decryption fails, it might be a plain text password
                        # or an incorrectly encrypted one, so we'll leave it as is
                        print(f"Decryption failed for password ID {pwd.get('id', 'unknown')}: {e}")
                        # For backwards compatibility, if decryption fails, 
                        # we'll assume it's already plain text
                        pass  # Keep the original value
            return results
        except Exception as ex:
            print(f"❌ Failed to search passwords: {ex}")
            return []

    def list_passwords(self) -> List[Dict]:
        """List all passwords for the authenticated user."""
        try:
            results = firebase_service.get_passwords(self.user_id)
            # Decrypt passwords before returning
            for pwd in results:
                if 'password' in pwd:
                    try:
                        pwd['password'] = decrypt_password(pwd['password'])
                    except Exception as e:
                        # If decryption fails, it might be a plain text password
                        # or an incorrectly encrypted one, so we'll leave it as is
                        print(f"Decryption failed for password ID {pwd.get('id', 'unknown')}: {e}")
                        # For backwards compatibility, if decryption fails, 
                        # we'll assume it's already plain text
                        pass  # Keep the original value
            return results
        except Exception as ex:
            print(f"❌ Failed to list passwords: {ex}")
            return []

    def delete_password(self, password_id: str) -> bool:
        """Delete a password by ID."""
        try:
            result = firebase_service.delete_password(password_id)
            return result
        except Exception as ex:
            print(f"❌ Failed to delete password: {ex}")
            return False

    def update_password(self, password_id: str, category: str, username: str, password: str) -> bool:
        """Update an existing password."""
        try:
            # Encrypt the password before updating
            encrypted_password = encrypt_password(password)
            
            update_data = {
                'category': category,
                'username': username,
                'password': encrypted_password
            }
            
            result = firebase_service.update_password(password_id, update_data)
            return result
        except Exception as ex:
            print(f"❌ Failed to update password: {ex}")
            return False