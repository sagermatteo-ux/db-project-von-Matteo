from flask import Flask, redirect, render_template, request, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from db import db_read, db_write  # Dein DB-Layer
from auth import authenticate, register_user

app = Flask(__name__)
app.secret_key = "supersecret"
app.config["DEBUG"] = True

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ---------------- AUTH ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = authenticate(request.form["username"], request.form["password"])
        if user:
            login_user(user)
            return redirect(url_for("index"))
        error = "Login fehlgeschlagen"
    return render_template("auth.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        if register_user(request.form["username"], request.form["password"]):
            return redirect(url_for("login"))
        error = "User existiert bereits"
    return render_template("auth.html", error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

# ---------------- APP ----------------

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    # POST: neuen Gegenstand hinzufügen
    if request.method == "POST":
        db_write(
            "INSERT INTO Material (user_id, content, cat, location) VALUES (%s, %s, %s, %s)",
            (current_user.id, request.form["contents"], request.form["category"], request.form["location"])
        )
        return redirect(url_for("index"))

    # GET: Todos laden + prüfen, ob User bereits angefragt hat
    try:
        todos = db_read("""
            SELECT 
                m.id, m.user_id, m.content, m.cat, m.location,
                EXISTS (
                    SELECT 1 FROM RentRequests r
                    WHERE r.material_id = m.id
                    AND r.requester_id = %s
                ) AS requested
            FROM Material m
        """, (current_user.id,))
    except Exception as e:
        print("SQL ERROR:", e)
        todos = []

    return render_template("main_page.html", todos=todos)

@app.post("/rent/<int:material_id>")
@login_required
def rent(material_id):
    try:
        db_write(
            "INSERT IGNORE INTO RentRequests (material_id, requester_id) VALUES (%s, %s)",
            (material_id, current_user.id)
        )
    except Exception as e:
        print("Rent SQL ERROR:", e)
    return redirect(url_for("index"))