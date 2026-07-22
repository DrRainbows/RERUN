"""RERUN.exe - the station in your system tray.

Tray mode (default): starts the server (unless one is already on the air),
puts the antenna in the tray. Right-click: Omniguide, quick-tune any
channel, Sign off. No browser involved - the Omniguide opens in a native
window via the OS webview.

The exe expects to live in the RERUN folder (next to rerun.json and
channels/).
"""
import os
import socket
import subprocess
import sys
import threading
import urllib.request

PORT = 8100


def server_alive():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            return True
    except OSError:
        return False


def viewer():
    import webview
    webview.create_window(
        "RERUN · Omniguide", f"http://localhost:{PORT}",
        width=1180, height=760, background_color="#000022")
    webview.start()


def tray_icon_image():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 34, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([4, 16, 60, 56], outline=(255, 204, 0, 255), width=4)
    d.line([20, 16, 32, 4], fill=(255, 204, 0, 255), width=4)
    d.line([44, 16, 32, 4], fill=(255, 204, 0, 255), width=4)
    d.rectangle([14, 26, 34, 46], fill=(34, 51, 153, 255))
    return img


def spawn_self(*args):
    if getattr(sys, "frozen", False):
        subprocess.Popen([sys.executable, *args])
    else:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), *args])


def http_tune(number):
    try:
        urllib.request.urlopen(f"http://localhost:{PORT}/tune/{number}",
                               timeout=15).read()
    except OSError:
        pass


def tray():
    if not server_alive():
        import server
        threading.Thread(target=server.main, args=(PORT,),
                         daemon=True).start()
    import engine
    import pystray

    def tune_action(number):
        return lambda: threading.Thread(target=http_tune, args=(number,),
                                        daemon=True).start()

    channel_items = [
        pystray.MenuItem(f"{c['number']}  {c['name']}",
                         tune_action(c["number"]))
        for c in engine.load_channels()]
    menu = pystray.Menu(
        pystray.MenuItem("Omniguide", lambda: spawn_self("--viewer"),
                         default=True),
        pystray.MenuItem("Tune", pystray.Menu(*channel_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sign off", lambda icon: icon.stop()))
    icon = pystray.Icon("RERUN", tray_icon_image(), "RERUN - always on",
                        menu)
    icon.run()
    os._exit(0)


def main():
    if "--viewer" in sys.argv:
        viewer()
    else:
        tray()


if __name__ == "__main__":
    main()
