import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # --- Core Flask ---
    SECRET_KEY = os.environ["SECRET_KEY"]

    # --- Database ---
    # Default: SQLite (zero setup, perfect for a college demo/viva)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}"
    )
    # To use MySQL instead, set an environment variable before running, e.g.:
    #   DATABASE_URL=mysql+pymysql://root:yourpassword@localhost/secure_docshare
    # and make sure you `pip install pymysql` and create the database first:
    #   CREATE DATABASE secure_docshare;
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- File storage ---
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    # Max upload size in MB. Override with an env var if your demo files are bigger,
    # e.g.: export MAX_UPLOAD_MB=100
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", 100)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "png", "jpg", "jpeg"}

    # --- Encryption ---
    # Master key used to encrypt/decrypt files at rest with Fernet (AES-128-CBC + HMAC).
    # Generate your own with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # and set it as an environment variable in production. A default is provided
    # here ONLY so the project runs out-of-the-box for a demo.
    FERNET_KEY = os.environ["FERNET_KEY"]

    # --- Session / auth ---
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # --- Secure browser module ---
    # Simple blocklist seeded on first run; extend from the admin/DB as needed.
    DEFAULT_BLOCKED_DOMAINS = [
        "malicious-test.com",
        "phishing-example.net",
        "torrentz2.eu",
        "example-malware.org",
    ]

    # --- Share link expiry options shown in the UI (minutes) ---
    EXPIRY_OPTIONS = [
        ("10", "10 minutes"),
        ("30", "30 minutes"),
        ("60", "1 hour"),
        ("1440", "1 day"),
        ("custom", "Custom"),
    ]
