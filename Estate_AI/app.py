from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import os
import shutil
import tempfile
import uuid

from models.yolo_model.yolo_model import detect_objects
from models.yolo_model.description import generate_listing, generate_facebook_ads
from models.clip_model.clip_model import detect_room_clip, is_floor_plan_clip, classify_image
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


def _user_upload_folder(user_id):
    """Per-user uploads folder: uploads/u<user_id>/"""
    folder = os.path.join(UPLOAD_FOLDER, f"u{user_id}")
    os.makedirs(folder, exist_ok=True)
    return folder


def _generation_upload_folder(user_id, gen_id):
    """Final per-generation folder: uploads/u<user_id>/g<gen_id>/"""
    folder = os.path.join(_user_upload_folder(user_id), f"g{gen_id}")
    os.makedirs(folder, exist_ok=True)
    return folder


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
    """Root: show landing page. If already logged in go to dashboard."""
    user = get_current_user()
    if user:
        if user["role"] == "admin":
            return redirect("/admin/")
        return redirect("/app/")
    return send_from_directory("chat_ui", "landing.html")


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


@app.route("/uploads/<path:subpath>")
def uploaded_file(subpath):
    """Serve images from per-user folders.
    Path format: u<user_id>/g<gen_id>/<filename>
    Legacy flat files (just <filename>) still served for backwards compat.
    Access control: only the owner or an admin can fetch a user's files.
    """
    user = get_current_user()
    parts = subpath.split("/")
    # Per-user nested path: u<id>/g<id>/file.jpg
    if parts and parts[0].startswith("u") and parts[0][1:].isdigit():
        owner_id = int(parts[0][1:])
        if not user or (user["id"] != owner_id and user["role"] != "admin"):
            return jsonify({"error": "Forbidden"}), 403
    return send_from_directory(UPLOAD_FOLDER, subpath)


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

    results     = []
    all_rooms   = []
    all_objects = []
    saved_paths = []

    # Stage 1: Save uploads to a temp folder under this user. We don't yet
    # know the gen_id (DB row not yet created), so we use a UUID-named folder
    # and rename it to g<gen_id> after the row is inserted.
    tmp_id = uuid.uuid4().hex[:12]
    tmp_folder = os.path.join(_user_upload_folder(user["id"]), f"tmp_{tmp_id}")
    os.makedirs(tmp_folder, exist_ok=True)

    import hashlib
    seen_hashes = set()   # deduplicate identical images
    seen_rooms  = set()   # deduplicate room types

    for file in files:
        if file.filename == "":
            continue

        # Sanitise filename to prevent path traversal
        safe_name = os.path.basename(file.filename)
        filepath = os.path.join(tmp_folder, safe_name)
        file.save(filepath)

        # ── Duplicate image check ──
        file_hash = hashlib.md5(open(filepath, "rb").read()).hexdigest()
        if file_hash in seen_hashes:
            print(f"[DUPLICATE IMAGE] {safe_name} — skipped")
            continue
        seen_hashes.add(file_hash)
        saved_paths.append(filepath)

        # Step 1+2: Floor plan check AND room detection in ONE CLIP call (2x faster)
        is_fp, room = classify_image(filepath)

        if is_fp:
            print(f"[FLOOR PLAN] {file.filename}")
            results.append({
                "filename":      safe_name,
                "objects":       [],
                "room":          "floor plan",
                "image_url":     "",
                "description":   None,
                "is_invalid":    False,
                "is_floor_plan": True
            })
            all_rooms.append("floor plan")
            all_objects.append([])
            continue

        print(f"[CLIP] Room: {room}")

        # ── Duplicate room type check ──
        if room in seen_rooms and room not in ("Unknown", "Room"):
            print(f"[DUPLICATE ROOM] {safe_name} already have a {room} — skipped")
            continue
        seen_rooms.add(room)

        # Step 3: YOLO object detection
        try:
            objects = detect_objects(filepath)
            all_rooms.append(room)
            all_objects.append(objects)
            results.append({
                "filename":      safe_name,
                "objects":       objects,
                "room":          room,
                "image_url":     "",
                "description":   None,
                "is_invalid":    False,
                "is_floor_plan": False
            })
        except Exception as e:
            print(f"[ERROR] {file.filename}: {e}")
            results.append({
                "filename":      safe_name,
                "objects":       [],
                "room":          "Unknown",
                "image_url":     "",
                "description":   None,
                "is_invalid":    False,
                "is_floor_plan": False,
                "error":         str(e)
            })
            all_rooms.append("Unknown")
            all_objects.append([])

    # Step 4: Separate LLaVA calls
    property_analysis      = {}
    room_description       = ""
    floor_plan_description = ""

    valid_indices      = [i for i, r in enumerate(results) if not r["is_invalid"] and not r["is_floor_plan"]]
    floor_plan_indices = [i for i, r in enumerate(results) if r["is_floor_plan"]]
    valid_paths   = [saved_paths[i] for i in valid_indices]
    valid_rooms   = [all_rooms[i]   for i in valid_indices]
    valid_objects = [all_objects[i] for i in valid_indices]
    fp_paths      = [saved_paths[i] for i in floor_plan_indices]

    if USE_LLAVA:
        if valid_paths:
            # Deduplicate: only describe the first image per unique room type
            seen_rooms = {}
            dedup_paths, dedup_rooms, dedup_objects, dedup_indices = [], [], [], []
            for i, room in enumerate(valid_rooms):
                key = room.lower()
                if key not in seen_rooms:
                    seen_rooms[key] = i
                    dedup_paths.append(valid_paths[i])
                    dedup_rooms.append(valid_rooms[i])
                    dedup_objects.append(valid_objects[i])
                    dedup_indices.append(i)

            dedup_descs = _describe_rooms(dedup_paths, dedup_rooms, dedup_objects, prompt, lang)

            # Map dedup descriptions back to all valid images by room type
            room_desc_map = {}
            for j, room in enumerate(dedup_rooms):
                desc = dedup_descs[j] if j < len(dedup_descs) else ""
                if not desc:
                    img_objs = dedup_objects[j]
                    obj_str  = ", ".join(img_objs[:4]) if img_objs else ""
                    desc = f"The {room.lower()} was detected"
                    desc += f" with the following items visible: {obj_str}." if obj_str else "."
                room_desc_map[room.lower()] = desc

            individual_descs = []
            for i in range(len(valid_paths)):
                room_key = valid_rooms[i].lower() if i < len(valid_rooms) else "room"
                individual_descs.append(room_desc_map.get(room_key, ""))

            for i, result_idx in enumerate(valid_indices):
                results[result_idx]["description"] = individual_descs[i] if i < len(individual_descs) else ""

            # Build room_description from unique descriptions only (one per room type)
            unique_descs = list(dict.fromkeys(d for d in individual_descs if d))

            # Craft a tone-matched intro line (randomly varied each generation)
            import random
            suburb    = details.get("suburb", "Adelaide")
            beds      = details.get("beds", "")
            baths     = details.get("baths", "")
            tone      = details.get("tone", "professional")
            prop_type = details.get("prop_type", "property")
            pt        = prop_type.lower()
            summary   = f"{beds} bedroom, {baths} bathroom" if beds and baths else ""

            desc = f"{summary} {pt}".strip() if summary else pt
            intro_options = {
                "professional": [
                    f"Welcome to this beautifully presented {desc} in {suburb}, where thoughtful design meets everyday comfort.",
                    f"This property offers a comfortable and stylish lifestyle with a thoughtfully designed {desc} set in the heart of {suburb}.",
                    f"Presenting a wonderful opportunity to secure this well-appointed {desc} in one of {suburb}'s most desirable pockets.",
                    f"Discover the perfect blend of modern living and timeless appeal in this impressive {desc} located in {suburb}.",
                    f"Step into a home that truly has it all — this {desc} in {suburb} delivers style, space, and convenience in equal measure.",
                ],
                "luxury": [
                    f"Welcome to an extraordinary {desc} in the prestigious suburb of {suburb}, where every detail has been curated for those who expect nothing but the finest.",
                    f"Step inside this exceptional {desc} in {suburb} — a residence where impeccable craftsmanship and refined living come together in perfect harmony.",
                    f"Indulge in the pinnacle of luxury living with this breathtaking {desc} nestled in the heart of {suburb}, offering an unparalleled lifestyle experience.",
                    f"For the discerning buyer who refuses to compromise, this magnificent {desc} in {suburb} represents a rare opportunity to acquire something truly special.",
                    f"Elevate your lifestyle with this one-of-a-kind {desc} in {suburb}, masterfully designed to satisfy the most sophisticated of tastes.",
                ],
                "family": [
                    f"Welcome home to this wonderful {desc} in the heart of {suburb} — a place where families grow, memories are made, and every day feels like coming home.",
                    f"This property offers a comfortable and inviting lifestyle perfect for the whole family, with a thoughtfully designed {desc} nestled in family-friendly {suburb}.",
                    f"From the moment you arrive, this warm and welcoming {desc} in {suburb} wraps you in comfort — designed for the way modern families truly live.",
                    f"Discover a home that grows with your family — this generous {desc} in {suburb} has everything you need for a relaxed and connected family life.",
                    f"Make cherished memories in this spacious and well-loved {desc} in {suburb}, perfectly positioned close to parks, schools, and all family essentials.",
                ],
                "investment": [
                    f"Presenting a compelling investment opportunity in {suburb} — this well-maintained {desc} offers strong rental appeal and outstanding long-term potential.",
                    f"This property offers a smart and strategic lifestyle investment, with a well-positioned {desc} in the high-demand suburb of {suburb}.",
                    f"Welcome to one of {suburb}'s most sought-after investment prospects — a solid {desc} with immediate rental appeal and a location tenants love.",
                    f"Secure your financial future with this outstanding {desc} in {suburb}, combining reliable rental income potential with excellent capital growth fundamentals.",
                    f"An astute investor's dream awaits in {suburb} — this {desc} delivers the perfect combination of location, quality, and yield.",
                ],
            }
            options = intro_options.get(tone, intro_options["professional"])
            intro = random.choice(options)

            # Build 2-3 paragraphs: intro as first, then up to 2 room descriptions
            para_parts = [intro] + [d.strip() for d in unique_descs[:2] if d.strip()]
            room_description = "\n\n".join(para_parts)
            print(f"[LLAVA] {len(dedup_paths)} unique rooms described (from {len(valid_paths)} images)")

        if fp_paths:
            try:
                floor_plan_description = _describe_floor_plans(fp_paths, prompt, lang)
                print(f"[LLAVA] Floor plan description generated ({len(floor_plan_description)} chars)")
                for result_idx in floor_plan_indices:
                    results[result_idx]["description"] = floor_plan_description
            except Exception as e:
                print(f"[LLAVA] Floor plan description error: {e}")

        # Build analysis from descriptions — no extra LLaVA call needed
        if valid_paths:
            from models.llava_model.llava_model import _fallback_analysis, _enrich_room_types_from_descriptions
            property_analysis = _fallback_analysis(valid_rooms, valid_objects, individual_descs)
            print(f"[ANALYSIS] Built from descriptions — {len(property_analysis.get('room_types', []))} rooms")

    flat_objects   = [obj for sublist in all_objects for obj in sublist]
    unique_objects = list(dict.fromkeys(flat_objects))
    primary_room   = next((r for r in all_rooms if r not in ["invalid", "floor plan"]), "Property")

    listing_template = generate_listing(room_type=primary_room, objects=unique_objects, details=details)
    ads = generate_facebook_ads(room_type=primary_room, objects=unique_objects, details=details)

    # Build final listing: LLaVA paragraphs (if available) + highlights from template
    if room_description and "The Highlights:" in listing_template:
        highlights_part = listing_template[listing_template.index("The Highlights:"):]
        listing = room_description + "\n\n" + highlights_part
    else:
        listing = listing_template

    # Compliance check on generated listing
    compliance_violations = db.check_compliance(listing)

    # Persist generation to history (gets us a gen_id we can name the folder with)
    gen_id = None
    image_paths = []
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
            "image_paths":     [],  # filled in below after rename
            "language":        lang,
        })
    except Exception as e:
        print(f"[DB] Failed to save generation: {e}")
        gen_id = None

    # Stage 2: Rename tmp folder to its final per-generation home and update paths.
    if gen_id is not None:
        final_folder = os.path.join(_user_upload_folder(user["id"]), f"g{gen_id}")
        try:
            # If somehow the target exists (collision), just use it as-is
            if not os.path.exists(final_folder):
                os.rename(tmp_folder, final_folder)
            else:
                # Move files individually
                for fname in os.listdir(tmp_folder):
                    shutil.move(os.path.join(tmp_folder, fname),
                                os.path.join(final_folder, fname))
                shutil.rmtree(tmp_folder, ignore_errors=True)

            # Build relative paths (used for both URL and filesystem reference)
            for r in results:
                rel = f"uploads/u{user['id']}/g{gen_id}/{r['filename']}"
                r["image_url"] = "/" + rel
                image_paths.append(rel)

            # Persist final paths to the row
            db.update_generation_image_paths(gen_id, image_paths)
        except Exception as e:
            print(f"[FS] Failed to finalise upload folder: {e}")
            # Fallback: keep tmp folder, point URLs there
            for r in results:
                rel = f"uploads/u{user['id']}/tmp_{tmp_id}/{r['filename']}"
                r["image_url"] = "/" + rel
                image_paths.append(rel)
            db.update_generation_image_paths(gen_id, image_paths)
    else:
        # DB save failed — still serve images from tmp so the user gets a result
        for r in results:
            rel = f"uploads/u{user['id']}/tmp_{tmp_id}/{r['filename']}"
            r["image_url"] = "/" + rel

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


@app.route("/api/generations", methods=["DELETE"])
@login_required()
def delete_all_my_generations():
    """Delete every generation belonging to the current user.
    Requires JSON body {"confirm": "DELETE"} as a typed-confirmation safeguard.
    """
    user = request.current_user
    body = request.get_json(silent=True) or {}
    if (body.get("confirm") or "").strip().upper() != "DELETE":
        return jsonify({
            "error": "Confirmation required",
            "hint":  'Send {"confirm":"DELETE"} in the request body.'
        }), 400
    deleted = db.delete_all_generations(user["id"])
    return jsonify({"success": True, "deleted": deleted})


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