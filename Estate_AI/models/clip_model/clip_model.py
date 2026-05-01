import torch
import clip
from PIL import Image

device = "cuda" if torch.cuda.is_available() else "cpu"

model, preprocess = clip.load("ViT-B/32", device=device)

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
]

room_display_names = [
    "Bedroom",
    "Bedroom",
    "Living Room",
    "Living Room",
    "Living Room",
    "Kitchen",
    "Kitchen",
    "Dining Room",
    "Bathroom",
    "Ensuite",
    "Garage",
    "Backyard",
    "Outdoor Area",
    "Laundry",
    "Home Office",
    "Pool Area",
    "Exterior",
]

text = clip.tokenize(room_labels).to(device)

# ✅ Floor plan detection labels
floor_plan_labels = [
    "a 2D architectural floor plan drawing with wall lines and room labels",
    "a blueprint or architectural layout drawing viewed from above",
    "a real photograph of a room interior with furniture",
    "a real photo of a bedroom living room or kitchen",
]
floor_plan_text = clip.tokenize(floor_plan_labels).to(device)


def is_floor_plan_clip(image_path: str) -> bool:
    """
    Use CLIP to detect if image is a floor plan by content.
    Fast and reliable — no LLaVA needed for this task.
    """
    try:
        image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)

        with torch.no_grad():
            logits, _ = model(image, floor_plan_text)
            probs = logits.softmax(dim=-1).cpu().numpy()[0]

        # First 2 labels = floor plan, last 2 = real photo
        floor_plan_score = probs[0] + probs[1]
        photo_score = probs[2] + probs[3]

        print(f"[CLIP] Floor plan score: {floor_plan_score:.2f}, Photo score: {photo_score:.2f}")
        return floor_plan_score > photo_score

    except Exception as e:
        print(f"[CLIP] Floor plan detection error: {e}")
        return False


def detect_room_clip(image_path: str) -> str:
    try:
        image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)

        with torch.no_grad():
            logits_per_image, _ = model(image, text)
            probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]

        best_index = probs.argmax()
        confidence = probs[best_index]

        # Print top 3 for debugging
        top3 = probs.argsort()[::-1][:3]
        for idx in top3:
            print(f"[CLIP] {room_display_names[idx]}: {probs[idx]:.2f}")

        # Low confidence — return "Room" so LLaVA validation runs and rejects non-property images
        if confidence < 0.20:
            print(f"[CLIP] Low confidence ({confidence:.2f}), flagging for LLaVA validation")
            return "Room"

        # Kitchen vs Living Room tiebreaker
        kitchen_score = max(
            probs[i] for i, name in enumerate(room_display_names) if name == "Kitchen"
        )
        living_score = max(
            probs[i] for i, name in enumerate(room_display_names) if name == "Living Room"
        )

        if room_display_names[best_index] == "Kitchen" and (kitchen_score - living_score) < 0.20:
            print(f"[CLIP] Kitchen ({kitchen_score:.2f}) vs Living Room ({living_score:.2f}) too close → Living Room")
            return "Living Room"  # Both are valid property rooms, keep as Living Room

        print(f"[CLIP] Final: {room_display_names[best_index]} ({confidence:.2f})")
        return room_display_names[best_index]

    except Exception as e:
        print(f"CLIP error for {image_path}: {e}")
        return "Room"