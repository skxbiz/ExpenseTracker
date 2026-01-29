from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
from datetime import datetime
import traceback
import json

# Import our services
from services.firebase_db import firebase_service
from services.utils_fastapi import CATEGORIES, classify_and_insert
from services.dashboard_service_fastapi import DashboardService
from services.add_service_fastapi import AddService
from services.subcategory_service_fastapi import SubcategoryService
from services.edit_service_fastapi import EditService
from services.delete_service_fastapi import DeleteService
from services.data_service_fastapi import DataService
from services.analytics_service_fastapi import AnalyticsService
from services.backup_service_fastapi import BackupService
from services.password_service_fastapi import PasswordService
from services.password_utils import hash_password, verify_password


# Initialize FastAPI app
app = FastAPI(title="Expense Tracker", debug=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Add template context processor for static files
def static_url(filename: str):
    return f"/static/{filename}"

templates.env.globals['static_url'] = static_url

# Security
# Using pbkdf2_sha256 for password hashing instead of bcrypt

# Session middleware
app.add_middleware(SessionMiddleware, secret_key=os.environ.get('SECRET_KEY', 'your-secret-key-here'))

# Utility functions
# def hash_password(password: str) -> str:
#     return pbkdf2_sha256.hash(password)

# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     return pbkdf2_sha256.verify(plain_password, hashed_password)

def login_required(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    return user_id

# Custom template filters
def datetimeformat_filter(value, format='%b %Y'):
    if not value:
        return ""
    try:
        if isinstance(value, str):
            # Try to parse different datetime formats
            if "T" in value:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        else:
            dt = value
        return dt.strftime(format)
    except:
        return str(value)

def format_dt_filter(value):
    if not value:
        return ""
    try:
        if isinstance(value, str):
            if "T" in value:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        else:
            dt = value
        return dt.strftime("%d %b, %I:%M %p")
    except:
        try:
            if isinstance(value, str):
                dt = datetime.strptime(value, "%Y-%m-%d")
                return dt.strftime("%d %B %Y")
            else:
                return str(value)
        except:
            return str(value)

# Add filters to templates
templates.env.filters['datetimeformat'] = datetimeformat_filter
templates.env.filters['format_dt'] = format_dt_filter

# Add flash messages functionality for Jinja2
def get_flashed_messages(with_categories=False):
    # This function simulates Flask's get_flashed_messages for compatibility
    # Since we're using FastAPI, we'll implement a similar concept using session
    # In practice, you would implement proper flash messaging here
    return []

templates.env.globals['get_flashed_messages'] = get_flashed_messages

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    print(f"Internal Server Error: {traceback.format_exc()}")
    return templates.TemplateResponse("500.html", {"request": request}, status_code=500)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("500.html", {"request": request}, status_code=exc.status_code)

# Startup event
@app.on_event("startup")
async def startup_event():
    try:
        print("✅ Application started successfully.")
    except Exception as ex:
        print(f"❌ Application startup failed: {ex}")

# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, month: str = None):
    try:
        user_id = login_required(request)
        user = firebase_service.get_user_by_id(user_id)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        service = DashboardService(user_id, month)
        context = service.get_context()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user": user,
            "summary": context["summary"],
            "totals": context["totals"],
            "networth": context["networth"],
            "months": context["months"],
            "month_filter": context["month_filter"],
            "categories": ["all", "Food & Drinks", "Shopping", "Transport", "Bills & Utilities"]
        })
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/add", response_class=HTMLResponse)
async def add_chat_get(request: Request):
    try:
        user_id = login_required(request)
        add_service = AddService(user_id)
        txns = add_service.fetch_current_month_txns()
        return templates.TemplateResponse("add.html", {
            "request": request,
            "transactions": txns
        })
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.post("/add", response_class=JSONResponse)
async def add_chat_post(request: Request, text: str = Form(...)):
    try:
        user_id = login_required(request)
        txn = await classify_and_insert(text, user_id)
        if txn:
            return JSONResponse({"success": True, "txn": txn})
        return JSONResponse({"success": False, "error": "Could not parse amount"})
    except HTTPException:
        return JSONResponse({"success": False, "error": "Authentication required"}, status_code=401)

