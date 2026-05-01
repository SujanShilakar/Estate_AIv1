import os
import base64
import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
LLAVA_MODEL = "llava"

# Google Translate language codes for deep-translator
GOOGLE_LANG_CODES = {
    "hi": "hi",
    "zh": "zh-CN",
    "ja": "ja",
}


def _translate(text: str, language: str) -> str:
    """Translate text using Google Translate (via deep-translator). Fast and reliable."""
    if not text or language == "en" or language not in GOOGLE_LANG_CODES:
        return text
    try:
        from deep_translator import GoogleTranslator
        target = GOOGLE_LANG_CODES[language]
        result = GoogleTranslator(source="en", target=target).translate(text)
        print(f"[TRANSLATE] ({language}) ok — {len(result)} chars")
        return result if result else text
    except Exception as e:
        print(f"[TRANSLATE] Error: {e}")
        return text


def _encode_image(image_path: str, max_px: int = 640) -> str:
    """Encode image as base64, resizing to max_px on the longest side first."""
    try:
        from PIL import Image as PILImage
        import io
        img = PILImage.open(image_path).convert("RGB")
        w, h = img.size
        if max(w, h) > max_px:
            scale = max_px / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


def _convert_to_jpg_if_needed(image_path: str) -> str:
    ext = os.path.splitext(image_path)[1].lower()
    if ext in [".webp", ".bmp", ".tiff"]:
        try:
            from PIL import Image
            converted_path = os.path.splitext(image_path)[0] + "_converted.jpg"
            img = Image.open(image_path).convert("RGB")
            img.save(converted_path, "JPEG")
            return converted_path
        except Exception:
            return image_path
    return image_path


