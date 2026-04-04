import os
from dotenv import load_dotenv
load_dotenv()
import cloudinary
import cloudinary.uploader
from flask import Flask, render_template, request, redirect, jsonify, session
from groq import Groq
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase

# Firebase Admin (for database)
import json
if os.getenv("FIREBASE_CREDENTIALS"):
    # On Render — use environment variable
    firebase_creds = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
    cred = credentials.Certificate(firebase_creds)
else:
    # Local — use firebase_key.json file
    cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Cloudinary config
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# Pyrebase (for authentication)
firebase_config = {
    "apiKey": os.getenv("FIREBASE_API_KEY", "AIzaSyATBDDqqiFIbTvG-FDyj9ddasearGFTuyY"),
    "authDomain": "project-setu-46c4e.firebaseapp.com",
    "projectId": "project-setu-46c4e",
    "storageBucket": "project-setu-46c4e.firebasestorage.app",
    "messagingSenderId": "130749773235",
    "appId": "1:130749773235:web:dec27730af29eefaedc7c6",
    "databaseURL": ""
}

firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "projectsetu2026")

# ─── ROUTES ───────────────────────────────────────
@app.route("/")
def home():
    return render_template("home.html", session=session)

@app.route("/about")
def about():
    return "This is Zyra - Built by Anand"

# ─── AUTH ─────────────────────────────────────────
@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        branch = request.form["branch"]
        semester = request.form["semester"]
        skills = request.form["skills"]

        try:
            user = auth.create_user_with_email_and_password(email, password)
            uid = user["localId"]
            db.collection("students").document(uid).set({
                "uid": uid,
                "name": name,
                "email": email,
                "branch": branch,
                "semester": semester,
                "skills": skills
            })
            session["uid"] = uid
            session["name"] = name
            session["email"] = email
            return redirect("/profile")
        except Exception as e:
            error = "Email already exists or invalid. Try again."

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        try:
            user = auth.sign_in_with_email_and_password(email, password)
            uid = user["localId"]
            student = db.collection("students").document(uid).get()
            if student.exists:
                data = student.to_dict()
                session["uid"] = uid
                session["name"] = data["name"]
                session["email"] = data["email"]
                return redirect("/profile")
            else:
                error = "Profile not found. Please sign up first."
        except Exception as e:
            error = "Invalid email or password. Try again."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/profile")
def profile():
    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]
    student = db.collection("students").document(uid).get()

    if student.exists:
        data = student.to_dict()
        all_posts = db.collection("posts").stream()
        my_posts = []
        for p in all_posts:
            post_data = p.to_dict()
            if post_data.get("author") == data["name"]:
                post_data["id"] = p.id
                my_posts.append(post_data)
        return render_template("profile.html", student=data, my_posts=my_posts)

    return redirect("/login")


@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]

    if request.method == "POST":
        db.collection("students").document(uid).update({
            "branch": request.form["branch"],
            "semester": request.form["semester"],
            "skills": request.form["skills"]
        })
        return redirect("/profile")

    student = db.collection("students").document(uid).get().to_dict()
    return render_template("edit_profile.html", student=student)


@app.route("/register")
def register():
    return redirect("/signup")


# ─── POST ─────────────────────────────────────────
@app.route("/post", methods=["GET", "POST"])
def post():
    if "uid" not in session:
        return redirect("/login")

    if request.method == "POST":
        image_url = None

        if "image" in request.files:
            image = request.files["image"]
            if image.filename != "":
                upload_result = cloudinary.uploader.upload(image)
                image_url = upload_result["secure_url"]

        new_post = {
            "author": session["name"],
            "author_uid": session["uid"],
            "category": request.form["category"],
            "title": request.form["title"],
            "description": request.form["description"],
            "image_url": image_url,
            "likes": 0,
            "comments": [],
            "time": datetime.now().strftime("%d %b %Y, %I:%M %p")
        }

        db.collection("posts").add(new_post)
        return redirect("/feed")

    return render_template("post.html")


# ─── FEED ─────────────────────────────────────────
@app.route("/feed")
def feed():
    posts_ref = db.collection("posts").stream()
    posts = []
    for p in posts_ref:
        post_data = p.to_dict()
        post_data["id"] = p.id
        post_data["likes"] = post_data.get("likes", 0)
        post_data["comments"] = post_data.get("comments", [])
        posts.append(post_data)

    # Sort by time — newest first
    posts.reverse()

    students_ref = db.collection("students").stream()
    students = []
    for student in students_ref:
        students.append(student.to_dict())

    return render_template("feed.html", posts=posts, students=students, session=session)


