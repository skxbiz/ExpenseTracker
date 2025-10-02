from services.db import get_db

class PasswordService:
    def add_password(self, user_id, category, username, password):
        """Add a new password to the database."""
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO passwords (user_id, category, username, password)
                VALUES (%s, %s, %s, %s)
                RETURNING id, category, username, password, date_time
                """,
                (user_id, category, username, password)
            )
            inserted_row = cur.fetchone()  # ✅ Now it will return the inserted row
            conn.commit()
            cur.close()
            conn.close()

            if inserted_row:
                return {
                    "id": inserted_row[0],
                    "category": inserted_row[1],
                    "username": inserted_row[2],
                    "password": inserted_row[3],
                    "date_time": inserted_row[4]
                }
            else:
                return None

        except Exception as ex:
            print(f"❌ Failed to add password: {ex}")
            return None


    def search_passwords(self, user_id, category, username):
        """Search passwords by category and username."""
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, category, username, password, date_time FROM passwords WHERE user_id = %s AND category = %s AND username = %s",
                (user_id, category, username)
            )
            results = cur.fetchall()
            cur.close()
            conn.close()
            return results
        except Exception as ex:
            print(f"❌ Failed to search passwords: {ex}")
            return []

    def list_passwords(self, user_id):
        """List all passwords for the authenticated user."""
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, category, username, password, date_time FROM passwords WHERE user_id = %s",
                (user_id,)
            )
            results = cur.fetchall()
            cur.close()
            conn.close()
            return results
        except Exception as ex:
            print(f"❌ Failed to list passwords: {ex}")
            return []

    def delete_password(self, user_id, password_id):
        """Delete a password by ID."""
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM passwords WHERE user_id = %s AND id = %s",
                (user_id, password_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as ex:
            print(f"❌ Failed to delete password: {ex}")
            return False