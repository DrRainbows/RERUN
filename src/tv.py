"""RERUN TV mode: the one-window television set.

The 2004 layout, realized: info panel top-left, live video top-right
(libVLC embedded - no external player), the guide grid below. Click a row
or type a channel number to flip; the video never leaves the window.

  keys:  0-9   direct tune (two digits within a second works)
         up/down + enter   move the highlight, tune
         f     watch mode (video fills the window)   g / esc   back to guide
         q     sign off

Standalone: needs no server. Reads the same library/channels the engine uses.
  python src/tv.py            open the set
  python src/tv.py --test     muted 8-second self-test (CI-friendly)
"""
import datetime as dt
import sys
import tkinter as tk
import tkinter.font as tkfont

import vlc

import engine

BG = "#000022"
CELL = "#223399"
CELL_DARK = "#111155"
CHAN_BG = "#001155"
YELLOW = "#ffcc00"
GRID_LINE = "#222266"

REFRESH_MS = 60000


class TV:
    def __init__(self, test=False):
        self.test = test
        self.lib = engine.load_library()
        self.durs = engine.Durations()
        self.channels = engine.load_channels()
        self.current = self.channels[0]["number"]
        self.digit_buffer = ""
        self.digit_job = None
        self.watch_mode = False

        self.root = tk.Tk()
        self.root.title("RERUN")
        self.root.configure(bg=BG)
        self.root.geometry("1280x800")
        self.f_big = tkfont.Font(family="Verdana", size=26, weight="bold")
        self.f_med = tkfont.Font(family="Verdana", size=13, weight="bold")
        self.f_sml = tkfont.Font(family="Verdana", size=10)

        self.info = tk.Frame(self.root, bg=BG)
        self.lbl_chan = tk.Label(self.info, fg=YELLOW, bg=BG, font=self.f_big,
                                 anchor="w")
        self.lbl_now = tk.Label(self.info, fg="white", bg=BG, font=self.f_med,
                                anchor="w", wraplength=560, justify="left")
        self.lbl_pos = tk.Label(self.info, fg="#99aaff", bg=BG,
                                font=self.f_sml, anchor="w")
        self.lbl_next = tk.Label(self.info, fg="#8899cc", bg=BG,
                                 font=self.f_sml, anchor="w", justify="left")
        for w in (self.lbl_chan, self.lbl_now, self.lbl_pos, self.lbl_next):
            w.pack(fill="x", padx=18, pady=2, anchor="w")

        self.video = tk.Frame(self.root, bg="black")
        self.grid = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.grid.bind("<Button-1>", self.on_click)
        self.grid.bind("<MouseWheel>", lambda e: self.grid.yview_scroll(
            -1 if e.delta > 0 else 1, "units"))

        self.vlc = vlc.Instance("--quiet")
        self.player = self.vlc.media_player_new()
        self.player.video_set_mouse_input(False)
        self.player.video_set_key_input(False)
        events = self.player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached,
                            lambda e: self.root.after(200, self.retune))

        self.root.bind("<Key>", self.on_key)
        self.layout()
        self.root.after(60, self.attach_video)
        self.root.after(120, lambda: self.tune(self.current))
        self.root.after(REFRESH_MS, self.periodic)
        if test:
            self.root.after(400, lambda: self.player.audio_set_mute(True))
            self.root.after(8000, self.finish_test)

    def attach_video(self):
        self.player.set_hwnd(self.video.winfo_id())

    def layout(self):
        if self.watch_mode:
            self.info.place_forget()
            self.grid.place_forget()
            self.video.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        else:
            self.info.place(x=0, y=0, relwidth=0.55, relheight=0.38)
            self.video.place(relx=0.55, y=0, relwidth=0.45, relheight=0.38)
            self.grid.place(x=0, rely=0.38, relwidth=1.0, relheight=0.62)
            self.draw_grid()

    # ---- schedule/tuning ----
    def sched_for(self, number):
        ch = next(c for c in self.channels if c["number"] == number)
        return ch, engine.schedule_at(ch, self.lib, self.durs,
                                      dt.datetime.now(), lookahead=8)

    def tune(self, number):
        try:
            ch, sched = self.sched_for(number)
        except StopIteration:
            return
        if not sched:
            return
        self.current = number
        media = self.vlc.media_new(sched["item"]["path"])
        self.player.set_media(media)
        self.player.play()
        offset_ms = int(sched["offset"] * 1000)
        self.root.after(500, lambda: self.player.set_time(offset_ms))
        self.lbl_chan.config(text=f"{ch['number']}  {ch['name']}")
        self.lbl_now.config(text=engine.display_name(sched["item"]))
        mins_in = int(sched["offset"] // 60)
        mins_left = int(sched["remaining"] // 60)
        self.lbl_pos.config(text=f"{mins_in}m in · {mins_left}m left")
        nxt = "\n".join(
            f"{t:%I:%M %p}  {engine.display_name(item)}"
            for t, item in sched["upcoming"][:3])
        self.lbl_next.config(text=nxt)
        self.durs.save()
        if not self.watch_mode:
            self.draw_grid()

    def retune(self):
        self.tune(self.current)

    # ---- the grid ----
    def draw_grid(self):
        c = self.grid
        c.delete("all")
        c.update_idletasks()
        w = c.winfo_width() or 1280
        now = dt.datetime.now()
        slot0 = now.replace(minute=(0 if now.minute < 30 else 30),
                            second=0, microsecond=0)
        slots = [slot0 + dt.timedelta(minutes=30 * k) for k in range(4)]
        horizon = slots[-1] + dt.timedelta(minutes=30)
        chan_w = 150
        col_w = (w - chan_w) / 4
        header_h = 28
        row_h = 54

        c.create_rectangle(0, 0, w, header_h, fill="#000044", outline="")
        for k, s in enumerate(slots):
            c.create_text(chan_w + col_w * k + col_w / 2, header_h / 2,
                          text=f"{s:%I:%M %p}", fill=YELLOW,
                          font=self.f_sml)
        y = header_h
        self.row_map = []
        for ch in self.channels:
            sched = engine.schedule_at(ch, self.lib, self.durs, now,
                                       lookahead=8)
            if not sched:
                continue
            hl = ch["number"] == self.current
            c.create_rectangle(0, y, chan_w, y + row_h, fill=CHAN_BG,
                               outline=YELLOW if hl else GRID_LINE,
                               width=2 if hl else 1)
            c.create_text(12, y + row_h / 2, anchor="w",
                          text=f"{ch['number']}  {ch['name']}",
                          fill=YELLOW, font=self.f_sml)
            progs = [(now - dt.timedelta(seconds=sched["offset"]),
                      now + dt.timedelta(seconds=sched["remaining"]),
                      sched["item"])]
            for t, item in sched["upcoming"]:
                end = t + dt.timedelta(
                    seconds=max(60.0, self.durs.get(item["path"])))
                progs.append((t, end, item))
            for start, end, item in progs:
                if start >= horizon:
                    break
                x0 = chan_w + max(
                    0, (max(start, slot0) - slot0).total_seconds() / 1800
                ) * col_w
                x1 = chan_w + min(
                    4, (min(end, horizon) - slot0).total_seconds() / 1800
                ) * col_w
                if x1 - x0 < 8:
                    continue
                c.create_rectangle(x0 + 2, y + 3, x1 - 2, y + row_h - 3,
                                   fill=CELL if start < slot0 else CELL_DARK,
                                   outline=GRID_LINE)
                c.create_text(x0 + 10, y + row_h / 2, anchor="w",
                              text=engine.display_name(item)[:int(
                                  (x1 - x0) / 7.5)],
                              fill="white", font=self.f_sml)
            self.row_map.append((y, y + row_h, ch["number"]))
            y += row_h
        c.configure(scrollregion=(0, 0, w, y))

    def on_click(self, event):
        cy = self.grid.canvasy(event.y)
        for y0, y1, number in getattr(self, "row_map", []):
            if y0 <= cy <= y1:
                self.tune(number)
                return

    # ---- keys ----
    def on_key(self, event):
        k = event.keysym.lower()
        if k in ("q",):
            self.sign_off()
        elif k == "f":
            self.watch_mode = True
            self.layout()
        elif k in ("g", "escape"):
            self.watch_mode = False
            self.layout()
        elif k.isdigit():
            self.digit_buffer += k
            if self.digit_job:
                self.root.after_cancel(self.digit_job)
            self.digit_job = self.root.after(900, self.commit_digits)
        elif k == "return":
            if self.digit_buffer:
                self.commit_digits()
        elif k in ("up", "down"):
            nums = [c["number"] for c in self.channels]
            i = nums.index(self.current) if self.current in nums else 0
            i = (i + (1 if k == "down" else -1)) % len(nums)
            self.tune(nums[i])

    def commit_digits(self):
        try:
            n = int(self.digit_buffer)
        except ValueError:
            n = 0
        self.digit_buffer = ""
        self.digit_job = None
        if n:
            self.tune(n)

    def periodic(self):
        if not self.watch_mode:
            self.draw_grid()
        self.root.after(REFRESH_MS, self.periodic)

    def finish_test(self):
        ok = self.player.is_playing()
        print(f"TEST {'OK' if ok else 'FAIL'} playing={bool(ok)} "
              f"channel={self.current}")
        self.root.destroy()
        sys.exit(0 if ok else 1)

    def sign_off(self):
        self.player.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    TV(test="--test" in sys.argv).run()


if __name__ == "__main__":
    main()
