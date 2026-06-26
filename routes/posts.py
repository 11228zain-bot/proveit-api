"""
Posts / Feed Routes
GET  /api/posts/feed     — فید اجتماعی
POST /api/posts          — پست جدید
POST /api/posts/:id/like  — لایک
POST /api/posts/:id/cheer — تشویق
"""

import uuid
from flask import Blueprint, request, jsonify
from models.db import get_db
from middleware.auth import require_auth

posts_bp = Blueprint("posts", __name__)


# ── Feed ────────────────────────────────────────────────────────────
@posts_bp.route("/feed", methods=["GET"])
@require_auth
def feed():
    db = get_db()
    limit = min(int(request.args.get("limit", 20)), 50)
    offset = int(request.args.get("offset", 0))

    posts = db.execute(
        """SELECT p.*,
                  u.display_name, u.avatar_emoji, u.level, u.username,
                  c.title as challenge_title, c.category as challenge_category,
                  (SELECT COUNT(*) FROM likes l WHERE l.post_id=p.id AND l.type='like') as likes_count,
                  (SELECT COUNT(*) FROM likes l WHERE l.post_id=p.id AND l.type='cheer') as cheers_count,
                  (SELECT 1 FROM likes l WHERE l.post_id=p.id AND l.user_id=? AND l.type='like') as i_liked,
                  (SELECT 1 FROM likes l WHERE l.post_id=p.id AND l.user_id=? AND l.type='cheer') as i_cheered
           FROM posts p
           JOIN users u ON p.user_id = u.id
           LEFT JOIN challenges c ON p.challenge_id = c.id
           ORDER BY p.created_at DESC
           LIMIT ? OFFSET ?""",
        (request.user_id, request.user_id, limit, offset)
    ).fetchall()

    return jsonify([dict(p) for p in posts])


# ── Create Post ─────────────────────────────────────────────────────
@posts_bp.route("/", methods=["POST", "OPTIONS"])
@posts_bp.route("", methods=["POST", "OPTIONS"])
@require_auth
def create_post():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json() or {}
    caption = data.get("caption", "").strip()

    if not caption and not data.get("media_url"):
        return jsonify({"error": "متن یا رسانه الزامی است"}), 400

    post_id = str(uuid.uuid4())
    db = get_db()

    db.execute(
        """INSERT INTO posts (id, user_id, challenge_id, caption, media_url, media_type)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            post_id,
            request.user_id,
            data.get("challenge_id"),
            caption,
            data.get("media_url", ""),
            data.get("media_type", "image")
        )
    )
    db.commit()

    return jsonify({
        "message": "پست ثبت شد! 📸",
        "post_id": post_id
    }), 201


# ── Like / Cheer ────────────────────────────────────────────────────
def toggle_reaction(post_id, user_id, reaction_type):
    db = get_db()

    post = db.execute("SELECT id FROM posts WHERE id=?", (post_id,)).fetchone()
    if not post:
        return jsonify({"error": "پست یافت نشد"}), 404

    existing = db.execute(
        "SELECT id FROM likes WHERE user_id=? AND post_id=? AND type=?",
        (user_id, post_id, reaction_type)
    ).fetchone()

    if existing:
        db.execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        action = "removed"
    else:
        db.execute(
            "INSERT INTO likes (id, user_id, post_id, type) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, post_id, reaction_type)
        )
        action = "added"

    db.commit()

    count = db.execute(
        "SELECT COUNT(*) as c FROM likes WHERE post_id=? AND type=?",
        (post_id, reaction_type)
    ).fetchone()["c"]

    return jsonify({"action": action, "count": count})


@posts_bp.route("/<post_id>/like", methods=["POST", "OPTIONS"])
@require_auth
def like_post(post_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    return toggle_reaction(post_id, request.user_id, "like")


@posts_bp.route("/<post_id>/cheer", methods=["POST", "OPTIONS"])
@require_auth
def cheer_post(post_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    return toggle_reaction(post_id, request.user_id, "cheer")


# ── Get Single Post ─────────────────────────────────────────────────
@posts_bp.route("/<post_id>", methods=["GET"])
@require_auth
def get_post(post_id):
    db = get_db()
    post = db.execute(
        """SELECT p.*, u.display_name, u.avatar_emoji, u.level, u.username,
                  c.title as challenge_title
           FROM posts p
           JOIN users u ON p.user_id = u.id
           LEFT JOIN challenges c ON p.challenge_id = c.id
           WHERE p.id=?""",
        (post_id,)
    ).fetchone()

    if not post:
        return jsonify({"error": "پست یافت نشد"}), 404

    return jsonify(dict(post))
