from datetime import datetime
import os
from flask import Flask, redirect, render_template, request, flash, abort, current_app,jsonify, send_file, url_for, session
from flask.views import MethodView
from werkzeug.security import generate_password_hash, check_password_hash
from services.db import get_db, init_db
from services.utils import classify_and_insert
from services.dashboard_service import DashboardService
from services.add_service import AddService
from services.subcategory_service import SubcategoryService
from services.edit_service import EditService
from services.delete_service import DeleteService 
from services.data_service import DataService
from services.analytics_service import AnalyticsService
from services.backup_service import BackupService
from werkzeug.utils import secure_filename


from services.utils import CATEGORIES
import traceback
from functools import wraps


# -------------------- Flask App --------------------
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', os.urandom(24))
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Decorator to require login for routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# Apply login_required to all routes
@app.before_request
def require_login():
    excluded_routes = ["login", "signup", "static"]
    current_app.logger.debug(f"Request endpoint: {request.endpoint}")
    if request.endpoint in excluded_routes or request.endpoint is None:
        current_app.logger.debug("Access allowed: Excluded route or static file.")
        return  # Allow access to excluded routes and static files
    if "user_id" not in session:
        current_app.logger.debug("Access denied: User not logged in.")
        return redirect(url_for("login"))

# -------------------- Error Handlers --------------------
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    current_app.logger.error("Internal Server Error: %s", traceback.format_exc())
    return render_template('500.html'), 500

@app.errorhandler(Exception)
def handle_any_error(e):
    current_app.logger.error("Unhandled Exception: %s", traceback.format_exc())
    flash("An unexpected error occurred.", "danger")
    return render_template('500.html'), 500

# -------------------- Initialize DB --------------------

with app.app_context():
    try:
        init_db()
        print("✅ Database initialized successfully.")
    except Exception as ex:
        print(f"❌ Database initialization failed: {ex}")



# -------------------- Custom Jinja2 filter --------------------

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%b %Y'):
    return value.strftime(format) if value else ""

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



# -------------------- Class-Based Views --------------------
class IndexView(MethodView):
    def get(self):
        month_filter = request.args.get("month", "").strip()
        service = DashboardService(month_filter)
        try:
            context = service.get_context()
            return render_template(
                "index.html",
                summary=context["summary"],
                totals=context["totals"],
                networth=context["networth"],
                months=context["months"],
                month_filter=context["month_filter"]
            )
        except Exception as ex:
            current_app.logger.error("Index fetch failed: %s", ex)
            abort(500)

class AddChatView(MethodView):
    def get(self):
        try:
            add_service = AddService()
            txns = add_service.fetch_current_month_txns()
        except Exception as ex:
            current_app.logger.error("Add: GET failed: %s", ex)
            flash("Could not fetch transactions", "danger")
            txns = []
        return render_template("add.html", transactions=txns)

    def post(self):
        text = request.form.get("text")
        txn = classify_and_insert(text)
        if txn:
            return jsonify({"success": True, "txn": txn})
        return jsonify({"success": False, "error": "Could not parse amount"})
    

class SubcategoryView(MethodView):
    def get(self, category, sub_category):
        try:
            subcat_service = SubcategoryService()
            txns = subcat_service.fetch_transactions_by_subcategory(category, sub_category)
        except Exception as ex:
            current_app.logger.error("Subcategory fetch failed: %s", ex)
            abort(500)
        return render_template("subcategory.html", transactions=txns, category=category, sub_category=sub_category)
    


class EditView(MethodView):
    def get(self, txn_id):
        print("Fetching transaction for edit...",txn_id)
        try:
            service = EditService()
            txn = service.fetch_transaction(txn_id)
            if txn is None:
                current_app.logger.error("Transaction not found or access denied for txn_id: %s", txn_id)
                abort(404)
        except Exception as ex:
            current_app.logger.error("Edit fetch failed: %s", ex)
            abort(404)
        return render_template("edit.html", txn=txn, categories=CATEGORIES)

    def post(self, txn_id):
        try:
            service = EditService()
            new_desc = request.form["description"]
            new_amount = request.form["amount"]
            new_cat = request.form["category"]
            new_sub = request.form["sub_category"]
            service.update_transaction(txn_id, new_desc, new_amount, new_cat, new_sub)
            flash("Transaction updated successfully!", "success")
            return redirect(url_for("add_chat", txn_id=txn_id))
        except Exception as ex:
            current_app.logger.error("Edit update failed: %s", ex)
            abort(500)

