"""The rerun engine: deterministic broadcast math.

A channel's schedule is a pure function of wall-clock time. Every channel has
been airing since the epoch; (now - epoch) mod loop-length finds the current
item and how deep we are into it. Shuffle channels reshuffle per loop with a
seed derived from (channel seed, loop index), so the order varies loop to loop
but any two calls agree on what is playing.
"""
import datetime as dt
import json
import os
import random
import subprocess
import sys

if getattr(sys, "frozen", False):
    HERE = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUR_CACHE = os.path.join(HERE, "durations.json")


def load_config():
    with open(os.path.join(HERE, "rerun.json"), encoding="utf-8-sig") as f:
        return json.load(f)


def load_library():
    with open(os.path.join(HERE, "library.json"), encoding="utf-8-sig") as f:
        return json.load(f)


def load_channels():
    chdir = os.path.join(HERE, "channels")
    out = []
    for n in sorted(os.listdir(chdir)):
        if n.endswith(".json"):
            with open(os.path.join(chdir, n), encoding="utf-8-sig") as f:
                out.append(json.load(f))
    return sorted(out, key=lambda c: c["number"])


class Durations:
    def __init__(self):
        self.cache = {}
        if os.path.exists(DUR_CACHE):
            with open(DUR_CACHE, encoding="utf-8-sig") as f:
                self.cache = json.load(f)
        self.dirty = 0

    def get(self, path):
        if path in self.cache:
            return self.cache[path]
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path],
                capture_output=True, text=True, timeout=60).stdout.strip()
            dur = float(out)
        except Exception:
            dur = 0.0
        self.cache[path] = dur
        self.dirty += 1
        if self.dirty >= 25:
            self.save()
        return dur

    def save(self):
        with open(DUR_CACHE, "w", encoding="utf-8-sig") as f:
            json.dump(self.cache, f)
        self.dirty = 0


def vlc_args(cfg, sched):
    """Build the VLC invocation for a resolved schedule position.

    --one-instance: flips hand the new program to the already-open window
    over VLC's IPC (offset included), so the window - and wherever the
    viewer dragged it - never goes away between channels.
    """
    args = [cfg["vlc"], "--one-instance", "--no-video-title-show",
            "--no-qt-video-autoresize"]
    if cfg.get("fullscreen"):
        args.append("--fullscreen")
    args += [sched["item"]["path"], f":start-time={int(sched['offset'])}"]
    for _t, item in sched["upcoming"][:3]:
        args.append(item["path"])
    return args


def resolve_items(channel, library):
    """Channel definition -> ordered base playlist (before loop shuffling)."""
    picked = []
    if "movies" in channel:
        for query in channel["movies"]:
            q = query.lower().strip()
            matches = [i for i in library if i["kind"] == "movie"
                       and q in f"{i['title']} ({i['year']})"]
            if matches:
                picked.append(max(matches, key=lambda m: m["size"]))
    if "movies_all" in channel:
        hits = []
        for query in channel["movies_all"]:
            q = query.lower().strip()
            hits.extend(i for i in library if i["kind"] == "movie"
                        and q in f"{i['title']} ({i['year']})")
        hits.sort(key=lambda h: (h["year"], h["title"]))
        picked.extend(hits)
    if "series" in channel:
        eps = [i for i in library if i["kind"] == "tv"
               and i["series"] in [s.lower() for s in channel["series"]]]
        eps.sort(key=lambda e: (e["season"], e["episode"]))
        picked.extend(eps)
    if "folders" in channel:
        for folder in channel["folders"]:
            fl = folder.lower().rstrip("\\")
            hits = [i for i in library
                    if os.path.dirname(i["path"]).lower().startswith(fl)]
            hits.sort(key=lambda h: h["path"])
            picked.extend(hits)
    seen = set()
    out = []
    for p in picked:
        if p["path"] not in seen:
            seen.add(p["path"])
            out.append(p)
    return out


def loop_order(items, channel, loop_index):
    if channel.get("type") == "shuffle":
        order = list(items)
        random.Random(f"{channel.get('seed', 0)}:{loop_index}").shuffle(order)
        return order
    return items


def schedule_at(channel, library, durs, when, lookahead=4):
    """-> {now: {item, offset, remaining}, upcoming: [(start_dt, item), ...]}"""
    cfg = load_config()
    epoch = dt.datetime.fromisoformat(cfg["epoch"])
    items = resolve_items(channel, library)
    if not items:
        return None
    lengths = [max(60.0, durs.get(i["path"])) for i in items]
    total = sum(lengths)
    elapsed = (when - epoch).total_seconds() % total
    loop_index = int((when - epoch).total_seconds() // total)

    order = loop_order(items, channel, loop_index)
    ordered_lengths = [max(60.0, durs.get(i["path"])) for i in order]

    pos = 0.0
    idx = 0
    for idx, ln in enumerate(ordered_lengths):
        if pos + ln > elapsed:
            break
        pos += ln
    now_item = order[idx]
    offset = elapsed - pos
    remaining = ordered_lengths[idx] - offset

    upcoming = []
    t = when + dt.timedelta(seconds=remaining)
    j, li = idx + 1, loop_index
    cur_order, cur_lengths = order, ordered_lengths
    while len(upcoming) < lookahead:
        if j >= len(cur_order):
            j, li = 0, li + 1
            cur_order = loop_order(items, channel, li)
            cur_lengths = [max(60.0, durs.get(i["path"])) for i in cur_order]
        upcoming.append((t, cur_order[j]))
        t += dt.timedelta(seconds=cur_lengths[j])
        j += 1

    return {"item": now_item, "offset": offset, "remaining": remaining,
            "upcoming": upcoming}


def display_name(item):
    if item["kind"] == "tv":
        import re as _re
        series = _re.sub(r"\s+s\d+$", "", item["series"])
        return (f"{series.title()} "
                f"S{item['season']:02d}E{item['episode']:02d}")
    if item["kind"] == "movie":
        return f"{item['title'].title()} ({item['year']})"
    return item["title"].title()