# ─── LIKE ─────────────────────────────────────────
@app.route("/like/<post_id>", methods=["POST"])
def like_post(post_id):
    post_ref = db.collection("posts").document(post_id)
    post = post_ref.get()
    if post.exists:
        current_likes = post.to_dict().get("likes", 0)
        post_ref.update({"likes": current_likes + 1})
    return redirect("/feed")


# ─── COMMENT ──────────────────────────────────────
@app.route("/comment/<post_id>", methods=["POST"])
def comment_post(post_id):
    author = request.form.get("author", "Anonymous")
    comment = {
        "author": author,
        "text": request.form["comment"]
    }
    post_ref = db.collection("posts").document(post_id)
    post = post_ref.get()
    if post.exists:
        current_comments = post.to_dict().get("comments", [])
        current_comments.append(comment)
        post_ref.update({"comments": current_comments})
    return redirect("/feed")


# ─── DELETE POST ──────────────────────────────────
@app.route("/delete-post/<post_id>", methods=["POST"])
def delete_post(post_id):
    if "uid" not in session:
        return redirect("/login")

    post_ref = db.collection("posts").document(post_id)
    post = post_ref.get()

    if post.exists:
        post_data = post.to_dict()
        if post_data.get("author") == session["name"]:
            post_ref.delete()

    return redirect("/feed")


# ─── N8N API ──────────────────────────────────────
@app.route("/api/add-post", methods=["POST"])
def api_add_post():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    post = {
        "author": data["author"],
        "category": data["category"],
        "title": data["title"],
        "description": data["description"],
        "likes": 0,
        "comments": []
    }
    db.collection("posts").add(post)
    return jsonify({"status": "success"})


# ─── AI MATCH ─────────────────────────────────────
@app.route("/match", methods=["GET", "POST"])
def match():
    result = None
    query = None
    students = []

    if request.method == "POST":
        query = request.form["query"]

        students_ref = db.collection("students").stream()
        for s in students_ref:
            students.append(s.to_dict())

        student_list = ""
        for s in students:
            student_list += f"- {s['name']} | Branch: {s['branch']} | Skills: {s['skills']}\n"

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that matches students based on skills. Be friendly and specific."
                },
                {
                    "role": "user",
                    "content": f"I need help finding a teammate. My requirement: {query}\n\nHere are the registered students:\n{student_list}\n\nWho is the best match and why? Give a short friendly answer."
                }
            ]
        )

        result = response.choices[0].message.content

    else:
        students_ref = db.collection("students").stream()
        for s in students_ref:
            students.append(s.to_dict())

    return render_template("match.html", result=result, query=query, students=students, session=session)


# ─── ANNOUNCEMENTS ────────────────────────────────
@app.route("/announcements")
def announcements():
    ann_ref = db.collection("announcements").stream()
    announcements_list = []
    for a in ann_ref:
        data = a.to_dict()
        data["id"] = a.id
        announcements_list.append(data)
    announcements_list.reverse()
    return render_template("announcements.html", announcements=announcements_list, session=session)


# ─── ADMIN ────────────────────────────────────────
@app.route("/admin/announce", methods=["GET", "POST"])
def admin_announce():
    if request.method == "POST":
        if request.form.get("admin_key") == os.getenv("ADMIN_KEY", "projectsetu2026"):
            announcement = {
                "title": request.form["title"],
                "description": request.form["description"],
                "category": request.form["category"],
                "date": datetime.now().strftime("%d %b %Y, %I:%M %p"),
                "posted_by": "Admin"
            }
            db.collection("announcements").add(announcement)
            return redirect("/announcements")
        else:
            return render_template("admin_announce.html", error="Wrong admin key!")
    return render_template("admin_announce.html", error=None)


# ─── ASKZYRA ──────────────────────────────────────
@app.route("/askzyra", methods=["GET", "POST"])
def askzyra():
    response_text = None
    user_question = None

    if request.method == "POST":
        user_question = request.form["question"]

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """You are AskZyra, a helpful AI assistant for college students in Bihar, India.
You help students with college queries, career guidance, government jobs, competitive exams,
startup ideas, and technical skills. Be friendly, encouraging and practical.
Always give actionable advice. If asked in Hindi, reply in Hindi."""
                },
                {
                    "role": "user",
                    "content": user_question
                }
            ]
        )

        response_text = response.choices[0].message.content

    return render_template("askzyra.html", response=response_text, question=user_question, session=session)


