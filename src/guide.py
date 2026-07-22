"""The Omniguide: terminal now/next view + the 2004-blue HTML grid."""
import datetime as dt
import html
import os

import engine

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fmt_min(sec):
    return f"{int(sec // 60)}m"


def terminal_guide(only=None):
    lib = engine.load_library()
    durs = engine.Durations()
    now = dt.datetime.now()
    print(f"\n  RERUN · {now:%a %I:%M %p}\n")
    for ch in engine.load_channels():
        if only and ch["number"] not in only:
            continue
        sched = engine.schedule_at(ch, lib, durs, now)
        if not sched:
            print(f"  {ch['number']:>2} {ch['name']:<12} (no items found)")
            continue
        name = engine.display_name(sched["item"])
        line = (f"  {ch['number']:>2} {ch['name']:<12} NOW  {name}"
                f"  · {fmt_min(sched['offset'])} in, {fmt_min(sched['remaining'])} left")
        print(line)
        for t, item in sched["upcoming"][:2]:
            print(f"     {'':<12} {t:%I:%M %p}  {engine.display_name(item)}")
        print()
    durs.save()


def html_guide(only=None, out_path=None):
    doc = html_guide_string(only=only)
    out_path = out_path or os.path.join(HERE, "omniguide.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return out_path


def html_guide_string(only=None, live=False):
    lib = engine.load_library()
    durs = engine.Durations()
    now = dt.datetime.now()
    slot0 = now.replace(minute=(0 if now.minute < 30 else 30), second=0,
                        microsecond=0)
    slots = [slot0 + dt.timedelta(minutes=30 * k) for k in range(4)]
    horizon = slots[-1] + dt.timedelta(minutes=30)

    rows = []
    for ch in engine.load_channels():
        if only and ch["number"] not in only:
            continue
        sched = engine.schedule_at(ch, lib, durs, now, lookahead=8)
        if not sched:
            continue
        progs = [(now - dt.timedelta(seconds=sched["offset"]),
                  now + dt.timedelta(seconds=sched["remaining"]),
                  sched["item"])]
        for t, item in sched["upcoming"]:
            end = t + dt.timedelta(seconds=max(
                60.0, durs.get(item["path"])))
            progs.append((t, end, item))
        cells = []
        for start, end, item in progs:
            if start >= horizon:
                break
            s = max(start, slot0)
            span = max(1, round((min(end, horizon) - s).total_seconds() / 1800))
            joined = " · JOINED" if start < slot0 else ""
            cells.append((span, engine.display_name(item), joined))
        rows.append((ch, cells))
    durs.save()

    cell_html = ""
    for ch, cells in rows:
        tds = "".join(
            f'<td colspan="{span}"><div class="prog">{html.escape(name)}'
            f'<span class="joined">{joined}</span></div></td>'
            for span, name, joined in cells)
        cell_html += (f'<tr class="row" data-ch="{ch["number"]}">'
                      f'<td class="chan"><span class="num">{ch["number"]}'
                      f'</span><br>{html.escape(ch["name"])}</td>{tds}</tr>\n')

    live_css = (".row { cursor: pointer; } "
                ".row:hover td.chan { background: #1133aa; }" if live else "")
    live_js = """
<script>
function tune(n) {
  document.getElementById('status').textContent = 'TUNING ' + n + '...';
  fetch('/tune/' + n).then(r => r.json()).then(d => {
    document.getElementById('status').textContent = d.error ? d.error :
      'CH ' + d.channel + ' ' + d.name + ' \\u00b7 ' + d.now +
      ' \\u00b7 joined ' + d.offset_min + 'm in';
  });
}
document.querySelectorAll('.row').forEach(r =>
  r.addEventListener('click', () => tune(r.dataset.ch)));
document.addEventListener('keydown', e => {
  if (e.key >= '1' && e.key <= '9') tune(e.key);
});
setTimeout(() => location.reload(), 60000);
</script>""" if live else ""
    foot_note = ("click a channel or press its number to tune &middot; "
                 '<span id="status"></span>' if live
                 else "tune with: python src/tune.py &lt;channel&gt;")

    slot_html = "".join(f"<th>{s:%I:%M %p}</th>" for s in slots)
    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>RERUN &middot; Omniguide</title>
<style>
  body {{ background: #000022; color: #fff; font-family: Verdana, Arial, sans-serif;
         margin: 0; padding: 24px; }}
  .head {{ display: flex; justify-content: space-between; align-items: baseline;
          border-bottom: 3px solid #ffcc00; padding-bottom: 8px; }}
  .brand {{ color: #ffcc00; font-size: 28px; font-weight: bold;
           letter-spacing: 4px; }}
  .clock {{ color: #99aaff; font-size: 14px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 14px;
          table-layout: fixed; }}
  th {{ background: #000044; color: #ffcc00; font-size: 12px; padding: 6px;
       border: 1px solid #222266; width: 22%; }}
  th:first-child, td.chan {{ width: 12%; }}
  td {{ border: 1px solid #222266; padding: 0; vertical-align: top; }}
  td.chan {{ background: linear-gradient(#001155, #000033); text-align: center;
            color: #ffcc00; font-size: 11px; font-weight: bold; padding: 8px 4px; }}
  td.chan .num {{ font-size: 20px; color: #fff; }}
  .prog {{ background: linear-gradient(#223399, #111155); margin: 2px;
          padding: 10px 8px; font-size: 12px; min-height: 34px;
          border-radius: 2px; overflow: hidden; white-space: nowrap;
          text-overflow: ellipsis; }}
  .prog:hover {{ background: linear-gradient(#3355cc, #223388); }}
  .joined {{ color: #88ff88; font-size: 9px; }}
  .foot {{ margin-top: 12px; color: #667; font-size: 11px; }}
  #status {{ color: #88ff88; }}
  {live_css}
</style></head><body>
<div class="head"><span class="brand">RERUN</span>
<span class="clock">{now:%A %B %d &middot; %I:%M %p} &middot; the station that's always on</span></div>
<table><tr><th>CHANNEL</th>{slot_html}</tr>
{cell_html}</table>
<div class="foot">OMNIGUIDE &middot; {foot_note}</div>
{live_js}
</body></html>"""
    return doc
