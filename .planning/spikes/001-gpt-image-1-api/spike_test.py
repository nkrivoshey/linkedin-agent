"""
Spike 001: gpt-image-1 API validation
Validates: gpt-image-1 returns LinkedIn-quality image as bytes, integratable with binary upload.

Run: cd /Users/nikitakrivoshey/projects/linkedin-agent && python .planning/spikes/001-gpt-image-1-api/spike_test.py
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

# Realistic LinkedIn post prompt (data analyst in Dubai)
TEST_POST_TEXT = """
Most analytics teams are optimizing for speed, but speed isn't the bottleneck.
At Metropolitan Premium Properties, I discovered that 80% of our broker decisions
were based on a single lagging metric — conversion rate. Not because it's the best,
but because it was the only one on the dashboard.

The real constraint isn't compute, it's trust. Brokers need to trust the number
before they act on it.

Has your team made this mistake? Drop a 🔥 if yes.

#DataAnalytics #BusinessIntelligence #DataDriven #SQL #PowerBI
"""

PROMPTS_TO_TEST = [
    # Most specific — mirrors the post content
    {
        "label": "Specific scene",
        "prompt": (
            "Professional LinkedIn post image. A data analyst in Dubai reviewing "
            "real estate dashboard metrics on a large monitor at night, city skyline "
            "visible through office window. Clean, modern office. Photorealistic, "
            "cinematic lighting. Landscape 16:9."
        ),
    },
    # Mid-level — professional context
    {
        "label": "Professional abstract",
        "prompt": (
            "Professional LinkedIn image for a data analytics post. "
            "Abstract visualization of data flow and business metrics, "
            "dark blue and gold color palette, modern minimalist design. "
            "No text. High quality, suitable for LinkedIn."
        ),
    },
    # Generic fallback
    {
        "label": "Generic professional",
        "prompt": (
            "Professional LinkedIn post image. Data analyst working with "
            "business intelligence dashboards. Clean corporate environment. "
            "Photorealistic, professional photography style."
        ),
    },
]

OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def generate_image(prompt: str, label: str) -> dict:
    print(f"\n--- Generating: {label} ---")
    print(f"Prompt: {prompt[:80]}...")

    start = time.time()
    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            size="1536x1024",
            quality="medium",
        )
        elapsed = time.time() - start

        # gpt-image-1 returns b64_json
        image_data = response.data[0]
        b64 = image_data.b64_json

        if not b64:
            # Some versions return URL instead
            url = getattr(image_data, "url", None)
            print(f"  Got URL instead of base64: {url}")
            return {"label": label, "success": True, "format": "url", "url": url, "elapsed": elapsed}

        image_bytes = base64.b64decode(b64)

        # Save to file
        filename = label.replace(" ", "_") + ".png"
        filepath = OUTPUT_DIR / filename
        filepath.write_bytes(image_bytes)

        size_kb = len(image_bytes) // 1024
        print(f"  OK: {size_kb} KB, {elapsed:.1f}s → {filepath}")

        # Verify it's a valid PNG/JPEG
        is_png = image_bytes[:4] == b'\x89PNG'
        is_jpg = image_bytes[:2] == b'\xff\xd8'
        fmt = "PNG" if is_png else "JPEG" if is_jpg else "unknown"
        print(f"  Format: {fmt}")

        return {
            "label": label,
            "success": True,
            "format": "base64",
            "file": str(filepath),
            "size_kb": size_kb,
            "elapsed": elapsed,
            "image_format": fmt,
        }

    except Exception as e:
        elapsed = time.time() - start
        print(f"  FAILED ({elapsed:.1f}s): {e}")
        return {"label": label, "success": False, "error": str(e), "elapsed": elapsed}


def test_bytes_uploadable(result: dict) -> bool:
    """Verify bytes can be used in LinkedIn-style binary upload."""
    if not result.get("success") or result.get("format") != "base64":
        return False
    filepath = Path(result["file"])
    if not filepath.exists():
        return False
    image_bytes = filepath.read_bytes()
    # LinkedIn upload accepts raw bytes — simulate by checking non-empty valid image
    return len(image_bytes) > 10_000  # meaningful image, not garbage


print("=" * 60)
print("SPIKE 001: gpt-image-1 API Validation")
print("=" * 60)

results = []
for p in PROMPTS_TO_TEST:
    r = generate_image(p["prompt"], p["label"])
    results.append(r)

print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)

for r in results:
    uploadable = test_bytes_uploadable(r)
    status = "PASS" if r["success"] else "FAIL"
    upload_ok = "binary-upload-ready" if uploadable else "NOT uploadable"
    print(f"  [{status}] {r['label']}: {r.get('size_kb', '?')} KB, "
          f"{r.get('elapsed', 0):.1f}s, {upload_ok}")

all_passed = all(r["success"] for r in results)
print(f"\nVerdict: {'VALIDATED' if all_passed else 'PARTIAL/INVALIDATED'}")
print(f"Output images in: {OUTPUT_DIR}")
print("\nOpen the .png files to check LinkedIn quality.")
