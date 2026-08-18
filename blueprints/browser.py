from flask import Blueprint, render_template, flash, request
from flask_login import login_required, current_user

from extensions import db
from models import BrowsingHistory, BlockedDomain, AccessLog, Share
from utils.validators import is_url_safe, normalize_url

browser_bp = Blueprint("browser", __name__)


@browser_bp.route("/browser", methods=["GET", "POST"])
@login_required
def browser():
    result_url = None
    if request.method == "POST":
        raw_url = request.form.get("url", "")
        blocked = {b.domain for b in BlockedDomain.query.all()}
        safe, reason = is_url_safe(raw_url, blocked)
        normalized = normalize_url(raw_url)

        db.session.add(BrowsingHistory(
            user_id=current_user.id,
            url=normalized,
            status="allowed" if safe else "blocked",
            reason=reason,
        ))
        db.session.commit()

        if safe:
            result_url = normalized
        else:
            flash(f"Blocked: {reason}", "danger")

    return render_template("browser.html", result_url=result_url)


@browser_bp.route("/history")
@login_required
def history():
    browsing = BrowsingHistory.query.filter_by(user_id=current_user.id).order_by(
        BrowsingHistory.timestamp.desc()
    ).limit(100).all()

    access = (
        AccessLog.query.join(Share)
        .filter(Share.shared_by_id == current_user.id)
        .order_by(AccessLog.timestamp.desc())
        .limit(100)
        .all()
    )
    return render_template("history.html", browsing=browsing, access=access)
