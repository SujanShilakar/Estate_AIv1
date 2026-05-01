"""
Admin-only API routes for user management, generation history,
templates, compliance rules, and analytics.
"""
from flask import Blueprint, request, jsonify
from . import database as db
from .routes import login_required


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ── Users ───────────────────────────────────
@admin_bp.route("/users", methods=["GET"])
@login_required(role="admin")
def list_users_route():
    role = request.args.get("role")
    return jsonify({"users": db.list_users(role=role)})


@admin_bp.route("/users", methods=["POST"])
@login_required(role="admin")
def create_user_route():
    data = request.get_json() or {}
    try:
        uid = db.create_user(
            username=data.get("username", "").strip(),
            email=data.get("email", "").strip().lower(),
            password=data.get("password", ""),
            role=data.get("role", "agent"),
            full_name=data.get("full_name", ""),
            agency=data.get("agency", ""),
            phone=data.get("phone", ""),
        )
        return jsonify({"success": True, "id": uid})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.route("/users/<int:uid>/toggle", methods=["POST"])
@login_required(role="admin")
def toggle_user(uid):
    user = db.get_user_by_id(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user["role"] == "admin":
        return jsonify({"error": "Cannot disable admin accounts"}), 400
    db.update_user_active(uid, not user["is_active"])
    return jsonify({"success": True, "is_active": not user["is_active"]})


@admin_bp.route("/users/<int:uid>", methods=["DELETE"])
@login_required(role="admin")
def delete_user_route(uid):
    user = db.get_user_by_id(uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user["role"] == "admin":
        return jsonify({"error": "Cannot delete admin accounts"}), 400
    db.delete_user(uid)
    return jsonify({"success": True})


# ── Generation history ──────────────────────
@admin_bp.route("/generations", methods=["GET"])
@login_required(role="admin")
def list_generations_route():
    user_id = request.args.get("user_id", type=int)
    return jsonify({"generations": db.list_generations(user_id=user_id, limit=200)})


@admin_bp.route("/generations/<int:gid>", methods=["GET"])
@login_required(role="admin")
def get_generation_route(gid):
    gen = db.get_generation(gid)
    if not gen:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"generation": gen})


@admin_bp.route("/generations/<int:gid>", methods=["DELETE"])
@login_required(role="admin")
def delete_generation_route(gid):
    db.delete_generation(gid)
    return jsonify({"success": True})


# ── Templates ───────────────────────────────
@admin_bp.route("/templates", methods=["GET"])
@login_required(role="admin")
def list_templates_route():
    return jsonify({"templates": db.list_templates()})


@admin_bp.route("/templates", methods=["POST"])
@login_required(role="admin")
def create_template_route():
    data = request.get_json() or {}
    if not data.get("name") or not data.get("tone") or not data.get("content"):
        return jsonify({"error": "Name, tone, and content are required"}), 400
    tid = db.create_template(
        name=data["name"], tone=data["tone"],
        content=data["content"], description=data.get("description", "")
    )
    return jsonify({"success": True, "id": tid})


@admin_bp.route("/templates/<int:tid>", methods=["PUT"])
@login_required(role="admin")
def update_template_route(tid):
    data = request.get_json() or {}
    db.update_template(
        tid, data.get("name", ""), data.get("tone", ""),
        data.get("content", ""), data.get("description", ""),
        data.get("is_active", True)
    )
    return jsonify({"success": True})


@admin_bp.route("/templates/<int:tid>", methods=["DELETE"])
@login_required(role="admin")
def delete_template_route(tid):
    db.delete_template(tid)
    return jsonify({"success": True})


# ── Compliance rules ────────────────────────
@admin_bp.route("/compliance", methods=["GET"])
@login_required(role="admin")
def list_compliance_route():
    return jsonify({"rules": db.list_compliance_rules()})


@admin_bp.route("/compliance", methods=["POST"])
@login_required(role="admin")
def create_compliance_route():
    data = request.get_json() or {}
    if not data.get("rule_name") or not data.get("pattern") or not data.get("message"):
        return jsonify({"error": "Rule name, pattern, and message are required"}), 400
    rid = db.create_compliance_rule(
        rule_name=data["rule_name"], pattern=data["pattern"],
        severity=data.get("severity", "warning"), message=data["message"]
    )
    return jsonify({"success": True, "id": rid})


@admin_bp.route("/compliance/<int:rid>", methods=["PUT"])
@login_required(role="admin")
def update_compliance_route(rid):
    data = request.get_json() or {}
    db.update_compliance_rule(
        rid, data.get("rule_name", ""), data.get("pattern", ""),
        data.get("severity", "warning"), data.get("message", ""),
        data.get("is_active", True)
    )
    return jsonify({"success": True})


@admin_bp.route("/compliance/<int:rid>", methods=["DELETE"])
@login_required(role="admin")
def delete_compliance_route(rid):
    db.delete_compliance_rule(rid)
    return jsonify({"success": True})


# ── Analytics ───────────────────────────────
@admin_bp.route("/analytics", methods=["GET"])
@login_required(role="admin")
def analytics():
    return jsonify(db.get_analytics())


# ── Compliance check (used by agent UI too) ─
@admin_bp.route("/compliance/check", methods=["POST"])
@login_required()
def check_text():
    data = request.get_json() or {}
    text = data.get("text", "")
    return jsonify({"violations": db.check_compliance(text)})
