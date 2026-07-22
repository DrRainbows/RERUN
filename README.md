# RERUN

**The station that's always on.**

RERUN turns a personal media library into a broadcast television station: numbered
channels, continuous schedules, and the lost pleasure of *arriving* — flipping to a
channel and landing twenty minutes into something you love, no menu, no decision,
already playing.

Every channel has been "airing" since the epoch. Nothing is ever paused, because a
broadcast doesn't wait for you. Tune in, and RERUN computes exactly what its schedule
says is on *right now* and drops you there, mid-stream, the way television used to
find you.

- **RERUN** — the station. Channels over your own collection: linear runs
  (Simpsons, episode to episode), marathons that loop like old cable, night movie
  blocks, seasonal logic (Independence Day knows it's July 4th; Die Hard 2 knows
  it's Christmas), and a 24/7 John Wick channel, because obviously.
- **The Omniguide** — the guide. A 2004-cable-box grid: channels down the side,
  half-hour slots across the top, what's on, how far in, what's next. Flip, don't
  browse.
- **The rerun engine** — the machinery. Deterministic schedule math anchored to a
  fixed epoch: the same wall-clock moment always resolves to the same point in a
  channel's loop, so the station exists whether or not anyone is watching.

## Quickstart

```
python src/tune.py --scan          # index the library (writes library.json)
python src/tune.py --guide        # terminal guide: now/next on every channel
python src/tune.py --html         # generate + open the Omniguide grid
python src/tune.py 1              # tune channel 1 (VLC, joined in progress)
```

Configure roots and the VLC path in `rerun.json`. Channels live in `channels/*.json`.

## Channel definitions

```json
{
  "number": 1,
  "name": "WICK",
  "type": "loop",                      // loop (as listed) | linear (S/E order) | shuffle (seeded per loop)
  "movies": ["john wick (2014)", "john wick chapter 2 (2017)"],
  "series": ["family guy"],            // matched against parsed series identity
  "folders": ["O:\\Family Guy Mashups"],
  "seed": 7
}
```

The library indexer parses every filename into a content identity (series + episode,
or movie + year), collapses duplicate copies to the best one, and ignores junk.
Durations are probed once via ffprobe and cached in `durations.json`.

## Architecture, present and planned

```
library.py    walk + parse + dedupe            -> library.json
engine.py     channel -> deterministic schedule (epoch-anchored, loop-aware)
guide.py      terminal guide + omniguide.html  (the 2004 grid)
tune.py       CLI: scan / guide / html / tune N
channels/     the dial
```

Built on the sidecar infrastructure of the wider project: every title carries (or
will carry) a `.transcript.md` meaning-map and an on-demand `.joints.json`
boundary-map, which is what lets future channels be *composed*, not just scheduled —
auto-generated mashup channels, themed supercut blocks, holiday reels.

Roadmap: the rerun engine as a resident daemon with gapless handoff · Omniguide
interactivity (click-to-tune, remote-friendly) · dayparts and seasonal rules ·
auto-composed channels from the mashup pipeline · the ear (ambient room-state from
the AI-DJ project) gently steering what late night feels like.

*Component lineage: the Omniguide is named for the original dream — a 2004-style
guide over everything. RERUN is named for the feeling.*