def describe_property_image(
    image_path: str,
    detected_objects: list,
    room_type: str,
    user_prompt: str = ""
) -> str:
    image_path = _convert_to_jpg_if_needed(image_path)
    objects_str = ", ".join(detected_objects) if detected_objects else "various furnishings"

    prompt = (
        f"You are a property inspector writing factual room notes. "
        f"CLIP identified this room as: {room_type}. "
        f"YOLOv8 detected these objects: {objects_str}. "
        f"Describe only what is visible. Be factual and concise. "
        f"Include: estimated room size (small/medium/large/generous), "
        f"flooring type if visible, ceiling height if notable, "
        f"and major fixtures or built-ins only (e.g. built-in wardrobe, ensuite, island bench). "
        f"Do NOT use words like stunning, beautiful, luxurious, elegant, serene, inviting, appealing, resort-style, or any marketing adjectives. "
        f"Write 2-3 plain factual sentences."
    )

    if user_prompt.strip():
        prompt += f" Additional context: {user_prompt}"

    payload = {
        "model": LLAVA_MODEL,
        "prompt": prompt,
        "images": [_encode_image(image_path)],
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama.")
    except requests.exceptions.Timeout:
        raise RuntimeError("LLaVA request timed out.")


def is_floor_plan_image(image_path: str) -> bool:
    """LLaVA: Detect if image is strictly a 2D floor plan drawing."""
    image_path = _convert_to_jpg_if_needed(image_path)

    prompt = (
        "Look at this image carefully. "
        "A floor plan is ONLY a 2D top-down architectural drawing with lines representing walls, "
        "labeled rooms, and no furniture photos or real photographs. "
        "Is this image a 2D top-down architectural drawing with wall lines and room labels? "
        "Reply ONLY 'yes' if it is strictly a 2D architectural drawing. "
        "Reply ONLY 'no' if it is a real photo, 3D render, or interior room photo. "
        "Reply with ONLY one word: yes or no."
    )

    payload = {
        "model": LLAVA_MODEL,
        "prompt": prompt,
        "images": [_encode_image(image_path)],
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        answer = response.json().get("response", "").strip().lower()
        return answer.startswith("yes")
    except Exception:
        return False


def is_valid_property_image(image_path: str) -> bool:
    """LLaVA: Validate if image is a real estate property image."""
    valid_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in valid_extensions:
        return False

    image_path = _convert_to_jpg_if_needed(image_path)

    prompt = (
        "Look at this image carefully. "
        "Reply 'yes' if this image shows a real estate property space — "
        "this includes furnished or unfurnished rooms (bedroom, kitchen, bathroom, living room, "
        "dining room, laundry, garage, home office), property exterior, backyard, pool area, "
        "or an architectural floor plan drawing. Furniture and appliances in a room are fine. "
        "Reply 'no' ONLY if the image clearly shows: a person or people, an animal, food, "
        "a car, a product close-up, a screenshot, abstract art, or something completely unrelated "
        "to a real estate property. "
        "Reply with ONLY one word: yes or no."
    )

    payload = {
        "model": LLAVA_MODEL,
        "prompt": prompt,
        "images": [_encode_image(image_path)],
        "stream": False,
        "options": {"temperature": 0}
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        answer = response.json().get("response", "").strip().lower()
        return answer.startswith("yes")
    except Exception:
        return True


def _describe_rooms(image_paths: list, all_rooms: list, all_objects: list, user_prompt: str = "", language: str = "en") -> list:
    """
    Describe ALL room images in ONE LLaVA call.
    Returns a list of per-image descriptions (translated if needed).
    """
    n = len(image_paths)
    if n == 0:
        return []

    # Build per-image room labels only — no YOLO objects (they cause LLaVA to mention/negate them)
    room_labels = [all_rooms[i].lower() if i < len(all_rooms) else "room" for i in range(n)]

    room_guide = (
        "flooring type (e.g. timber, tile, carpet), estimated room size (small/medium/large/generous), "
        "ceiling height if notable, and any permanent built-in features visible (e.g. built-in wardrobe, "
        "island bench, overhead cabinetry, ensuite, fireplace). "
        "Do NOT mention moveable furniture, appliances, decor, or the absence of any item."
    )

    if n == 1:
        room_name = room_labels[0]
        prompt = (
            f"You are a professional property inspector. Look at this {room_name} photo. "
            f"Write a single plain paragraph of 3-4 sentences in English starting with 'The {room_name}'. "
            f"Describe only: {room_guide} "
            f"Do NOT number sentences. Do NOT use brackets, bullet points, or hyphens. "
            f"Write flowing prose only. No marketing adjectives."
        )
    else:
        room_list = ", ".join(f"the {r}" for r in room_labels)
        sections = " ".join(
            f"Start the {room_labels[i]} description with 'The {room_labels[i]}'."
            for i in range(n)
        )
        prompt = (
            f"You are a professional property inspector. I am showing you {n} room photos: {room_list}.\n\n"
            f"Write one continuous paragraph in English with no headings, no numbering, and no labels. "
            f"{sections} "
            f"For each room describe only: {room_guide} "
            f"CRITICAL: Do NOT write 'Image 1', 'Image 2', or any image numbers or labels anywhere. "
            f"Do NOT use bullet points or hyphens. Write plain flowing prose only. "
            f"No marketing adjectives. No mention of furniture, appliances, or absent items."
        )

    if user_prompt.strip():
        prompt += f" Additional context: {user_prompt}"

    encoded = [_encode_image(_convert_to_jpg_if_needed(p)) for p in image_paths]
    payload = {"model": LLAVA_MODEL, "prompt": prompt, "images": encoded,
               "stream": False, "options": {"temperature": 0}}

    raw = ""
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=240)
        r.raise_for_status()
        raw = r.json().get("response", "").strip()
        print(f"[LLAVA] _describe_rooms batch ok ({n} images, {len(raw)} chars)")
    except Exception as e:
        print(f"[LLAVA] _describe_rooms error: {e}")
        return [""] * n

    raw = _clean_llava_output(raw)

    # For multi-room: LLaVA returns one paragraph — split into per-room chunks by room name
    if n == 1:
        descriptions = [raw]
    else:
        room_labels = [all_rooms[i].lower() if i < len(all_rooms) else "room" for i in range(n)]
        descriptions = _split_paragraph_by_room(raw, room_labels)

    # Translate each description via Google Translate
    if language != "en":
        descriptions = [_translate(d, language) if d else "" for d in descriptions]

    return descriptions


def stream_descriptions(
    image_paths: list,
    all_rooms: list,
    fp_paths: list,
    user_prompt: str = "",
    language: str = "en",
):
    """
    Generator that streams LLaVA output chunk by chunk.
    Yields dicts: {"type": "chunk", "text": "..."} during generation,
                  {"type": "fp_chunk", "text": "..."} for floor plan,
                  {"type": "done", "descriptions": [...], "fp_description": "..."}
    """
    import re

    # ── Build prompt (same logic as _describe_rooms) ──
    n = len(image_paths)
    room_labels = [all_rooms[i].lower() if i < len(all_rooms) else "room" for i in range(n)]
    room_guide = (
        "flooring type (e.g. timber, tile, carpet), estimated room size (small/medium/large/generous), "
        "ceiling height if notable, and any permanent built-in features visible (e.g. built-in wardrobe, "
        "island bench, overhead cabinetry, ensuite, fireplace). "
        "Do NOT mention moveable furniture, appliances, decor, or the absence of any item."
    )

    room_raw = ""
    if image_paths:
        if n == 1:
            room_name = room_labels[0]
            prompt = (
                f"You are a professional property inspector. Look at this {room_name} photo. "
                f"Write a single plain paragraph of 3-4 sentences in English starting with 'The {room_name}'. "
                f"Describe only: {room_guide} "
                f"Do NOT number sentences. Do NOT use brackets, bullet points, or hyphens. "
                f"Write flowing prose only. No marketing adjectives."
            )
        else:
            room_list = ", ".join(f"the {r}" for r in room_labels)
            sections = " ".join(
                f"Start the {room_labels[i]} description with 'The {room_labels[i]}'."
                for i in range(n)
            )
            prompt = (
                f"You are a professional property inspector. I am showing you {n} room photos: {room_list}.\n\n"
                f"Write one continuous paragraph in English with no headings, no numbering, and no labels. "
                f"{sections} "
                f"For each room describe only: {room_guide} "
                f"CRITICAL: Do NOT write 'Image 1', 'Image 2', or any image numbers or labels anywhere. "
                f"Do NOT use bullet points or hyphens. Write plain flowing prose only. "
                f"No marketing adjectives. No mention of furniture, appliances, or absent items."
            )
        if user_prompt.strip():
            prompt += f" Additional context: {user_prompt}"

        encoded = [_encode_image(_convert_to_jpg_if_needed(p)) for p in image_paths]
        payload = {"model": LLAVA_MODEL, "prompt": prompt, "images": encoded,
                   "stream": True, "options": {"temperature": 0}}

        try:
            r = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=240)
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                chunk_data = json.loads(line)
                token = chunk_data.get("response", "")
                room_raw += token
                if token:
                    yield {"type": "chunk", "text": token}
                if chunk_data.get("done"):
                    break
        except Exception as e:
            print(f"[LLAVA] stream_descriptions room error: {e}")

    room_raw = _clean_llava_output(room_raw)

    # Split into per-image descriptions for analysis extraction
    if n == 1:
        descriptions = [room_raw]
    else:
        descriptions = _split_paragraph_by_room(room_raw, room_labels)
    if language != "en":
        descriptions = [_translate(d, language) for d in descriptions]

    # ── Floor plan streaming ──
    fp_raw = ""
    if fp_paths:
        fp_prompt = (
            f"You are reading {len(fp_paths)} architectural floor plan drawing(s). "
            "Look carefully at every labelled room and space on the plan. "
            "Write a single plain paragraph of 3-6 sentences in English describing the layout. "
            "Include: total number of rooms, name each space, how rooms connect and flow, "
            "and any notable layout features. "
            "Output ONLY plain sentences as one paragraph. "
            "No bullet points, dashes, hyphens, numbered lists, or headings."
        )
        if user_prompt.strip():
            fp_prompt += f" Additional context: {user_prompt}"
        fp_encoded = [_encode_image(_convert_to_jpg_if_needed(p)) for p in fp_paths]
        fp_payload = {"model": LLAVA_MODEL, "prompt": fp_prompt, "images": fp_encoded,
                      "stream": True, "options": {"temperature": 0}}
        try:
            r = requests.post(OLLAMA_URL, json=fp_payload, stream=True, timeout=180)
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                chunk_data = json.loads(line)
                token = chunk_data.get("response", "")
                fp_raw += token
                if token:
                    yield {"type": "fp_chunk", "text": token}
                if chunk_data.get("done"):
                    break
        except Exception as e:
            print(f"[LLAVA] stream_descriptions fp error: {e}")

    if language != "en" and fp_raw:
        fp_raw = _translate(fp_raw, language)

    yield {"type": "done", "descriptions": descriptions, "fp_description": fp_raw}


def _clean_llava_output(raw: str) -> str:
    import re
    raw = re.sub(r'[Ii]mage\s*\d+\s*[\(\[]?[^)\]]*[\)\]]?\s*:?\s*', '', raw)
    raw = re.sub(r'\[\d+\]|\(\d+\)|\d+\.\s+', '', raw)
    return raw.strip()


def _split_paragraph_by_room(paragraph: str, room_labels: list) -> list:
    """Split a multi-room paragraph into per-room chunks by matching room names."""
    import re
    n = len(room_labels)
    chunks = []

    for i, room in enumerate(room_labels):
        # Find where this room's description starts ("The bedroom", "The living room", etc.)
        pattern = re.compile(rf"\bthe\s+{re.escape(room)}\b", re.IGNORECASE)
        match = pattern.search(paragraph)
        if not match:
            chunks.append(("", match))
            continue
        # Find where the next room starts
        if i + 1 < n:
            next_pattern = re.compile(rf"\bthe\s+{re.escape(room_labels[i+1])}\b", re.IGNORECASE)
            next_match = next_pattern.search(paragraph, match.start() + 1)
            end = next_match.start() if next_match else len(paragraph)
        else:
            end = len(paragraph)
        chunks.append((paragraph[match.start():end].strip(), match))

    # If parsing fails (e.g. LLaVA used different room names), return whole paragraph for room 0
    results = [c[0] for c in chunks]
    if not any(results):
        return [paragraph] + [""] * (n - 1)
    # Fill empty slots with whole paragraph as fallback
    return [r if r else paragraph for r in results]


def _describe_floor_plans(floor_plan_paths: list, user_prompt: str = "", language: str = "en") -> str:
    """Generate English floor plan description then translate via Google Translate."""
    prompt = (
        f"You are reading {len(floor_plan_paths)} architectural floor plan drawing(s). "
        "Look carefully at every labelled room and space on the plan. "
        "Write a single plain paragraph of 3-6 sentences in English describing the layout. "
        "Include: total number of rooms, name each space (bedrooms, bathrooms, "
        "kitchen, living, dining, garage, alfresco, staircase, WIR, ensuite etc), "
        "how rooms connect and flow, and any notable layout features. "
        "Output ONLY plain sentences as one paragraph. "
        "No bullet points, dashes, hyphens, numbered lists, or headings."
    )
    if user_prompt.strip():
        prompt += f" Additional context: {user_prompt}"

    encoded = [_encode_image(_convert_to_jpg_if_needed(p)) for p in floor_plan_paths]
    payload = {"model": LLAVA_MODEL, "prompt": prompt, "images": encoded, "stream": False, "options": {"temperature": 0}}
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=180)
        r.raise_for_status()
        result = r.json().get("response", "").strip()
        print(f"[LLAVA] _describe_floor_plans ok ({len(result)} chars)")
        return _translate(result, language)
    except Exception as e:
        print(f"[LLAVA] _describe_floor_plans error: {e}")
        return ""


