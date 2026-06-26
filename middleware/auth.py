"""JWT Auth Middleware"""

import jwt
from flask import request, jsonify, current_app
from functools import wraps


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "توکن ارسال نشده"}), 401

        try:
            payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            request.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "توکن منقضی شده"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "توکن نامعتبر"}), 401

        return f(*args, **kwargs)
    return decorated
