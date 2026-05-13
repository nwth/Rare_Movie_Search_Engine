"""Image upload service for CineSeeker.

Uploads local images to free image hosting services to get a public URL,
which can then be used with SerpApi Google Lens for identification.

Supported providers (try in order):
1. imgbb.com - requires free API key (IMGBB_API_KEY in .env)
2. telegra.ph - free, no key needed
"""

import asyncio
import base64
import io
import logging
from typing import Optional

import httpx
from PIL import Image

from config.config import settings

logger = logging.getLogger(__name__)

# Max image size for upload (3MB after compression)
MAX_UPLOAD_SIZE = 3 * 1024 * 1024


def _compress_image(data_uri: str, max_dim: int = 800) -> Optional[bytes]:
    """Resize and compress a base64 image to a reasonable upload size.

    Args:
        data_uri: data:image/...;base64,.... URI
        max_dim: Maximum dimension for the longest side

    Returns:
        Compressed JPEG bytes, or None on failure.
    """
    try:
        raw_b64 = data_uri.split(",", 1)[1]
        raw_bytes = base64.b64decode(raw_b64)
        img = Image.open(io.BytesIO(raw_bytes))

        # Resize if needed
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        # Compress to JPEG
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82, optimize=True)
        return buf.getvalue()

    except Exception as e:
        logger.warning(f"Image compression failed: {e}")
        return None


class ImgBBUploader:
    """Upload images to imgbb.com (free, API key required)."""

    BASE_URL = "https://api.imgbb.com/1/upload"

    def __init__(self):
        self.api_key = settings.imgbb_api_key

    async def upload(self, data_uri: str) -> Optional[str]:
        """Upload an image and return its public URL.

        Returns None if upload fails or no API key configured.
        """
        if not self.api_key:
            return None

        img_data = _compress_image(data_uri)
        if not img_data:
            return None

        b64 = base64.b64encode(img_data).decode()

        async with httpx.AsyncClient(timeout=20) as c:
            try:
                r = await c.post(self.BASE_URL, data={
                    "key": self.api_key,
                    "image": b64,
                })
                data = r.json()
                if data.get("success"):
                    url = data["data"]["url"]
                    logger.debug(f"ImgBB upload OK: {url}")
                    return url
                else:
                    error = data.get("error", {}).get("message", "unknown")
                    logger.warning(f"ImgBB upload failed: {error}")
                    return None
            except Exception as e:
                logger.warning(f"ImgBB request failed: {e}")
                return None


class TelegraphUploader:
    """Upload images to telegra.ph (free, no API key needed)."""

    async def upload(self, data_uri: str) -> Optional[str]:
        """Upload image via telegra.ph GraphQL API.

        telegra.ph is a free publishing platform by Telegram.
        Images uploaded here get permanent public URLs.
        """
        img_data = _compress_image(data_uri)
        if not img_data:
            return None

        files = {
            "file": ("image.jpg", img_data, "image/jpeg"),
        }

        async with httpx.AsyncClient(timeout=20) as c:
            try:
                r = await c.post("https://telegra.ph/upload", files=files)
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    src = data[0].get("src", "")
                    if src:
                        url = f"https://telegra.ph{src}" if src.startswith("/") else src
                        logger.debug(f"Telegra.ph upload OK: {url}")
                        return url
                logger.warning(f"Telegra.ph upload failed: {r.text[:200]}")
                return None
            except Exception as e:
                logger.warning(f"Telegra.ph request failed: {e}")
                return None


class ImgurUploader:
    """Upload images to imgur.com (anonymous, no API key needed).

    Uses anonymous client ID, no registration required.
    Rate limited to ~50 uploads per hour.
    """

    CLIENT_ID = "9e57cb1c4791f3a"  # Anonymous client ID for CineSeeker
    BASE_URL = "https://api.imgur.com/3/image"

    async def upload(self, data_uri: str) -> Optional[str]:
        """Upload image to imgur anonymously and return the URL."""
        img_data = _compress_image(data_uri)
        if not img_data:
            return None

        b64 = base64.b64encode(img_data).decode()
        headers = {"Authorization": f"Client-ID {self.CLIENT_ID}"}

        async with httpx.AsyncClient(timeout=20) as c:
            try:
                r = await c.post(
                    self.BASE_URL,
                    headers=headers,
                    data={"image": b64, "type": "base64"},
                )
                data = r.json()
                if data.get("success"):
                    url = data["data"]["link"]
                    logger.debug(f"Imgur upload OK: {url}")
                    return url
                error = data.get("data", {}).get("error", "unknown")
                logger.warning(f"Imgur upload failed: {error}")
                return None
            except Exception as e:
                logger.warning(f"Imgur request failed: {e}")
                return None


class ImageUploader:
    """Orchestrate image upload across multiple providers.

    Provider priority:
    1. Imgur (anonymous, no key needed, ~50/hr limit)
    2. ImgBB (if IMGBB_API_KEY configured)
    3. Telegra.ph (no key, may be blocked in some regions)
    """

    def __init__(self):
        self.providers = []

        # Provider 1: Imgur (anonymous, always available)
        self.providers.append(("imgur", ImgurUploader()))

        # Provider 2: ImgBB (if API key configured)
        imgbb = ImgBBUploader()
        if imgbb.api_key:
            self.providers.append(("imgbb", imgbb))

        # Provider 3: Telegra.ph (no key needed)
        self.providers.append(("telegraph", TelegraphUploader()))

    async def upload(self, data_uri: str) -> Optional[str]:
        """Upload image to the first available provider.

        Tries providers in order; returns the first successful URL.
        """
        if not data_uri or not data_uri.startswith("data:"):
            logger.warning("Invalid data URI, cannot upload")
            return None

        for name, provider in self.providers:
            try:
                url = await provider.upload(data_uri)
                if url:
                    return url
                logger.debug(f"{name} failed, trying next...")
            except Exception as e:
                logger.debug(f"{name} error: {e}")

        logger.error("All image upload providers failed")
        return None
