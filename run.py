from dotenv import load_dotenv

import os
result = load_dotenv()

from pathlib import Path

from app import create_app


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()

app = create_app()

if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "1") == "1"
    use_reloader = os.getenv("FLASK_USE_RELOADER", "0") == "1"
    app.run(debug=debug_enabled, use_reloader=use_reloader)
