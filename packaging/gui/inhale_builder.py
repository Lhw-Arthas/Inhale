"""Inhale Builder: a small window over nx2/make_game.py, for players who do not use a terminal. Pick your .nup or extracted
folders, pick where the game goes, Build, then Play. The standard library only (tkinter), on the packages' own Python.

    python -I packaging/gui/inhale_builder.py      (a checkout: the system's build tools, as the README says)

The build runs as a child process, python -I nx2/make_game.py ..., in the environment of tools_env.build_env (the bundled
tools). Its stdout is read on a thread into a queue, and the window polls the queue; protocol.parse turns each line into an
event. The last choices are kept in inhale-builder.json in the user's config folder.
"""
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (python -I leaves the script folder off)
import protocol  # noqa: E402
import tools_env  # noqa: E402

WINDOWS = os.name == "nt"
MAKE_GAME = os.path.join(tools_env.ROOT, "nx2", "make_game.py")
TITLE = "Inhale Builder"


def config_path():
    base = os.environ.get("APPDATA") if WINDOWS else os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base or os.path.expanduser("~"), "Inhale" if WINDOWS else "", "inhale-builder.json")


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(data):
    try:
        os.makedirs(os.path.dirname(config_path()), exist_ok=True)
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
    except OSError:
        pass   # (a read-only config folder costs the remembered choices only)


def default_out():
    return os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), "Games", "Inhale") if WINDOWS else \
        os.path.expanduser("~/Games/Inhale")


def default_work():
    """make_game.py's own default for --work"""
    if WINDOWS:
        return os.path.join(os.environ.get("LOCALAPPDATA") or tools_env.ROOT, "InhaleBuilder")
    return os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "inhale-builder")


def full(var):
    """A path the player typed or chose, absolute: make_game.py runs in the tools' folder, not where the window started"""
    return os.path.abspath(os.path.expanduser(var.get().strip()))


def game_program(folder):
    """The game's program in a folder make_game.py built, or None"""
    names = ("inhale.exe",) if WINDOWS else ("inhale",)
    for n in names:
        for p in (os.path.join(folder, n), os.path.join(folder, "bin", n)):
            if os.path.isfile(p):
                return p
    return None


