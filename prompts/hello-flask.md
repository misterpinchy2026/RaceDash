# Prompt: Hello World Flask App

## Summary
Build the simplest possible Flask application (Python 3.9+) that exposes a single `/` endpoint returning "Hello, World!". Use this as a foundation scaffold for environment validation or future microservices.

## Functional Requirements
- Route `/` responds to GET with HTTP 200 and the string `Hello, World!`.
- Server runs locally via `python app.py`, binding to `127.0.0.1:5000` with `debug=True` and printing a startup log message.

## Non-Goals
- No auth, DB, Docker, CI/CD, or cloud deployment.
- Keep code under 25 lines and in a single file.

## Deliverables
- `hello-flask/app.py` implementing the route.
- `hello-flask/requirements.txt` pinning `Flask>=3.0.0`.
- `hello-flask/README.md` documenting setup, run instructions, and acceptance criteria.

## Definition of Done
- App starts without errors.
- Visiting `http://127.0.0.1:5000/` returns `Hello, World!`.
- No extra endpoints or dependencies beyond Flask.