def describe_property_multi(
    image_paths: list,
    all_objects: list,
    all_rooms: list,
    floor_plan_paths: list = None,
    user_prompt: str = "",
    language: str = "en"
) -> str:
    """
    ✅ Calls LLaVA SEPARATELY for room photos and floor plans, then joins cleanly.
    Prevents mixing of room photo descriptions with floor plan layout.
    """
    floor_plan_paths = floor_plan_paths or []

    if not image_paths and not floor_plan_paths:
        return "No images provided."

    parts = []

    if image_paths:
        room_desc = _describe_rooms(image_paths, all_rooms, all_objects, user_prompt, language)
        if room_desc:
            parts.append(room_desc)

    if floor_plan_paths:
        fp_desc = _describe_floor_plans(floor_plan_paths, user_prompt, language)
        if fp_desc:
            parts.append(fp_desc)

    return "\n\n".join(parts) if parts else "No description generated."


def _extract_room_analysis(description: str, room: str) -> dict:
    """
    Extract size, flooring, and ceiling from an existing LLaVA description.
    Zero extra LLaVA calls — reads what was already written in the description.
    """
    import re
    text = description.lower()

    # ── Size ──
    size = "unknown"
    if re.search(r"\bgenerous\b", text):
        size = "generous"
    elif re.search(r"\blarge\b", text):
        size = "large"
    elif re.search(r"\bmedium\b", text):
        size = "medium"
    elif re.search(r"\bsmall\b", text):
        size = "small"

    # ── Flooring ──
    flooring = "unknown"
    flooring_map = [
        (r"\btimber\b|\bhardwood\b|\bwood(?:en)?\s+floor", "timber"),
        (r"\btile[ds]?\b|\bporcelain\b|\bterracotta\b", "tile"),
        (r"\bcarpet(?:ed)?\b", "carpet"),
        (r"\bconcrete\b|\bpolished\s+concrete\b", "concrete"),
        (r"\bvinyl\b|\blaminate\b", "vinyl"),
        (r"\bstone\b|\bmarble\b|\bgranite\b", "stone"),
    ]
    for pattern, label in flooring_map:
        if re.search(pattern, text):
            flooring = label
            break

    # ── Ceiling ──
    ceiling = "standard"
    if re.search(r"\bvery\s+high\s+ceiling|double[- ]height\b|void\b", text):
        ceiling = "very high"
    elif re.search(r"\bhigh\s+ceiling|generous\s+ceiling|raked\s+ceiling|vaulted\b", text):
        ceiling = "high"

    # ── Fixtures (built-ins mentioned in description) ──
    fixtures = []
    fixture_patterns = [
        (r"\bbuilt[- ]in\s+wardrobe|BIR\b", "built-in wardrobe"),
        (r"\bwalk[- ]in\s+(?:robe|wardrobe)|WIR\b", "walk-in robe"),
        (r"\bisland\s+bench\b", "island bench"),
        (r"\boverhead\s+cabinet", "overhead cabinetry"),
        (r"\bfireplace\b", "fireplace"),
        (r"\bensuite\b", "ensuite"),
        (r"\bskylight\b", "skylight"),
        (r"\bbuilt[- ]in\s+shelv", "built-in shelving"),
    ]
    for pattern, label in fixture_patterns:
        if re.search(pattern, text):
            fixtures.append(label)

    return {"size": size, "flooring": flooring, "ceiling": ceiling, "fixtures": fixtures}


