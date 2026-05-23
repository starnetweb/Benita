"""
Generate and set featured images for WordPress posts.
- Claude writes a descriptive image prompt based on post title/content
- Pollinations.ai generates the image (free, no API key)
- Image is uploaded to WordPress Media Library
- Set as featured image on the post

Usage: python add_featured_images.py [--post-ids 11445,11446,11447]
"""
import argparse
import io
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(Path(__file__).parent.parent / "logs" / "agent.log"),
                            encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("featured_images")

import anthropic
import requests
sys.path.insert(0, str(Path(__file__).parent))
import db
import wp_poster

claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "openai").lower()
logger.info(f"Image provider: {IMAGE_PROVIDER}")


# ── Step 1: Build image prompt ────────────────────────────────────────────────

def generate_image_prompt(post_title: str, post_excerpt: str) -> str:
    """Build the featured image prompt."""
    prompt = f"""You are a professional creative director and digital artist.

Generate a high-quality blog featured image for the article titled:

"{post_title}"

Context:
Nigerian university admission, JAMB, Post-UTME, education news

Image Style:
- modern editorial illustration or abstract 3D concept design only (no photography)
- clean, minimal, premium blog featured image style
- designed for website hero/featured image use
- conceptual visual metaphors only (icons, shapes, abstract objects, UI elements)

Composition:
- strong central concept representing the topic
- balanced layout with clear visual hierarchy
- large clean negative space for headline text overlay
- smooth abstract shapes or structured digital elements
- depth and perspective without any human figures

Visual Content Rules:
- only abstract objects, symbols, charts, devices, books, buildings, or conceptual UI elements related to the topic
- no human figures, no faces, no silhouettes

Color and Lighting (STRICT):
- muted color palette only
- off-white, light gray, soft beige, and desaturated pastel tones
- VERY light desaturated blue ONLY as secondary accent (barely noticeable)
- ABSOLUTELY NO bright blue, NO neon blue, NO electric blue
- ABSOLUTELY NO bright green, NO neon green, NO lime green
- no saturated or vivid colors of any kind
- soft neutral lighting, no glowing or neon effects

Strict exclusions:
- no realistic humans or human-like figures
- no faces or body parts
- no bright blue or bright green in any form
- no neon colors or high saturation
- no cyberpunk, gaming, or futuristic glow style
- no cluttered visuals
- no text inside image
- no logos or watermarks

Quality:
- ultra-detailed
- 4K visual quality
- sharp, clean composition
- premium global editorial blog standard (TechCrunch / Medium-level featured image aesthetic)"""
    logger.info(f"Image prompt: {prompt[:80]}...")
    return prompt


# ── Step 2: Generate image — provider dispatcher ─────────────────────────────

def _generate_openai(prompt: str) -> bytes:
    """OpenAI gpt-image-1 — set OPENAI_API_KEY in .env"""
    from openai import OpenAI
    import base64
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or key.startswith("your_"):
        raise RuntimeError("OPENAI_API_KEY not set in .env")
    client = OpenAI(api_key=key)
    model  = os.getenv("IMAGE_MODEL_OPENAI", "gpt-image-1")
    logger.info(f"[OpenAI {model}] generating image...")
    resp = client.images.generate(
        model=model,
        size="1024x1024",   # smallest size = lowest cost
        quality="low",      # lowest quality tier = minimal cost
        prompt=prompt,
        output_format="jpeg",
    )
    # gpt-image-1 returns base64 by default
    b64 = resp.data[0].b64_json
    if b64:
        return base64.b64decode(b64)
    # fallback: URL
    image_url = resp.data[0].url
    return requests.get(image_url, timeout=90).content


def _generate_google(prompt: str) -> bytes:
    """Google Imagen 4 via AI Studio API."""
    import base64
    key   = os.getenv("GOOGLE_API_KEY", "")
    if not key or key.startswith("your_"):
        raise RuntimeError("GOOGLE_API_KEY not set in .env")
    model = os.getenv("IMAGE_MODEL_GOOGLE", "imagen-4.0-generate-001")
    logger.info(f"[Google Imagen 4] model={model}")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict?key={key}"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",
            "safetySetting": "block_only_high",
            "personGeneration": "dont_allow"
        }
    }
    resp = requests.post(url, json=payload, timeout=90)
    resp.raise_for_status()
    b64 = resp.json()["predictions"][0]["bytesBase64Encoded"]
    return base64.b64decode(b64)


