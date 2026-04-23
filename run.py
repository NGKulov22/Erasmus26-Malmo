import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "1") == "1"
    use_reloader = os.getenv("FLASK_USE_RELOADER", "0") == "1"
    app.run(debug=debug_enabled, use_reloader=use_reloader)