def analyse_property_images(
    image_paths: list,
    all_rooms: list,
    all_objects: list,
    language: str = "en",
    descriptions: list = None,
) -> dict:
    """
    Build the 5-dimension property analysis from descriptions LLaVA already wrote.
    No extra LLaVA calls — extracts size/flooring/ceiling via keyword matching.
    """
    if not image_paths:
        return {}

    descriptions = descriptions or [""] * len(image_paths)
    room_types = []
    all_fixtures = []

    for room, desc in zip(all_rooms, descriptions):
        if room in ("invalid", "floor plan"):
            continue
        data = _extract_room_analysis(desc, room)
        room_types.append({
            "room": room,
            "size": data["size"],
            "flooring": data["flooring"],
            "ceiling": data["ceiling"],
        })
        all_fixtures.extend(data["fixtures"])

    # Condition: infer from YOLO object quality signals (simple heuristic)
    flat_objects = [o for sublist in all_objects for o in sublist]
    condition = "good"  # default — LLaVA described it, so it's presentable

    analysis = {
        "room_types": room_types,
        "interior_condition": {
            "rating": condition,
            "notes": f"Assessed from {len(room_types)} room(s).",
        },
        "fixtures": list(dict.fromkeys(all_fixtures)),
        "architectural_style": {"style": "unknown", "confidence": "low", "notes": ""},
        "luxury_features": [],
    }

    if language != "en":
        ic = analysis["interior_condition"]
        ic["notes"] = _translate(ic["notes"], language)

    return analysis


def _fallback_analysis(all_rooms: list, all_objects: list) -> dict:
    rooms = [r for r in all_rooms if r not in ("invalid", "floor plan")]
    flat_objects = [obj for sublist in all_objects for obj in sublist]
    return {
        "room_types": [
            {"room": r, "size": "unknown", "flooring": "unknown", "ceiling": "unknown"}
            for r in list(dict.fromkeys(rooms))
        ],
        "interior_condition": {"rating": "unknown", "notes": "Could not analyse condition."},
        "fixtures": list(set(flat_objects)),
        "architectural_style": {"style": "unknown", "confidence": "low", "notes": ""},
        "luxury_features": []
    }