def _generate_fal(prompt: str) -> bytes:
    """Fal.ai (Flux 1.1 Pro) — set FAL_API_KEY in .env (fal.ai/dashboard/keys)"""
    key   = os.getenv("FAL_API_KEY", "")
    if not key or key.startswith("your_"):
        raise RuntimeError("FAL_API_KEY not set in .env")
    model = os.getenv("IMAGE_MODEL_FAL", "fal-ai/flux-pro/v1.1")
    logger.info(f"[Fal.ai] model={model}")
    url = f"https://fal.run/{model}"
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    payload = {"prompt": prompt, "image_size": "landscape_16_9", "num_images": 1, "safety_tolerance": "2"}
    resp = requests.post(url, json=payload, headers=headers, timeout=90)
    resp.raise_for_status()
    image_url = resp.json()["images"][0]["url"]
    return requests.get(image_url, timeout=60).content


def _generate_pollinations(prompt: str) -> bytes:
    """Pollinations.ai — free, no key needed"""
    logger.info("[Pollinations] generating image...")
    # Use a clean, concise version of the prompt for Pollinations
    clean = re.sub(r'[^a-zA-Z0-9 ,.\-]', '', prompt).strip()
    clean = ' '.join(clean.split())  # collapse whitespace
    encoded = clean.replace(' ', '%20')
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1536&height=1024&nologo=true&enhance=true&model=flux-pro"
        f"&negative=text,words,letters,watermark,logo,signature,humans,faces,blurry,low+quality"
    )
    resp = requests.get(url, timeout=90)
    resp.raise_for_status()
    return resp.content


def generate_image(prompt: str) -> bytes:
    """Dispatch to the configured image provider. Falls back to Pollinations on error."""
    providers = {
        "openai":       _generate_openai,
        "google":       _generate_google,
        "fal":          _generate_fal,
        "pollinations": _generate_pollinations,
    }
    fn = providers.get(IMAGE_PROVIDER, _generate_pollinations)

    for attempt in range(3):
        try:
            data = fn(prompt)
            logger.info(f"Image generated: {len(data)//1024}KB")
            return data
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed ({IMAGE_PROVIDER}): {e}")
            if attempt < 2:
                wait = 30 if "429" in str(e) else 5
                logger.info(f"Waiting {wait}s before retry...")
                time.sleep(wait)

    # Final fallback
    logger.warning("Primary provider failed — falling back to Pollinations")
    return _generate_pollinations(prompt)


# ── Step 2b: Overlay blog title on image ─────────────────────────────────────

def add_title_overlay(image_bytes: bytes, title: str) -> bytes:
    """
    Add a blue/green gradient banner with the blog title at the bottom of the image.
    Returns JPEG bytes of the composed image.
    """
    from PIL import Image, ImageDraw, ImageFont
    import io

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    W, H = img.size

    # Create gradient overlay layer (bottom 28% of image)
    overlay  = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_ov  = ImageDraw.Draw(overlay)
    band_h   = int(H * 0.32)
    band_top = H - band_h

    # Draw gradient: transparent → dark teal/navy
    for y in range(band_h):
        alpha = int(220 * (y / band_h))          # 0 → 220
        # Blend teal (0,80,80) to navy (10,30,80)
        r = int(10  * (y / band_h))
        g = int(30  + 50 * (1 - y / band_h))     # 80 → 30
        b = int(80  + 40 * (y / band_h))          # 80 → 120
        draw_ov.line([(0, band_top + y), (W, band_top + y)], fill=(r, g, b, alpha))

    # Add green accent bar at very bottom
    accent_h = max(8, int(H * 0.008))
    draw_ov.rectangle([(0, H - accent_h), (W, H)], fill=(0, 200, 120, 255))

    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # --- Font setup ---
    font_size = max(36, int(W * 0.033))
    font = None
    font_paths = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arial Bold.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
        "C:/Windows/Fonts/trebucbd.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    # --- Wrap title text ---
    words    = title.split()
    lines    = []
    cur_line = ""
    max_w    = int(W * 0.90)

    for word in words:
        test = (cur_line + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_w:
            cur_line = test
        else:
            if cur_line:
                lines.append(cur_line)
            cur_line = word
    if cur_line:
        lines.append(cur_line)
    lines = lines[:3]   # max 3 lines

    # --- Position text ---
    line_h    = font_size + int(font_size * 0.25)
    total_h   = len(lines) * line_h
    text_top  = H - accent_h - int(H * 0.035) - total_h

    for i, line in enumerate(lines):
        y = text_top + i * line_h
        # Shadow
        draw.text((42, y + 3), line, font=font, fill=(0, 0, 0, 180))
        # White text
        draw.text((40, y), line, font=font, fill=(255, 255, 255, 255))

    # --- Convert back to JPEG ---
    final = img.convert("RGB")
    buf   = io.BytesIO()
    final.save(buf, format="JPEG", quality=92, optimize=True)
    logger.info(f"Title overlay added — final size: {len(buf.getvalue())//1024}KB")
    return buf.getvalue()


# ── Step 3: Upload image to WordPress Media Library ───────────────────────────

def upload_to_wordpress(image_bytes: bytes, filename: str, alt_text: str) -> int:
    """
    Upload image to WP Media Library.
    Returns the media ID.
    """
    api_base = wp_poster.API_BASE
    upload_url = f"{api_base}/media"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/jpeg",
    }

    logger.info(f"Uploading image to WordPress media library...")
    resp = requests.post(
        upload_url,
        headers=headers,
        data=image_bytes,
        auth=wp_poster._auth(),
        timeout=60,
    )
    resp.raise_for_status()
    media = resp.json()
    media_id = media["id"]

    # Set alt text
    requests.post(
        f"{api_base}/media/{media_id}",
        json={"alt_text": alt_text, "caption": alt_text},
        auth=wp_poster._auth(),
        headers={"Content-Type": "application/json"},
        timeout=15,
    )

    logger.info(f"Uploaded media ID: {media_id} — {media.get('source_url','')}")
    return media_id


