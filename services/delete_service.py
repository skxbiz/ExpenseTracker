# services/delete_service.py

from services.db import get_db

class DeleteService:
    def delete_transaction(self, txn_id, user_id):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (txn_id, user_id))
            conn.commit()
        finally:
            cur.close()
            conn.close()