@app.get("/subcategory/{category}/{sub_category}", response_class=HTMLResponse)
async def subcategory_view(request: Request, category: str, sub_category: str):
    try:
        user_id = login_required(request)
        subcat_service = SubcategoryService(user_id)
        txns = subcat_service.fetch_transactions_by_subcategory(category, sub_category)
        return templates.TemplateResponse("subcategory.html", {
            "request": request,
            "transactions": txns,
            "category": category,
            "sub_category": sub_category
        })
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/edit/{txn_id}", response_class=HTMLResponse)
async def edit_get(request: Request, txn_id: str):
    try:
        user_id = login_required(request)
        service = EditService(user_id)
        txn = service.fetch_transaction(txn_id)
        if txn is None:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return templates.TemplateResponse("edit.html", {
            "request": request,
            "txn": txn,
            "categories": CATEGORIES
        })
    except HTTPException as ex:
        if ex.status_code == 401:
            return RedirectResponse(url="/login", status_code=303)
        raise ex

@app.post("/edit/{txn_id}", response_class=RedirectResponse)
async def edit_post(
    request: Request, 
    txn_id: str,
    description: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...),
    sub_category: str = Form(...)
):
    try:
        user_id = login_required(request)
        service = EditService(user_id)
        success = service.update_transaction(txn_id, description, amount, category, sub_category)
        if success:
            request.session["flash"] = {"type": "success", "message": "Transaction updated successfully!"}
        else:
            request.session["flash"] = {"type": "danger", "message": "Failed to update transaction"}
        return RedirectResponse(url=f"/add", status_code=303)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.post("/delete/{txn_id}", response_class=RedirectResponse)
async def delete_transaction(request: Request, txn_id: str):
    try:
        user_id = login_required(request)
        service = DeleteService(user_id)
        success = service.delete_transaction(txn_id)
        if success:
            request.session["flash"] = {"type": "success", "message": "Transaction deleted successfully!"}
        else:
            request.session["flash"] = {"type": "danger", "message": "Could not delete transaction!"}
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)
    return RedirectResponse(url="/add", status_code=303)

@app.get("/data/{sub_category}", response_class=HTMLResponse)
async def dynamic_data(request: Request, sub_category: str, search: str = "", month: str = ""):
    try:
        user_id = login_required(request)
        user = firebase_service.get_user_by_id(user_id)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        service = DataService(user_id)
        txns, subcat_list, months, month_filter = service.fetch(sub_category, month, search)
        return templates.TemplateResponse("all-data.html", {
            "request": request,
            "user": user,
            "transactions": txns,
            "sub_category": sub_category,
            "subcat_list": subcat_list,
            "months": months,
            "month_filter": month_filter
        })
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    try:
        user_id = login_required(request)
        user = firebase_service.get_user_by_id(user_id)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        service = AnalyticsService(user_id)
        expenses_data, income_rows, savings_rows, up_rows = service.fetch_analytics()
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "user": user,
            "expenses_data": expenses_data,
            "income_rows": income_rows,
            "savings_rows": savings_rows,
            "up_rows": up_rows
        })
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    try:
        user_id = login_required(request)
        user = firebase_service.get_user_by_id(user_id)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        return templates.TemplateResponse("profile.html", {"request": request, "user": user})
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/backup/download")
async def download_backup(request: Request):
    try:
        user_id = login_required(request)
        service = BackupService(user_id)
        file_path = service.export_xlsx()
        return FileResponse(file_path, filename="backup.xlsx")
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.post("/backup/upload")
async def upload_backup(request: Request, file: bytes = Form(...), filename: str = Form(...)):
    try:
        user_id = login_required(request)
        # Save file temporarily
        upload_folder = "uploads"
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        
        with open(file_path, "wb") as f:
            f.write(file)
        
        service = BackupService(user_id)
        service.import_xlsx(file_path)
        
        request.session["flash"] = {"type": "success", "message": "Data uploaded successfully!"}
        return RedirectResponse(url="/profile", status_code=303)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/backup", response_class=HTMLResponse)
