# Hello World Flask App

> Version: 1.0 · Status: Ready to Build

This project implements the minimal Flask scaffold described in the PRD. It runs locally, exposes a single `/` endpoint, and returns `Hello, World!` so you can validate your environment or bootstrap future microservices.

## Project Structure

```
hello-flask/
├── app.py
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.9+
- Flask (installed via `requirements.txt`)

## Setup

```bash
cd hello-flask
python -m venv venv             # optional but recommended
source venv/bin/activate         # macOS/Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

## Run the App

```bash
python app.py
```

Visit <http://127.0.0.1:5000> and you should see `Hello, World!`. The server prints a startup message and runs with `debug=True` for local development. If you don’t see the response, fix your Python environment before adding more complexity.

## Acceptance Criteria Checklist

- [x] Starts without errors via `python app.py`
- [x] `GET /` returns HTTP 200 and `Hello, World!`
- [x] No other endpoints or dependencies
- [x] Code stays under 25 lines and is simple to extend

## Stretch Ideas (Optional)

- Return HTML: `return "<h1>Hello, World!</h1>"`
- Return JSON: `return jsonify(message="Hello, World!")`
- Custom port: `app.run(host="0.0.0.0", port=8000)`

Build it. Commit it. Move on.
