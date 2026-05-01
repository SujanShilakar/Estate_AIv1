import os
import base64
import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
LLAVA_MODEL = "llava:latest"
print("[LLAVA DEBUG] Patched module loaded — num_predict=600 active")

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


def _encode_image(image_path: str) -> str:
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
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 400,
            "num_ctx": 4096,
        },
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

    # Build per-image context hints for LLaVA
    context_parts = []
    for i, (room, objs) in enumerate(zip(all_rooms, all_objects)):
        obj_str = ", ".join(objs) if objs else ""
        line = f"Image {i+1}: {room}"
        if obj_str:
            line += f" (objects detected: {obj_str})"
        context_parts.append(line)

    room_guide = (
        "flooring type and room size, any permanent built-in features (wardrobe, walk-in robe, "
        "island bench, ensuite, fireplace, overhead cabinetry, built-in shelving) or mention there are none, "
        "ceiling height and any notable wall or ceiling features, natural light or spatial flow if clearly visible, "
        "and overall condition and presentation."
    )

    if n == 1:
        room_name = all_rooms[0].lower() if all_rooms else "room"
        obj_str = ", ".join(all_objects[0]) if all_objects and all_objects[0] else ""
        prompt = (
            f"You are a professional property inspector. Look at this {room_name} photo."
            + (f" Detected objects: {obj_str}." if obj_str else "")
            + f" Write a single plain paragraph of 4-5 sentences in English starting with 'The {room_name}'. "
            f"Cover: {room_guide} "
            f"IMPORTANT: Do NOT number sentences. Do NOT use [1] [2] or any brackets or bullet points. "
            f"Write flowing prose only. No marketing words."
        )
    else:
        room_labels = [all_rooms[i].lower() if i < len(all_rooms) else "room" for i in range(n)]
        sections = " ".join(
            f"For image {i+1} (the {room_labels[i]}), begin with 'The {room_labels[i]}'."
            for i in range(n)
        )
        prompt = (
            f"You are a professional property inspector. I am showing you {n} room photos.\n"
            f"Detected rooms: {'; '.join(context_parts)}.\n\n"
            f"Write one continuous paragraph in English. {sections} "
            f"For each room cover: {room_guide} "
            f"CRITICAL RULES: "
            f"Do NOT number sentences. Do NOT write [1] [2] [3] or any numbers in brackets. "
            f"Do NOT use bullet points or hyphens. Write plain flowing prose only. "
            f"No marketing adjectives. No furniture, curtains, linen, plants, artwork."
        )

    if user_prompt.strip():
        prompt += f" Additional context: {user_prompt}"

    encoded = [_encode_image(_convert_to_jpg_if_needed(p)) for p in image_paths]
    payload = {
        "model": LLAVA_MODEL,
        "prompt": prompt,
        "images": encoded,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 600,
            "num_ctx": 4096,
        },
    }

    print(f"[LLAVA DEBUG] About to POST with options={payload['options']}")
    raw = ""
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=240)
        r.raise_for_status()
        raw = r.json().get("response", "").strip()
        print(f"[LLAVA] _describe_rooms batch ok ({n} images, {len(raw)} chars)")
    except Exception as e:
        print(f"[LLAVA] _describe_rooms error: {e}")
        return [""] * n

    # Strip numbered patterns LLaVA sometimes adds despite instructions
    import re
    raw = re.sub(r'\[\d+\]|\(\d+\)|\d+\.\s+', '', raw).strip()

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
    payload = {
        "model": LLAVA_MODEL,
        "prompt": prompt,
        "images": encoded,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 500,
            "num_ctx": 4096,
        },
    }
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


