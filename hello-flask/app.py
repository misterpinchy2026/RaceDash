from flask import Flask

app = Flask(__name__)


@app.route("/", methods=["GET"])
def hello() -> tuple[str, int]:
    return "Hello, World!", 200


if __name__ == "__main__":
    print("Starting Hello World Flask app on http://127.0.0.1:5000")
    app.run(debug=True)
