# services/utils_fastapi.py
import re
import joblib
from datetime import datetime
from services.firebase_db import firebase_service
from typing import Optional, Dict

# -------------------- Load ML models --------------------
vectorizer = clf = classes = None
amount_vectorizer = amount_clf = amount_le = None

try:
    vectorizer, clf, classes = joblib.load("money_ai_model.pkl")
except Exception as ex:
    print(f"AI model loading failed: {ex}")
    vectorizer = clf = classes = None

try:
    amount_vectorizer, amount_clf, amount_le = joblib.load("amount_extractor.pkl")
except Exception as ex:
    print(f"Amount extractor model loading failed: {ex}")
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
def extract_amounts(text: str) -> float:
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
async def classify_and_insert(user_input: str, user_id: str) -> Optional[Dict]:
    """Classify transaction and insert into Firebase."""
    if vectorizer is None or clf is None:
        return None

    amount = extract_amounts(user_input)
    X_test = vectorizer.transform([user_input])
    prediction = clf.predict(X_test)[0]
    category, sub_category = prediction.split("|")

    try:
        transaction_data = {
            'category': category,
            'sub_category': sub_category,
            'description': user_input,
            'amount': amount,
            'date_time': datetime.now(),
            'user_id': user_id
        }
        
        txn_id = firebase_service.create_transaction(transaction_data)
        
        if txn_id:
            # Fetch the created transaction to return complete data
            txn = firebase_service.get_transaction(txn_id, user_id)
            return txn
        else:
            return None
            
    except Exception as ex:
        print(f"Firebase Insert failed: {ex}")
        return None

# -------------------- Helper --------------------
# Note: This function is no longer needed with Firebase as we get dictionaries directly
# Keeping it for compatibility with existing code that might still use it
def rows_to_dict(cursor_description, rows):
    """Convert DB rows to dictionary (for backward compatibility)."""
    desc = [d[0] for d in cursor_description]
    return [dict(zip(desc, row)) for row in rows]