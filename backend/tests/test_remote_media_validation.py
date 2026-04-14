from io import BytesIO

import pytest
from PIL import Image

from app.services import remote_media_validation


def _png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _palette_image(used_index: int) -> Image.Image:
    image = Image.new("P", (2, 2))
    palette = [0] * 768
    palette[0:3] = [255, 0, 0]
    palette[3:6] = [0, 0, 255]
    image.putpalette(palette)
    image.putdata([used_index] * 4)
    image.info["transparency"] = 0
    return image


@pytest.mark.asyncio
async def test_inspect_remote_image_does_not_flag_opaque_rgba_png_as_alpha(monkeypatch):
    content = _png_bytes(Image.new("RGBA", (2, 2), (255, 0, 0, 255)))

    async def fake_download_remote_bytes(_url, timeout=None):
        return content, "image/png"

    monkeypatch.setattr(remote_media_validation, "download_remote_bytes", fake_download_remote_bytes)

    metadata = await remote_media_validation.inspect_remote_image("https://oss.example.com/opaque-rgba.png")

    assert metadata["format"] == "PNG"
    assert metadata["has_alpha"] is False


@pytest.mark.asyncio
async def test_inspect_remote_image_flags_visible_transparent_pixels(monkeypatch):
    image = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
    image.putpixel((0, 0), (255, 0, 0, 0))
    content = _png_bytes(image)

    async def fake_download_remote_bytes(_url, timeout=None):
        return content, "image/png"

    monkeypatch.setattr(remote_media_validation, "download_remote_bytes", fake_download_remote_bytes)

    metadata = await remote_media_validation.inspect_remote_image("https://oss.example.com/transparent.png")

    assert metadata["has_alpha"] is True


@pytest.mark.asyncio
async def test_inspect_remote_image_ignores_unused_palette_transparency(monkeypatch):
    content = _png_bytes(_palette_image(used_index=1))

    async def fake_download_remote_bytes(_url, timeout=None):
        return content, "image/png"

    monkeypatch.setattr(remote_media_validation, "download_remote_bytes", fake_download_remote_bytes)

    metadata = await remote_media_validation.inspect_remote_image("https://oss.example.com/palette.png")

    assert metadata["has_alpha"] is False
