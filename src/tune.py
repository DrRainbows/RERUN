"""RERUN CLI.

  python src/tune.py --scan         rebuild library.json
  python src/tune.py --guide        terminal guide (now/next per channel)
  python src/tune.py --html         generate + open the Omniguide grid
  python src/tune.py 7              tune channel 7: VLC joins in progress
  add --only 1,6,7 to limit guide builds to specific channels
"""
import datetime as dt
import os
import subprocess
import sys

import engine
import guide
import library

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_only(args):
    if "--only" in args:
        vals = args[args.index("--only") + 1]
        return {int(v) for v in vals.split(",")}
    return None


def tune(number):
    lib = engine.load_library()
    durs = engine.Durations()
    channels = {c["number"]: c for c in engine.load_channels()}
    if number not in channels:
        print(f"no channel {number}. dial: {sorted(channels)}")
        return 1
    ch = channels[number]
    sched = engine.schedule_at(ch, lib, durs, dt.datetime.now())
    durs.save()
    if not sched:
        print(f"channel {number} resolved no items - check its definition")
        return 1
    name = engine.display_name(sched["item"])
    print(f"tuning {number} {ch['name']}: {name} "
          f"({int(sched['offset'] // 60)}m in)")
    cfg = engine.load_config()
    args = [cfg["vlc"], "--fullscreen", "--no-video-title-show",
            sched["item"]["path"], f":start-time={int(sched['offset'])}"]
    for _t, item in sched["upcoming"][:3]:
        args.append(item["path"])
    subprocess.Popen(args)
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 0
    if args[0] == "--scan":
        return library.main()
    if args[0] == "--guide":
        guide.terminal_guide(only=parse_only(args))
        return 0
    if args[0] == "--html":
        path = guide.html_guide(only=parse_only(args))
        print(f"omniguide: {path}")
        try:
            os.startfile(path)
        except OSError:
            pass
        return 0
    return tune(int(args[0]))


if __name__ == "__main__":
    sys.exit(main())
