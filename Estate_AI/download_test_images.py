"""
Download 20 real Adelaide property listings for AI model testing.

Each house folder contains:
  - Unique photos only (MD5 dedup) — bedroom, kitchen, bathroom, living room,
    exterior, and floor plan where the agent uploaded one
  - metadata.json  — select with the images in the app to auto-fill the
    property details form

Suburbs: Glenelg, Prospect, Burnside, Norwood, Unley

Usage:
  python download_test_images.py
"""

import hashlib
import json
import urllib.request
import urllib.error
from pathlib import Path

HEADERS   = {"User-Agent": "Mozilla/5.0"}
CDN       = "https://www.homely.com.au/img-variant/l-{key}-{n}.jpg"
MAX_KEEP  = 8     # max unique images per house (keeps things fast to test)
MAX_SLOTS = 30    # scan up to slot 30 to catch late-uploaded floor plans
MIN_BYTES = 8_000 # anything smaller is a placeholder / error image

# ── 20 real Adelaide house listings ──────────────────────────────────────────
LISTINGS = [
    # Glenelg SA 5045
    {"suburb": "Glenelg",  "address": "40b High Street",    "key": "MyDesktop-13060573", "beds": "3", "baths": "2", "parking": "2", "price": "",          "land_size": ""},
    {"suburb": "Glenelg",  "address": "3 Eitzen Street",    "key": "MyDesktop-13026744", "beds": "4", "baths": "2", "parking": "2", "price": "$2,200,000", "land_size": ""},
    {"suburb": "Glenelg",  "address": "3 Maturin Road",     "key": "AgentBox-12999494",  "beds": "5", "baths": "2", "parking": "4", "price": "$3,500,000", "land_size": "464 sqm"},
    {"suburb": "Glenelg",  "address": "1 Saltram Road",     "key": "AgentBox-13022247",  "beds": "2", "baths": "2", "parking": "1", "price": "",          "land_size": ""},
    # Prospect SA 5082
    {"suburb": "Prospect", "address": "50 Barker Road",     "key": "AgentBox-13106043",  "beds": "3", "baths": "1", "parking": "2", "price": "",          "land_size": "787 sqm"},
    {"suburb": "Prospect", "address": "92 Rose Street",     "key": "VaultRE-13097896",   "beds": "3", "baths": "1", "parking": "2", "price": "$880,000",   "land_size": ""},
    {"suburb": "Prospect", "address": "3 Gordon Road",      "key": "VaultRE-13092461",   "beds": "4", "baths": "2", "parking": "4", "price": "",          "land_size": "625 sqm"},
    {"suburb": "Prospect", "address": "35 Albert Street",   "key": "VaultRE-13092153",   "beds": "3", "baths": "1", "parking": "2", "price": "",          "land_size": "697 sqm"},
    {"suburb": "Prospect", "address": "64B Guilford Avenue","key": "LJHooker-13032776",  "beds": "4", "baths": "3", "parking": "4", "price": "",          "land_size": "417 sqm"},
    # Burnside SA 5066
    {"suburb": "Burnside", "address": "20 Wyatt Road",      "key": "AgentBox-13107103",  "beds": "4", "baths": "3", "parking": "2", "price": "",          "land_size": ""},
    {"suburb": "Burnside", "address": "12 Nilpinna Street", "key": "RayWhite-13093043",  "beds": "4", "baths": "2", "parking": "2", "price": "",          "land_size": "851 sqm"},
    {"suburb": "Burnside", "address": "65 Hallett Road",    "key": "RayWhite-13091411",  "beds": "3", "baths": "1", "parking": "3", "price": "",          "land_size": "350 sqm"},
    {"suburb": "Burnside", "address": "16 Hill Street",     "key": "RayWhite-12908961",  "beds": "4", "baths": "3", "parking": "2", "price": "$2,199,000", "land_size": "420 sqm"},
    {"suburb": "Burnside", "address": "71 Lockwood Road",   "key": "VaultRE-12799097",   "beds": "4", "baths": "3", "parking": "2", "price": "",          "land_size": "452 sqm"},
    {"suburb": "Burnside", "address": "35 Royal Avenue",    "key": "AgentBox-12577067",  "beds": "3", "baths": "2", "parking": "6", "price": "",          "land_size": "1643 sqm"},
    # Norwood SA 5067
    {"suburb": "Norwood",  "address": "115 Queen Street",   "key": "VaultRE-13096367",   "beds": "3", "baths": "2", "parking": "2", "price": "",          "land_size": ""},
    {"suburb": "Norwood",  "address": "106 Beulah Road",    "key": "AgentBox-12958153",  "beds": "4", "baths": "2", "parking": "2", "price": "",          "land_size": ""},
    {"suburb": "Norwood",  "address": "20A Edward Street",  "key": "LJHooker-12848155",  "beds": "3", "baths": "2", "parking": "4", "price": "$2,850,000", "land_size": ""},
    # Unley SA 5061
    {"suburb": "Unley",    "address": "17 Hughes Street",   "key": "AgentBox-13081848",  "beds": "3", "baths": "1", "parking": "3", "price": "",          "land_size": "900 sqm"},
    {"suburb": "Unley",    "address": "10A Maud Street",    "key": "AgentBox-12951104",  "beds": "3", "baths": "2", "parking": "1", "price": "$1,900,000", "land_size": "374 sqm"},
]


