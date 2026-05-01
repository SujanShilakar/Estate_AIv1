from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import os

from models.yolo_model.yolo_model import detect_objects
from models.yolo_model.description import generate_listing, generate_facebook_ads
from models.clip_model.clip_model import detect_room_clip, is_floor_plan_clip
from models.llava_model.llava_model import (
    analyse_property_images,
    _describe_rooms,
    _describe_floor_plans,
)

from auth import database as db
from auth.routes import auth_bp, login_required, get_current_user
from auth.admin_routes import admin_bp


app = Flask(__name__, static_folder="chat_ui", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "estate-ai-dev-secret-change-me")
CORS(app, supports_credentials=True)

# Initialise DB and seed defaults
db.init_db()

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

USE_LLAVA = True

FLOOR_PLAN_KEYWORDS = ["floorplan", "floor-plan", "floor_plan", "blueprint", "layout-plan"]


def is_floor_plan(filepath: str) -> bool:
    filename = os.path.basename(filepath).lower()
    if any(word in filename for word in FLOOR_PLAN_KEYWORDS):
        print(f"[FLOOR PLAN] Detected by filename: {filename}")
        return True
    return is_floor_plan_clip(filepath)


# ─── Static page routing ──────────────────────────
@app.route("/")
def index_redirect():
    """Root: send to login if not authenticated, otherwise to the right dashboard."""
    user = get_current_user()
    if not user:
        return redirect("/login")
    if user["role"] == "admin":
        return redirect("/admin/")
    return redirect("/app/")


@app.route("/login")
def login_page():
    return send_from_directory("chat_ui/auth", "login.html")


@app.route("/register")
def register_page():
    return send_from_directory("chat_ui/auth", "register.html")


@app.route("/admin-login")
def admin_login_page():
    return send_from_directory("chat_ui/auth", "admin-login.html")


@app.route("/app/")
def agent_app():
    return send_from_directory("chat_ui", "index.html")


@app.route("/admin/")
def admin_app():
    return send_from_directory("chat_ui/admin", "index.html")


@app.route("/admin/<path:path>")
def admin_static(path):
    return send_from_directory("chat_ui/admin", path)


@app.route("/auth/<path:path>")
def auth_static(path):
    return send_from_directory("chat_ui/auth", path)


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory("uploads", filename)


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("chat_ui", path)


