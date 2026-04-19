import io
import requests
import logging
from PIL import Image, ImageDraw, ImageFont, ImageOps

logger = logging.getLogger(__name__)


def _fetch_image_from_url(url: str) -> Image.Image | None:
    """Download an image from a URL and return a PIL Image, or None on failure."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None


def _make_circle_mask(size: tuple[int, int]) -> Image.Image:
    """Return a white-on-black circular mask for the given (width, height)."""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
    return mask


def generate_digital_id_card(freelancer_profile) -> io.BytesIO | None:
    """
    Generate a digital ID card image for the freelancer.

    - Fetches the live photo from Cloudinary and composites it as a circular avatar.
    - Returns raw PNG bytes as an io.BytesIO ready for upload_to_cloudinary().
    - Falls back gracefully when the live photo is unavailable.

    Returns:
        io.BytesIO with PNG data on success, or None on failure.
    """
    from appone.utils.cloudinary import generate_signed_url

    try:
        WIDTH, HEIGHT = 700, 420
        DARK_BG = "#ffffff"
        HEADER_BG = "#FCFCFD"
        ACCENT = "#2b00ff"
        WHITE = "#080000"
        GREY = "#FCFBFB"

        img = Image.new("RGB", (WIDTH, HEIGHT), color=DARK_BG)
        draw = ImageDraw.Draw(img)

        # Fonts
        try:
            font_title = ImageFont.truetype("arial.ttf", 22)
            font_sub = ImageFont.truetype("arial.ttf", 13)
            font_label = ImageFont.truetype("arial.ttf", 14)
            font_value = ImageFont.truetype("arial.ttf", 16)
            font_small = ImageFont.truetype("arial.ttf", 12)
        except OSError:
            font_title = font_sub = font_label = font_value = font_small = (
                ImageFont.load_default()
            )

        # Header bar
        draw.rectangle([(0, 0), (WIDTH, 72)], fill=HEADER_BG)
        draw.text((20, 16), "VIRTUAL CITIZENSHIP", fill=ACCENT, font=font_title)
        draw.text((20, 48), "Digital Work Permit", fill=WHITE, font=font_sub)
        draw.rectangle([(0, 72), (WIDTH, 75)], fill=ACCENT)

        # Live photo (circular avatar)
        PHOTO_SIZE = 110
        PHOTO_X = WIDTH - PHOTO_SIZE - 30
        PHOTO_Y = 90
        BORDER_PAD = 4

        live_photo_loaded = False
        if freelancer_profile.live_photo:
            try:
                fetchable_url = generate_signed_url(
                    freelancer_profile.live_photo,
                    resource_type="image",
                    expiry_seconds=60,
                )
                raw_photo = _fetch_image_from_url(fetchable_url)
            except Exception:
                raw_photo = None

            if raw_photo:
                raw_photo = ImageOps.fit(
                    raw_photo, (PHOTO_SIZE, PHOTO_SIZE), method=Image.LANCZOS
                )
                draw.ellipse(
                    [
                        PHOTO_X - BORDER_PAD,
                        PHOTO_Y - BORDER_PAD,
                        PHOTO_X + PHOTO_SIZE + BORDER_PAD,
                        PHOTO_Y + PHOTO_SIZE + BORDER_PAD,
                    ],
                    fill=ACCENT,
                )
                mask = _make_circle_mask((PHOTO_SIZE, PHOTO_SIZE))
                img.paste(raw_photo, (PHOTO_X, PHOTO_Y), mask)
                live_photo_loaded = True

        if not live_photo_loaded:
            draw.ellipse(
                [PHOTO_X, PHOTO_Y, PHOTO_X + PHOTO_SIZE, PHOTO_Y + PHOTO_SIZE],
                fill=HEADER_BG,
                outline=ACCENT,
                width=2,
            )
            draw.text(
                (PHOTO_X + PHOTO_SIZE // 2 - 20, PHOTO_Y + PHOTO_SIZE // 2 - 8),
                "NO PHOTO",
                fill=GREY,
                font=font_small,
            )

        # Info fields
        TEXT_X = 30
        y = 95
        LINE_GAP = 38

        def draw_field(label: str, value: str, y_pos: int):
            draw.text((TEXT_X, y_pos), label, fill=ACCENT, font=font_label)
            draw.text((TEXT_X, y_pos + 16), value, fill=WHITE, font=font_value)

        full_name = (
            f"{freelancer_profile.first_name} {freelancer_profile.last_name}".strip()
        )
        draw_field("Full Name", full_name or "—", y)
        y += LINE_GAP + 6

        draw_field("Digital ID", str(freelancer_profile.digital_id), y)
        y += LINE_GAP + 6

        status_label = freelancer_profile.verification_status.upper()
        status_color = (
            "#3300ff" if freelancer_profile.verification_status == "verified" else "#ff0000"
        )
        draw.text((TEXT_X, y), "Status", fill=ACCENT, font=font_label)
        draw.text((TEXT_X, y + 16), status_label, fill=status_color, font=font_value)
        y += LINE_GAP + 6

        if freelancer_profile.approved_countries:
            countries = ", ".join(freelancer_profile.approved_countries[:4])
            draw_field("Approved For", countries, y)
            y += LINE_GAP + 6

        if freelancer_profile.skills:
            skills_str = ", ".join(str(s) for s in freelancer_profile.skills[:5])
            if len(skills_str) > 45:
                skills_str = skills_str[:42] + "…"
            draw_field("Skills", skills_str, y)

        # Footer bar
        draw.rectangle([(0, HEIGHT - 48), (WIDTH, HEIGHT)], fill=HEADER_BG)
        draw.text(
            (20, HEIGHT - 32),
            "Issued by Virtual Citizenship Platform  |  virtualcitizenship.com",
            fill=GREY,
            font=font_small,
        )

        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True)
        output.seek(0)
        return output

    except Exception as exc:
        logger.error("generate_digital_id_card FAILED: %r", exc)
        return None
