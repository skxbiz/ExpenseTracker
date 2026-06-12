from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import os

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)

# Generate a key for encryption - in production, this should be stored securely
try:
    import hashlib

    password = "RioMario0201"
    key = base64.urlsafe_b64encode(
        hashlib.sha256(password.encode()).digest()
    )

    cipher_suite = Fernet(key)

except Exception as e:
    print(f"Error initializing encryption: {e}")
    key = Fernet.generate_key()
    cipher_suite = Fernet(key)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def encrypt_password(password: str) -> str:
    """Encrypt a password using Fernet symmetric encryption."""
    encrypted_bytes = cipher_suite.encrypt(password.encode())
    return base64.b64encode(encrypted_bytes).decode('utf-8')


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt a password using Fernet symmetric encryption."""
    encrypted_bytes = base64.b64decode(encrypted_password.encode())
    decrypted_bytes = cipher_suite.decrypt(encrypted_bytes)
    return decrypted_bytes.decode('utf-8')
