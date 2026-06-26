"""
Auth Routes
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
"""

import uuid
import hashlib
import datetime
import jwt

from flask import Blueprint, request, jsonify, current_app
from models.db import get_db
from middleware.auth import require_auth

auth_bp = Blueprint("auth", __name__)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def make_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


# ── Register ────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST", "OPTIONS"])
def register():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json()
    if not data:
        return jsonify({"error": "داده‌ای ارسال نشده"}), 400

    username = data.get("username", "").strip().lower()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    display_name = data.get("display_name", username)

    # Validate
    if not username or len(username) < 3:
        return jsonify({"error": "نام کاربری باید حداقل ۳ کاراکتر باشد"}), 400
    if not email or "@" not in email:
        return jsonify({"error": "ایمیل نامعتبر است"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "رمز عبور باید حداقل ۶ کاراکتر باشد"}), 400

    db = get_db()
    # Check duplicate
    existing = db.execute(
        "SELECT id FROM users WHERE username=? OR email=?", (username, email)
    ).fetchone()
    if existing:
        return jsonify({"error": "این نام کاربری یا ایمیل قبلاً ثبت شده"}), 409

    user_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO users (id, username, email, password, display_name)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, username, email, hash_password(password), display_name)
    )
    db.commit()

    token = make_token(user_id)
    return jsonify({
        "message": "ثبت‌نام موفق! 🎉",
        "token": token,
        "user": {
            "id": user_id,
            "username": username,
            "display_name": display_name,
            "level": 1,
            "xp": 0
        }
    }), 201


# ── Login ───────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST", "OPTIONS"])
def login():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json()
    if not data:
        return jsonify({"error": "داده‌ای ارسال نشده"}), 400

    identifier = data.get("identifier", "").strip().lower()  # username or email
    password   = data.get("password", "")

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username=? OR email=?", (identifier, identifier)
    ).fetchone()

    if not user or user["password"] != hash_password(password):
        return jsonify({"error": "نام کاربری یا رمز عبور اشتباه است"}), 401

    token = make_token(user["id"])
    return jsonify({
        "message": "خوش اومدی! 🔥",
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "avatar_emoji": user["avatar_emoji"],
            "level": user["level"],
            "xp": user["xp"],
            "streak": user["streak"]
        }
    })


# ── Me ──────────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (request.user_id,)).fetchone()
    if not user:
        return jsonify({"error": "کاربر یافت نشد"}), 404

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "avatar_emoji": user["avatar_emoji"],
        "bio": user["bio"],
        "level": user["level"],
        "xp": user["xp"],
        "streak": user["streak"],
        "interests": user["interests"],
        "created_at": user["created_at"]
    })
