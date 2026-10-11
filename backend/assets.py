"""Serving the site's own files (pages, scripts, styles, fonts, pictures) quickly.

Three things make the first visit and every later one cheaper:
  * text files are compressed once and kept in memory (re-done only if the file changes on disk),
  * every file carries an ETag, so a browser that already has it gets a tiny "not modified" answer instead of the file,
  * the heavy, rarely changing files (fonts and the casino pictures) may be kept by the browser for a while.
Pages, scripts and styles are always re-checked, so a new deploy shows up on the next load without clearing anything.
"""
import gzip
import hashlib
import mimetypes
import os
import posixpath
import re
import threading

from . import config

_CACHE = {}                      # full path -> (mtime_ns, size, Asset)
_LOCK = threading.Lock()

# Kept by the browser without asking again: (path prefix, how long). The picture or font can still be swapped:
# people just see the new one after that time (or straight away on a hard refresh).
LONG_LIVED = (("/fonts/", 604800), ("/casino-icons/", 86400))

COMPRESSIBLE = ("text/", "application/javascript", "application/json", "image/svg+xml")


class Asset:
    __slots__ = ("body", "gz", "etag", "ctype", "cache")

    def __init__(self, body, ctype, cache):
        self.body, self.ctype, self.cache = body, ctype, cache
        digest = hashlib.sha1(body).hexdigest()[:20]
        self.etag = f'"{digest}"'
        packed = gzip.compress(body, 6) if len(body) > 600 and ctype.startswith(COMPRESSIBLE) else None
        self.gz = packed if packed is not None and len(packed) < len(body) else None

    def etag_for(self, gzipped):
        return self.etag[:-1] + '-gz"' if gzipped else self.etag


def cache_header(url_path):
    for prefix, seconds in LONG_LIVED:
        if url_path.startswith(prefix):
            return f"public, max-age={seconds}, stale-while-revalidate={seconds * 7}"
    return "no-cache"            # keep it, but check with the server first (a 304 costs next to nothing)


# ---- which scripts the first screen needs, so the browser can fetch them all at once -----------------------------

_IMPORT = re.compile(r"""(?:import|export)\s[^'";]*?from\s*['"]([^'"]+)['"]|import\s*['"]([^'"]+)['"]""")
FIRST_SCREEN = ("/js/app.js", "/js/views/markets.js")        # the page shell, and where people land
_preload = None


def _local_imports(url_path):
    full = os.path.join(config.STATIC_DIR, url_path.lstrip("/"))
    try:
        with open(full, "r", encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return []
    out = []
    for a, b in _IMPORT.findall(src):
        spec = a or b
        if spec.startswith("."):           # URL paths always use "/", whatever the computer (os.path gives "\" on Windows)
            out.append(posixpath.normpath(posixpath.join(posixpath.dirname(url_path), spec)))
    return out


def preload_list():
    """Every script the first screen pulls in, directly or through other scripts, in discovery order."""
    global _preload
    if _preload is None:
        seen, queue = [], list(FIRST_SCREEN)
        while queue:
            p = queue.pop(0)
            if p in seen:
                continue
            seen.append(p)
            queue.extend(_local_imports(p))
        _preload = seen
    return _preload


def _with_preload(html):
    tags = "".join(f'<link rel="modulepreload" href="{p}">\n' for p in preload_list())
    return html.replace("</head>", tags + "</head>", 1)


# ---- lookup -------------------------------------------------------------------------------------------------------

def find(url_path):
    """The file for a URL path, or the page shell for anything that is not a file (the site is a single-page app)."""
    rel = url_path.lstrip("/") or "index.html"
    full = os.path.normpath(os.path.join(config.STATIC_DIR, rel))
    if not full.startswith(config.STATIC_DIR + os.sep) or not os.path.isfile(full):
        full = os.path.join(config.STATIC_DIR, "index.html")
    return full


def get(full):
    st = os.stat(full)
    with _LOCK:
        hit = _CACHE.get(full)
        if hit and hit[0] == st.st_mtime_ns and hit[1] == st.st_size:
            return hit[2]
    with open(full, "rb") as f:
        data = f.read()
    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
        ctype += "; charset=utf-8"
    url = "/" + os.path.relpath(full, config.STATIC_DIR).replace(os.sep, "/")
    if url == "/index.html":
        data = _with_preload(data.decode("utf-8")).encode("utf-8")
    asset = Asset(data, ctype, cache_header(url))
    with _LOCK:
        _CACHE[full] = (st.st_mtime_ns, st.st_size, asset)
    return asset


def matches(if_none_match, etag):
    """Does the browser's If-None-Match header name this version?"""
    if not if_none_match:
        return False
    want = etag.strip('"')
    for tag in if_none_match.split(","):
        tag = tag.strip()
        if tag == "*" or tag.removeprefix("W/").strip('"') == want:
            return True
    return False
