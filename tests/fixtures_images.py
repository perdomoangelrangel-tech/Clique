"""Tiny real pictures (64x64) for the upload tests. Made once; nothing here needs an image library to run."""
import base64
import struct
import zlib

JPEG_64 = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIfIiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD0CvmKivp2vm/+RT/f5/la339yfhCvmKivp2j/AJFP9/n+Vrff3D4Qr5ior6do/wCRT/f5/la339w+EK+YqK+naP8AkU/3+f5Wt9/cPhCvmKivp2j/AJFP9/n+Vrff3D4Qr5ior6do/wCRT/f5/la339w+EK+YqK+naP8AkU/3+f5Wt9/cPhCvmKivp2j/AJFP9/n+Vrff3D4Qr5ior6do/wCRT/f5/la339w+EK+YqK+naP8AkU/3+f5Wt9/cPhCvmKivp2j/AJFP9/n+Vrff3D4Qr5ior6do/wCRT/f5/la339w+EK+YqK+naP8AkU/3+f5Wt9/cPhCvmKivp2j/AJFP9/n+Vrff3D4Qr5ior6do/wCRT/f5/la339w+EK+YqK+naP8AkU/3+f5Wt9/cPhP/2Q=="
WEBP_64 = "UklGRqIAAABXRUJQVlA4IJYAAAAQBwCdASpAAEAAAoBCJaAb3+h+3/q3/mgPwD+AfgB+gH8AncwEfnf4AbOJ1X8AP1g3gGZ+Bu0/tk/7g5gT5EI8UAD+4d1ZcU+IAudIyP6UOAk7ghZkB5htuVJhx9cOH1+/P67aeK+kJ3uPQjpw6iRgjqyYKflhPfbTtskuso+UKv8HkS6smCn42/2q5gKUNBRbiavkAAA="
WEBP_LOSSLESS_64 = "UklGRjgAAABXRUJQVlA4TCwAAAAvP8APAA9wBvQ74F4BZf4DD4ratoHKn3QA9NieEf0nG6Ao7N5A7hXuff9vAA=="


def png(width=64, height=64, color=(198, 244, 50), extra_chunks=(), trailing=b"", break_crc=False):
    """A valid PNG made from scratch (flat colour), optionally damaged or with extra chunks / trailing bytes."""
    def chunk(kind, data, bad=False):
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", (crc ^ 1) if bad else crc)
    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0), break_crc)
    for kind, data in extra_chunks:
        out += chunk(kind, data)
    out += chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return out + trailing


JPEG = base64.b64decode(JPEG_64)
WEBP = base64.b64decode(WEBP_64)
WEBP_LL = base64.b64decode(WEBP_LOSSLESS_64)