def fetch(url: str) -> bytes | None:
    """Fetch URL, return bytes or None on failure."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except Exception:
        return None


def download_house(house_num: int, listing: dict) -> int:
    out = Path(f"test_images/house_{house_num:02d}")
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n  House {house_num:02d}  —  {listing['address']}, {listing['suburb']}")

    seen_hashes: set[str] = set()
    saved: list[str] = []          # filenames saved so far
    consecutive_fails = 0          # stop early after 3 consecutive 404s

    for n in range(1, MAX_SLOTS + 1):
        if len(saved) >= MAX_KEEP:
            print(f"    [DONE] limit of {MAX_KEEP} images reached")
            break

        url = CDN.format(key=listing["key"], n=n)
        data = fetch(url)

        if data is None or len(data) < MIN_BYTES:
            consecutive_fails += 1
            if consecutive_fails >= 3 and n > 5:
                # 3 consecutive misses past slot 5 → no more photos
                break
            continue
        consecutive_fails = 0   # reset on success

        # MD5 dedup — skip identical images (agents sometimes repeat hero shot)
        h = hashlib.md5(data).hexdigest()
        if h in seen_hashes:
            print(f"    SKIP photo_{n:02d}.jpg (duplicate content)")
            continue
        seen_hashes.add(h)

        fname = f"photo_{n:02d}.jpg"
        (out / fname).write_bytes(data)
        saved.append(fname)
        print(f"    photo_{n:02d}.jpg  ({len(data) // 1024} KB)")

    # Save metadata.json for auto-filling property details in the app
    meta = {
        "address":   listing["address"],
        "suburb":    listing["suburb"],
        "beds":      listing["beds"],
        "baths":     listing["baths"],
        "parking":   listing["parking"],
        "price":     listing["price"],
        "land_size": listing["land_size"],
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"    metadata.json saved  ->  {len(saved)} unique photos")
    return len(saved)


def main():
    print("=" * 64)
    print("  Downloading 20 real Adelaide property listings")
    print("  Suburbs: Glenelg · Prospect · Burnside · Norwood · Unley")
    print(f"  Max {MAX_KEEP} unique images per house · duplicates skipped")
    print("  metadata.json saved per house for property-details auto-fill")
    print("=" * 64)

    total = 0
    for i, listing in enumerate(LISTINGS):
        total += download_house(i + 1, listing)

    print(f"\n{'=' * 64}")
    print(f"  Done — {total} unique photos across 20 Adelaide houses")
    print(f"  Saved to: {Path('test_images').resolve()}")
    print()
    print("  HOW TO USE:")
    print("  Open a house folder -> select ALL files (photos + metadata.json)")
    print("  -> Property details auto-fill in the app")
    print(f"{'=' * 64}")


if __name__ == "__main__":
    main()
