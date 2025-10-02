# services/add_service.py
from services.db import get_db
from services.utils import rows_to_dict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import session

class AddService:
    def fetch_current_month_txns(self):
        now = datetime.now()
        conn = get_db()
        try:
            cur = conn.cursor()
            start_month = datetime(now.year, now.month, 1)
            next_month = start_month + relativedelta(months=1)
            cur.execute("""
                SELECT * FROM transactions
                WHERE user_id = %s AND date_time >= %s AND date_time < %s
                ORDER BY date_time ASC
            """, (
                session["user_id"],
                start_month.strftime("%Y-%m-%d %H:%M:%S"),
                next_month.strftime("%Y-%m-%d %H:%M:%S")
            ))
            print(session["user_id"], start_month, next_month)

            txns = rows_to_dict(cur, cur.fetchall())
        finally:
            cur.close()
            conn.close()
        return txns
    
    
    

