# Erasmus26-Malmo

Flask web app for Erasmus students in Malmo.

## Structure

```text
Erasmus26-Malmo/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── main/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── templates/
│       ├── base.html
│       ├── home.html
│       ├── about.html
│       └── contact.html
├── requirements.txt
└── run.py
```

## Run

1. Install dependencies:

	```bash
	pip install -r requirements.txt
	```

2. Configure environment variables:

	- Copy `.env.example` to `.env`
	- Set `DATABASE_URL` to your shared PostgreSQL database

	Example:
	```text
	DATABASE_URL=postgresql://postgres:postgres@localhost:5432/malmo_connect
	```

3. Create PostgreSQL database (once):

	```bash
	createdb malmo_connect
	```

4. Start app:

	```bash
	python run.py
	```

5. Open:

	```text
	http://127.0.0.1:5000
	```

## Notes

- SQLite is no longer used for app data.
- The old local file `app/data/malmo_connect.db` can stay on disk; it is ignored by git and not used by the app.
- For all teammates to see the same forum posts/messages, everyone must use the same `DATABASE_URL`.