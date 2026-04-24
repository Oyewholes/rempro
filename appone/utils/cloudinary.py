import time

import cloudinary.uploader
import cloudinary.utils


def upload_to_cloudinary(file, file_type, freelancer_id):
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
