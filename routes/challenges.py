"""
Challenges Routes
GET   /api/challenges         — لیست و فید چالش‌ها
POST  /api/challenges         — ساخت چالش جدید (توسط کاربر)
GET   /api/challenges/:id     — جزئیات چالش
POST  /api/challenges/:id/join      — پیوستن
POST  /api/challenges/:id/complete  — اتمام + XP
GET   /api/challenges/trending      — ترندها
GET   /api/challenges/mine          — چالش‌های من
"""

import uuid
import json
from flask import Blueprint, request, jsonify
from models.db import get_db
from middleware.auth import require_auth

challenges_bp = Blueprint("challenges", __name__)

XP_PER_LEVEL = 1000  # هر 1000 XP = یک لِوِل


def check_level_up(db, user_id):
    """بررسی و آپدیت لِوِل کاربر"""
    user = db.execute("SELECT xp, level FROM users WHERE id=?", (user_id,)).fetchone()
    new_level = (user["xp"] // XP_PER_LEVEL) + 1
    if new_level != user["level"]:
        db.execute("UPDATE users SET level=? WHERE id=?", (new_level, user_id))
        return True, new_level
    return False, user["level"]


# ── List Challenges ─────────────────────────────────────────────────
@challenges_bp.route("/", methods=["GET"])
@challenges_bp.route("", methods=["GET"])
@require_auth
def list_challenges():
    db = get_db()
    category = request.args.get("category", "")
    search = request.args.get("q", "")
    limit = min(int(request.args.get("limit", 20)), 50)

    query = """
        SELECT c.*, u.display_name as creator_name, u.avatar_emoji as creator_avatar,
               (SELECT COUNT(*) FROM user_challenges uc
                WHERE uc.challenge_id=c.id AND uc.user_id=?) as joined
        FROM challenges c
        JOIN users u ON c.creator_id = u.id
        WHERE c.is_public = 1
    """
    params = [request.user_id]

    if category:
        query += " AND c.category=?"
        params.append(category)
    if search:
        query += " AND (c.title LIKE ? OR c.description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY c.participants_count DESC, c.created_at DESC LIMIT ?"
    params.append(limit)

    challenges = db.execute(query, params).fetchall()
    return jsonify([dict(c) for c in challenges])


# ── Trending ────────────────────────────────────────────────────────
@challenges_bp.route("/trending", methods=["GET"])
@require_auth
def trending():
    db = get_db()
    challenges = db.execute(
        """SELECT c.*, u.display_name as creator_name, u.avatar_emoji as creator_avatar
           FROM challenges c
           JOIN users u ON c.creator_id = u.id
           WHERE c.is_public = 1
           ORDER BY c.participants_count DESC, c.created_at DESC
           LIMIT 10"""
    ).fetchall()
    return jsonify([dict(c) for c in challenges])


# ── My Challenges ───────────────────────────────────────────────────
@challenges_bp.route("/mine", methods=["GET"])
@require_auth
def my_challenges():
    db = get_db()
    challenges = db.execute(
        """SELECT c.*, uc.status, uc.started_at, uc.completed_at, uc.xp_earned
           FROM user_challenges uc
           JOIN challenges c ON uc.challenge_id = c.id
           WHERE uc.user_id=?
           ORDER BY uc.started_at DESC""",
        (request.user_id,)
    ).fetchall()
    return jsonify([dict(c) for c in challenges])


# ── Create Challenge ────────────────────────────────────────────────
@challenges_bp.route("/", methods=["POST", "OPTIONS"])
@challenges_bp.route("", methods=["POST", "OPTIONS"])
@require_auth
def create_challenge():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json() or {}

    title = data.get("title", "").strip()
    if not title or len(title) < 5:
        return jsonify({"error": "عنوان چالش باید حداقل ۵ کاراکتر باشد"}), 400

    challenge_id = str(uuid.uuid4())
    db = get_db()

    db.execute(
        """INSERT INTO challenges
           (id, creator_id, title, description, category, tags, proof_type, duration_hours, xp_reward, is_public)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            challenge_id,
            request.user_id,
            title,
            data.get("description", ""),
            data.get("category", "عمومی"),
            json.dumps(data.get("tags", []), ensure_ascii=False),
            data.get("proof_type", "photo"),
            int(data.get("duration_hours", 24)),
            int(data.get("xp_reward", 100)),
            1 if data.get("is_public", True) else 0
        )
    )
    db.commit()

    return jsonify({
        "message": "چالش ساخته شد! 🔥",
        "challenge_id": challenge_id
    }), 201


# ── Get Challenge Detail ────────────────────────────────────────────
@challenges_bp.route("/<challenge_id>", methods=["GET"])
@require_auth
def get_challenge(challenge_id):
    db = get_db()
    challenge = db.execute(
        """SELECT c.*, u.display_name as creator_name, u.avatar_emoji as creator_avatar,
                  (SELECT COUNT(*) FROM user_challenges uc
                   WHERE uc.challenge_id=c.id AND uc.user_id=?) as joined
           FROM challenges c
           JOIN users u ON c.creator_id = u.id
           WHERE c.id=?""",
        (request.user_id, challenge_id)
    ).fetchone()

    if not challenge:
        return jsonify({"error": "چالش یافت نشد"}), 404

    # Recent participants
    participants = db.execute(
        """SELECT u.id, u.display_name, u.avatar_emoji, u.level, uc.status
           FROM user_challenges uc
           JOIN users u ON uc.user_id = u.id
           WHERE uc.challenge_id=?
           ORDER BY uc.started_at DESC LIMIT 10""",
        (challenge_id,)
    ).fetchall()

    result = dict(challenge)
    result["participants"] = [dict(p) for p in participants]
    return jsonify(result)


# ── Join Challenge ──────────────────────────────────────────────────
@challenges_bp.route("/<challenge_id>/join", methods=["POST", "OPTIONS"])
@require_auth
def join_challenge(challenge_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200

    db = get_db()

    # Check challenge exists
    challenge = db.execute("SELECT * FROM challenges WHERE id=?", (challenge_id,)).fetchone()
    if not challenge:
        return jsonify({"error": "چالش یافت نشد"}), 404

    # Check already joined
    existing = db.execute(
        "SELECT id FROM user_challenges WHERE user_id=? AND challenge_id=?",
        (request.user_id, challenge_id)
    ).fetchone()
    if existing:
        return jsonify({"error": "قبلاً به این چالش پیوسته‌ای"}), 409

    uc_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO user_challenges (id, user_id, challenge_id) VALUES (?, ?, ?)",
        (uc_id, request.user_id, challenge_id)
    )
    db.execute(
        "UPDATE challenges SET participants_count = participants_count + 1 WHERE id=?",
        (challenge_id,)
    )
    db.commit()

    return jsonify({
        "message": "به چالش پیوستی! 🎯",
        "user_challenge_id": uc_id
    }), 201


# ── Complete Challenge ──────────────────────────────────────────────
@challenges_bp.route("/<challenge_id>/complete", methods=["POST", "OPTIONS"])
@require_auth
def complete_challenge(challenge_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200

    db = get_db()

    uc = db.execute(
        """SELECT uc.*, c.xp_reward FROM user_challenges uc
           JOIN challenges c ON uc.challenge_id = c.id
           WHERE uc.user_id=? AND uc.challenge_id=?""",
        (request.user_id, challenge_id)
    ).fetchone()

    if not uc:
        return jsonify({"error": "اول باید به چالش بپیوندی"}), 400
    if uc["status"] == "done":
        return jsonify({"error": "این چالش رو قبلاً انجام دادی"}), 409

    xp = uc["xp_reward"]
    proof_url = request.get_json(silent=True) or {}
    proof_url = proof_url.get("proof_url", "")

    db.execute(
        """UPDATE user_challenges
           SET status='done', xp_earned=?, proof_url=?,
               completed_at=datetime('now')
           WHERE user_id=? AND challenge_id=?""",
        (xp, proof_url, request.user_id, challenge_id)
    )
    db.execute(
        "UPDATE users SET xp = xp + ?, streak = streak + 1 WHERE id=?",
        (xp, request.user_id)
    )
    db.commit()

    leveled_up, new_level = check_level_up(db, request.user_id)
    db.commit()

    return jsonify({
        "message": "چالش تکمیل شد! 🏆",
        "xp_earned": xp,
        "leveled_up": leveled_up,
        "new_level": new_level if leveled_up else None
    })
