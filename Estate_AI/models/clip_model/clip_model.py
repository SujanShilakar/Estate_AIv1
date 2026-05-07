import torch
import clip
from PIL import Image

device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)

# ── Combined labels — room types + floor plan detection in ONE list ──────────
# This means we only tokenise and run CLIP ONCE per image instead of twice
room_labels = [
    "a bedroom with a bed and pillows",
    "a bedroom with large bed and wardrobes",
    "a living room with sofa couch and coffee table",
    "a living room with tv couch sofa and coffee table",
    "an open plan living and dining area with couch and table",
    "a kitchen with stove oven sink and kitchen cabinets only",
    "a modern kitchen with cooking appliances and benchtop only",
    "a dining room with dining table and dining chairs",
    "a bathroom with shower bath toilet and sink vanity",
    "an ensuite bathroom with shower and vanity",
    "a garage with garage door and concrete floor",
    "a backyard garden with grass and plants outdoor",
    "an outdoor patio deck with outdoor furniture",
    "a laundry room with washing machine",
    "a home office study with desk computer and bookshelf",
    "a swimming pool with water and pool tiles",
    "an exterior front of a house with driveway",
    # Floor plan labels at the end
    "a 2D architectural floor plan drawing with wall lines and room labels",
    "a blueprint or architectural layout drawing viewed from above",
]

room_display_names = [
    "Bedroom", "Bedroom",
    "Living Room", "Living Room", "Living Room",
    "Kitchen", "Kitchen",
    "Dining Room",
    "Bathroom", "Ensuite",
    "Garage", "Backyard", "Outdoor Area",
    "Laundry", "Home Office", "Pool Area", "Exterior",
    "__floor_plan__", "__floor_plan__",
]

FLOOR_PLAN_INDICES = {17, 18}

# Tokenise ONCE at module load — shared for all calls
text = clip.tokenize(room_labels).to(device)


def classify_image(image_path: str):
    """
    Single CLIP call per image that handles BOTH floor plan detection
    and room classification. Cuts CLIP time in half.
    Returns: (is_floor_plan: bool, room_name: str)
    """
    try:
        image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
        with torch.no_grad():
            logits, _ = model(image, text)
            probs = logits.softmax(dim=-1).cpu().numpy()[0]

        fp_score   = sum(probs[i] for i in FLOOR_PLAN_INDICES)
        room_probs = [(i, probs[i]) for i in range(len(room_labels)) if i not in FLOOR_PLAN_INDICES]
        best_idx, best_conf = max(room_probs, key=lambda x: x[1])

        print(f"[CLIP] fp={fp_score:.2f} room={room_display_names[best_idx]}({best_conf:.2f})")

        if fp_score > 0.35:
            return True, "floor plan"

        if best_conf < 0.18:
            return False, "Room"

        # Kitchen vs Living Room tiebreaker
        kitchen = max((probs[i] for i,n in enumerate(room_display_names) if n=="Kitchen"), default=0)
        living  = max((probs[i] for i,n in enumerate(room_display_names) if n=="Living Room"), default=0)
        if room_display_names[best_idx] == "Kitchen" and (kitchen - living) < 0.20:
            return False, "Living Room"

        return False, room_display_names[best_idx]

    except Exception as e:
        print(f"[CLIP] Error: {e}")
        return False, "Room"


# Backwards-compatible wrappers so app.py does not need changes
def is_floor_plan_clip(image_path: str) -> bool:
    is_fp, _ = classify_image(image_path)
    return is_fp


def detect_room_clip(image_path: str) -> str:
    _, room = classify_image(image_path)
    return room
