"""
Spike 001b: Face-consistent image generation via images.edit
Validates: gpt-image-1 edit API preserves Nikita's face while placing him in professional scenes.

Run: cd /Users/nikitakrivoshey/projects/linkedin-agent && python .planning/spikes/001-gpt-image-1-api/spike_001b_face_edit.py
Requires: data/profile_photos/nikita_01.jpg (or multiple photos)
"""
import base64
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    print("ERROR: OPENAI_API_KEY not set in .env")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: pip install openai")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

PHOTOS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "profile_photos"
OUTPUT_DIR = Path(__file__).parent / "outputs_face"
OUTPUT_DIR.mkdir(exist_ok=True)

# Realistic LinkedIn scene prompts — each tied to a specific post type
SCENE_PROMPTS = [
    {
        "label": "data_dashboard",
        "post_type": "news_insight",
        "prompt": (
            "The person in the photo is working at a modern tech office, multiple large monitors "
            "showing data analytics dashboards and charts, confident expression, professional attire, "
            "Dubai skyline visible through floor-to-ceiling windows, cinematic natural lighting. "
            "Photorealistic, LinkedIn professional photo style. Keep the person's face exactly as in the reference photo."
        ),
    },
    {
        "label": "thinking_professional",
        "post_type": "hot_take",
        "prompt": (
            "The person in the photo is sitting at a clean modern desk, arms crossed, thoughtful expression, "
            "looking slightly off-camera as if explaining a point. Minimal background — white wall, "
            "small plant, laptop. Photorealistic, professional headshot style. "
            "Keep the person's face exactly as in the reference photo."
        ),
    },
    {
        "label": "achievement_celebration",
        "post_type": "achievement",
        "prompt": (
            "The person in the photo is smiling confidently in a professional setting, "
            "laptop open with a successful dashboard or metric on screen, modern open-plan office, "
            "natural lighting. Subtle celebration mood. Photorealistic, LinkedIn style. "
            "Keep the person's face exactly as in the reference photo."
        ),
    },
]


def find_reference_photo() -> Path | None:
    """Find first available reference photo."""
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
        photos = list(PHOTOS_DIR.glob(ext))
        if photos:
            return photos[0]
    return None


def test_edit_api(reference_photo: Path, scene: dict) -> dict:
    """Test images.edit with reference photo and scene prompt."""
    label = scene["label"]
    prompt = scene["prompt"]
    print(f"\n--- Testing: {label} ---")
    print(f"Reference: {reference_photo.name}")
    print(f"Prompt: {prompt[:80]}...")

    start = time.time()
    try:
        with open(reference_photo, "rb") as img_file:
            response = client.images.edit(
                model="gpt-image-1",
                image=img_file,
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality="medium",
            )
        elapsed = time.time() - start

        image_data = response.data[0]
        b64 = image_data.b64_json

        if not b64:
            url = getattr(image_data, "url", None)
            print(f"  Got URL instead of base64: {url}")
            return {"label": label, "success": True, "format": "url", "url": url, "elapsed": elapsed}

        image_bytes = base64.b64decode(b64)
        filename = f"{label}.png"
        filepath = OUTPUT_DIR / filename
        filepath.write_bytes(image_bytes)

        size_kb = len(image_bytes) // 1024
        print(f"  OK: {size_kb} KB, {elapsed:.1f}s → {filepath}")

        return {
            "label": label,
            "success": True,
            "file": str(filepath),
            "size_kb": size_kb,
            "elapsed": elapsed,
        }

    except Exception as e:
        elapsed = time.time() - start
        print(f"  FAILED ({elapsed:.1f}s): {e}")
        return {"label": label, "success": False, "error": str(e), "elapsed": elapsed}


print("=" * 60)
print("SPIKE 001b: Face-Consistent Image Generation")
print("=" * 60)

ref_photo = find_reference_photo()
if not ref_photo:
    print(f"\nERROR: No reference photo found in {PHOTOS_DIR}")
    print("Save at least one photo as: data/profile_photos/nikita_01.jpg")
    sys.exit(1)

print(f"Reference photo: {ref_photo}")
print(f"Output dir: {OUTPUT_DIR}")

results = []
for scene in SCENE_PROMPTS:
    r = test_edit_api(ref_photo, scene)
    results.append(r)

print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
for r in results:
    status = "PASS" if r["success"] else "FAIL"
    print(f"  [{status}] {r['label']}: {r.get('size_kb', '?')} KB, {r.get('elapsed', 0):.1f}s")

all_passed = all(r["success"] for r in results)
print(f"\nVerdict: {'VALIDATED' if all_passed else 'PARTIAL/INVALIDATED'}")
print(f"\nCheck face consistency in: {OUTPUT_DIR}")
print("Questions to evaluate:")
print("  1. Is the face recognizable as Nikita?")
print("  2. Does the scene match the post type?")
print("  3. Is quality good enough for LinkedIn?")
