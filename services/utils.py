# utils.py
import re
import joblib
from datetime import datetime
from flask import current_app, session
from services.db import get_db

# -------------------- Load ML models --------------------
try:
    vectorizer, clf, classes = joblib.load("money_ai_model.pkl")
except Exception as ex:
    current_app.logger.error("AI model loading failed: %s", ex)
    vectorizer = clf = classes = None

try:
    amount_vectorizer, amount_clf, amount_le = joblib.load("amount_extractor.pkl")
except Exception as ex:
    current_app.logger.error("Amount extractor model loading failed: %s", ex)
    amount_vectorizer = amount_clf = amount_le = None

# -------------------- Categories --------------------
CATEGORIES = {
    "Income": ["Salary", "Other Income Sources"],
    "Expenses": [
        "Food & Drinks", "Shopping", "Personal Care", "Transport", "Loans & EMI",
        "Education", "Bills & Utilities", "Housing", "Entertainment", "Gifts", "Others"
    ],
    "Usne-Pasne": ["Money Sent", "Money Received"],
    "Savings / Investments": ["Savings", "Mutual Fund", "Stock", "Crypto", "Forex", "Property"]
}

# -------------------- Amount Extraction --------------------
def extract_amounts(text):
    """Extract numeric amounts from text."""
    if amount_vectorizer is None or amount_clf is None or amount_le is None:
        matches = re.findall(r'[\d,.]+', text)
        amounts = [float(m.replace(',', '')) for m in matches]
        return sum(amounts) if amounts else 0

    tokens = text.split()
    X_vect = amount_vectorizer.transform(tokens)
    y_pred = amount_clf.predict(X_vect)
    labels = amount_le.inverse_transform(y_pred)

    amounts = []
    for token, label in zip(tokens, labels):
        if label == "AMOUNT":
            clean_token = re.sub(r'[^\d.]', '', token)
            if clean_token:
                amounts.append(float(clean_token))
    return sum(amounts) if amounts else 0

# -------------------- Classification & Insert --------------------
def classify_and_insert(user_input: str):
    """Classify transaction and insert into DB."""
    if vectorizer is None or clf is None:
        return None

    amount = extract_amounts(user_input)
    X_test = vectorizer.transform([user_input])
    prediction = clf.predict(X_test)[0]
    category, sub_category = prediction.split("|")

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO transactions (category, sub_category, description, amount, date_time, user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (category, sub_category, user_input, amount, datetime.now(), session["user_id"]))

        cur.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        txn_id = row[0] if row else None
        conn.commit()
        cur.close()
        return {"id": txn_id, "category": category, "sub_category": sub_category, "amount": amount, "description": user_input}
    except Exception as ex:
        current_app.logger.error("DB Insert failed: %s", ex)
        return None
    finally:
        if conn:
            conn.close()

# -------------------- Helper --------------------
def rows_to_dict(cur, rows):
    """Convert DB rows to dictionary."""
    desc = [d[0] for d in cur.description]
    return [dict(zip(desc, row)) for row in rows]