# ─── Generation pipeline (now requires login) ────
@app.route("/upload", methods=["POST"])
@login_required()
def upload():
    user = request.current_user
    files = request.files.getlist("images")

    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No images uploaded"}), 400

    details = {
        "beds":      request.form.get("beds", ""),
        "baths":     request.form.get("baths", ""),
        "parking":   request.form.get("parking", ""),
        "suburb":    request.form.get("suburb", "Adelaide"),
        "land_size": request.form.get("land_size", ""),
        "price":     request.form.get("price", ""),
        "tone":      request.form.get("tone", "professional"),
        "prop_type": request.form.get("prop_type", "House"),
        "features":  request.form.get("features", ""),
    }

    lang   = request.form.get("lang", "en")
    prompt = request.form.get("prompt", "")

    results      = []
    seen_hashes  = set()   # duplicate image detection
    seen_rooms   = set()   # duplicate room type detection

    # These are built in-loop so indices always stay aligned with results
    valid_indices      = []   # indices into results for accepted room photos
    floor_plan_indices = []   # indices into results for floor plans
    valid_paths        = []
    valid_rooms        = []
    valid_objects      = []
    fp_paths           = []

    import hashlib

    for file in files:
        if file.filename == "":
            continue

        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)

        # ── Duplicate image check (hash file bytes) ──
        file_hash = hashlib.md5(open(filepath, "rb").read()).hexdigest()
        if file_hash in seen_hashes:
            print(f"[DUPLICATE IMAGE] {file.filename} — rejected")
            results.append({
                "filename":      file.filename,
                "objects":       [],
                "room":          "duplicate",
                "image_url":     f"/uploads/{file.filename}",
                "description":   "Duplicate image removed.",
                "is_invalid":    True,
                "is_floor_plan": False,
                "duplicate":     True,
            })
            continue
        seen_hashes.add(file_hash)

        # Step 1: Floor plan check
        if is_floor_plan(filepath):
            print(f"[FLOOR PLAN] {file.filename}")
            floor_plan_indices.append(len(results))
            fp_paths.append(filepath)
            results.append({
                "filename":      file.filename,
                "objects":       [],
                "room":          "floor plan",
                "image_url":     f"/uploads/{file.filename}",
                "description":   None,
                "is_invalid":    False,
                "is_floor_plan": True
            })
            continue

        # Step 2: CLIP room classification
        room = detect_room_clip(filepath)
        print(f"[CLIP] Room: {room}")

        # ── Duplicate room type check ──
        if room in seen_rooms and room not in ("Unknown", "Room"):
            print(f"[DUPLICATE ROOM] {file.filename} already have a {room} — rejected")
            results.append({
                "filename":      file.filename,
                "objects":       [],
                "room":          room,
                "image_url":     f"/uploads/{file.filename}",
                "description":   f"A {room} image was already included.",
                "is_invalid":    True,
                "is_floor_plan": False,
                "duplicate":     True,
            })
            continue
        seen_rooms.add(room)

        # Step 3: YOLO object detection
        try:
            objects = detect_objects(filepath)
            valid_indices.append(len(results))
            valid_paths.append(filepath)
            valid_rooms.append(room)
            valid_objects.append(objects)
            results.append({
                "filename":      file.filename,
                "objects":       objects,
                "room":          room,
                "image_url":     f"/uploads/{file.filename}",
                "description":   None,
                "is_invalid":    False,
                "is_floor_plan": False
            })
        except Exception as e:
            print(f"[ERROR] {file.filename}: {e}")
            valid_indices.append(len(results))
            valid_paths.append(filepath)
            valid_rooms.append("Unknown")
            valid_objects.append([])
            results.append({
                "filename":      file.filename,
                "objects":       [],
                "room":          "Unknown",
                "image_url":     f"/uploads/{file.filename}",
                "description":   None,
                "is_invalid":    False,
                "is_floor_plan": False,
                "error":         str(e)
            })

    # Step 4: Separate LLaVA calls
    property_analysis      = {}
    room_description       = ""
    floor_plan_description = ""

    if USE_LLAVA:
        if valid_paths:
            individual_descs = _describe_rooms(valid_paths, valid_rooms, valid_objects, prompt, lang)

            for i in range(len(valid_paths)):
                if i >= len(individual_descs) or not individual_descs[i]:
                    img_room = valid_rooms[i] if i < len(valid_rooms) else "room"
                    img_objs = valid_objects[i] if i < len(valid_objects) else []
                    obj_str  = ", ".join(img_objs[:4]) if img_objs else ""
                    fb = f"The {img_room.lower()} was detected"
                    fb += f" with the following items visible: {obj_str}." if obj_str else "."
                    if i < len(individual_descs):
                        individual_descs[i] = fb
                    else:
                        individual_descs.append(fb)

            for i, result_idx in enumerate(valid_indices):
                results[result_idx]["description"] = individual_descs[i] if i < len(individual_descs) else ""

            room_description = " ".join(individual_descs) if individual_descs else "No description generated."
            print(f"[LLAVA] {len(individual_descs)} room descriptions generated (1 batch call)")

        if fp_paths:
            try:
                floor_plan_description = _describe_floor_plans(fp_paths, prompt, lang)
                print(f"[LLAVA] Floor plan description generated ({len(floor_plan_description)} chars)")
                for result_idx in floor_plan_indices:
                    results[result_idx]["description"] = floor_plan_description
            except Exception as e:
                print(f"[LLAVA] Floor plan description error: {e}")

        if valid_paths:
            try:
                print(f"[LLAVA] Running 5-dimension analysis...")
                property_analysis = analyse_property_images(
                    image_paths=valid_paths,
                    all_rooms=valid_rooms,
                    all_objects=valid_objects,
                    language=lang,
                    descriptions=individual_descs,
                )
                print(f"[LLAVA] Analysis complete")
            except Exception as e:
                print(f"[LLAVA] Analysis error: {e}")
                property_analysis = {}

        if valid_paths and not property_analysis.get("room_types"):
            seen = []
            for r in valid_rooms:
                if r not in seen and r not in ("invalid", "floor plan"):
                    seen.append(r)
            property_analysis["room_types"] = [
                {"room": r, "size": "unknown", "flooring": "unknown", "ceiling": "unknown"}
                for r in seen
            ]

    flat_objects   = [obj for sublist in valid_objects for obj in sublist]
    unique_objects = list(dict.fromkeys(flat_objects))
    primary_room   = next((r for r in valid_rooms if r not in ["invalid", "floor plan"]), "Property")

    listing = generate_listing(room_type=primary_room, objects=unique_objects, details=details)
    ads = generate_facebook_ads(room_type=primary_room, objects=unique_objects, details=details)

    # Compliance check on generated listing
    compliance_violations = db.check_compliance(listing)

    # Persist generation to history
    try:
        gen_id = db.save_generation(user["id"], {
            "suburb":          details["suburb"],
            "beds":            details["beds"],
            "baths":           details["baths"],
            "parking":         details["parking"],
            "price":           details["price"],
            "tone":            details["tone"],
            "prop_type":       details["prop_type"],
            "listing":         listing,
            "ads":             ads,
            "room_desc":       room_description,
            "floor_plan_desc": floor_plan_description,
            "analysis":        property_analysis,
            "images":          [r["filename"] for r in results],
            "language":        lang,
        })
    except Exception as e:
        print(f"[DB] Failed to save generation: {e}")
        gen_id = None

    return jsonify({
        "images":                 results,
        "all_objects":            unique_objects,
        "details":                details,
        "content": {
            "listing":            listing,
            "facebook_ads":       ads,
        },
        "room_description":       room_description,
        "floor_plan_description": floor_plan_description,
        "final_description":      listing,
        "property_analysis":      property_analysis,
        "compliance":             compliance_violations,
        "generation_id":          gen_id,
    })


