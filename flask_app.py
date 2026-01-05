from flask import Flask, redirect, render_template, request, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from db import db_read, db_write  # Dein DB-Layer, muss commit() in db_write haben
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecret"
app.config["DEBUG"] = True

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ---------------- User Loader ----------------
@login_manager.user_loader
def load_user(user_id):
    # Lädt User aus der DB
    user = db_read("SELECT id, username, password FROM users WHERE id=%s", (user_id,))
    if user:
        row = user[0]
        class UserObj:
            def __init__(self, id, username):
                self.id = id
                self.username = username
                self.is_authenticated = True
            def is_active(self): return True
            def is_anonymous(self): return False
            def get_id(self): return str(self.id)
        return UserObj(row[0], row[1])
    return None

# ---------------- Auth Routes ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = db_read("SELECT id, username, password FROM users WHERE username=%s", (username,))
        if user and check_password_hash(user[0][2], password):
            login_user(load_user(user[0][0]))
            return redirect(url_for("index"))
        error = "Login fehlgeschlagen"
    return render_template("auth.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        try:
            db_write("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            return redirect(url_for("login"))
        except:
            error = "Benutzer existiert bereits"
    return render_template("auth.html", error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---------------- Main App ----------------
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        # Neues Material hinzufügen
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