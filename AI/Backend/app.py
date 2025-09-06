# =========================================================================================== #
# ========================== Libraries =================================================== #
# =========================================================================================== #

from flask import Flask, redirect, render_template, request, url_for, session, flash, jsonify
from datetime import datetime, timezone, timedelta
import sqlite3
from flask_mail import Mail, Message
import random
import uuid
from openai import OpenAI

# =========================================================================================== #
# ========================== End of Libraries ============================================== #
# =========================================================================================== #

# =========================================================================================== #
# ========================== Variables ==================================================== #
# =========================================================================================== #

app = Flask(
    __name__,
    template_folder='A:\\AI\\Fronted',
    static_folder='A:\\AI\\static',
)


client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "<Your API Key>"
)

app.permanent_session_lifetime = timedelta(days=30)
secret_key='<Your Secret Key>'
app.secret_key = secret_key

app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME='<Your E-mail Address>',
    MAIL_PASSWORD='<Your Google App Password>'
)

mail = Mail(app)

@app.after_request
def add_headers(response):
    response.headers["Permissions-Policy"] = "microphone=*"
    return response
# ----------- Allowed Email ----------- #
ALLOWED_DOMAINS = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com"]

def is_email_allowed(email):
    domain = email.split("@")[-1].lower()
    return domain in ALLOWED_DOMAINS

# ------------ Variables ------------- #
LOGIN_LOG_FILE = "user_login_log.txt"
REGISTER_LOG_FILE = "user_register_log.txt"
DATABASE = "users.db"
SYSTEM_PROMPT = "<Your System Prompt>"
SUMMARY_MAX_LENGTH = 32000

# ----------- Database connection function ----------- #
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# =========================================================================================== #
# ========================== End of Variables =============================================== #
# =========================================================================================== #

# =========================================================================================== #
# ========================== Code Verification System ======================================= #
# =========================================================================================== #

# ----------- Send Verification Code ------------- #
def send_verification_code(email):
    code = str(random.randint(100000, 999999))
    msg = Message(
        subject="Your Verification Code",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email],
        body=f"Your verification code: {code}\nYou must use this code within 5 minutes."
    )
    mail.send(msg)
    return code

# ----------- verify system ------------- #
@app.route("/verify_code", methods=["POST"])
def verify_code():
    user_code = request.form.get("code")
    real_code = session.get("email_code")
    user_data = session.get("pending_register")

    # Warn if code or user data is missing
    if not user_code or not real_code or not user_data:
        flash("Your session has expired or your code is missing. Please register again.", "error")
        return redirect(url_for("registerpage"))

    # Revert if code is incorrect
    if user_code != real_code:
        flash("The verification code entered is incorrect.", "error")
        return redirect(url_for("registerpage"))

    # Save to database
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (user_data["username"], user_data["email"], user_data["password"])
        )
        conn.commit()

        # Write to log file
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        ip = request.remote_addr
        terms = user_data.get("terms_accepted", False)

        with open("user_register_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{timestamp} | IP: {ip} | Username: {user_data['username']} | Email: {user_data['email']} | Terms of Use and Privacy Policy: {terms}\n")

        # Clear temporary data from Session
        session.pop("pending_register", None)
        session.pop("email_code", None)

        flash("Registration successful! You can log in.", "success")
        return redirect(url_for("loginpage"))

    except sqlite3.IntegrityError:
        flash("This email address is already registered.", "error")
        return redirect(url_for("registerpage"))
    finally:
        conn.close()

# =========================================================================================== #
# ========================== End of Code Verification System ================================ #
# =========================================================================================== #

# ----------- Terms ve Privacy ----------- #
@app.route("/terms")
def terms():
    return render_template("Terms.html")

@app.route("/privacy")
def privacy():
    return render_template("Privacy.html")

# ----------- User Registration ----------- #
@app.route("/register", methods=["GET", "POST"])
def registerpage():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        accepted = request.form.get("terms_accepted") == "on"

        error = False

        # Free space checks
        if not username:
            flash("Username cannot be blank.", "error")
            error = True

        if not email:
            flash("Email address cannot be blank.", "error")
            error = True

        if not password:
            flash("The password field cannot be empty.", "error")
            error = True

        if not accepted:
            flash("You must accept the Terms of Use and Privacy Policy to continue.", "error")
            error = True

        # Email extension control
        if email and not is_email_allowed(email):
            flash("Please use a valid and official email address. (gmail.com, outlook.com, hotmail.com, yahoo.com)", "error")
            error = True

        if error:
            return render_template("RegisterPage.html")

        # Send email verification code
        try:
            code = send_verification_code(email)

            # Store registration information and terms_accepted status in session
            session["pending_register"] = {
                "username": username,
                "email": email,
                "password": password,
                "terms_accepted": accepted
            }
            session["email_code"] = code

            flash("A verification code has been sent to your email address.", "success")
            return render_template("RegisterPage.html", show_code_modal=True)

        except Exception as e:
            flash(f"Email could not be sent: {str(e)}", "error")
            return render_template("RegisterPage.html")

    return render_template("RegisterPage.html")

