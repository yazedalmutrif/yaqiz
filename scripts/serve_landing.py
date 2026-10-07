"""Serve the built landing page (site/dist) on http://127.0.0.1:4180 with correct file types.

Windows can map .js to text/plain, which browsers refuse for module scripts, so the types are set here.
Stop it by closing the window (or Ctrl+C).
"""
import functools
import http.server
import mimetypes
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "site" / "dist"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4180

mimetypes.init()
for ext, kind in ((".js", "text/javascript"), (".mjs", "text/javascript"), (".css", "text/css"),
                  (".html", "text/html"), (".svg", "image/svg+xml"), (".webp", "image/webp"),
                  (".woff2", "font/woff2"), (".woff", "font/woff"), (".json", "application/json")):
    mimetypes.add_type(kind, ext)

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
print(f"Landing page: http://127.0.0.1:{PORT}  (close this window to stop)")
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler).serve_forever()
