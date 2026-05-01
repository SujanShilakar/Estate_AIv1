from ultralytics import YOLO

model = YOLO("yolov8m.pt")

VALID_HOME_OBJECTS = {
    "bed", "chair", "dining table", "tv", "laptop",
    "refrigerator", "sink", "toilet", "couch", "cabinet",
    "window", "door", "lamp", "pillow", "clock", "vase",
    "microwave", "oven", "toaster", "book", "mirror"
}

def detect_objects(image_path):
    """
    YOLO: Detect objects in property image.
    Returns list of valid home objects with confidence >= 0.5
    """
    results = model(image_path, conf=0.5)

    objects = []
    for r in results:
        for box, c in zip(r.boxes.conf, r.boxes.cls):
            if box >= 0.5:
                name = model.names[int(c)]
                if name in VALID_HOME_OBJECTS:
                    objects.append(name)
                    print(f"[YOLO] Detected: {name} ({float(box):.2f})")

    detected = list(set(objects))
    print(f"[YOLO] Final objects: {detected}")
    return detected