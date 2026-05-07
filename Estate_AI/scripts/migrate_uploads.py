"""
One-time migration: move existing flat uploads/<file>.jpg into per-user/per-generation
folders, and backfill the new image_paths column in the generations table.

Safe to run multiple times (idempotent).

Usage:
    cd Estate_AI
    python scripts/migrate_uploads.py
"""
import os
import sys
import json
import shutil

# Make the auth package importable when this script runs from anywhere
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from auth import database as db  # noqa: E402

UPLOAD_FOLDER = os.path.join(ROOT, "uploads")


def main():
    if not os.path.isdir(UPLOAD_FOLDER):
        print(f"[SKIP] No uploads/ folder found at {UPLOAD_FOLDER}")
        return

    db.init_db()

    moved = 0
    backfilled = 0
    skipped = 0
    missing = 0

    with db.get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, user_id, images, image_paths FROM generations ORDER BY id ASC")
        rows = c.fetchall()

    for row in rows:
        gen_id   = row["id"]
        user_id  = row["user_id"]
        existing = row["image_paths"]

        # If image_paths already populated, skip
        if existing:
            try:
                if json.loads(existing):
                    skipped += 1
                    continue
            except Exception:
                pass

        try:
            filenames = json.loads(row["images"] or "[]")
        except Exception:
            filenames = []

        if not filenames:
            backfilled += 1
            continue

        target_folder = os.path.join(UPLOAD_FOLDER, f"u{user_id}", f"g{gen_id}")
        os.makedirs(target_folder, exist_ok=True)

        new_paths = []
        for fname in filenames:
            safe = os.path.basename(fname)
            old_path = os.path.join(UPLOAD_FOLDER, safe)
            new_path = os.path.join(target_folder, safe)
            rel = f"uploads/u{user_id}/g{gen_id}/{safe}"

            if os.path.exists(new_path):
                # Already moved on a prior run
                new_paths.append(rel)
                continue

            if os.path.exists(old_path):
                try:
                    shutil.move(old_path, new_path)
                    moved += 1
                    new_paths.append(rel)
                except Exception as e:
                    print(f"[ERR] Could not move {old_path} → {new_path}: {e}")
                    missing += 1
            else:
                # Original file is gone — record the path anyway so the
                # row stays consistent. The UI will show a missing-image
                # placeholder for these.
                missing += 1
                new_paths.append(rel)

        # Write back
        with db.get_db() as conn:
            c = conn.cursor()
            c.execute("UPDATE generations SET image_paths = ? WHERE id = ?",
                      (json.dumps(new_paths), gen_id))
        backfilled += 1

    print("─" * 50)
    print(f"Files moved:           {moved}")
    print(f"Generations updated:   {backfilled}")
    print(f"Generations skipped:   {skipped} (already had paths)")
    print(f"Files missing on disk: {missing}")
    print("─" * 50)
    print("Done. Old flat uploads/ files have been moved into")
    print("uploads/u<user_id>/g<gen_id>/ folders.")


if __name__ == "__main__":
    main()