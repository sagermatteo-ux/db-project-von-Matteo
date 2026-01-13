from flask import Flask, redirect, render_template, request, url_for
from dotenv import load_dotenv
import os
import git
import hmac
import hashlib
from db import db_read, db_write
from auth import login_manager, authenticate, register_user
from flask_login import login_user, logout_user, login_required, current_user
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

load_dotenv()
W_SECRET = os.getenv("W_SECRET")

app = Flask(__name__)
app.config["DEBUG"] = True
app.secret_key = "supersecret"

login_manager.init_app(app)
login_manager.login_view = "login"


# ---------- WEBHOOK (NICHT ÄNDERN) ----------
def is_valid_signature(x_hub_signature, data, private_key):
    hash_algorithm, github_signature = x_hub_signature.split('=', 1)
    algorithm = hashlib.__dict__.get(hash_algorithm)
    encoded_key = bytes(private_key, 'latin-1')
    mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
    return hmac.compare_digest(mac.hexdigest(), github_signature)


@app.post('/update_server')
def webhook():
    x_hub_signature = request.headers.get('X-Hub-Signature')
    if is_valid_signature(x_hub_signature, request.data, W_SECRET):
        repo = git.Repo('./mysite')
        repo.remotes.origin.pull()
        return 'Updated', 200
    return 'Unauthorized', 401


# ---------- AUTH ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = authenticate(
            request.form["username"],
            request.form["password"]
        )
        if user:
            login_user(user)
            return redirect(url_for("index"))
        error = "Login fehlgeschlagen."
    return render_template("auth.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        if register_user(request.form["username"], request.form["password"]):
            return redirect(url_for("login"))
        error = "Benutzer existiert bereits."
    return render_template("auth.html", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ---------- MAIN ----------
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        db_write(
            """
            INSERT INTO Material (user_id, content, cat, location, pickup_time)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                current_user.id,
                request.form["contents"],
                request.form["category"],
                request.form["location"],
                request.form["pickup_time"],
            )
        )
        return redirect(url_for("index"))

    todos = db_read(
        """
        SELECT m.id, m.user_id, m.content, m.cat, m.location, m.pickup_time,
               r.status
        FROM Material m
        LEFT JOIN RentRequests r ON m.id = r.material_id
        """,
    )

    return render_template("main_page.html", todos=todos)


@app.post("/rent/<int:material_id>")
@login_required
def rent(material_id):
    db_write(
        "INSERT IGNORE INTO RentRequests (material_id, requester_id) VALUES (%s, %s)",
        (material_id, current_user.id),
    )
    return redirect(url_for("index"))


@app.post("/delete_material/<int:material_id>")
@login_required
def delete_material(material_id):
    db_write(
        "DELETE FROM Material WHERE id = %s AND user_id = %s",
        (material_id, current_user.id),
    )
    return redirect(url_for("index"))


@app.post("/accept_request/<int:material_id>")
@login_required
def accept_request(material_id):
    db_write(
        "UPDATE RentRequests SET status = 'accepted' WHERE material_id = %s",
        (material_id,),
    )
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run()