import os
import pandas as pd
from flask import current_app
from services.db import get_db

class BackupService:
    def export_xlsx(self):
        conn = get_db()
        try:
            df = pd.read_sql_query("SELECT * FROM transactions", conn)
        finally:
            conn.close()
        file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], "backup.xlsx")
        df.to_excel(file_path, index=False)
        return file_path

    def import_xlsx(self, file_path):
        df = pd.read_excel(file_path)
        conn = get_db()
        try:
            cur = conn.cursor()
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO transactions (id, category, sub_category, description, amount, date_time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    int(row.get("id")) if row.get("id") else None, row.get("category"),
                    row.get("sub_category"), row.get("description"),
                    row.get("amount"), row.get("date_time")
                ))
            conn.commit()
        finally:
            cur.close()
            conn.close()