# ─── MY POSTS ─────────────────────────────────────
@app.route("/myposts")
def myposts():
    if "uid" not in session:
        return redirect("/login")

    all_posts = db.collection("posts").stream()
    my_posts = []
    total_likes = 0
    total_comments = 0

    for p in all_posts:
        post_data = p.to_dict()
        if post_data.get("author") == session["name"]:
            post_data["id"] = p.id
            post_data["likes"] = post_data.get("likes", 0)
            post_data["comments"] = post_data.get("comments", [])
            total_likes += post_data["likes"]
            total_comments += len(post_data["comments"])
            my_posts.append(post_data)

    return render_template(
        "myposts.html",
        my_posts=my_posts,
        student_name=session["name"],
        total_likes=total_likes,
        total_comments=total_comments,
        session=session
    )
# ─── MESSAGES ─────────────────────────────────────
@app.route("/messages")
def messages():
    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]

    # Get all conversations involving this user
    sent = db.collection("messages").where("sender_uid", "==", uid).stream()
    received = db.collection("messages").where("receiver_uid", "==", uid).stream()

    conversations = {}

    for msg in sent:
        data = msg.to_dict()
        other_uid = data["receiver_uid"]
        other_name = data["receiver_name"]
        if other_uid not in conversations:
            conversations[other_uid] = {
                "name": other_name,
                "uid": other_uid,
                "last_message": data["text"],
                "time": data["time"]
            }

    for msg in received:
        data = msg.to_dict()
        other_uid = data["sender_uid"]
        other_name = data["sender_name"]
        if other_uid not in conversations:
            conversations[other_uid] = {
                "name": other_name,
                "uid": other_uid,
                "last_message": data["text"],
                "time": data["time"]
            }

    return render_template("messages.html",
        conversations=list(conversations.values()),
        session=session
    )


@app.route("/chat/<receiver_uid>", methods=["GET", "POST"])
def chat(receiver_uid):
    if "uid" not in session:
        return redirect("/login")

    uid = session["uid"]

    # Get receiver info
    receiver = db.collection("students").document(receiver_uid).get()
    if not receiver.exists:
        return redirect("/messages")

    receiver_data = receiver.to_dict()

    if request.method == "POST":
        text = request.form["text"]
        if text.strip():
            db.collection("messages").add({
                "sender_uid": uid,
                "sender_name": session["name"],
                "receiver_uid": receiver_uid,
                "receiver_name": receiver_data["name"],
                "text": text,
                "time": datetime.now().strftime("%d %b %Y, %I:%M %p")
            })
        return redirect(f"/chat/{receiver_uid}")

    # Get all messages between these two users
    sent = db.collection("messages")\
        .where("sender_uid", "==", uid)\
        .where("receiver_uid", "==", receiver_uid)\
        .stream()

    received = db.collection("messages")\
        .where("sender_uid", "==", receiver_uid)\
        .where("receiver_uid", "==", uid)\
        .stream()

    chat_messages = []
    for msg in sent:
        data = msg.to_dict()
        data["is_me"] = True
        chat_messages.append(data)

    for msg in received:
        data = msg.to_dict()
        data["is_me"] = False
        chat_messages.append(data)

    # Sort by time
    chat_messages.sort(key=lambda x: x["time"])

    return render_template("chat.html",
        receiver=receiver_data,
        messages=chat_messages,
        session=session
    )


@app.route("/send-message/<receiver_uid>")
def send_message_page(receiver_uid):
    if "uid" not in session:
        return redirect("/login")
    return redirect(f"/chat/{receiver_uid}")




# ─── STUDENT PROFILE ──────────────────────────────
@app.route("/student/<student_uid>")
def student_profile(student_uid):
    if "uid" not in session:
        return redirect("/login")

    student = db.collection("students").document(student_uid).get()
    if not student.exists:
        return redirect("/feed")

    data = student.to_dict()
    all_posts = db.collection("posts").stream()
    their_posts = []
    for p in all_posts:
        post_data = p.to_dict()
        if post_data.get("author") == data["name"]:
            post_data["id"] = p.id
            their_posts.append(post_data)

    return render_template("student_profile.html",
        student=data,
        my_posts=their_posts,
        session=session
    )
if __name__ == "__main__":
    app.run(debug=True)
