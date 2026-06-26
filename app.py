"""
ProveIt MVP Backend
Stack: Flask + SQLite (dev) / PostgreSQL (production) + JWT
"""

from flask import Flask
from flask import jsonify
import os

from routes.auth import auth_bp
from routes.users import users_bp
from routes.challenges import challenges_bp
from routes.posts import posts_bp
from routes.uploads import uploads_bp
from routes.messages import messages_bp
from models.db import init_db

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "proveit-dev-secret-change-me")
app.config["DATABASE"] = "proveit.db"

# Always make sure tables exist (safe to call every boot — uses CREATE IF NOT EXISTS)
init_db(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(users_bp, url_prefix="/api/users")
app.register_blueprint(challenges_bp, url_prefix="/api/challenges")
app.register_blueprint(posts_bp, url_prefix="/api/posts")
app.register_blueprint(uploads_bp, url_prefix="/api/uploads")
app.register_blueprint(messages_bp, url_prefix="/api/messages")

# CORS headers
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    return response

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "app": "ProveIt API", "version": "1.0.0"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🔥 ProveIt API running on http://localhost:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
