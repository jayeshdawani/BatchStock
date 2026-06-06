from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

from .celery_app import celery_init_app
from .config import Config
from .services import job_store


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    with app.app_context():
        job_store.init_db()

    celery_init_app(app)

    # Import after Celery initialization so shared tasks bind to this app.
    from . import tasks  # noqa: F401
    from .routes import dashboard_bp

    app.register_blueprint(dashboard_bp)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_error: RequestEntityTooLarge):
        return jsonify({"error": "CSV uploads must be 2 MB or smaller."}), 413

    return app
