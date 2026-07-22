"""Library indexer: walk the roots, parse every video into a content identity,
collapse duplicate copies, write library.json.

Identities:  tv    -> (series, season, episode)
             movie -> (title, year)
             other -> kept as-is (mashups, unlabeled files)
"""
import json
import os
import re
import sys

if getattr(sys, "frozen", False):
    HERE = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".m4v", ".wmv", ".mpg", ".mpeg",
             ".ts", ".webm", ".mov", ".flv"}

EXTRA_RX = re.compile(
    r"(?i)\b(trailer|teaser|featurette|behind[\s\.\-_]the[\s\.\-_]scenes|"
    r"deleted[\s\.\-_]scenes?|bonus|bloopers?|gag[\s\.\-_]reel|promo|recap|"
    r"extras?|interview|making[\s\.\-_]of|sample)\b")
EP_RX = re.compile(r"(?i)[S](\d{1,2})[\s\._\-]*[E](\d{1,3})")
XEP_RX = re.compile(r"(?i)\b(\d{1,2})x(\d{2,3})\b")
YEAR_RX = re.compile(r"\b(19[3-9]\d|20[0-2]\d)\b")
CAM_RX = re.compile(r"(?i)\b(cam|hdcam|hdts|hd-?ts|telesync|telecine|hdtc|ts)\b")
JUNK_RX = re.compile(
    r"(?i)[\s\.\-_]*\b(2160p|1080p|720p|576p|480p|360p|bluray|blu[\s\.\-_]?ray|"
    r"bdrip|brrip|webrip|web[\s\.\-_]?dl|hdtv|dvdrip|dvd|remastered|extended|"
    r"unrated|uncut|proper|repack|internal|limited|imax|hdr|10bit|8bit|x264|"
    r"x265|h[\s\.]?264|h[\s\.]?265|hevc|xvid|divx|aac.*|ac3.*|dd5.*|ddp.*|"
    r"dts.*|eac3.*|5\.1|7\.1|amzn|nf|hulu|dsnp|hmax|atvp|open[\s\.\-_]?matte)\b.*$")


def norm(s):
    s = re.sub(r"[\.\-_]+", " ", s)
    s = JUNK_RX.sub("", s)
    s = re.sub(r"[\[\(].*?[\]\)]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def classify(path):
    name = os.path.basename(path)
    stem, _ = os.path.splitext(name)
    if EXTRA_RX.search(stem):
        return None
    m = EP_RX.search(stem) or XEP_RX.search(stem)
    if m:
        season, ep = int(m.group(1)), int(m.group(2))
        if 0 < season <= 50 and 0 < ep <= 300:
            series = norm(stem[:m.start()])
            if len(series) < 2:
                series = norm(os.path.basename(os.path.dirname(path)))
                series = re.sub(r"(?i)\bseason \d+\b|\bcomplete\b", "",
                                series).strip()
            if len(series) >= 2:
                return {"kind": "tv", "series": series, "season": season,
                        "episode": ep,
                        "identity": f"tv|{series}|s{season:02d}e{ep:03d}"}
    years = YEAR_RX.findall(stem)
    if years:
        year = years[-1]
        title = norm(stem[:stem.rfind(year)])
        if len(title) >= 2:
            return {"kind": "movie", "title": title, "year": int(year),
                    "identity": f"mv|{title}|{year}"}
    return {"kind": "other", "title": norm(stem),
            "identity": f"ot|{os.path.dirname(path).lower()}|{norm(stem)}"}


def build(roots, min_bytes):
    groups = {}
    for root in roots:
        for base, _dirs, names in os.walk(root):
            for n in names:
                if os.path.splitext(n)[1].lower() not in VIDEO_EXT:
                    continue
                p = os.path.join(base, n)
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                if size < min_bytes:
                    continue
                info = classify(p)
                if info is None:
                    continue
                info["path"] = p
                info["size"] = size
                groups.setdefault(info["identity"], []).append(info)

    items = []
    for members in groups.values():
        best = max(members, key=lambda m: (
            0 if CAM_RX.search(os.path.basename(m["path"])) else 1, m["size"]))
        items.append(best)
    return items


def main():
    with open(os.path.join(HERE, "rerun.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    items = build(cfg["roots"], cfg.get("min_bytes", 0))
    out = os.path.join(HERE, "library.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(items, f)
    tv = sum(1 for i in items if i["kind"] == "tv")
    mv = sum(1 for i in items if i["kind"] == "movie")
    print(f"library.json: {len(items)} items ({tv} episodes, {mv} movies, "
          f"{len(items) - tv - mv} other)")


if __name__ == "__main__":
    sys.exit(main())
