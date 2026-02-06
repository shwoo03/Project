from flask import Flask, render_template, request, session, abort
import os, time, secrets, json
from pathlib import Path
import random

app = Flask(__name__)
app.secret_key = os.environ.get("???", "???")

BASE_DIR = Path(__file__).resolve().parent
FLAG_PATH = BASE_DIR / "flag.txt"
ADS_JSON = BASE_DIR / "static" / "ads.json"


def read_flag():
    return FLAG_PATH.read_text(encoding="utf-8").strip()

def _now():
    return int(time.time())

def _ensure_session():
    if "sid" not in session:
        session["sid"] = secrets.token_urlsafe(16)
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    if "last_hb" not in session:
        session["last_hb"] = _now()

def load_ads():
    data = json.loads(ADS_JSON.read_text(encoding="utf-8"))

    ads = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "Sponsored Ad"))
        body = str(item.get("body", "Best deal of your life."))
        ads.append({"title": title, "body": body})
    return ads


@app.after_request
def security_headers(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp

@app.route("/", methods=["GET"])
def index():
    _ensure_session()
    session["last_hb"] = _now()
    ads = load_ads()
    return render_template(
        "index.html",
        csrf=session["csrf"],
        max_ads=min(20, len(ads)) if ads else 20,
        hb_ms=1000,
        stale_seconds=5,
        ads=ads,
        flag=None
    )

@app.route("/hb", methods=["POST"])
def hb():
    if "sid" not in session:
        return ("", 204)
    session["last_hb"] = _now()
    return ("", 204)

@app.route("/claim", methods=["POST"])
def claim():
    _ensure_session()
    csrf = request.form.get("csrf", "")
    if csrf != session.get("csrf"):
        abort(400, description="Bad CSRF")

    last_hb = session.get("last_hb", 0)
    age = _now() - last_hb
    ads = load_ads()

    if age < 5:
        msg = f"You're still in ads, kill all ads"
        return render_template(
            "index.html",
            csrf=session["csrf"],
            max_ads=min(20, len(ads)) if ads else 20,
            hb_ms=1000,
            stale_seconds=5,
            ads=ads,
            flag=None,
            error=msg
        ), 403

    flag = read_flag()
    return render_template(
        "index.html",
        csrf=session["csrf"],
        max_ads=min(20, len(ads)) if ads else 20,
        hb_ms=1000,
        stale_seconds=5,
        ads=ads,
        flag=flag
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