class Child:
    """make_game.py running, its lines in a queue; kill() ends it and every compiler it started"""

    def __init__(self, args):
        cmd = [tools_env.python(), "-I", "-u", "-X", "utf8", MAKE_GAME] + args
        kw = {}
        if WINDOWS:
            kw["creationflags"] = 0x08000000 | 0x00000200   # (CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP)
        else:
            kw["start_new_session"] = True   # (its own process group: kill() reaches the compilers too)
        self.lines = queue.Queue()
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     env=tools_env.build_env(), cwd=tools_env.ROOT, text=True, encoding="utf-8",
                                     errors="replace", bufsize=1, **kw)
        self.lines.put(("log", "$ " + " ".join(cmd)))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(protocol.parse(line))
        self.lines.put(("exit", self.proc.wait()))

    def kill(self):
        if self.proc.poll() is not None:
            return
        if WINDOWS:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)], capture_output=True,
                           creationflags=0x08000000)
            return
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            for _ in range(30):
                if self.proc.poll() is not None:
                    return
                time.sleep(0.1)
            os.killpg(self.proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITLE)
        self.minsize(640, 440)
        icon = os.path.join(tools_env.GUI, "inhale.png")
        if os.path.isfile(icon):
            try:
                self.iconphoto(True, tk.PhotoImage(file=icon))
            except tk.TclError:
                pass
        self.cfg = load_config()
        self.game = tk.StringVar(value=self.cfg.get("game", ""))
        self.out = tk.StringVar(value=self.cfg.get("out") or default_out())
        self.work = tk.StringVar(value=self.cfg.get("work") or default_work())
        self.jobs = tk.StringVar(value=str(self.cfg.get("jobs", "")))
        self.update_dir = tk.StringVar(value=self.cfg.get("out") or default_out())
        self.check_text = tk.StringVar()
        self.checked = None   # (the path the last check was of: another path is checked again before Next)
        self.game.trace_add("write", lambda *_: self.game_changed())
        self.stage = tk.StringVar()
        self.eta = tk.StringVar()
        self.status = tk.StringVar()
        self.child = None
        self.mode = None   # ("check" | "build")
        self.log = []
        self.check_ok = False
        self.error = None
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.body = ttk.Frame(self, padding=16)
        self.body.pack(fill="both", expand=True)
        self.show_start()

    # ---- the screens ----
    def clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def heading(self, text, sub=None):
        ttk.Label(self.body, text=text, font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        if sub:
            ttk.Label(self.body, text=sub, wraplength=600, justify="left").pack(anchor="w", pady=(4, 12))

    def buttons(self, *specs):
        row = ttk.Frame(self.body)
        row.pack(side="bottom", fill="x", pady=(12, 0))
        out = []
        for text, cmd, side in specs:
            b = ttk.Button(row, text=text, command=cmd)
            b.pack(side=side, padx=4)
            out.append(b)
        return out

    def show_start(self):
        self.clear()
        self.heading("Inhale Builder", "Builds the PC version of the game from your own copy of it: its .nup package, or the "
                     "extracted exefs and aoc folders. Nothing of the game comes with this program.")
        ttk.Button(self.body, text="Build the game from my copy...", command=self.show_game).pack(fill="x", pady=4)
        ttk.Separator(self.body).pack(fill="x", pady=12)
        ttk.Label(self.body, text="Update an existing game folder (after you updated Inhale Builder):").pack(anchor="w")
        row = ttk.Frame(self.body)
        row.pack(fill="x", pady=4)
        ttk.Entry(row, textvariable=self.update_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=lambda: self.pick_dir(self.update_dir)).pack(side="left", padx=4)
        ttk.Button(row, text="Update", command=self.start_update).pack(side="left")
        self.buttons(("Quit", self.quit_app, "right"))

    def show_game(self):
        self.clear()
        self.heading("1. Your game", "Choose the game's .nup file, or a folder that holds the extracted exefs/ and aoc/ "
                     "folders. It is checked to be the right game and version.")
        row = ttk.Frame(self.body)
        row.pack(fill="x")
        entry = ttk.Entry(row, textvariable=self.game)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _: self.run_check())
        ttk.Button(row, text=".nup file...", command=self.pick_nup).pack(side="left", padx=4)
        ttk.Button(row, text="Folder...", command=lambda: self.pick_dir(self.game, then=self.run_check)).pack(side="left")
        self.check_label = ttk.Label(self.body, textvariable=self.check_text, wraplength=600, justify="left")
        self.check_label.pack(anchor="w", pady=12)
        _, self.next_btn = self.buttons(("Back", self.show_start, "left"), ("Next", self.show_where, "right"))
        self.next_btn.state(["!disabled"] if self.check_ok else ["disabled"])
        if self.game.get() and not self.check_ok:
            self.run_check()

    def show_where(self):
        self.clear()
        self.heading("2. Where", "The game folder gets the game (about 12 GB). The work folder holds the build's own files, "
                     "kept so that a later update is quick.")
        grid = ttk.Frame(self.body)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        for r, (label, var) in enumerate((("Game folder", self.out), ("Work folder", self.work))):
            ttk.Label(grid, text=label).grid(row=r, column=0, sticky="w", pady=4)
            ttk.Entry(grid, textvariable=var).grid(row=r, column=1, sticky="ew", padx=4)
            ttk.Button(grid, text="Browse...", command=lambda v=var: self.pick_dir(v)).grid(row=r, column=2)
        ttk.Label(grid, text="CPU threads").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(grid, textvariable=self.jobs, width=6).grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(grid, text="empty: automatic (all but one, as the memory allows)").grid(row=3, column=1, sticky="w", padx=4)
        self.buttons(("Back", self.show_game, "left"), ("Build", self.start_build, "right"))

    def show_build(self, title):
        self.clear()
        self.heading(title)
        ttk.Label(self.body, textvariable=self.stage, wraplength=600).pack(anchor="w")
        self.bar = ttk.Progressbar(self.body, maximum=1.0)
        self.bar.pack(fill="x", pady=8)
        ttk.Label(self.body, textvariable=self.eta).pack(anchor="w")
        self.log_shown = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.body, text="Show the log", variable=self.log_shown, command=self.toggle_log).pack(anchor="w", pady=4)
        self.log_frame = ttk.Frame(self.body)
        self.log_text = tk.Text(self.log_frame, height=14, wrap="none", state="disabled")
        sb = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)
        (self.cancel_btn,) = self.buttons(("Cancel", self.cancel, "right"))

    def show_done(self, folder):
        self.clear()
        self.heading("Done", "The game is in %s." % folder)
        if self.status.get():
            ttk.Label(self.body, textvariable=self.status, wraplength=600, justify="left").pack(anchor="w", pady=(0, 8))
        for text, cmd in (("Play", lambda: self.play(folder)), ("Open folder", lambda: self.open_folder(folder)),
                          ("Create shortcut", lambda: self.shortcut(folder)), ("Copy log", self.copy_log)):
            ttk.Button(self.body, text=text, command=cmd).pack(fill="x", pady=3)
        self.buttons(("Quit", self.quit_app, "right"), ("Start over", self.show_start, "left"))

    # ---- choices ----
    def pick_nup(self):
        p = filedialog.askopenfilename(title="Your game's .nup", filetypes=[("Game package", "*.nup"), ("All files", "*")])
        if p:
            self.game.set(p)
            self.run_check()

    def pick_dir(self, var, then=None):
        p = filedialog.askdirectory(title="Choose a folder", initialdir=var.get() or os.path.expanduser("~"))
        if p:
            var.set(p)
            if then:
                then()

    def game_changed(self):
        if self.check_ok and full(self.game) != self.checked:
            self.check_ok = False
            self.check_text.set("Press Enter, or choose the file or folder again, to check it.")
            if getattr(self, "next_btn", None) and self.next_btn.winfo_exists():
                self.next_btn.state(["disabled"])

    def remember(self):
        self.cfg.update(game=self.game.get(), out=self.out.get(), work=self.work.get(), jobs=self.jobs.get().strip())
        save_config(self.cfg)

    # ---- running make_game.py ----
    def run_check(self):
        if self.child:
            return
        self.check_ok = False
        self.next_btn.state(["disabled"])
        self.check_text.set("Checking...")
        self.log = []
        self.mode = "check"
        self.checked = full(self.game)
        self.child = Child(["--check", "--game", self.checked, "--work", full(self.work)])
        self.after(100, self.poll)

    def start_build(self):
        jobs = self.jobs.get().strip()
        if jobs and not (jobs.isdigit()):
            messagebox.showerror(TITLE, "CPU threads must be a whole number, or empty for automatic.")
            return
        self.remember()
        args = ["--game", full(self.game), "--out", full(self.out), "--work", full(self.work)]
        self.run_build(args + (["--jobs", jobs] if jobs else []), "3. Building")

    def start_update(self):
        folder = full(self.update_dir)
        if not os.path.isdir(folder):
            messagebox.showerror(TITLE, "There is no folder %s." % folder)
            return
        self.out.set(folder)
        self.remember()
        self.run_build(["--update", folder, "--work", full(self.work)], "Updating " + folder)

    def run_build(self, args, title):
        self.log, self.error = [], None
        self.stage.set("Starting...")
        self.eta.set("")
        self.status.set("")
        self.show_build(title)
        self.mode = "build"
        self.child = Child(args)
        self.after(100, self.poll)

    def poll(self):
        child = self.child
        if child is None:
            return
        try:
            while True:
                kind, value = child.lines.get_nowait()
                if kind == "exit":
                    self.child = None
                    self.finished(value)
                    return
                self.event(kind, value)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def append_log(self, line):
        self.log.append(line)
        if self.mode == "build" and getattr(self, "log_text", None) and self.log_text.winfo_exists():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line + "\n")
            if int(self.log_text.index("end-1c").split(".")[0]) > 5000:
                self.log_text.delete("1.0", "1000.0")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

    def event(self, kind, value):
        if kind in ("log", "not_prepared"):
            self.append_log(value)
            if kind == "not_prepared":
                self.status.set("The shaders will be prepared when the game first starts (that start takes longer).")
            return
        self.append_log("@@%s %s" % (kind, value))
        if kind == "check":
            ok, text = value
            self.check_ok = ok
            self.check_text.set(("\u2713 " if ok else "\u2717 ") + text)
        elif kind == "stage":
            self.stage.set(value[1])
            self.bar["value"] = 0
        elif kind == "progress":
            self.bar["value"] = value
        elif kind == "eta":
            self.eta.set(protocol.eta_text(value))
        elif kind == "error":
            self.error = value
        elif kind == "done":
            self.done_folder = value

    def finished(self, code):
        if self.mode == "check":
            if not self.check_ok and not self.check_text.get().startswith("\u2717"):
                self.check_text.set("\u2717 " + (self.error or (self.log[-1] if self.log else "the check stopped")))
            if self.next_btn.winfo_exists():
                self.next_btn.state(["!disabled"] if self.check_ok else ["disabled"])
            return
        if code == 0 and not self.error:
            self.show_done(getattr(self, "done_folder", "") or self.out.get())
            return
        if getattr(self, "cancelled", False):
            self.cancelled = False
            self.stage.set("Cancelled.")
            self.cancel_btn.configure(text="Back", command=self.show_where)
            return
        self.stage.set("The build stopped.")
        self.cancel_btn.configure(text="Back", command=self.show_where)
        self.error_dialog(self.error or "make_game.py ended with code %s; the log says why." % code)

    def cancel(self):
        if self.child and messagebox.askyesno(TITLE, "Stop the build? What it has compiled so far is kept for the next one."):
            self.cancelled = True
            self.child.kill()

    def error_dialog(self, text):
        top = tk.Toplevel(self)
        top.title(TITLE + ": the build stopped")
        top.transient(self)
        frame = ttk.Frame(top, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=text, wraplength=520, justify="left").pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(12, 0))
        ttk.Button(row, text="Copy log", command=self.copy_log).pack(side="left")
        ttk.Button(row, text="Close", command=top.destroy).pack(side="right")

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append("\n".join(self.log))

    def toggle_log(self):
        if self.log_shown.get():
            self.log_frame.pack(fill="both", expand=True)
        else:
            self.log_frame.pack_forget()

    # ---- after the build ----
    def play(self, folder):
        exe = game_program(folder)
        if not exe:
            messagebox.showerror(TITLE, "No game program in %s." % folder)
            return
        kw = {"creationflags": 0x00000008 | 0x00000200} if WINDOWS else {"start_new_session": True}   # (DETACHED_PROCESS)
        subprocess.Popen([exe], cwd=folder, env=tools_env.play_env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True, **kw)

    def open_folder(self, folder):
        if WINDOWS:
            os.startfile(folder)   # noqa: S606 (the player's own folder)
        else:
            subprocess.Popen(["xdg-open", folder], env=tools_env.play_env(), start_new_session=True)

    def shortcut(self, folder):
        exe = game_program(folder)
        if not exe:
            messagebox.showerror(TITLE, "No game program in %s." % folder)
            return
        try:
            where = make_shortcut(folder, exe)
        except (OSError, subprocess.CalledProcessError) as e:
            messagebox.showerror(TITLE, "The shortcut could not be made: %s" % e)
            return
        messagebox.showinfo(TITLE, "Shortcut made: %s" % where)

    def quit_app(self):
        if self.child and self.mode == "build":
            if not messagebox.askyesno(TITLE, "A build is running. Stop it and quit?"):
                return
        if self.child:
            self.child.kill()
        self.destroy()


