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


def _encode_image(image_path: str, max_px: int = 640) -> str:
    """Encode image as base64, resizing to max_px on longest side first for speed."""
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
        f"Describe ONLY the permanent physical characteristics visible in the photo: "
        f"room size (small/medium/large/master if bedroom), flooring type and finish, "
        f"ceiling height, and any built-in fixtures only (e.g. built-in wardrobe, ensuite, "
        f"island bench, overhead cabinetry, fireplace, skylights). "
        f"Do NOT mention any moveable items such as furniture, TV, appliances, decor, or plants. "
        f"Do NOT use marketing adjectives. Write 2-3 plain factual sentences."
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
            "num_ctx": 2048,
        },
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
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
    Describe each room image individually — one LLaVA call per image.
    Guarantees no repetition, 3 focused sentences per room, built-in features only.
    """
    import re
    if not image_paths:
        return []

    descriptions = []

    for img_path, room, objects in zip(image_paths, all_rooms, all_objects):
        room_name = room.lower() if room else "room"

        prompt = (
            f"You are a property copywriter describing a {room_name} for a real estate listing.\n"
            f"Write 4 to 5 sentences in polished, engaging English starting with 'The {room_name}'.\n"
            f"Cover the following in order:\n"
            f"1. Overall room size and impression (e.g. generous proportions, well-sized, spacious). "
            f"If a bedroom, note whether it reads as a master or secondary bedroom.\n"
            f"2. Flooring — describe the type, finish, and visual appeal (e.g. rich timber floorboards, "
            f"sleek polished concrete, plush carpet).\n"
            f"3. Ceiling height and how it affects the feel of the room.\n"
            f"4. Any permanent built-in fixtures visible (e.g. walk-in robe, ensuite, island bench, "
            f"overhead cabinetry, fireplace, skylights, built-in shelving). Skip if none visible.\n"
            f"5. A closing sentence on the overall character or liveability of the space.\n"
            f"STRICT RULES:\n"
            f"- Do NOT mention any moveable items: no furniture, TV, appliances, decor, plants, vases, chairs, beds.\n"
            f"- You MAY use tasteful adjectives (refined, generous, well-appointed, striking) but avoid clichés "
            f"like stunning, breathtaking, or resort-style.\n"
            f"- Plain flowing prose. No bullet points, no numbering."
        )

        if user_prompt.strip():
            prompt += f" Additional context: {user_prompt}"

        encoded = _encode_image(_convert_to_jpg_if_needed(img_path))
        payload = {
            "model": LLAVA_MODEL,
            "prompt": prompt,
            "images": [encoded],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 300,
                "num_ctx": 2048,
            },
        }

        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=60)
            r.raise_for_status()
            raw = r.json().get("response", "").strip()
            # Strip any numbering LLaVA adds
            raw = re.sub(r'\[\d+\]|\(\d+\)|\b\d+\.\s+', '', raw).strip()
            print(f"[LLAVA] {room_name}: {len(raw)} chars")
            descriptions.append(raw)
        except Exception as e:
            print(f"[LLAVA] {room_name} error: {e}")
            descriptions.append("")

    # Translate if needed
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
            "num_predict": 250,
            "num_ctx": 2048,
        },
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=90)
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
    descriptions: list = None,
) -> dict:
    """5-dimension AI property analysis across all images combined."""
    if not image_paths:
        return {}

    # Build rich per-room context including LLaVA descriptions if available
    room_context_parts = []
    for i, (room, objects) in enumerate(zip(all_rooms, all_objects)):
        if room in ("invalid", "floor plan"):
            continue
        obj_str = ", ".join(objects) if objects else "none detected"
        line = f"{room.title()} (objects: {obj_str}"
        if descriptions and i < len(descriptions) and descriptions[i]:
            line += f"; description: {descriptions[i]}"
        line += ")"
        room_context_parts.append(line)
    context_str = "; ".join(room_context_parts) if room_context_parts else "multiple rooms"

    prompt = (
        f"You are an expert property analyst. I am showing you {len(image_paths)} interior property image(s). "
        f"Pre-analysis context: {context_str}. "
        f"Using both the images AND the context above, return ONLY a valid JSON object in English — no explanation, no markdown, no backticks. "
        f"The JSON must have exactly these keys:\n"
        f"  room_types: array of objects, one per visible room, each with keys: "
        f"    'room' (room name), 'size' ('small'|'medium'|'large'|'generous'), "
        f"    'flooring' (e.g. 'timber', 'tile', 'carpet', 'concrete', 'hybrid'), "
        f"    'ceiling' ('standard'|'high'|'very high'|'unknown')\n"
        f"  interior_condition: object with 'rating' ('poor'|'fair'|'good'|'excellent') and 'notes' (1 short factual sentence)\n"
        f"  fixtures: array of strings listing built-in fixtures only. Empty array if none.\n"
        f"  architectural_style: object with 'style', 'confidence' ('low'|'medium'|'high'), 'notes' (1 short sentence)\n"
        f"  luxury_features: array of strings. Empty array if none.\n"
        f"IMPORTANT: Use the description context to fill in size, flooring and ceiling — do NOT return 'unknown' if the description mentions them. "
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
            "num_predict": 1200,
            "num_ctx": 4096,
        },
    }

    raw = ""
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        print("[LLAVA] Analysis: cannot connect to Ollama — using fallback")
        return _fallback_analysis(all_rooms, all_objects, descriptions)
    except requests.exceptions.Timeout:
        print("[LLAVA] Analysis: request timed out — using fallback")
        return _fallback_analysis(all_rooms, all_objects, descriptions)
    except Exception as e:
        print(f"[LLAVA] Analysis request error: {e}")
        return _fallback_analysis(all_rooms, all_objects, descriptions)

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

    # Fill any remaining 'unknown' fields by extracting from descriptions
    if descriptions:
        analysis["room_types"] = _enrich_room_types_from_descriptions(
            analysis["room_types"], all_rooms, descriptions
        )
        print(f"[LLAVA] room_types enriched from descriptions")

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


def _extract_from_description(desc: str) -> dict:
    """
    Extract size, flooring and ceiling from a plain-text room description.
    Returns a dict with keys 'size', 'flooring', 'ceiling' — value is None if not found.
    """
    import re
    d = desc.lower()

    # ── SIZE ── (match only room-size context, not "large window" etc.)
    size = None
    if re.search(r'\bgenerous(?:ly[\s-]sized)?\b|\bvery\s+large\s+(?:room|space)\b|\bexpansive\b|\bspacious\s+(?:room|space|area)\b', d):
        size = "generous"
    elif re.search(r'\blarge[\s-]sized\b|\blarge\s+(?:room|space|area)\b|\bsizeable\b', d):
        size = "large"
    elif re.search(r'\bmedium[\s-]sized\b|\bmoderate[\s-]sized\b', d):
        size = "medium"
    elif re.search(r'\bsmall[\s-]sized\b|\bsmall\s+(?:room|space|area)\b|\bcompact\b|\bcosy\b|\bcozy\b', d):
        size = "small"

    # ── FLOORING ──────────────────────────────────────────────────────────────
    flooring = None
    flooring_patterns = [
        (r'\btimber\b|\bhardwood\b|\bwood(?:en)?\s+floor|\boak\b|\bfloorboard', "timber"),
        (r'\bpolished\s+concrete\b|\bconcrete\s+floor', "polished concrete"),
        (r'\bconcrete\b', "concrete"),
        (r'\bporcelain\b', "porcelain tile"),
        (r'\bterracotta\b', "terracotta tile"),
        (r'\bstone\s+tile|\bstone\s+floor|\bnatural\s+stone', "stone tile"),
        (r'\btile[sd]?\s+floor|\btiling\b|\btiled\b|\btile\b', "tile"),
        (r'\bcarpet(?:ed)?\b', "carpet"),
        (r'\bhybrid\b|\blvp\b|\bvinyl\b|\blaminate\b', "hybrid/laminate"),
        (r'\bslatted\b|\bdeck(?:ing)?\b', "timber decking"),
    ]
    for pattern, label in flooring_patterns:
        if re.search(pattern, d):
            flooring = label
            break

    # ── CEILING ───────────────────────────────────────────────────────────────
    ceiling = None
    if re.search(r'\bvery\s+high\s+ceiling|\bdouble[\s-]height\b|\bvaulted\b|\braked\b', d):
        ceiling = "very high"
    elif re.search(r'\bhigh\s+ceiling|\belevated\s+ceiling|\bsoaring\b|\bgrand\s+ceiling', d):
        ceiling = "high"
    elif re.search(r'\bstandard\s+ceiling|\baverage\s+ceiling|\bmoderate\s+ceiling\b', d):
        ceiling = "standard"
    elif re.search(r'\bceiling\s+height\s+is\s+average\b|\bceiling\s+is\s+standard\b', d):
        ceiling = "standard"

    return {"size": size, "flooring": flooring, "ceiling": ceiling}


def _enrich_room_types_from_descriptions(room_types: list, all_rooms: list, descriptions: list) -> list:
    """
    For each room_type entry that has 'unknown' fields, try to fill them
    from the matching description text.
    """
    if not descriptions:
        return room_types

    # Build a map: room name (lower) -> description
    desc_map = {}
    for i, room in enumerate(all_rooms):
        if room in ("invalid", "floor plan"):
            continue
        if i < len(descriptions) and descriptions[i]:
            desc_map[room.lower()] = descriptions[i]

    for rt in room_types:
        room_key = rt.get("room", "").lower()
        desc = desc_map.get(room_key, "")
        if not desc:
            # try partial match
            for k, v in desc_map.items():
                if k in room_key or room_key in k:
                    desc = v
                    break
        if not desc:
            continue

        extracted = _extract_from_description(desc)
        if rt.get("size", "unknown") in ("unknown", "", None) and extracted["size"]:
            rt["size"] = extracted["size"]
        if rt.get("flooring", "unknown") in ("unknown", "", None) and extracted["flooring"]:
            rt["flooring"] = extracted["flooring"]
        if rt.get("ceiling", "unknown") in ("unknown", "", None) and extracted["ceiling"]:
            rt["ceiling"] = extracted["ceiling"]

    return room_types


def _fallback_analysis(all_rooms: list, all_objects: list, descriptions: list = None) -> dict:
    rooms = [r for r in all_rooms if r not in ("invalid", "floor plan")]
    flat_objects = [obj for sublist in all_objects for obj in sublist]
    room_types = [
        {"room": r, "size": "unknown", "flooring": "unknown", "ceiling": "unknown"}
        for r in list(dict.fromkeys(rooms))
    ]
    # Even in fallback, extract what we can from descriptions
    if descriptions:
        room_types = _enrich_room_types_from_descriptions(room_types, all_rooms, descriptions)
    return {
        "room_types": room_types,
        "interior_condition": {"rating": "unknown", "notes": "Could not analyse condition."},
        "fixtures": list(set(flat_objects)),
        "architectural_style": {"style": "unknown", "confidence": "low", "notes": ""},
        "luxury_features": []
    }