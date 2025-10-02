# services/edit_service.py

from services.db import get_db
from services.utils import rows_to_dict
import joblib
from flask import session

class EditService:
    def fetch_transaction(self, txn_id):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM transactions WHERE id=%s AND user_id=%s", (txn_id, session["user_id"]))
            txn = rows_to_dict(cur, cur.fetchall())[0] if cur.rowcount > 0 else None
        finally:
            cur.close()
            conn.close()
        return txn

    def update_transaction(self, txn_id, description, amount, category, sub_category):
        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE transactions
                SET description=%s, amount=%s, category=%s, sub_category=%s
                WHERE id=%s AND user_id=%s
            """, (description, amount, category, sub_category, txn_id, session["user_id"]))
            conn.commit()
        finally:
            cur.close()
            conn.close()

        # Update ML model with new label
        new_label = f"{category}|{sub_category}"
        v, m, c = joblib.load("money_ai_model.pkl")
        if new_label not in c:
            c = list(c) + [new_label]
        X_new = v.transform([description])
        m.partial_fit(X_new, [new_label], classes=c)
        joblib.dump((v, m, c), "money_ai_model.pkl")