# ----------- User Login ----------- #
@app.route("/login", methods=["GET", "POST"])
def loginpage():

    # ✅ If the user is already logged in, do not enter the login page
    if session.get("logged_in") and session.get("user_email"):
        return redirect(url_for("chat"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        accepted = request.form.get("terms_accepted")
        remember = request.form.get("remember")

        error = False

        # Free space checks
        if not email:
            flash("Email address cannot be left blank.", "warning")
            error = True
        if not password:
            flash("Password cannot be left blank.", "warning")
            error = True
        if not accepted:
            flash("You must accept the Terms of Use to continue.", "warning")
            error = True

        if error:
            return render_template("LoginPage.html")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and password:
            session.clear()
            session["logged_in"] = True
            session["user_email"] = user["email"]

            session.permanent = (remember == "on")
            print("Remember value:", remember, "| Session permanent:", session.permanent)

            # log record
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
            ip = request.remote_addr
            with open("user_login_log.txt", "a", encoding="utf-8") as f:
                f.write(f"{timestamp} | IP: {ip} | Login: {email} | Terms: {accepted} | Remember: {remember}\n")

            flash("Login successful.", "success")
            return redirect(url_for("chat"))
        else:
            flash("Email or password is incorrect.", "error")
            return render_template("LoginPage.html")

    return render_template("LoginPage.html")

# ----------- logout ----------- #
@app.route("/logout")
def logout():
    session.clear()
    flash("Successfully logged out.", "success")
    return redirect(url_for("loginpage"))

# ----------- Login Requirement Decorator ----------- #
def login_required(func):
    def wrapper(*args, **kwargs):
        if not session.get("logged_in") or not session.get("user_email"):
            session.clear()
            flash("The session is invalid. Please log in again.", "error")
            return redirect(url_for("loginpage"))

        # Is the user still in the database?
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (session["user_email"],))
        user = cursor.fetchone()
        conn.close()

        if not user:
            session.clear()
            flash("Your account has been deleted or you do not have access to it.", "error")
            return redirect(url_for("loginpage"))

        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# auxiliary function
def get_user_id(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user["id"] if user else None

# =========================================================================================== #
# ========================== AI ============================================================= #
# =========================================================================================== #

# Routes for chat management
@app.route("/api/start_chat", methods=["POST"])
@login_required
def start_chat():
    try:
        user_id = get_user_id(session["user_email"])
        chat_id = str(uuid.uuid4())
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create the chats table (if it doesn't exist)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                title TEXT DEFAULT 'Yeni Sohbet',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create the messages table (if it doesn't exist)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats (chat_id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Add new chat
        cursor.execute(
            "INSERT INTO chats (chat_id, user_id) VALUES (?, ?)",
            (chat_id, user_id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "chat_id": chat_id})
        
    except Exception as e:
        print(f"Error starting chat: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/save_message", methods=["POST"])
@login_required
def save_message():
    try:
        data = request.get_json()
        chat_id = data.get("chat_id")
        role = data.get("role")
        content = data.get("content")
        
        print(f"DEBUG: Saving message - chat_id={chat_id}, role={role}")
        print(f"DEBUG: Content: {content[:100]}...")
        
        if not all([chat_id, role, content]):
            print("DEBUG: Missing parameters")
            return jsonify({"success": False, "error": "Missing parameters"})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First make sure the chat exists (user_id check removed)
        cursor.execute(
            "SELECT id FROM chats WHERE chat_id = ?",
            (chat_id,)
        )
        chat = cursor.fetchone()
        
        if not chat:
            print("DEBUG: Chat not found")
            conn.close()
            return jsonify({"success": False, "error": "Chat not found"})
        
        # Save message (without user_id)
        cursor.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content)
        )
        
        # Update chat thread (if first message)
        if role == "user":
            cursor.execute(
                "SELECT title FROM chats WHERE chat_id = ? AND title = 'New Chat'",
                (chat_id,)
            )
            chat = cursor.fetchone()
            if chat:
                short_title = content[:30] + "..." if len(content) > 30 else content
                cursor.execute(
                    "UPDATE chats SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
                    (short_title, chat_id)
                )
        
        conn.commit()
        
        # Check if registration was successful
        cursor.execute(
            "SELECT COUNT(*) as count FROM messages WHERE chat_id = ?",
            (chat_id,)
        )
        message_count = cursor.fetchone()["count"]
        print(f"DEBUG: Total messages in chat now: {message_count}")
        
        conn.close()
        
        print("DEBUG: Message saved successfully")
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"ERROR saving message: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/get_chats", methods=["GET"])
@login_required
def get_chats():
    try:
        user_id = get_user_id(session["user_email"])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT chat_id, title, created_at FROM chats WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        )
        chats = cursor.fetchall()
        conn.close()
        
        chats_list = []
        for chat in chats:
            chats_list.append({
                "id": chat["chat_id"],
                "title": chat["title"],
                "created_at": chat["created_at"]
            })
        
        return jsonify({"success": True, "chats": chats_list})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/get_messages/<chat_id>", methods=["GET"])
