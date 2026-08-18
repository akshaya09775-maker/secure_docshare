from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from models import Document, Share

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    my_docs = Document.query.filter_by(owner_id=current_user.id).order_by(Document.uploaded_at.desc()).all()

    shares_i_made = (
        Share.query.join(Document)
        .filter(Document.owner_id == current_user.id)
        .order_by(Share.created_at.desc())
        .all()
    )
    shares_with_me = (
        Share.query.filter_by(shared_with_id=current_user.id)
        .order_by(Share.created_at.desc())
        .all()
    )

    return render_template(
        "dashboard.html",
        my_docs=my_docs,
        shares_i_made=shares_i_made,
        shares_with_me=shares_with_me,
        now=datetime.utcnow(),
    )
