# services/subcategory_service.py

from flask import session
from services.db import get_db
from services.utils import rows_to_dict

class SubcategoryService:
    def fetch_transactions_by_subcategory(self, category, sub_category):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM transactions WHERE user_id = %s AND category=%s AND sub_category=%s ORDER BY date_time DESC",
                (session["user_id"], category, sub_category)
            )
            txns = rows_to_dict(cur, cur.fetchall())
        finally:
            cur.close()
            conn.close()
        return txns
