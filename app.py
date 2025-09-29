import os
import re
import pandas as pd
import joblib
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, flash, abort
from werkzeug.utils import secure_filename
from datetime import datetime
from dateutil.relativedelta import relativedelta

SECRET_KEY = os.environ.get('FLASK_SECRET', os.urandom(24))
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
DATABASE_URL = os.environ.get('DATABASE_URL')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

    # ------------- Error Handlers -------------
    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        return render_template('500.html'), 500

    @app.errorhandler(Exception)
    def handle_any_error(e):
        flash("An unexpected error occurred.", "danger")
        return render_template('500.html'), 500

    # ------------- DB Helper -----------------
    def get_db():
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            return conn
        except Exception as ex:
            app.logger.error("DB Connection Failed: %s", ex)
            abort(500)

    def init_db():
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    category TEXT,
                    sub_category TEXT,
                    description TEXT,
                    amount REAL,
                    date_time TEXT
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
        except Exception as ex:
            app.logger.error("DB Initialization failed: %s", ex)
            abort(500)

    init_db()

    try:
        vectorizer, clf, classes = joblib.load("money_ai_model.pkl")
    except Exception as ex:
        app.logger.error("AI model loading failed: %s", ex)
        vectorizer = clf = classes = None

    try:
        amount_vectorizer, amount_clf, amount_le = joblib.load("amount_extractor.pkl")
    except Exception as ex:
        app.logger.error("Amount extractor model loading failed: %s", ex)
        amount_vectorizer = amount_clf = amount_le = None



    # ------------- Categories ------------
    CATEGORIES = {
        "Income": ["Salary", "Other Income Sources"],
        "Expenses": [
            "Food & Drinks", "Shopping", "Personal Care", "Transport", "Loans & EMI",
            "Education", "Bills & Utilities", "Housing", "Entertainment", "Gifts", "Others"
        ],
        "Usne-Pasne": ["Money Sent", "Money Received"],
        "Savings / Investments": ["Savings", "Mutual Fund", "Stock", "Crypto", "Forex", "Property"]
    }



    def extract_amounts(text):
        if amount_vectorizer is None or amount_clf is None or amount_le is None:
            # Fallback to regex
            matches = re.findall(r'[\d,.]+', text)
            amounts = [float(m.replace(',', '')) for m in matches]
            return sum(amounts) if amounts else 0
        
        X_test = amount_vectorizer.transform([text])
        y_pred = amount_clf.predict(X_test)
        labels = amount_le.inverse_transform(y_pred)
        
        amounts = []
        for token, label in zip(text.split(), labels):
            if label == "AMOUNT":
                clean_token = re.sub(r'[^\d.]', '', token)
                if clean_token:
                    amounts.append(float(clean_token))
        return sum(amounts) if amounts else 0




    # ------------ Helper Functions -------------
    def classify_and_insert(user_input: str):
        # Extract amount from the user input
        amount = extract_amounts(user_input)

        # Predict category and sub-category
        if vectorizer is None or clf is None:
            category, sub_category = "Expenses", "Others"
        else:
            X_test = vectorizer.transform([user_input])
            prediction = clf.predict(X_test)[0]
            category, sub_category = prediction.split("|")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (category, sub_category, description, amount, date_time)
            VALUES (?, ?, ?, ?, ?)
        """, (category, sub_category, user_input, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        txn_id = cur.lastrowid
        conn.commit()
        conn.close()

        return {
            "id": txn_id,
            "category": category,
            "sub_category": sub_category,
            "amount": amount,
            "description": user_input
        }

    # ------------ Routes ----------------------

    # Utility for converting result
    def rows_to_dict(cur, rows):
        desc = [d[0] for d in cur.description]
        return [dict(zip(desc, row)) for row in rows]

    @app.route("/")
    def index():
        try:
            conn = get_db()
            cur = conn.cursor()
            now = datetime.now()
            current_year = now.year
            months = [ (now-relativedelta(months=i)).strftime("%Y-%m") for i in range(12) ]
            month_filter = request.args.get("month", "").strip()
            if not month_filter or month_filter not in months:
                month_filter = now.strftime("%Y-%m")
            year, month = map(int, month_filter.split("-"))
            start_of_month = datetime(year, month, 1)
            next_month = datetime(year+1, 1, 1) if month==12 else datetime(year, month+1, 1)
            cur.execute("""
                SELECT category, sub_category, SUM(amount) as total
                FROM transactions
                WHERE date_time >= %s AND date_time < %s
                GROUP BY category, sub_category
            """, (start_of_month.strftime("%Y-%m-%d 00:00:00"), next_month.strftime("%Y-%m-%d 00:00:00")))
            data = rows_to_dict(cur, cur.fetchall())
            cur.execute("SELECT SUM(amount) as networth FROM transactions WHERE date_time >= %s AND date_time < %s",
                        (f"{current_year}-01-01 00:00:00", f"{current_year+1}-01-01 00:00:00"))
            networth_row = cur.fetchone()
            networth = networth_row[0] or 0
            cur.close()
            conn.close()
            summary = {}
            for cat, subs in CATEGORIES.items():
                summary[cat] = []
                for sub in subs:
                    summary[cat].append({"sub_category": sub, "amount": 0})
            for row in data:
                cat, sub, amt = row["category"], row["sub_category"], row["total"]
                if cat not in summary:
                    summary[cat] = [{"sub_category": sub, "amount": amt}]
                    continue
                for item in summary[cat]:
                    if item["sub_category"] == sub:
                        item["amount"] = amt
            totals = {cat: sum([x["amount"] for x in summary[cat]]) for cat in summary}
            return render_template("index.html", summary=summary, totals=totals, networth=networth, months=months, month_filter=month_filter)
        except Exception as ex:
            app.logger.error("Index fetch failed: %s", ex)
            abort(500)

    @app.route("/add", methods=["GET", "POST"])
    def add_chat():
        if request.method == "POST":
            text = request.form.get("text")
            txn = classify_and_insert(text)
            if txn:
                return jsonify({"success": True, "txn": txn})
            return jsonify({"success": False, "error": "Could not parse amount"})
        try:
            now = datetime.now()
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM transactions
                WHERE date_time >= %s AND date_time < %s
                ORDER BY date_time ASC
            """, (now.strftime("%Y-%m-01 00:00:00"), (now + relativedelta(months=+1)).strftime("%Y-%m-01 00:00:00")))
            txns = rows_to_dict(cur, cur.fetchall())
            cur.close()
            conn.close()
        except Exception as ex:
            app.logger.error("Add: GET failed: %s", ex)
            flash("Could not fetch transactions", "danger")
            txns = []
        return render_template("add.html", transactions=txns)

    @app.route("/subcategory/<category>/<sub_category>")
    def subcategory_view(category, sub_category):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM transactions WHERE category=%s AND sub_category=%s ORDER BY date_time DESC", (category, sub_category))
            txns = rows_to_dict(cur, cur.fetchall())
            cur.close()
            conn.close()
        except Exception as ex:
            app.logger.error("Subcategory fetch failed: %s", ex)
            abort(500)
        return render_template("subcategory.html", transactions=txns, category=category, sub_category=sub_category)

    @app.route("/edit/<int:txn_id>", methods=["GET", "POST"])
    def edit(txn_id):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM transactions WHERE id=%s", (txn_id,))
            txn = rows_to_dict(cur, cur.fetchall())[0] if cur.rowcount > 0 else None
            if request.method == "POST":
                new_desc = request.form["description"]
                new_amount = request.form["amount"]
                new_cat = request.form["category"]
                new_sub = request.form["sub_category"]
                cur.execute("""
                    UPDATE transactions
                    SET description=%s, amount=%s, category=%s, sub_category=%s
                    WHERE id=%s
                """, (new_desc, new_amount, new_cat, new_sub, txn_id))
                conn.commit()
                cur.close()
                conn.close()
                new_label = f"{new_cat}|{new_sub}"
                # Safe model update (for demo)
                v, m, c = joblib.load("money_ai_model.pkl")
                if new_label not in c:
                    c = list(c) + [new_label]
                X_new = v.transform([new_desc])
                m.partial_fit(X_new, [new_label], classes=c)
                joblib.dump((v, m, c), "money_ai_model.pkl")
                flash("Transaction updated successfully!", "success")
                return redirect(url_for("edit", txn_id=txn_id))
            cur.close()
            conn.close()
        except Exception as ex:
            app.logger.error("Edit fetch/update failed: %s", ex)
            abort(500)
        return render_template("edit.html", txn=txn, categories=CATEGORIES)

    @app.route("/data/<sub_category>")
    def dynamic_data(sub_category):
        search = request.args.get("search", "").strip()
        month_filter = request.args.get("month", "").strip()
        now = datetime.now()
        months = [ (now-relativedelta(months=i)).strftime("%Y-%m") for i in range(12) ]
        if not month_filter or month_filter not in months:
            month_filter = now.strftime("%Y-%m")
        year, month = map(int, month_filter.split("-"))
        start_of_month = datetime(year, month, 1)
        next_month = datetime(year+1, 1, 1) if month==12 else datetime(year, month+1, 1)
        try:
            conn = get_db()
            cur = conn.cursor()
            if sub_category.lower() == "all":
                query = "SELECT * FROM transactions WHERE date_time >= %s AND date_time < %s"
                params = [start_of_month.strftime("%Y-%m-%d 00:00:00"), next_month.strftime("%Y-%m-%d 00:00:00")]
            else:
                query = "SELECT * FROM transactions WHERE sub_category=%s AND date_time >= %s AND date_time < %s"
                params = [sub_category, start_of_month.strftime("%Y-%m-%d 00:00:00"), next_month.strftime("%Y-%m-%d 00:00:00")]
            if search:
                query += " AND (description ILIKE %s OR category ILIKE %s OR sub_category ILIKE %s)"
                params.extend([f"%{search}%"]*3)
            query += " ORDER BY date_time DESC"
            cur.execute(query, params)
            txns = rows_to_dict(cur, cur.fetchall())
            cur.close()
            conn.close()
        except Exception as ex:
            app.logger.error("Dynamic data fetch failed: %s", ex)
            txns = []
        subcat_list = [{ "category": cat, "sub_category": sub } for cat, subs in CATEGORIES.items() for sub in subs]
        return render_template(
            "all-data.html",
            transactions=txns,
            sub_category=sub_category,
            subcat_list=subcat_list,
            months=months,
            month_filter=month_filter
        )

    @app.route("/analytics")
    def analytics():
        try:
            conn = get_db()
            cur = conn.cursor()
            now = datetime.now()
            start_of_month = datetime(now.year, now.month, 1)
            next_month = datetime(now.year+1, 1, 1) if now.month==12 else datetime(now.year, now.month+1, 1)
            cur.execute("""
                SELECT date(date_time) as day, SUM(amount) as total
                FROM transactions
                WHERE category='Expenses' AND date_time >= %s AND date_time < %s
                GROUP BY day ORDER BY day ASC
            """, (start_of_month.strftime("%Y-%m-%d 00:00:00"), next_month.strftime("%Y-%m-%d 00:00:00")))
            expenses_rows = rows_to_dict(cur, cur.fetchall())
            expenses_data = {row["day"].isoformat(): row["total"] for row in expenses_rows}
            cur.execute("""
                SELECT substring(date_time,1,7) as month, SUM(amount) as total
                FROM transactions WHERE category='Income'
                GROUP BY month ORDER BY month ASC
            """)
            income_rows = rows_to_dict(cur, cur.fetchall())
            cur.execute("""
                SELECT substring(date_time,1,7) as month, SUM(amount) as total
                FROM transactions WHERE category='Savings / Investments'
                GROUP BY month ORDER BY month ASC
            """)
            savings_rows = rows_to_dict(cur, cur.fetchall())
            cur.execute("""
                SELECT substring(date_time,1,7) as month,
                    SUM(CASE WHEN sub_category='Money Sent' THEN amount ELSE 0 END) as sent,
                    SUM(CASE WHEN sub_category='Money Received' THEN amount ELSE 0 END) as received
                FROM transactions WHERE category='Usne-Pasne'
                GROUP BY month ORDER BY month ASC
            """)
            up_rows = rows_to_dict(cur, cur.fetchall())
            cur.close()
            conn.close()
            return render_template("analytics.html",expenses_data=expenses_data,income_rows=income_rows,savings_rows=savings_rows,up_rows=up_rows)
        except Exception as ex:
            app.logger.error("Analytics fetch failed: %s", ex)
            expenses_data, income_rows, savings_rows, up_rows = {}, [], [], []
            return render_template("analytics.html",expenses_data=expenses_data,income_rows=income_rows,savings_rows=savings_rows,up_rows=up_rows)

    @app.route("/profile", methods=["GET"])
    def profile():
        return render_template("profile.html")

    @app.template_filter('format_dt')
    def format_datetime(value):
        if not value:
            return ""
        try:
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%-d %b, %-I.%M %p")
        except:
            try:
                dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.strftime("%d %B %Y")
            except:
                return value

    @app.template_filter('datetimeformat')
    def datetimeformat(value, fmt='%b %Y'):
        return datetime.strptime(value, "%Y-%m").strftime(fmt)

    @app.context_processor
    def inject_categories():
        categories = ["all", "Food & Drinks", "Shopping", "Transport", "Bills & Utilities"]
        return dict(categories=categories)

    @app.route("/backup/download")
    def download_backup():
        try:
            conn = get_db()
            df = pd.read_sql_query("SELECT * FROM transactions", conn)
            conn.close()
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], "backup.xlsx")
            df.to_excel(file_path, index=False)
            return send_file(file_path, as_attachment=True)
        except Exception as ex:
            app.logger.error("Backup download failed: %s", ex)
            abort(500)

    @app.route("/backup/upload", methods=["POST"])
    def upload_backup():
        try:
            if "file" not in request.files or request.files["file"].filename == "":
                flash("No file uploaded or selected!", "danger")
                return redirect(url_for("backup_page"))
            file = request.files["file"]
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)
            df = pd.read_excel(file_path)
            conn = get_db()
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
            cur.close()
            conn.close()
            flash("Data uploaded successfully! Duplicate data were skipped", "success")
            return redirect(url_for("profile"))
        except Exception as ex:
            app.logger.error("Backup upload failed: %s", ex)
            flash("Upload failed!", "danger")
            return redirect(url_for("backup_page"))

    @app.route("/backup", methods=["GET"])
    def backup_page():
        return render_template("backup.html")

    return app

if __name__ == "__main__":
    # For production, use Gunicorn: gunicorn "app:create_app()" --bind 0.0.0.0:8000 --workers 4
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
