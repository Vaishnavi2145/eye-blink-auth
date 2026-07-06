# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session,send_from_directory,jsonify
import mysql.connector as mq
from mysql.connector import Error, IntegrityError
import os


import pickle
import cv2
import face_recognition
import base64
import numpy as np


import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase

app = Flask(__name__)
app.secret_key = "super-secret-key-change-me"


# Folder where user files will be stored
UPLOAD_BASE = os.path.join("static", "uploads")
os.makedirs(UPLOAD_BASE, exist_ok=True)

def sendemail(emailid):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login("your-email@gmail.com", "your-app-password-here")
        message = f"Subject: Someone tried to access application by your email"
        server.sendmail("your-email@gmail.com", emailid, message)
        server.quit()
    except Exception as e:
        print("Error sending email:", e)


# ---------- MySQL connection helper ----------
def dbconnection():
    # change host/user/password/database as needed
    con = mq.connect(host='127.0.0.1',
                     database='blinkcountauth',
                     user='root',
                     password='',
                     autocommit=False,
                     charset='utf8')
    return con

# ---------- Initialize DB (create table if not exists) ----------
'''def init_db():
    con = None
    try:
        con = dbconnection()
        cur = con.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(150) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            phone VARCHAR(30),
            gender VARCHAR(20),
            address TEXT,
            blink_count INT NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        con.commit()
    except Error as e:
        print("Error creating table:", e)
    finally:
        if con:
            con.close()

@app.before_first_request
def setup():
    init_db()'''

# ---------- Helper to fetch user by email ----------
def get_user_by_email(email):
    con = None
    try:
        con = dbconnection()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        return user
    except Error as e:
        print("DB error in get_user_by_email:", e)
        return None
    finally:
        if con:
            con.close()

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")



#***************--face authentictation-*************#

REF_NAME_PATH = "ref_name.pkl"
REF_EMBED_PATH = "ref_embed.pkl"

