import os

from flask import Flask, render_template

from config import Config
from extensions import db, login_manager
from models import User, BlockedDomain


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    # --- Register each page/module as its own blueprint ---
    from blueprints.auth import auth_bp
    from blueprints.main import main_bp
    from blueprints.documents import documents_bp
    from blueprints.browser import browser_bp

    app.register_blueprint(auth_bp)        # /register, /login, /logout
    app.register_blueprint(main_bp)        # /, /dashboard
    app.register_blueprint(documents_bp)   # /upload, /share/<id>, /shared/<token>, ...
    app.register_blueprint(browser_bp)     # /browser, /history

    with app.app_context():
        db.create_all()
        _seed_blocked_domains(app)

    @app.errorhandler(413)
    def too_large(e):
        max_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return render_template("too_large.html", max_mb=max_mb), 413

    return app


def _seed_blocked_domains(app):
    if BlockedDomain.query.count() == 0:
        for domain in app.config["DEFAULT_BLOCKED_DOMAINS"]:
            db.session.add(BlockedDomain(domain=domain))
        db.session.commit()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
