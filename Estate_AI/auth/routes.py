"""
Auth routes — login, register, logout, session checks.
Provides decorators for route protection.
"""
from functools import wraps
from flask import Blueprint, request, jsonify, send_from_directory, redirect
from . import database as db


auth_bp = Blueprint("auth", __name__)


# ─── Helpers ──────────────────────────────────────
def get_token_from_request():
    """Get session token from cookie or Authorization header."""
    token = request.cookies.get("estate_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    return token


def get_current_user():
    """Return the current logged-in user dict, or None."""
    return db.get_session_user(get_token_from_request())


def login_required(role=None):
    """Decorator: enforce login. Optionally require a specific role."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Authentication required"}), 401
            if role and user["role"] != role:
                return jsonify({"error": "Forbidden — insufficient permissions"}), 403
            request.current_user = user
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ─── Routes ───────────────────────────────────────
@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    expected_role = data.get("role")  # optional — agent or admin

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    user = db.get_user_by_username(username)
    if not user or not db.verify_password(password, user["password"], user["salt"]):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user["is_active"]:
        return jsonify({"error": "Account disabled. Contact your administrator."}), 403

    if expected_role and user["role"] != expected_role:
        return jsonify({
            "error": f"This login is for {expected_role}s only. Please use the correct portal."
        }), 403

    token = db.create_session(user["id"])
    db.update_last_login(user["id"])

    resp = jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "full_name": user["full_name"],
            "agency": user["agency"],
        },
        "token": token,
        "redirect": "/admin/" if user["role"] == "admin" else "/app/",
    })
    resp.set_cookie("estate_token", token, max_age=7 * 24 * 3600, httponly=True, samesite="Lax")
    return resp


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    """Public registration — agents only."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    agency = (data.get("agency") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not username or not email or not password:
        return jsonify({"error": "Username, email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if "@" not in email:
        return jsonify({"error": "Invalid email address"}), 400

    try:
        uid = db.create_user(username, email, password, role="agent",
                             full_name=full_name, agency=agency, phone=phone)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    token = db.create_session(uid)
    user = db.get_user_by_id(uid)
    resp = jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "full_name": user["full_name"],
            "agency": user["agency"],
        },
        "token": token,
        "redirect": "/app/",
    })
    resp.set_cookie("estate_token", token, max_age=7 * 24 * 3600, httponly=True, samesite="Lax")
    return resp


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    token = get_token_from_request()
    if token:
        db.delete_session(token)
    resp = jsonify({"success": True})
    resp.delete_cookie("estate_token")
    return resp


@auth_bp.route("/api/auth/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False}), 200
    return jsonify({
        "authenticated": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "full_name": user["full_name"],
            "agency": user["agency"],
            "phone": user["phone"],
        }
    })