def desktop_entry(folder, exe):
    """The text of a .desktop file that starts the game in folder"""
    def q(s):   # (the Exec key's quoting: a path with spaces or quotes stays one argument)
        return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
    icon = os.path.join(folder, "inhale.png")
    return "\n".join(["[Desktop Entry]", "Type=Application", "Name=Inhale", "Comment=Kirby and the Forgotten Land on PC",
                      "Exec=%s" % q(exe), "Path=%s" % folder, "Icon=%s" % (icon if os.path.isfile(icon) else "applications-games"),
                      "Terminal=false", "Categories=Game;", ""])


def make_shortcut(folder, exe):
    if WINDOWS:
        desktop = os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), "Desktop", "Inhale.lnk")
        # (the paths go in through the environment, not into the script's text: no quoting to get wrong)
        script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:INHALE_LNK); $s.TargetPath = $env:INHALE_EXE; "
                  "$s.WorkingDirectory = $env:INHALE_DIR; $s.IconLocation = $env:INHALE_EXE; $s.Save()")
        env = dict(os.environ, INHALE_LNK=desktop, INHALE_EXE=exe, INHALE_DIR=folder)
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], env=env, check=True,
                       capture_output=True, creationflags=0x08000000)
        return desktop
    apps = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "applications")
    os.makedirs(apps, exist_ok=True)
    path = os.path.join(apps, "inhale.desktop")
    with open(path, "w", encoding="utf-8") as f:
        f.write(desktop_entry(folder, exe))
    os.chmod(path, 0o755)
    return path


if __name__ == "__main__":
    App().mainloop()
