"""
Messages Routes — چت با polling (هر چند ثانیه فرانت چک می‌کنه)
برای MVP این از WebSocket ساده‌تر و قابل‌اعتمادتره، بعداً قابل ارتقاست

GET  /api/messages/chats          — لیست گفتگوها
GET  /api/messages/with/:user_id  — تاریخچه با یک نفر
POST /api/messages/send           — ارسال پیام
"""

import uuid
from flask import Blueprint, request, jsonify
from models.db import get_db
from middleware.auth import require_auth

messages_bp = Blueprint("messages", __name__)


# ── List my chats (latest message per conversation) ─────────────────
@messages_bp.route("/chats", methods=["GET"])
@require_auth
def list_chats():
    db = get_db()
    rows = db.execute(
        """SELECT m.*,
                  CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END as other_id
           FROM messages m
           WHERE m.sender_id=? OR m.receiver_id=?
           ORDER BY m.created_at DESC""",
        (request.user_id, request.user_id, request.user_id)
    ).fetchall()

    # Keep only the latest message per other_id
    seen = set()
    chats = []
    for r in rows:
        r = dict(r)
        if r["other_id"] in seen:
            continue
        seen.add(r["other_id"])
        other = db.execute(
            "SELECT id, username, display_name, avatar_emoji, level FROM users WHERE id=?",
            (r["other_id"],)
        ).fetchone()
        if not other:
            continue
        unread = db.execute(
            "SELECT COUNT(*) as c FROM messages WHERE sender_id=? AND receiver_id=? AND is_read=0",
            (r["other_id"], request.user_id)
        ).fetchone()["c"]
        chats.append({
            "user": dict(other),
            "last_message": r["content"],
            "last_time": r["created_at"],
            "unread": unread
        })

    return jsonify(chats)


# ── Conversation history with one user ───────────────────────────────
@messages_bp.route("/with/<other_id>", methods=["GET"])
@require_auth
def conversation(other_id):
    db = get_db()
    rows = db.execute(
        """SELECT * FROM messages
           WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)
           ORDER BY created_at ASC LIMIT 100""",
        (request.user_id, other_id, other_id, request.user_id)
    ).fetchall()

    # Mark messages from other_id as read
    db.execute(
        "UPDATE messages SET is_read=1 WHERE sender_id=? AND receiver_id=? AND is_read=0",
        (other_id, request.user_id)
    )
    db.commit()

    return jsonify([dict(r) for r in rows])


# ── Send a message ────────────────────────────────────────────────────
@messages_bp.route("/send", methods=["POST", "OPTIONS"])
@require_auth
def send_message():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json() or {}
    receiver_id = data.get("receiver_id")
    content = data.get("content", "").strip()
    challenge_id = data.get("challenge_id")  # optional — for challenge invites

    if not receiver_id or not content:
        return jsonify({"error": "گیرنده و متن پیام الزامی است"}), 400
    if receiver_id == request.user_id:
        return jsonify({"error": "نمی‌توانی به خودت پیام بدهی"}), 400

    db = get_db()
    receiver = db.execute("SELECT id FROM users WHERE id=?", (receiver_id,)).fetchone()
    if not receiver:
        return jsonify({"error": "کاربر یافت نشد"}), 404

    msg_id = str(uuid.uuid4())
    msg_type = "challenge_invite" if challenge_id else "text"
    db.execute(
        """INSERT INTO messages (id, sender_id, receiver_id, content, type, challenge_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (msg_id, request.user_id, receiver_id, content, msg_type, challenge_id)
    )
    db.commit()

    return jsonify({"message": "ارسال شد ✅", "message_id": msg_id}), 201