def analyse_property_images(
    image_paths: list,
    all_rooms: list,
    all_objects: list,
    language: str = "en",
) -> dict:
    """5-dimension AI property analysis across all images combined."""
    if not image_paths:
        return {}

    room_context_parts = []
    for room, objects in zip(all_rooms, all_objects):
        if room in ("invalid", "floor plan"):
            continue
        obj_str = ", ".join(objects) if objects else "none detected"
        room_context_parts.append(f"{room.title()} (YOLO objects: {obj_str})")
    context_str = "; ".join(room_context_parts) if room_context_parts else "multiple rooms"

    prompt = (
        f"You are an expert property analyst. I am showing you {len(image_paths)} interior property image(s). "
        f"CLIP/YOLO pre-analysis: {context_str}. "
        f"Analyse all images and return ONLY a valid JSON object in English — no explanation, no markdown, no backticks. "
        f"The JSON must have exactly these keys:\n"
        f"  room_types: array of objects, one per visible room, each with keys: "
        f"    'room', 'size' ('small'|'medium'|'large'|'generous'), 'flooring', 'ceiling' ('standard'|'high'|'very high'|'unknown')\n"
        f"  interior_condition: object with 'rating' ('poor'|'fair'|'good'|'excellent') and 'notes' (1 short factual sentence)\n"
        f"  fixtures: array of strings. Empty array if none.\n"
        f"  architectural_style: object with 'style', 'confidence' ('low'|'medium'|'high'), 'notes' (1 short sentence)\n"
        f"  luxury_features: array of strings. Empty array if none.\n"
        f"Return ONLY the JSON object. No other text."
    )

    encoded_images = []
    for img_path in image_paths:
        encoded_images.append(_encode_image(_convert_to_jpg_if_needed(img_path)))

    payload = {
        "model": LLAVA_MODEL,
        "prompt": prompt,
        "images": encoded_images,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 800,
            "num_ctx": 4096,
        },
    }

    raw = ""
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        print("[LLAVA] Analysis: cannot connect to Ollama — using fallback")
        return _fallback_analysis(all_rooms, all_objects)
    except requests.exceptions.Timeout:
        print("[LLAVA] Analysis: request timed out — using fallback")
        return _fallback_analysis(all_rooms, all_objects)
    except Exception as e:
        print(f"[LLAVA] Analysis request error: {e}")
        return _fallback_analysis(all_rooms, all_objects)

    # Safe print — avoid Windows encoding crash with non-ASCII chars
    print(f"[LLAVA] Raw analysis received ({len(raw)} chars)")

    # Strip markdown code fences if present
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            if part.startswith("json"):
                raw = part[4:].strip()
                break
            if "{" in part:
                raw = part.strip()
                break

    # Extract outermost JSON object
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]
    else:
        print("[LLAVA] No JSON object found in analysis response — using fallback")
        return _fallback_analysis(all_rooms, all_objects)

    try:
        analysis = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[LLAVA] JSON parse error: {e}")
        return _fallback_analysis(all_rooms, all_objects)

    print(f"[LLAVA] Analysis parsed OK — keys: {list(analysis.keys())}")

    # If LLaVA returned empty room_types, fill from CLIP data
    if not analysis.get("room_types"):
        rooms = [r for r in all_rooms if r not in ("invalid", "floor plan")]
        analysis["room_types"] = [
            {"room": r, "size": "unknown", "flooring": "unknown", "ceiling": "unknown"}
            for r in list(dict.fromkeys(rooms))
        ]
        print(f"[LLAVA] room_types filled from CLIP inside analysis: {rooms}")

    # Translate free-text fields after parsing (always safe — _translate has its own try/except)
    if language != "en":
        ic = analysis.get("interior_condition", {})
        if ic.get("notes"):
            ic["notes"] = _translate(ic["notes"], language)
        as_ = analysis.get("architectural_style", {})
        if as_.get("notes"):
            as_["notes"] = _translate(as_["notes"], language)
        if analysis.get("fixtures"):
            analysis["fixtures"] = [_translate(f, language) for f in analysis["fixtures"]]
        if analysis.get("luxury_features"):
            analysis["luxury_features"] = [_translate(f, language) for f in analysis["luxury_features"]]

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