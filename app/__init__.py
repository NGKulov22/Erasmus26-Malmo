from flask import Flask, g, session

from app.auth import auth_bp
from app.config import Config
from app.main import main_bp
from app.services.db import init_db_app
from app.services.user_service import get_user_by_id


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    init_db_app(app)

    @app.before_request
    def load_current_user() -> None:
        g.current_user = get_user_by_id(session.get("user_id"))

    @app.context_processor
    def inject_auth_state() -> dict:
        return {
            "current_user": getattr(g, "current_user", None),
            "is_logged_in": getattr(g, "current_user", None) is not None,
        }

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app