
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier

# ----------------------
# Categories
# ----------------------
CATEGORIES = {
    "Income": ["Salary", "Other Income Sources"],
    "Expenses": ["Food & Drinks","Shopping","Personal Care","Transport","Loans & EMI",
                 "Education","Bills & Utilities","Housing","Entertainment","Gifts","Others"],
    "Usne-Pasne": ["Money Sent","Money Received"],
    "Savings / Investments": ["Savings","Mutual Fund","Stock","Crypto","Forex","Property"]
}

# Generate classes for the model
classes = []
for main_cat, subcats in CATEGORIES.items():
    for sub in subcats:
        classes.append(f"{main_cat}|{sub}")
classes = sorted(classes)

# ----------------------
# Training Data
# ----------------------
training_sentences = [
    "i got salary 30000", "my paycheck is 20000", "salary credited 25000",
    "bonus 5000", "i won 2000", "income from rent 7000",
    "tea 15", "coffee 20", "lunch 200", "dinner 300",
    "petrol 1000", "bus ticket 50", "train pass 600",
    "bike emi 1600", "loan payment 5000", "car emi 12000",
    "recharge 300", "electricity bill 1200", "wifi bill 800",
    "add 5000 in mutual fund", "invest 2000 in stock", "buy crypto 1500", 
    "save 1000 in savings account", "property 20000",
    "i give 300 to sushant", "i sent 500 to friend",
    "i got 200 from paggo", "borrowed 400 from raj"
]

labels = [
    "Income|Salary", "Income|Salary", "Income|Salary",
    "Income|Other Income Sources", "Income|Other Income Sources", "Income|Other Income Sources",
    "Expenses|Food & Drinks", "Expenses|Food & Drinks", "Expenses|Food & Drinks", "Expenses|Food & Drinks",
    "Expenses|Transport", "Expenses|Transport", "Expenses|Transport",
    "Expenses|Loans & EMI", "Expenses|Loans & EMI", "Expenses|Loans & EMI",
    "Expenses|Bills & Utilities", "Expenses|Bills & Utilities", "Expenses|Bills & Utilities",
    "Savings / Investments|Mutual Fund", "Savings / Investments|Stock", "Savings / Investments|Crypto",
    "Savings / Investments|Savings", "Savings / Investments|Property",
    "Usne-Pasne|Money Sent", "Usne-Pasne|Money Sent",
    "Usne-Pasne|Money Received", "Usne-Pasne|Money Received"
]

# ----------------------
# Vectorize
# ----------------------
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(training_sentences)

# ----------------------
# SGDClassifier (supports partial_fit for online learning)
# ----------------------
clf = SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3)

# Initial partial_fit using all known classes
clf.partial_fit(X, labels, classes=classes)

# ----------------------
# Save vectorizer, classifier, and classes
# ----------------------
joblib.dump((vectorizer, clf, classes), "money_ai_model.pkl")
print("✅ AI Model trained and saved with fixed classes for online learning")