# ── Step 4: Set featured image on WP post ────────────────────────────────────

def set_featured_image(wp_post_id: int, media_id: int) -> bool:
    """Set the featured image (post thumbnail) on a WordPress post."""
    api_base = wp_poster.API_BASE
    resp = requests.post(
        f"{api_base}/posts/{wp_post_id}",
        json={"featured_media": media_id},
        auth=wp_poster._auth(),
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    logger.info(f"Featured image set on WP post {wp_post_id}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def process_post(db_post: dict) -> bool:
    """Full pipeline for one post."""
    title   = db_post["title"]
    excerpt = db_post.get("meta_description") or db_post.get("content", "")[:300]
    wp_id   = db_post.get("wp_post_id")

    if not wp_id:
        logger.warning(f"Post '{title[:50]}' has no wp_post_id — skipping")
        return False

    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: [{wp_id}] {title[:60]}")
    logger.info(f"{'='*60}")

    try:
        # 1. Claude writes the image prompt
        prompt = generate_image_prompt(title, excerpt)

        # 2. Generate image (gpt-image-1 renders title text directly — no Pillow overlay needed)
        image_bytes = generate_image(prompt)

        # 3. Build filename from slug
        slug = db_post.get("slug") or re.sub(r'[^a-z0-9]+', '-', title.lower())[:50]
        filename = f"{slug}-featured.jpg"
        alt_text = f"{title} - JAMB Admission News"

        # 4. Upload to WordPress
        media_id = upload_to_wordpress(image_bytes, filename, alt_text)

        # 5. Set as featured image
        set_featured_image(wp_id, media_id)

        # 6. Update DB
        conn = db.get_conn()
        conn.execute(
            "UPDATE posts SET schema_markup=CASE WHEN schema_markup IS NULL THEN ? ELSE schema_markup END WHERE id=?",
            (json.dumps({"featured_media_id": media_id}), db_post["id"])
        )
        conn.commit()
        conn.close()

        db.log_entry("INFO", f"Featured image set for WP post {wp_id}", {
            "media_id": media_id, "prompt": prompt
        })
        logger.info(f"SUCCESS: Featured image set for post {wp_id}")
        return True

    except Exception as e:
        logger.error(f"FAILED for post {wp_id}: {e}", exc_info=True)
        db.log_entry("ERROR", f"Featured image failed for WP post {wp_id}: {str(e)[:300]}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--post-ids",
                        help="Comma-separated WP post IDs (default: all with no featured image in DB)")
    args = parser.parse_args()

    # Test WP connection
    logger.info("Testing WordPress connection...")
    if not wp_poster.test_wp_connection():
        logger.error("Cannot reach WordPress.")
        sys.exit(1)

    # Get posts to process
    conn = db.get_conn()
    if args.post_ids:
        ids = [int(i.strip()) for i in args.post_ids.split(",")]
        placeholders = ",".join("?" * len(ids))
        posts = conn.execute(
            f"SELECT * FROM posts WHERE wp_post_id IN ({placeholders}) ORDER BY id",
            ids
        ).fetchall()
    else:
        # All posts that have been pushed to WP
        posts = conn.execute(
            "SELECT * FROM posts WHERE wp_post_id IS NOT NULL AND wp_post_id > 0 ORDER BY id"
        ).fetchall()
    conn.close()

    posts = [dict(p) for p in posts]
    logger.info(f"Posts to process: {len(posts)}")

    if not posts:
        logger.info("No posts found.")
        return

    ok, fail = 0, 0
    for post in posts:
        success = process_post(post)
        if success:
            ok += 1
        else:
            fail += 1
        time.sleep(2)  # polite delay

    logger.info(f"\nFeatured images complete. Success: {ok}  Failed: {fail}")


if __name__ == "__main__":
    main()