def load_pickle(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return {}

def save_pickle(obj, path):
    with open(path, "wb") as f:
        pickle.dump(obj, f)
def capture_face_samples():
    NUM_FACE_SAMPLES = 8
    face_samples = []
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None, "Cannot open camera."

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        rgb_small = np.ascontiguousarray(cv2.resize(frame, (0,0), fx=0.5, fy=0.5)[:, :, ::-1])
        faces = face_recognition.face_locations(rgb_small)
        display_frame = frame.copy()

        if len(faces) == 1:
            cv2.putText(display_frame, "press 'S' to capture 8 samples", (30,40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        elif len(faces) > 1:
            cv2.putText(display_frame, "❌ Multiple faces detected", (30,40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
        else:
            cv2.putText(display_frame, "No face detected", (30,40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

        cv2.imshow("Face Capture (Press S to save, Q to quit)", display_frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('s') and len(faces) == 1:
            full_rgb = np.ascontiguousarray(frame[:, :, ::-1])  
            full_locations = face_recognition.face_locations(full_rgb)
            encoding = face_recognition.face_encodings(full_rgb, full_locations)[0]
            face_samples.append(encoding)
            print(f"Captured {len(face_samples)}/{NUM_FACE_SAMPLES} samples")
        elif key == ord('q'):
            break
        if len(face_samples) >= NUM_FACE_SAMPLES:
            break

    cap.release()
    cv2.destroyAllWindows()
    if len(face_samples) < NUM_FACE_SAMPLES:
        return None, "Face capture failed."
    return face_samples, "Face capture completed."

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        gender = request.form.get("gender", "").strip()
        address = request.form.get("address", "").strip()
        blink_count = request.form.get("blink_count", "").strip()

        if not name or not email or not blink_count.isdigit():
            flash("Please complete the form and capture your blink count.", "error")
            return redirect(url_for("signup"))

        con = None
        face_samples, msg = capture_face_samples()
        try:
            if os.path.exists(REF_NAME_PATH):
                with open(REF_NAME_PATH, "rb") as f:
                    ref_name = pickle.load(f)
            else:
                ref_name = {}
        except:
            ref_name = {}
        ref_name[email] = name
        with open(REF_NAME_PATH, "wb") as f:
            pickle.dump(ref_name, f)

        try:
            if os.path.exists(REF_EMBED_PATH):
                with open(REF_EMBED_PATH, "rb") as f:
                    embed_dict = pickle.load(f)
            else:
                embed_dict = {}
        except:
            embed_dict = {}
        embed_dict[email] = face_samples
        with open(REF_EMBED_PATH, "wb") as f:
            pickle.dump(embed_dict, f)
        try:
            
            con = dbconnection()
            cur = con.cursor()
            cur.execute("""
                INSERT INTO users (name, email, phone, gender, address, blink_count)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, email, phone, gender, address, int(blink_count)))
            con.commit()
            flash("Signup successful! You can now login with your blink count.", "success")
            return redirect(url_for("login"))
        except IntegrityError as ie:
            # duplicate email
            con.rollback()
            flash("Email already exists. Try logging in.", "error")
            return redirect(url_for("login"))
        except Error as e:
            if con:
                con.rollback()
            print("DB error during signup:", e)
            flash("An error occurred while saving. Try again.", "error")
            return redirect(url_for("signup"))
        finally:
            if con:
                con.close()

    return render_template("signup.html")

def get_encoding_from_base64(image_data):
    header, encoded = image_data.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    np_img = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_img, cv2.IMREAD_COLOR)

    if img is None:
        return None

    rgb = np.ascontiguousarray(img[:, :, ::-1])   # <-- fixed
    locations = face_recognition.face_locations(rgb)

    if len(locations) != 1:
        return None

    return face_recognition.face_encodings(rgb, locations)[0]


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        blink_count = request.form.get("blink_count", "").strip()
        face_image = request.form.get("face_image")

        if not email or not blink_count.isdigit() or not face_image:
            flash("Incomplete login data.", "error")
            return redirect(url_for("login"))

        user = get_user_by_email(email)
        if not user:
            flash("Email not registered.", "error")
            return redirect(url_for("login"))

        # Load stored face embeddings
        with open(REF_EMBED_PATH, "rb") as f:
            embed_dict = pickle.load(f)

        if email not in embed_dict:
            flash("No face registered for this email.", "error")
            return redirect(url_for("login"))

        live_encoding = get_encoding_from_base64(face_image)
        if live_encoding is None:
            flash("Face not detected properly.", "error")
            return redirect(url_for("login"))

        known_encodings = embed_dict[email]
        matches = face_recognition.compare_faces(
            known_encodings, live_encoding, tolerance=0.45
        )

        # ❌ FACE MISMATCH
        if True not in matches:
            flash("Face does not match the entered email.", "error")
            sendemail(email)
            return redirect(url_for("login"))

        # ❌ BLINK MISMATCH
        if user and int(blink_count) != int(user["blink_count"]):
            sendemail(email)
            flash("Blink count does not match.", "error")
            return redirect(url_for("login"))

        # ✅ SUCCESS
        session["user_email"] = user["email"]
        session["user_name"] = user["name"]
        flash("Login successful! Face + Blink verified.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")



'''@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        blink_count = request.form.get("blink_count", "").strip()

        if not email or not blink_count.isdigit():
            flash("Please enter email and capture your blink count.", "error")
            return redirect(url_for("login"))

        user = get_user_by_email(email)
        if user and int(blink_count) == int(user["blink_count"]):
            session["user_email"] = user["email"]
            session["user_name"] = user["name"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials (email or blink count mismatch).", "error")
            return redirect(url_for("login"))

    return render_template("login.html")'''

@app.route("/dashboard")
def dashboard():
    if "user_email" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))
    return render_template("dashboard.html", name=session.get("user_name"))


@app.route("/upload", methods=["POST"])
def upload():
    if "user_email" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    user_email = session["user_email"]

    # Create folder per user ID (use email as folder name)
    user_folder = os.path.join(UPLOAD_BASE, user_email)
    os.makedirs(user_folder, exist_ok=True)

    if "file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("dashboard"))

    file = request.files["file"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("dashboard"))

    # Save file
    file_path = os.path.join(user_folder, file.filename)
    file.save(file_path)

    flash("File uploaded successfully!", "success")
    return redirect(url_for("dashboard"))

@app.route("/files")
def files():
    if "user_email" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    user_email = session["user_email"]
    user_folder = os.path.join(UPLOAD_BASE, user_email)
    os.makedirs(user_folder, exist_ok=True)

    file_list = os.listdir(user_folder)
    return render_template("files.html", files=file_list, email=user_email)


@app.route("/download/<email>/<filename>")
def download(email, filename):
    user_folder = os.path.join(UPLOAD_BASE, email)
    return send_from_directory(user_folder, filename, as_attachment=True)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
