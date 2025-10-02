from services.db import get_db
from services.utils import rows_to_dict, CATEGORIES
from datetime import datetime
from dateutil.relativedelta import relativedelta

class DataService:
    def fetch(self, sub_category, month_filter, search, user_id):
        now = datetime.now()
        months = [(now - relativedelta(months=i)).strftime("%Y-%m") for i in range(12)]
        if not month_filter or month_filter not in months:
            month_filter = now.strftime("%Y-%m")

        year, month = map(int, month_filter.split("-"))
        start_of_month = datetime(year, month, 1)
        next_month = datetime(year, month+1, 1) if month < 12 else datetime(year+1, 1, 1)

        conn = get_db()
        try:
            cur = conn.cursor()
            if sub_category.lower() == "all":
                query = """
                    SELECT * FROM transactions 
                    WHERE user_id = %s AND date_time::timestamp >= %s AND date_time::timestamp < %s
                """
                params = [user_id, start_of_month, next_month]
            else:
                query = """
                    SELECT * FROM transactions 
                    WHERE sub_category=%s AND user_id = %s AND date_time::timestamp >= %s AND date_time::timestamp < %s
                """
                params = [sub_category, user_id, start_of_month, next_month]

            if search:
                query += " AND (description ILIKE %s OR category ILIKE %s OR sub_category ILIKE %s)"
                params.extend([f"%{search}%"] * 3)

            query += " ORDER BY date_time DESC"
            cur.execute(query, params)
            txns = rows_to_dict(cur, cur.fetchall())
        finally:
            cur.close()
            conn.close()

        subcat_list = [{"category": cat, "sub_category": sub} for cat, subs in CATEGORIES.items() for sub in subs]
        return txns, subcat_list, months, month_filter
