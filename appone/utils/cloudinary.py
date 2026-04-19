import time
import requests
import cloudinary.uploader
import cloudinary.utils
import logging

logger = logging.getLogger(__name__)


def upload_to_cloudinary(file, file_type, freelancer_id):
    """
    Upload any file to Cloudinary and return the secure URL (public_id).

    Args:
        file:          File-like object opened in binary mode.
        file_type:     Used as the public_id prefix and subfolder,
                       e.g. 'cv', 'live_photo', 'id_card'
        freelancer_id: UUID that makes the public_id unique per freelancer.

    Returns:
        str: Cloudinary public_id on success.

    Raises:
        Exception: Propagates Cloudinary errors — never swallows silently.
    """
    resource_type = "image" if file_type in ("live_photo", "id_card") else "raw"

    result = cloudinary.uploader.upload(
        file,
        folder=f"virtual_citizenship/{file_type}s",
        public_id=f"{file_type}_{freelancer_id}",
        resource_type=resource_type,
        type="authenticated",
        overwrite=True,
    )
    return result["public_id"]


def generate_signed_url(
    public_id: str, resource_type: str = "image", expiry_seconds: int = 300
) -> str:
    """
    Generate a time-limited signed Cloudinary URL.

    Uses private_download_url so the signature and expiry are validated on
    every request — CDN caching is bypassed entirely.
    """
    fmt = (
        "png"
        if resource_type == "image"
        else (public_id.rsplit(".", 1)[-1] if "." in public_id else "pdf")
    )
    expires_at = int(time.time()) + expiry_seconds

    return cloudinary.utils.private_download_url(
        public_id,
        fmt,
        resource_type=resource_type,
        expires_at=expires_at,
        attachment=False,
    )


def generate_signed_download_url(
    public_id: str,
    filename: str,
    resource_type: str = "image",
    expiry_seconds: int = 300,
) -> str:
    """
    Same as generate_signed_url but forces a file download with a custom filename.
    """
    fmt = (
        "png"
        if resource_type == "image"
        else (public_id.rsplit(".", 1)[-1] if "." in public_id else "pdf")
    )
    expires_at = int(time.time()) + expiry_seconds

    return cloudinary.utils.private_download_url(
        public_id,
        fmt,
        resource_type=resource_type,
        expires_at=expires_at,
        attachment=True,
    )
