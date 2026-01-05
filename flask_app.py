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
        origin = repo.remotes.origin
        origin.pull()
        return 'Updated PythonAnywhere successfully', 200
    return 'Unauthorized', 401


# ---------------- AUTH ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = authenticate(request.form["username"], request.form["password"])
        if user:
            login_user(user)
            return redirect(url_for("index"))
        error = "Benutzername oder Passwort ist falsch."
    return render_template("auth.html", title="Login", action=url_for("login"),
                           button_label="Einloggen", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        ok = register_user(request.form["username"], request.form["password"])
        if ok:
            return redirect(url_for("login"))
        error = "Benutzername existiert bereits."
    return render_template("auth.html", title="Register", action=url_for("register"),
                           button_label="Registrieren", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ---------------- APP ----------------

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "GET":
        todos = db_read("""
            SELECT 
                m.id,
                m.user_id,
                m.content,
                m.cat,
                m.location,
                EXISTS (
                    SELECT 1 FROM RentRequests r
                    WHERE r.material_id = m.id
                    AND r.requester_id = %s
                ) AS requested
            FROM Material m
        """, (current_user.id,))

        return render_template("main_page.html", todos=todos)

    db_write(
        "INSERT INTO Material (user_id, content, cat, location) VALUES (%s, %s, %s, %s)",
        (
            current_user.id,
            request.form["contents"],
            request.form["category"],
            request.form["location"],
        )
    )
    return redirect(url_for("index"))


@app.post("/rent/<int:material_id>")
@login_required
def rent(material_id):
    db_write(
        "INSERT IGNORE INTO RentRequests (material_id, requester_id) VALUES (%s, %s)",
        (material_id, current_user.id)
    )
    return redirect(url_for("index"))


@app.post("/complete")
@login_required
def complete():
    db_write(
        "DELETE FROM Material WHERE id=%s AND user_id=%s",
        (request.form["id"], current_user.id)
    )
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run()
    