async def backup_page(request: Request):
    try:
        login_required(request)
        return templates.TemplateResponse("backup.html", {"request": request})
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/passwords", response_class=HTMLResponse)
async def password_manager_get(request: Request):
    try:
        user_id = login_required(request)
        service = PasswordService(user_id)
        passwords = service.list_passwords()
        return templates.TemplateResponse("password_manager.html", {
            "request": request,
            "passwords": passwords
        })
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.post("/passwords", response_class=JSONResponse)
async def password_manager_post(
    request: Request,
    category: str = Form(None),
    username: str = Form(None),
    password: str = Form(None),
    activeOption: str = Form(...)
):
    try:
        user_id = login_required(request)
        service = PasswordService(user_id)
        
        # Validation depends on the active option
        if activeOption == "New":
            if not category or not username or not password:
                return JSONResponse({"success": False, "error": "All fields are required for adding a new password!"})
            result = service.add_password(category, username, password)
            return JSONResponse({"success": True, "password": result}) if result else JSONResponse({"success": False, "password": None})
        
        elif activeOption == "Search":
            # For search, we can search with partial information
            results = service.search_passwords(category or "", username or "")
            return JSONResponse({"success": True, "password": results}) if results else JSONResponse({"success": False, "password": []})
        
        elif activeOption == "List":
            # For list, we just fetch all passwords for the user
            passwords = service.list_passwords()
            return JSONResponse({"success": True, "password": passwords})
        
        else:
            return JSONResponse({"success": False, "error": "Invalid operation"})
            
    except HTTPException:
        return JSONResponse({"success": False, "error": "Authentication required"}, status_code=401)

@app.post("/passwords/delete/{password_id}", response_class=JSONResponse)
async def delete_password(request: Request, password_id: str):
    try:
        user_id = login_required(request)
        service = PasswordService(user_id)
        success = service.delete_password(password_id)
        if success:
            return JSONResponse({"success": True})
        else:
            return JSONResponse({"success": False, "error": "Failed to delete password"})
    except HTTPException:
        return JSONResponse({"success": False, "error": "Authentication required"}, status_code=401)

@app.put("/passwords/{password_id}", response_class=JSONResponse)
async def update_password(
    request: Request, 
    password_id: str,
    category: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    try:
        user_id = login_required(request)
        service = PasswordService(user_id)
        success = service.update_password(password_id, category, username, password)
        if success:
            return JSONResponse({"success": True, "message": "Password updated successfully"})
        else:
            return JSONResponse({"success": False, "error": "Failed to update password"})
    except HTTPException:
        return JSONResponse({"success": False, "error": "Authentication required"}, status_code=401)

@app.get("/signup", response_class=HTMLResponse)
async def signup_get(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup")
async def signup_post(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        # Check if user already exists
        existing_user = firebase_service.get_user_by_username(username)
        if existing_user:
            request.session["flash"] = {"type": "danger", "message": "Username already exists. Try a different username."}
            return RedirectResponse(url="/signup", status_code=303)
        
        # Create new user
        hashed_password = hash_password(password)
        user_id = firebase_service.create_user(username, hashed_password)
        
        if user_id:
            request.session["flash"] = {"type": "success", "message": "Signup successful! Please log in."}
            return RedirectResponse(url="/login", status_code=303)
        else:
            request.session["flash"] = {"type": "danger", "message": "Signup failed. Please try again."}
            return RedirectResponse(url="/signup", status_code=303)
            
    except Exception as ex:
        print(f"Signup failed: {ex}")
        request.session["flash"] = {"type": "danger", "message": "Signup failed. Please try again."}
        return RedirectResponse(url="/signup", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    # Check if already logged in
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    try:
        # Get user from database
        user = firebase_service.get_user_by_username(username)
        if not user:
            request.session["flash"] = {"type": "danger", "message": "Invalid credentials."}
            return RedirectResponse(url="/login", status_code=303)
        
        # Verify password
        if verify_password(password, user.get('password', '')):
            request.session["user_id"] = user['id']
            request.session["flash"] = {"type": "success", "message": "Login successful!"}
            return RedirectResponse(url="/", status_code=303)
        else:
            request.session["flash"] = {"type": "danger", "message": "Invalid credentials."}
            return RedirectResponse(url="/login", status_code=303)
            
    except Exception as ex:
        print(f"Login failed: {ex}")
        request.session["flash"] = {"type": "danger", "message": "Login failed. Please try again."}
        return RedirectResponse(url="/login", status_code=303)

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    request.session["flash"] = {"type": "success", "message": "Logged out successfully."}
    return RedirectResponse(url="/login", status_code=303)


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools():
    return {}


# Main entry point
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)