@login_required
def get_messages(chat_id):
    try:
        user_id = get_user_id(session["user_email"])
        
        print(f"DEBUG: Loading messages for chat_id={chat_id}, user_id={user_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check that the chat belongs to this user
        cursor.execute(
            "SELECT id FROM chats WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )
        chat = cursor.fetchone()
        
        if not chat:
            print("DEBUG: Chat not found for user")
            conn.close()
            return jsonify({"success": False, "error": "Chat not found"})
        
        # Fetch messages
        cursor.execute(
            "SELECT role, content, timestamp FROM messages WHERE chat_id = ? ORDER BY timestamp ASC",
            (chat_id,)
        )
        messages = cursor.fetchall()
        
        print(f"DEBUG: Found {len(messages)} messages in database")
        
        conn.close()
        
        messages_list = []
        for message in messages:
            messages_list.append({
                "role": message["role"],
                "content": message["content"],
                "timestamp": message["timestamp"]
            })
        
        return jsonify({"success": True, "messages": messages_list})
        
    except Exception as e:
        print(f"ERROR loading messages: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})

def get_chat_summary(chat_id):
    """Retrieve current summary information from DB."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT summary FROM chat_summaries WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row["summary"] if row else ""

def update_chat_summary(chat_id, new_summary):
    """If there is no summary in the DB, create it; if there is, update it."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM chat_summaries WHERE chat_id = ?", (chat_id,))
    if cursor.fetchone():
        cursor.execute("UPDATE chat_summaries SET summary = ? WHERE chat_id = ?", (new_summary, chat_id))
    else:
        cursor.execute("INSERT INTO chat_summaries (chat_id, summary) VALUES (?, ?)", (chat_id, new_summary))
    conn.commit()
    conn.close()

def summarize_messages(messages):
    """Summarize messages (simple here: last 10 messages or token limit)."""
    combined = "\n".join([f"{m['role']}: {m['content']}" for m in messages[-1000:]])
    if len(combined) > SUMMARY_MAX_LENGTH:
        combined = combined[-SUMMARY_MAX_LENGTH:]
    return combined

@app.route("/api/ask_ai", methods=["POST"])
@login_required
def ask_ai():
    data = request.get_json()
    chat_id = data.get("chat_id")
    user_message = data.get("message")

    if not chat_id or not user_message:
        return jsonify({"success": False, "error": "missing data"}), 400

    try:
        # 1. Get current summary and latest messages
        summary = get_chat_summary(chat_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp ASC", (chat_id,))
        messages = cursor.fetchall()
        conn.close()

        # 2. Create a new summary
        updated_summary = summarize_messages(messages)
        update_chat_summary(chat_id, updated_summary)

        # 3. NVIDIA API request: system prompt + summary + user message
        prompt_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if updated_summary:
            prompt_messages.append({"role": "system", "content": f"Summary: {updated_summary}"})
        prompt_messages.append({"role": "user", "content": user_message})

        completion = client.chat.completions.create(
            model="deepseek-ai/deepseek-v3.1",
            messages=prompt_messages,
            temperature=0.01,
            top_p=0.01,
            max_tokens=16384,
            extra_body={"chat_template_kwargs": {"thinking":True}},
        )

        ai_response = getattr(completion.choices[0].message, "content", None)
        if ai_response is None:
            ai_response = "No response from AI."

        return jsonify({"success": True, "response": ai_response})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
# =========================================================================================== #
# ========================== AI End ========================================================= #
# =========================================================================================== #
    
# ----------- Pages ----------- #
@app.route("/")
@login_required
def chat():
    return render_template("chat.html")

# ----------- Server Start ----------- #
port = 443

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=port, ssl_context=("<Your local.crt path>", "<Your Local.key path>"))