# ─── Agent endpoints ──────────────────────────────
@app.route("/api/my-generations", methods=["GET"])
@login_required()
def my_generations():
    user = request.current_user
    return jsonify({"generations": db.list_generations(user_id=user["id"], limit=50)})


@app.route("/api/generations/<int:gid>", methods=["GET"])
@login_required()
def get_my_generation(gid):
    user = request.current_user
    gen = db.get_generation(gid)
    if not gen:
        return jsonify({"error": "Not found"}), 404
    if gen["user_id"] != user["id"] and user["role"] != "admin":
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"generation": gen})


@app.route("/api/generations/<int:gid>", methods=["PUT"])
@login_required()
def update_my_generation(gid):
    """Allow agent to save edited listing back."""
    user = request.current_user
    gen = db.get_generation(gid)
    if not gen:
        return jsonify({"error": "Not found"}), 404
    if gen["user_id"] != user["id"] and user["role"] != "admin":
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json() or {}
    import json
    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE generations SET listing = ?, ads = ? WHERE id = ?",
                  (data.get("listing", gen["listing"]),
                   json.dumps(data.get("ads", json.loads(gen["ads"] or "[]"))),
                   gid))
    return jsonify({"success": True})


@app.route("/api/generations/<int:gid>", methods=["DELETE"])
@login_required()
def delete_my_generation(gid):
    """Allow agent to delete their own generation."""
    user = request.current_user
    gen = db.get_generation(gid)
    if not gen:
        return jsonify({"error": "Not found"}), 404
    if gen["user_id"] != user["id"] and user["role"] != "admin":
        return jsonify({"error": "Forbidden"}), 403
    db.delete_generation(gid)
    return jsonify({"success": True})


@app.route("/api/templates", methods=["GET"])
@login_required()
def get_active_templates():
    """Agents can view active templates."""
    return jsonify({"templates": db.list_templates(active_only=True)})


@app.route("/api/compliance/check", methods=["POST"])
@login_required()
def compliance_check():
    data = request.get_json() or {}
    text = data.get("text", "")
    return jsonify({"violations": db.check_compliance(text)})


@app.route("/test_translate", methods=["POST"])
def test_translate():
    from models.llava_model.llava_model import _translate, _get_text_model
    data = request.get_json()
    text = data.get("text", "The bedroom is medium with wooden flooring.")
    lang = data.get("lang", "hi")
    model = _get_text_model()
    result = _translate(text, lang)
    return jsonify({"model": model, "input": text, "translated": result, "lang": lang})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
