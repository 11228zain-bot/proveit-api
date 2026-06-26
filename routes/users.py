"""
Users Routes
GET   /api/users/:id         — پروفایل کاربر
PATCH /api/users/me          — ویرایش پروفایل
GET   /api/users/search      — جستجو
POST  /api/users/:id/friend  — درخواست دوستی
GET   /api/users/me/friends  — لیست دوستان
"""

import uuid
from flask import Blueprint, request, jsonify
from models.db import get_db
from middleware.auth import require_auth

users_bp = Blueprint("users", __name__)


# ── Get Profile ─────────────────────────────────────────────────────
@users_bp.route("/<user_id>", methods=["GET"])
@require_auth
def get_profile(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        return jsonify({"error": "کاربر یافت نشد"}), 404

    # Count stats
    challenge_count = db.execute(
        "SELECT COUNT(*) as c FROM user_challenges WHERE user_id=? AND status='done'",
        (user_id,)
    ).fetchone()["c"]

    friend_count = db.execute(
        "SELECT COUNT(*) as c FROM friendships WHERE (user_id=? OR friend_id=?) AND status='accepted'",
        (user_id, user_id)
    ).fetchone()["c"]

    # Friendship status with requester
    friendship = db.execute(
        """SELECT status FROM friendships
           WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)""",
        (request.user_id, user_id, user_id, request.user_id)
    ).fetchone()

    # Recent posts of this user
    posts = db.execute(
        """SELECT p.*, c.title as challenge_title
           FROM posts p
           LEFT JOIN challenges c ON p.challenge_id = c.id
           WHERE p.user_id=?
           ORDER BY p.created_at DESC LIMIT 12""",
        (user_id,)
    ).fetchall()

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "avatar_emoji": user["avatar_emoji"],
        "bio": user["bio"],
        "level": user["level"],
        "xp": user["xp"],
        "streak": user["streak"],
        "challenges_done": challenge_count,
        "friends_count": friend_count,
        "friendship_status": friendship["status"] if friendship else None,
        "posts": [dict(p) for p in posts]
    })


# ── Update Profile ──────────────────────────────────────────────────
@users_bp.route("/me", methods=["PATCH", "OPTIONS"])
@require_auth
def update_profile():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json() or {}
    allowed = ["display_name", "bio", "avatar_emoji", "interests"]
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        return jsonify({"error": "هیچ فیلدی برای آپدیت وجود ندارد"}), 400

    db = get_db()
    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [request.user_id]
    db.execute(f"UPDATE users SET {set_clause} WHERE id=?", values)
    db.commit()

    return jsonify({"message": "پروفایل آپدیت شد ✅"})


# ── Search Users ────────────────────────────────────────────────────
@users_bp.route("/search", methods=["GET"])
@require_auth
def search_users():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"error": "حداقل ۲ کاراکتر وارد کن"}), 400

    db = get_db()
    users = db.execute(
        """SELECT id, username, display_name, avatar_emoji, level
           FROM users
           WHERE (username LIKE ? OR display_name LIKE ?) AND id != ?
           LIMIT 20""",
        (f"%{q}%", f"%{q}%", request.user_id)
    ).fetchall()

    return jsonify([dict(u) for u in users])


# ── Send Friend Request ─────────────────────────────────────────────
@users_bp.route("/<friend_id>/friend", methods=["POST", "OPTIONS"])
@require_auth
def send_friend_request(friend_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200

    if friend_id == request.user_id:
        return jsonify({"error": "نمی‌توانی با خودت دوست شوی!"}), 400

    db = get_db()

    # Check if already exists
    existing = db.execute(
        """SELECT id, status FROM friendships
           WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)""",
        (request.user_id, friend_id, friend_id, request.user_id)
    ).fetchone()

    if existing:
        if existing["status"] == "accepted":
            return jsonify({"message": "شما قبلاً دوست هستید"}), 200
        # Auto-accept if other side already requested
        db.execute("UPDATE friendships SET status='accepted' WHERE id=?", (existing["id"],))
        db.commit()
        return jsonify({"message": "درخواست دوستی قبول شد! 🎉"})

    req_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO friendships (id, user_id, friend_id) VALUES (?, ?, ?)",
        (req_id, request.user_id, friend_id)
    )
    db.commit()
    return jsonify({"message": "درخواست دوستی ارسال شد ✅"}), 201


# ── My Friends ──────────────────────────────────────────────────────
@users_bp.route("/me/friends", methods=["GET"])
@require_auth
def my_friends():
    db = get_db()
    friends = db.execute(
        """SELECT u.id, u.username, u.display_name, u.avatar_emoji, u.level, u.xp
           FROM friendships f
           JOIN users u ON (
               CASE WHEN f.user_id=? THEN f.friend_id ELSE f.user_id END = u.id
           )
           WHERE (f.user_id=? OR f.friend_id=?) AND f.status='accepted'""",
        (request.user_id, request.user_id, request.user_id)
    ).fetchall()

    return jsonify([dict(f) for f in friends])


# ── Discover (suggested people) ──────────────────────────────────────
@users_bp.route("/discover", methods=["GET"])
@require_auth
def discover():
    """کسایی که هنوز باهاشون دوست نیستیم، با بیشترین فعالیت اول"""
    db = get_db()
    users = db.execute(
        """SELECT u.id, u.username, u.display_name, u.avatar_emoji, u.level, u.xp,
                  (SELECT COUNT(*) FROM user_challenges uc WHERE uc.user_id=u.id AND uc.status='done') as challenges_done
           FROM users u
           WHERE u.id != ?
             AND u.id NOT IN (
                 SELECT CASE WHEN user_id=? THEN friend_id ELSE user_id END
                 FROM friendships
                 WHERE user_id=? OR friend_id=?
             )
           ORDER BY u.xp DESC
           LIMIT 20""",
        (request.user_id, request.u
