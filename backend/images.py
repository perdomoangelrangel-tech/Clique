"""Checking an uploaded picture by looking inside it. Standard library only.

A profile picture is accepted only if all of this is true:
  * it is really a PNG, a JPEG or a WebP, judged by the bytes themselves (never by the file name or the type the browser
    claims, though the claimed type must agree with what is found),
  * its structure is complete and in order (PNG chunks with correct checksums ending in IEND, a JPEG that reaches its end
    marker, a WebP whose length matches its header) and nothing extra is stuck on the end, which is how a picture is
    turned into something else (a "polyglot"),
  * its width and height, read from the file's own header, are within the allowed range,
  * it is not animated and not larger than the size limit.
Anything else is refused with a plain explanation. The file is stored exactly as received (never re-saved), under a name
the server makes up, and is only ever served back with the type found here.
"""
import struct
import zlib

from . import economy
from .util import bad

TYPES = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}
EXT = {"png": "png", "jpeg": "jpg", "webp": "webp"}


def _png(b):
    if not b.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    pos, width, height, first, idat = 8, 0, 0, True, False
    while pos + 12 <= len(b):
        length, kind = struct.unpack(">I4s", b[pos:pos + 8])
        end = pos + 12 + length
        if end > len(b):
            raise bad("That PNG is cut short")
        if zlib.crc32(b[pos + 4:end - 4]) & 0xFFFFFFFF != struct.unpack(">I", b[end - 4:end])[0]:
            raise bad("That PNG is damaged")
        if first:
            if kind != b"IHDR" or length != 13:
                raise bad("That PNG does not start the way a PNG should")
            width, height = struct.unpack(">II", b[pos + 8:pos + 16])
            first = False
        elif kind == b"acTL":
            raise bad("Animated pictures are not allowed")
        elif kind == b"IDAT":
            idat = True
        elif kind == b"IEND":
            if end != len(b):
                raise bad("That file has extra data after the end of the picture")
            if not idat:
                raise bad("That PNG has no picture in it")
            return "png", width, height
        pos = end
    raise bad("That PNG never ends")


def _jpeg(b):
    if not b.startswith(b"\xff\xd8\xff"):
        return None
    pos, dims = 2, None
    while pos + 4 <= len(b):
        if b[pos] != 0xFF:
            raise bad("That JPEG is damaged")
        while pos < len(b) and b[pos] == 0xFF:                     # fill bytes
            pos += 1
        marker = b[pos]
        pos += 1
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if marker == 0xD9:
            break
        if pos + 2 > len(b):
            raise bad("That JPEG is cut short")
        length = struct.unpack(">H", b[pos:pos + 2])[0]
        if length < 2 or pos + length > len(b):
            raise bad("That JPEG is damaged")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", b[pos + 3:pos + 7])
            dims = (width, height)
        if marker == 0xDA:                                          # start of the compressed data: find the end marker
            tail = b.rfind(b"\xff\xd9")
            if tail == -1 or tail != len(b) - 2:
                raise bad("That JPEG does not end properly, or has extra data after it")
            if not dims:
                raise bad("That JPEG has no size in it")
            return "jpeg", dims[0], dims[1]
        pos += length
    raise bad("That JPEG is damaged")


def _webp(b):
    if not (b.startswith(b"RIFF") and b[8:12] == b"WEBP"):
        return None
    if struct.unpack("<I", b[4:8])[0] + 8 != len(b):
        raise bad("That WebP is damaged, or has extra data after it")
    kind = b[12:16]
    if kind == b"VP8 " and len(b) >= 30 and b[23:26] == b"\x9d\x01\x2a":
        w, h = struct.unpack("<HH", b[26:30])
        return "webp", w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L" and len(b) >= 25 and b[20] == 0x2F:
        bits = struct.unpack("<I", b[21:25])[0]
        return "webp", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X" and len(b) >= 30:
        if b[20] & 0x02:
            raise bad("Animated pictures are not allowed")
        w = 1 + int.from_bytes(b[24:27], "little")
        h = 1 + int.from_bytes(b[27:30], "little")
        return "webp", w, h
    raise bad("That WebP is not one we can read")


def inspect(data, claimed=None):
    """(kind, width, height) of a valid picture, or raises a 400 saying what is wrong."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise bad("Choose a picture first")
    if len(data) > economy.AVATAR_MAX_BYTES:
        raise bad(f"That picture is too big. The limit is {economy.AVATAR_MAX_BYTES / 1_000_000:.1f} MB.", 413)
    data = bytes(data)
    found = _png(data) or _jpeg(data) or _webp(data)
    if not found:
        raise bad("That is not a PNG, JPEG or WebP picture")
    kind, width, height = found
    if claimed and claimed.split(";")[0].strip().lower() not in (TYPES[kind], "application/octet-stream") and not (
            kind == "jpeg" and claimed.lower() == "image/jpg"):
        raise bad("The file says it is one kind of picture but is another")
    low, high = economy.AVATAR_MIN_PX, economy.AVATAR_MAX_PX
    if width < low or height < low:
        raise bad(f"That picture is too small. Both sides must be at least {low} pixels.")
    if width > high or height > high:
        raise bad(f"That picture is too large. Both sides must be at most {high} pixels.")
    if width > 4 * height or height > 4 * width:
        raise bad("That picture is too long and thin. Pick one that is closer to square.")
    return kind, width, height