class DeleteTransactionView(MethodView):
    def post(self, txn_id):
        try:
            service = DeleteService()
            service.delete_transaction(txn_id, session["user_id"])
            flash("Transaction deleted successfully!", "success")
        except Exception as ex:
            current_app.logger.error("Delete transaction failed: %s", ex)
            flash("Could not delete transaction!", "danger")
        return redirect(url_for("add_chat"))


class DynamicDataView(MethodView):
    def get(self, sub_category):
        search = request.args.get("search", "").strip()
        month_filter = request.args.get("month", "").strip()
        service = DataService()
        try:
            txns, subcat_list, months, month_filter = service.fetch(sub_category, month_filter, search, session["user_id"])
        except Exception as ex:
            current_app.logger.error("Dynamic data fetch failed: %s", ex)
            txns, subcat_list, months = [], [], []
        return render_template(
            "all-data.html",
            transactions=txns,
            sub_category=sub_category,
            subcat_list=subcat_list,
            months=months,
            month_filter=month_filter
        )
            

class AnalyticsView(MethodView):
    def get(self):
        try:
            service = AnalyticsService()
            expenses_data, income_rows, savings_rows, up_rows = service.fetch_analytics()
        except Exception as ex:
            current_app.logger.error("Analytics fetch failed: %s", ex)
            expenses_data, income_rows, savings_rows, up_rows = {}, [], [], []
        return render_template(
            "analytics.html",
            expenses_data=expenses_data,
            income_rows=income_rows,
            savings_rows=savings_rows,
            up_rows=up_rows
        )

class ProfileView(MethodView):
    def get(self):
        return render_template("profile.html")
    
class DownloadBackupView(MethodView):
    def get(self):
        try:
            service = BackupService()
            file_path = service.export_xlsx()
            return send_file(file_path, as_attachment=True)
        except Exception as ex:
            current_app.logger.error("Backup download failed: %s", ex)
            abort(500)

class UploadBackupView(MethodView):
    def post(self):
        try:
            if "file" not in request.files or request.files["file"].filename == "":
                flash("No file uploaded or selected!", "danger")
                return redirect(url_for("backup_page"))
            file = request.files["file"]
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)
            service = BackupService()
            service.import_xlsx(file_path)
            flash("Data uploaded successfully! Duplicate data were skipped", "success")
            return redirect(url_for("profile"))
        except Exception as ex:
            current_app.logger.error("Backup upload failed: %s", ex)
            flash("Upload failed!", "danger")
            return redirect(url_for("backup_page"))

class BackupPageView(MethodView):
    def get(self):
        return render_template("backup.html")
    
# -------------------- Register CBV with URL --------------------

app.add_url_rule("/", view_func=IndexView.as_view("index"))
app.add_url_rule("/add", view_func=AddChatView.as_view("add_chat"))
app.add_url_rule("/subcategory/<category>/<sub_category>",view_func=SubcategoryView.as_view("subcategory_view"))
app.add_url_rule("/edit/<int:txn_id>",view_func=EditView.as_view("edit"),methods=["GET", "POST"])
app.add_url_rule("/delete/<int:txn_id>",view_func=DeleteTransactionView.as_view("delete_transaction"),methods=["POST"])
app.add_url_rule("/data/<sub_category>", view_func=DynamicDataView.as_view("dynamic_data"))
app.add_url_rule("/analytics", view_func=AnalyticsView.as_view("analytics"))
app.add_url_rule("/profile", view_func=ProfileView.as_view("profile"))
app.add_url_rule("/backup/download", view_func=DownloadBackupView.as_view("download_backup"))
app.add_url_rule("/backup/upload", view_func=UploadBackupView.as_view("upload_backup"), methods=["POST"])
app.add_url_rule("/backup", view_func=BackupPageView.as_view("backup_page"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except Exception as ex:
            current_app.logger.error("Signup failed: %s", ex)
            flash("Signup failed. Try a different username.", "danger")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if user and check_password_hash(user[1], password):
                session["user_id"] = user[0]
                flash("Login successful!", "success")
                return redirect(url_for("index"))
            flash("Invalid credentials.", "danger")
        except Exception as ex:
            current_app.logger.error("Login failed: %s", ex)
            flash("Login failed. Please try again.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

# -------------------- Run App --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
