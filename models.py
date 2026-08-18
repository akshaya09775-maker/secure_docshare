import secrets
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    documents = db.relationship("Document", backref="owner", lazy=True, foreign_keys="Document.owner_id")

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)  # encrypted blob on disk
    file_size = db.Column(db.Integer, nullable=False, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    shares = db.relationship("Share", backref="document", lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document {self.original_filename}>"


class Share(db.Model):
    __tablename__ = "shares"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    shared_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    shared_with_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    token = db.Column(db.String(64), unique=True, nullable=False, index=True, default=lambda: secrets.token_urlsafe(32))
    permission = db.Column(db.String(10), nullable=False, default="view")  # "view" or "download"

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, default=False)  # owner can kill access early, independent of expiry

    shared_by = db.relationship("User", foreign_keys=[shared_by_id])
    shared_with = db.relationship("User", foreign_keys=[shared_with_id])
    access_logs = db.relationship("AccessLog", backref="share", lazy=True, cascade="all, delete-orphan")

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        return (not self.revoked) and (not self.is_expired())

    def __repr__(self):
        return f"<Share token={self.token[:8]}... expires={self.expires_at}>"


class AccessLog(db.Model):
    """Audit trail: every attempt to open a shared link, successful or not."""
    __tablename__ = "access_logs"

    id = db.Column(db.Integer, primary_key=True)
    share_id = db.Column(db.Integer, db.ForeignKey("shares.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(20), nullable=False)  # view / download / denied_expired / denied_permission / denied_revoked
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


class BrowsingHistory(db.Model):
    """Log for the Secure Browser module."""
    __tablename__ = "browsing_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # "allowed" or "blocked"
    reason = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")


class BlockedDomain(db.Model):
    __tablename__ = "blocked_domains"

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True, nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
