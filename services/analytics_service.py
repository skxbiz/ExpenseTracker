# services/analytics_service.py

from services.db import get_db
from services.utils import rows_to_dict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import session

class AnalyticsService:
    def fetch_analytics(self):
        now = datetime.now()
        start_of_month = datetime(now.year, now.month, 1)
        next_month = start_of_month + relativedelta(months=1)

        # convert datetimes → strings (since date_time is stored as text in DB)
        start_str = start_of_month.strftime("%Y-%m-%d %H:%M:%S")
        next_str = next_month.strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        try:
            cur = conn.cursor()

            # Expenses: sum per day
            cur.execute("""
                SELECT date(date_time::timestamp) as day, SUM(amount) as total
                FROM transactions
                WHERE user_id = %s AND category='Expenses' AND date_time::timestamp >= %s AND date_time::timestamp < %s
                GROUP BY day ORDER BY day ASC
            """, (session["user_id"], start_str, next_str))
            expenses_rows = rows_to_dict(cur, cur.fetchall())
            expenses_data = {row["day"].isoformat(): row["total"] for row in expenses_rows}

            # Income: sum per month
            cur.execute("""
                SELECT to_char(date_time::timestamp, 'YYYY-MM') as month, SUM(amount) as total
                FROM transactions WHERE user_id = %s AND category='Income'
                GROUP BY month ORDER BY month ASC
            """, (session["user_id"],))
            income_rows = rows_to_dict(cur, cur.fetchall())

            # Savings/Investments: sum per month
            cur.execute("""
                SELECT to_char(date_time::timestamp, 'YYYY-MM') as month, SUM(amount) as total
                FROM transactions WHERE user_id = %s AND category='Savings / Investments'
                GROUP BY month ORDER BY month ASC
            """, (session["user_id"],))
            savings_rows = rows_to_dict(cur, cur.fetchall())

            # Usne-Pasne: sent vs received per month
            cur.execute("""
                SELECT to_char(date_time::timestamp, 'YYYY-MM') as month,
                    SUM(CASE WHEN sub_category='Money Sent' THEN amount ELSE 0 END) as sent,
                    SUM(CASE WHEN sub_category='Money Received' THEN amount ELSE 0 END) as received
                FROM transactions WHERE user_id = %s AND category='Usne-Pasne'
                GROUP BY month ORDER BY month ASC
            """, (session["user_id"],))
            up_rows = rows_to_dict(cur, cur.fetchall())

        finally:
            cur.close()
            conn.close()

        return expenses_data, income_rows, savings_rows, up_rows
