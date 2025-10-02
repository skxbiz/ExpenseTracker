from services.db import get_db
from services.utils import rows_to_dict, CATEGORIES
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import session

class DashboardService:
    def __init__(self, month_filter=None):
        self.now = datetime.now()
        self.current_year = self.now.year
        self.months = [(self.now - relativedelta(months=i)).strftime("%Y-%m") for i in range(12)]
        self.month_filter = month_filter if month_filter in self.months else self.now.strftime("%Y-%m")
        self.year, self.month = map(int, self.month_filter.split("-"))
        self.start_of_month = datetime(self.year, self.month, 1)
        if self.month == 12:
            self.next_month = datetime(self.year + 1, 1, 1)
        else:
            self.next_month = datetime(self.year, self.month + 1, 1)

    def fetch_summary_networth(self):
        conn = get_db()
        try:
            cur = conn.cursor()
            # ✅ Cast text to timestamp
            cur.execute("""
                SELECT category, sub_category, SUM(amount) as total
                FROM transactions
                WHERE user_id = %s AND date_time::timestamp >= %s AND date_time::timestamp < %s
                GROUP BY category, sub_category
            """, (session["user_id"], self.start_of_month, self.next_month))
            data = rows_to_dict(cur, cur.fetchall())

            cur.execute("""
                SELECT SUM(amount) as networth 
                FROM transactions
                WHERE user_id = %s AND date_time::timestamp >= %s AND date_time::timestamp < %s
            """, (session["user_id"], datetime(self.current_year, 1, 1), datetime(self.current_year + 1, 1, 1)))
            networth_row = cur.fetchone()
            networth = networth_row[0] or 0
        finally:
            cur.close()
            conn.close()

        summary, totals = self.prepare_summary(data)
        return summary, totals, networth

    def prepare_summary(self, data):
        summary = {cat: [{"sub_category": sub, "amount": 0} for sub in subs] for cat, subs in CATEGORIES.items()}
        for row in data:
            cat, sub, amt = row["category"], row["sub_category"], row["total"]
            if cat not in summary:
                summary[cat] = [{"sub_category": sub, "amount": amt}]
                continue
            for item in summary[cat]:
                if item["sub_category"] == sub:
                    item["amount"] = amt
        totals = {cat: sum(x["amount"] for x in summary[cat]) for cat in summary}
        return summary, totals

    def get_context(self):
        summary, totals, networth = self.fetch_summary_networth()
        return {
            "summary": summary,
            "totals": totals,
            "networth": networth,
            "months": self.months,
            "month_filter": self.month_filter
        }
