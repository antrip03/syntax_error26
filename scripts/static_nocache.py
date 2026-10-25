"""Serve a folder like `python -m http.server`, but tell browsers not to cache (the game's ES modules change
together; a cached old module next to a new one breaks the boot). Usage: static_nocache.py <port> <dir>"""
import functools
import http.server
import sys


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()


port, root = int(sys.argv[1]), sys.argv[2]
http.server.ThreadingHTTPServer(("", port), functools.partial(NoCache, directory=root)).serve_forever()
