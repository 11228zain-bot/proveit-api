"""
Upload Routes — MVP version
عکس‌ها به‌صورت base64 داخل دیتابیس ذخیره می‌شن (بدون نیاز به S3/R2)
برای مقیاس بزرگ‌تر باید به Cloudflare R2 یا S3 منتقل شه — فعلاً برای تعداد کم کاربر کافیه
"""

import uuid
import base64
from flask import Blueprint, request, jsonify
from models.db import get_db
from middleware.auth import require_auth

uploads_bp = Blueprint("uploads", __name__)

MAX_SIZE_MB = 4
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@uploads_bp.route("/image", methods=["POST", "OPTIONS"])
@require_auth
def upload_image():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json() or {}
    image_data = data.get("image_data", "")  # data:image/jpeg;base64,xxxxx

    if not image_data or not image_data.startswith("data:"):
        return jsonify({"error": "فرمت عکس نامعتبر است"}), 400

    try:
        header, encoded = image_data.split(",", 1)
        mime = header.split(":")[1].split(";")[0]
    except Exception:
        return jsonify({"error": "فرمت عکس نامعتبر است"}), 400

    if mime not in ALLOWED_TYPES:
        return jsonify({"error": "فقط jpeg، png، webp و gif پشتیبانی می‌شود"}), 400

    # Rough size check (base64 is ~33% larger than binary)
    size_mb = (len(encoded) * 3 / 4) / (1024 * 1024)
    if size_mb > MAX_SIZE_MB:
        return jsonify({"error": f"حجم عکس باید کمتر از {MAX_SIZE_MB}MB باشد"}), 400

    image_id = str(uuid.uuid4())
    db = get_db()
    db.execute(
        "INSERT INTO images (id, user_id, mime_type, data) VALUES (?, ?, ?, ?)",
        (image_id, request.user_id, mime, encoded)
    )
    db.commit()

    # Return a URL that the /image/:id endpoint can serve
    return jsonify({
        "message": "عکس آپلود شد ✅",
        "image_id": image_id,
        "url": f"/api/uploads/image/{image_id}"
    }), 201


@uploads_bp.route("/image/<image_id>", methods=["GET"])
def get_image(image_id):
    """Serve image directly as binary — no auth required so <img> tags work"""
    from flask import Response

    db = get_db()
    row = db.execute("SELECT mime_type, data FROM images WHERE id=?", (image_id,)).fetchone()
    if not row:
        return jsonify({"error": "عکس یافت نشد"}), 404

    binary = base64.b64decode(row["data"])
    return Response(binary, mimetype=row["mime_type"])
