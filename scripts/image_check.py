"""Checking an image someone pasted (task 4 M5d, M5e): is it really a PNG, JPEG or WebP image,
whole, and of a sensible size? Used for the notes' pasted images (notes_store.save_asset) and
for formula recognition (formula_ocr).

The type comes from the bytes, never from a file name, an extension or what the browser said:
- the first bytes must be a PNG, JPEG or WebP signature (anything else, SVG and HTML included,
  is refused: they can carry scripts);
- Pillow must read it as that same format, with one frame (no animations);
- its size is checked from the header *before* the pixels are decoded (no decompression
  bombs: at most MAX_SIDE pixels a side and MAX_PIXELS in all), then it is decoded in full,
  so a truncated or damaged file is refused too.
The bytes themselves are kept as they came: nothing is converted or re-encoded.
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

from PIL import Image

MAX_BYTES = 10 * 1024 * 1024  # 10 MiB: a full-screen 4K screenshot as PNG is 1–6 MB
MAX_SIDE = 16_384  # pixels a side (WebP's own limit is 16,383)
MAX_PIXELS = 40_000_000  # an 8K screen (7680 × 4320) is 33.2 million

# kind: (Pillow's format name, the extension used for a new file, the MIME type served)
KINDS = {
    "png": ("PNG", ".png", "image/png"),
    "jpeg": ("JPEG", ".jpg", "image/jpeg"),
    "webp": ("WEBP", ".webp", "image/webp"),
}
EXTENSIONS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}


class ImageError(ValueError):
    """Not an image this tool takes (the message says why, for the page)."""


@dataclass(frozen=True)
class ImageInfo:
    kind: str  # png, jpeg or webp
    width: int
    height: int

    @property
    def extension(self) -> str:
        return KINDS[self.kind][1]

    @property
    def mime(self) -> str:
        return KINDS[self.kind][2]


def sniff(data: bytes) -> str | None:
    """png, jpeg or webp from the first bytes alone; None for anything else."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _open(data: bytes, kind: str) -> Image.Image:
    try:
        with warnings.catch_warnings():
            # (Pillow's own bomb warning: the limits below are checked anyway, before decoding)
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data), formats=[KINDS[kind][0]])
    except Image.DecompressionBombError:
        raise ImageError("the image is too large (too many pixels)") from None
    except Exception:  # Pillow's UnidentifiedImageError, SyntaxError, struct.error, ...
        raise ImageError(f"this isn't a readable {kind.upper()} image") from None
    if image.format != KINDS[kind][0]:
        raise ImageError("the image's contents don't match its type")
    return image


def _check_size(width: int, height: int) -> None:
    if width < 1 or height < 1:
        raise ImageError("the image has no pixels")
    if width > MAX_SIDE or height > MAX_SIDE or width * height > MAX_PIXELS:
        raise ImageError(
            f"the image is too large: {width} × {height} pixels (at most {MAX_SIDE:,} a side "
            f"and {MAX_PIXELS // 1_000_000} million in all)"
        )


def decode(data: bytes) -> tuple[ImageInfo, Image.Image]:
    """The checked image and its decoded pixels (for formula recognition). ImageError if the
    bytes aren't a whole PNG, JPEG or WebP image within the limits."""
    if not isinstance(data, bytes | bytearray) or not data:
        raise ImageError("no image")
    if len(data) > MAX_BYTES:
        raise ImageError(f"the image is larger than {MAX_BYTES // (1024 * 1024)} MB")
    kind = sniff(bytes(data[:16]))
    if kind is None:
        raise ImageError("only PNG, JPEG and WebP images can be pasted")
    image = _open(bytes(data), kind)
    try:
        _check_size(*image.size)  # from the header: nothing decoded yet
        if getattr(image, "n_frames", 1) != 1:
            raise ImageError("animated images aren't supported")
        image.verify()  # PNG CRCs and end chunks, not just decodable pixel data
        image.close()
        image = _open(bytes(data), kind)  # verify() consumes the image's input
        image.load()  # the whole image: a truncated or damaged one fails here
        _check_size(*image.size)
    except ImageError:
        image.close()
        raise
    except Image.DecompressionBombError:
        image.close()
        raise ImageError("the image is too large (too many pixels)") from None
    except Exception:
        image.close()
        raise ImageError(f"the {kind.upper()} image is damaged or incomplete") from None
    return ImageInfo(kind, image.width, image.height), image


def inspect(data: bytes) -> ImageInfo:
    """decode(), keeping only what was found out (the pixels are dropped)."""
    info, image = decode(data)
    image.close()
    return info
