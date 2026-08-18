import io
import os
from datetime import datetime, time, timedelta

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    send_file, abort, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import User, Document, Share, AccessLog
from utils.encryption import encrypt_bytes, decrypt_bytes
from utils.helpers import client_ip

documents_bp = Blueprint("documents", __name__)


def _allowed_file(filename):
    allowed = current_app.config["ALLOWED_EXTENSIONS"]
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def _log(share, action):
    db.session.add(AccessLog(
        share_id=share.id,
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        ip_address=client_ip(),
    ))
    db.session.commit()


# ---------------------------------------------------------------
# UPLOAD (encrypted at rest)
# ---------------------------------------------------------------
@documents_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files.get("document")
        if not file or file.filename == "":
            flash("Please choose a file.", "danger")
            return redirect(url_for("documents.upload"))

        if not _allowed_file(file.filename):
            flash("File type not allowed.", "danger")
            return redirect(url_for("documents.upload"))

        original_name = secure_filename(file.filename)
        plaintext = file.read()
        encrypted = encrypt_bytes(plaintext, current_app.config["FERNET_KEY"])

        stored_name = f"{current_user.id}_{int(datetime.utcnow().timestamp())}_{original_name}.enc"
        stored_path = os.path.join(current_app.config["UPLOAD_FOLDER"], stored_name)
        with open(stored_path, "wb") as f:
            f.write(encrypted)

        doc = Document(
            owner_id=current_user.id,
            original_filename=original_name,
            stored_filename=stored_name,
            file_size=len(plaintext),
        )
        db.session.add(doc)
        db.session.commit()

        flash(f"'{original_name}' uploaded and encrypted successfully.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("upload.html")


# ---------------------------------------------------------------
# SHARE (time-limited, permission-based)
# ---------------------------------------------------------------
@documents_bp.route("/share/<int:doc_id>", methods=["GET", "POST"])
@login_required
def share_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.owner_id != current_user.id:
        abort(403)

    # Includes the current user too, so you can generate a self-share link if you want.
    users = User.query.order_by(User.username).all()

    if request.method == "POST":
        recipient_id = request.form.get("recipient_id")
        permission = request.form.get("permission", "view")
        valid_until = request.form.get("valid_until")

        recipient = User.query.get(recipient_id)
        if not recipient:
            flash("Select a valid recipient.", "danger")
            return redirect(url_for("documents.share_document", doc_id=doc.id))

        end_hour = current_app.config.get("BUSINESS_HOURS_END", 17)
        try:
            until_date = datetime.strptime(valid_until, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            flash("Pick a valid 'valid through' date.", "danger")
            return redirect(url_for("documents.share_document", doc_id=doc.id))

        if until_date < datetime.utcnow().date():
            flash("The 'valid through' date can't be in the past.", "danger")
            return redirect(url_for("documents.share_document", doc_id=doc.id))

        # Link stops working after business-hours close on the chosen day.
        # Actual access on any day in between is further restricted to the
        # 9 AM - 5 PM business-hours window (see Share.is_within_business_hours).
        expires_at = datetime.combine(until_date, time(hour=end_hour, minute=0))

        share = Share(
            document_id=doc.id,
            shared_by_id=current_user.id,
            shared_with_id=recipient.id,
            permission=permission,
            expires_at=expires_at,
        )
        db.session.add(share)
        db.session.commit()

        share_url = url_for("documents.view_shared", token=share.token, _external=True)
        flash(
            f"Share link created for {recipient.username}, accessible 9 AM–5 PM daily through {until_date}.",
            "success",
        )
        return render_template("share_result.html", share_url=share_url, share=share, doc=doc)

    return render_template(
        "share.html",
        doc=doc,
        users=users,
        business_hours_start=current_app.config.get("BUSINESS_HOURS_START", 9),
        business_hours_end=current_app.config.get("BUSINESS_HOURS_END", 17),
    )


@documents_bp.route("/revoke/<int:share_id>", methods=["POST"])
@login_required
def revoke_share(share_id):
    share = Share.query.get_or_404(share_id)
    if share.document.owner_id != current_user.id:
        abort(403)
    share.revoked = True
    db.session.commit()
    flash("Access revoked immediately.", "info")
    return redirect(url_for("main.dashboard"))


# ---------------------------------------------------------------
# ACCESS A SHARED DOCUMENT (the time-limited gate)
# ---------------------------------------------------------------
@documents_bp.route("/shared/<token>")
@login_required
def view_shared(token):
    share = Share.query.filter_by(token=token).first()
    if not share:
        return render_template("expired.html", reason="This link does not exist."), 404

    if current_user.id != share.shared_with_id:
        _log(share, "denied_identity")
        return render_template("expired.html", reason="This link was not shared with your account."), 403

    if share.revoked:
        _log(share, "denied_revoked")
        return render_template("expired.html", reason="The owner has revoked this link."), 403

    if share.is_expired():
        _log(share, "denied_expired")
        return render_template("expired.html", reason="This document-sharing link has expired."), 403

    if not share.is_within_business_hours():
        _log(share, "denied_outside_hours")
        start = current_app.config.get("BUSINESS_HOURS_START", 9)
        end = current_app.config.get("BUSINESS_HOURS_END", 17)
        reason = (
            f"This document can only be accessed between {start}:00 AM and {end - 12}:00 PM. "
            "Please come back during business hours."
        )
        return render_template("expired.html", reason=reason), 403

    _log(share, "view")
    return render_template("view_shared.html", share=share, doc=share.document)


@documents_bp.route("/shared/<token>/download")
@login_required
def download_shared(token):
    share = Share.query.filter_by(token=token).first()
    if not share:
        abort(404)

    if current_user.id != share.shared_with_id:
        _log(share, "denied_identity")
        abort(403)

    if share.revoked:
        _log(share, "denied_revoked")
        return render_template("expired.html", reason="The owner has revoked this link."), 403

    if share.is_expired():
        _log(share, "denied_expired")
        return render_template("expired.html", reason="This document-sharing link has expired."), 403

    if not share.is_within_business_hours():
        _log(share, "denied_outside_hours")
        start = current_app.config.get("BUSINESS_HOURS_START", 9)
        end = current_app.config.get("BUSINESS_HOURS_END", 17)
        reason = (
            f"This document can only be accessed between {start}:00 AM and {end - 12}:00 PM. "
            "Please come back during business hours."
        )
        return render_template("expired.html", reason=reason), 403

    if share.permission != "download":
        _log(share, "denied_permission")
        flash("You only have View access to this document, not Download.", "danger")
        return redirect(url_for("documents.view_shared", token=token))

    doc = share.document
    stored_path = os.path.join(current_app.config["UPLOAD_FOLDER"], doc.stored_filename)
    with open(stored_path, "rb") as f:
        encrypted = f.read()
    plaintext = decrypt_bytes(encrypted, current_app.config["FERNET_KEY"])

    _log(share, "download")
    return send_file(
        io.BytesIO(plaintext),
        as_attachment=True,
        download_name=doc.original_filename,
    )
