"""RERUN server: the Omniguide as a live cable box.

Serves the guide at http://localhost:8100 — click a channel row (or press
its number) to tune. The server owns one VLC at a time: tuning flips the
channel, it never stacks windows. The grid redraws itself every minute.
"""
import datetime as dt
import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import engine
import guide

_vlc_lock = threading.Lock()
_vlc_proc = None


def tune(number):
    global _vlc_proc
    lib = engine.load_library()
    durs = engine.Durations()
    channels = {c["number"]: c for c in engine.load_channels()}
    if number not in channels:
        return {"error": f"no channel {number}"}
    ch = channels[number]
    sched = engine.schedule_at(ch, lib, durs, dt.datetime.now())
    durs.save()
    if not sched:
        return {"error": f"channel {number} resolved no items"}
    args = engine.vlc_args(engine.load_config(), sched)
    with _vlc_lock:
        if _vlc_proc and _vlc_proc.poll() is None:
            _vlc_proc.terminate()
        _vlc_proc = subprocess.Popen(args)
    return {"channel": number, "name": ch["name"],
            "now": engine.display_name(sched["item"]),
            "offset_min": int(sched["offset"] // 60)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, guide.html_guide_string(live=True))
        elif self.path.startswith("/tune/"):
            try:
                result = tune(int(self.path.split("/")[2]))
            except (ValueError, IndexError):
                result = {"error": "bad channel"}
            self._send(200, json.dumps(result), "application/json")
        elif self.path == "/schedule.txt":
            # pipe-delimited feed for the VLC Lua extension:
            # number|name|now-playing|offset-seconds|path
            lib = engine.load_library()
            durs = engine.Durations()
            now = dt.datetime.now()
            lines = []
            for ch in engine.load_channels():
                sched = engine.schedule_at(ch, lib, durs, now)
                if sched:
                    lines.append("|".join([
                        str(ch["number"]), ch["name"],
                        engine.display_name(sched["item"]),
                        str(int(sched["offset"])),
                        sched["item"]["path"]]))
            durs.save()
            self._send(200, "\n".join(lines), "text/plain; charset=utf-8")
        else:
            self._send(404, "static")


def main(port=8100):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"RERUN on the air: http://localhost:{port}  (ctrl+c to sign off)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
