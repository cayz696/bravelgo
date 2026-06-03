"""Modern dark UI kit for BravelGo (stdlib tkinter only)."""
from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk


class C:
    BG = "#0b0e14"
    SURFACE = "#12171f"
    SURFACE2 = "#181f2a"
    ELEVATED = "#1e2636"
    BORDER = "#2a3344"
    BORDER_FOCUS = "#4f46e5"
    ACCENT = "#6366f1"
    ACCENT_DIM = "#4338ca"
    ACCENT_TEXT = "#eef2ff"
    SUCCESS = "#10b981"
    SUCCESS_BG = "#0d2e24"
    DANGER = "#f87171"
    DANGER_BG = "#2a1212"
    WARN = "#fbbf24"
    TEXT = "#e8edf5"
    TEXT2 = "#a8b3c7"
    TEXT3 = "#6b7789"
    LOG_BG = "#070a0f"
    LOG_FG = "#34d399"
    INPUT_BG = "#0f141d"
    INPUT_FG = "#e8edf5"
    TAB_ACTIVE = "#1a2233"
    TAB_IDLE = "#0b0e14"
    HEADER = "#0d1118"


def pick_font(size=10, bold=False):
    for name in ("Ubuntu", "Cantarell", "Segoe UI", "Helvetica Neue", "Helvetica", "Arial"):
        try:
            weight = "bold" if bold else "normal"
            return (name, size, weight)
        except Exception:
            continue
    return ("TkDefaultFont", size, "bold" if bold else "normal")


def tk_font(font, fallback=("DejaVu Sans Mono", 10)):
    """Normalize font spec to (family, size) or (family, size, style)."""
    if isinstance(font, str):
        return (font, fallback[1])
    if not isinstance(font, (list, tuple)) or len(font) < 2:
        return fallback
    if isinstance(font[1], int):
        return font
    if isinstance(font[-1], int):
        return (font[0], font[-1])
    return fallback


def pick_mono_font(size=10):
    for name in ("Ubuntu Mono", "DejaVu Sans Mono", "Courier New", "Courier", "Monospace"):
        return (name, size)
    return ("Courier", size)


FONT = tk_font(pick_font(11))
FONT_BOLD = tk_font(pick_font(11, True))
FONT_SM = tk_font(pick_font(10))
FONT_LG = tk_font(pick_font(15, True))
FONT_MONO = tk_font(pick_mono_font(11))
FONT_DLG = tk_font(pick_font(12))


class ModernApp:
    """Mixin-style UI helpers."""

    def _init_theme(self, root: tk.Tk):
        self.colors = C
        root.configure(bg=C.BG)
        root.option_add("*Font", FONT)
        try:
            root.tk.call("tk", "scaling", 1.25)
        except Exception:
            pass

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=C.BG, foreground=C.TEXT, fieldbackground=C.INPUT_BG)
        style.configure("TCombobox", fieldbackground=C.INPUT_BG, foreground=C.INPUT_FG,
                        background=C.SURFACE2, arrowcolor=C.TEXT2)
        style.map("TCombobox", fieldbackground=[("readonly", C.INPUT_BG)])
        style.configure("TSpinbox", fieldbackground=C.INPUT_BG, foreground=C.INPUT_FG)
        style.configure("TCheckbutton", background=C.SURFACE, foreground=C.TEXT2)

    def _screen_size(self) -> tuple[int, int]:
        root = getattr(self, "root", None)
        if root is None:
            return 1280, 800
        root.update_idletasks()
        return root.winfo_screenwidth(), root.winfo_screenheight()

    def _apply_window_geometry(self, root: tk.Tk, ratio: float = 0.70) -> None:
        """Main window ≈ ratio of screen (default 70%)."""
        sw, sh = self._screen_size()
        w = max(960, int(sw * ratio))
        h = max(720, int(sh * ratio))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2 - 20)
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(int(sw * 0.55), int(sh * 0.50))
        self._hint_wrap = int(w * 0.82)

    def _show_dialog(self, title: str, message: str, kind: str = "info") -> None:
        """Large readable dialog instead of tiny system messagebox."""
        root = self.root
        sw, sh = self._screen_size()
        dlg = tk.Toplevel(root)
        dlg.title(title)
        dlg.configure(bg=C.BG)
        dlg.transient(root)
        dlg.grab_set()

        dw = max(520, min(int(sw * 0.48), 900))
        dh = max(280, min(int(sh * 0.42), 620))
        dlg.geometry(f"{dw}x{dh}+{(sw - dw) // 2}+{(sh - dh) // 2}")
        dlg.minsize(480, 260)

        bar = tk.Frame(dlg, bg=C.HEADER, padx=16, pady=14)
        bar.pack(fill="x")
        accent = C.SUCCESS if kind == "info" else C.DANGER if kind == "error" else C.WARN
        tk.Label(bar, text=title, font=FONT_LG, fg=C.TEXT, bg=C.HEADER).pack(anchor="w")
        tk.Frame(bar, bg=accent, height=3).pack(fill="x", pady=(8, 0))

        body = tk.Frame(dlg, bg=C.SURFACE, padx=18, pady=16)
        body.pack(fill="both", expand=True)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        box = scrolledtext.ScrolledText(
            body, bg=C.INPUT_BG, fg=C.TEXT, font=FONT_DLG,
            relief="flat", highlightthickness=0, wrap="word",
            padx=12, pady=10,
        )
        box.grid(row=0, column=0, sticky="nsew")
        box.insert("1.0", message)
        box.configure(state="disabled")

        foot = tk.Frame(dlg, bg=C.BG, padx=16, pady=12)
        foot.pack(fill="x")
        tk.Button(
            foot, text="OK", command=dlg.destroy,
            bg=C.ACCENT, fg=C.ACCENT_TEXT, activebackground=C.ACCENT_DIM,
            relief="flat", padx=28, pady=10, font=FONT_BOLD, cursor="hand2",
        ).pack(side="right")

        dlg.bind("<Return>", lambda _e: dlg.destroy())
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)
        dlg.wait_window()

    def show_info(self, title: str, message: str) -> None:
        self.root.after(0, lambda: self._show_dialog(title, message, "info"))

    def show_error(self, title: str, message: str) -> None:
        self.root.after(0, lambda: self._show_dialog(title, message, "error"))

    def _header(self, parent) -> tk.Frame:
        bar = tk.Frame(parent, bg=C.HEADER, height=64)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        accent = tk.Frame(bar, bg=C.ACCENT, width=4)
        accent.pack(side="left", fill="y")

        left = tk.Frame(bar, bg=C.HEADER)
        left.pack(side="left", fill="y", padx=(16, 0))
        tk.Label(left, text="BravelGo", font=FONT_LG, fg=C.TEXT, bg=C.HEADER).pack(anchor="w", pady=(12, 0))
        tk.Label(left, text="VM Profile Manager  ·  Ubuntu / UTM", font=FONT_SM,
                 fg=C.TEXT3, bg=C.HEADER).pack(anchor="w")

        self._status_dot = tk.Label(bar, text="● Ready", font=FONT_SM, fg=C.SUCCESS, bg=C.HEADER)
        self._status_dot.pack(side="right", padx=20)
        return bar

    def set_status(self, text: str, kind: str = "ok"):
        colors = {"ok": C.SUCCESS, "warn": C.WARN, "err": C.DANGER, "idle": C.TEXT3}
        self._status_dot.configure(text=f"● {text}", fg=colors.get(kind, C.TEXT2))

    def _tab_bar(self, parent, tabs: list[tuple[str, str]]) -> tuple[tk.Frame, dict[str, tk.Frame]]:
        """tabs = [(id, label), ...]"""
        wrap = tk.Frame(parent, bg=C.BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=(8, 0))

        bar = tk.Frame(wrap, bg=C.BG)
        bar.pack(fill="x", pady=(0, 10))

        content = tk.Frame(wrap, bg=C.BG)
        content.pack(fill="both", expand=True)

        frames: dict[str, tk.Frame] = {}
        buttons: dict[str, tk.Button] = {}
        self._active_tab = tabs[0][0]

        def select(tab_id: str):
            self._active_tab = tab_id
            for tid, fr in frames.items():
                fr.pack_forget()
            frames[tab_id].pack(fill="both", expand=True)
            for tid, btn in buttons.items():
                active = tid == tab_id
                btn.configure(
                    bg=C.TAB_ACTIVE if active else C.TAB_IDLE,
                    fg=C.ACCENT_TEXT if active else C.TEXT2,
                    font=FONT_BOLD if active else FONT,
                    relief="flat",
                    highlightthickness=1,
                    highlightbackground=C.ACCENT if active else C.BORDER,
                    highlightcolor=C.ACCENT if active else C.BORDER,
                )

        for tab_id, label in tabs:
            fr = tk.Frame(content, bg=C.BG)
            frames[tab_id] = fr
            btn = tk.Button(
                bar, text=label, command=lambda t=tab_id: select(t),
                bg=C.TAB_IDLE, fg=C.TEXT2, activebackground=C.TAB_ACTIVE,
                activeforeground=C.ACCENT_TEXT, relief="flat", bd=0,
                padx=16, pady=10, cursor="hand2", font=FONT,
                highlightthickness=1, highlightbackground=C.BORDER,
            )
            btn.pack(side="left", padx=(0, 6))
            buttons[tab_id] = btn

        select(tabs[0][0])
        return wrap, frames

    def _card(self, parent, title: str | None = None, expand=False) -> tk.Frame:
        outer = tk.Frame(parent, bg=C.BORDER, padx=1, pady=1)
        if expand:
            outer.pack(fill="both", expand=True, pady=(0, 12))
        else:
            outer.pack(fill="x", pady=(0, 12))

        inner = tk.Frame(outer, bg=C.SURFACE, padx=16, pady=14)
        inner.pack(fill="both", expand=True)

        if title:
            tk.Label(inner, text=title.upper(), font=FONT_SM, fg=C.TEXT3,
                     bg=C.SURFACE, anchor="w").pack(fill="x", pady=(0, 10))
        return inner

    def _btn(self, parent, text, command, variant="default", **pack_kw):
        styles = {
            "primary": (C.ACCENT, C.ACCENT_TEXT, C.ACCENT_DIM),
            "success": (C.SUCCESS_BG, C.SUCCESS, "#14532d"),
            "danger": (C.DANGER_BG, C.DANGER, "#450a0a"),
            "ghost": (C.SURFACE2, C.TEXT2, C.ELEVATED),
            "default": (C.ELEVATED, C.TEXT, C.SURFACE2),
        }
        bg, fg, active = styles.get(variant, styles["default"])
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg, activebackground=active, activeforeground=fg,
            relief="flat", bd=0, padx=14, pady=9, cursor="hand2", font=FONT_BOLD,
            highlightthickness=0,
        )
        btn.pack(**pack_kw)
        return btn

    def _entry(self, parent, **kw) -> tk.Entry:
        e = tk.Entry(
            parent, bg=C.INPUT_BG, fg=C.INPUT_FG, insertbackground=C.ACCENT,
            relief="flat", highlightthickness=1,
            highlightbackground=C.BORDER, highlightcolor=C.BORDER_FOCUS,
            font=FONT_MONO,
        )
        e.pack(fill="x", pady=(4, 0), ipady=8, **kw)
        return e

    def _listbox(self, parent, height=7) -> tk.Listbox:
        lb = tk.Listbox(
            parent, height=height, bg=C.INPUT_BG, fg=C.TEXT,
            selectbackground=C.ACCENT_DIM, selectforeground=C.ACCENT_TEXT,
            activestyle="none", relief="flat", highlightthickness=1,
            highlightbackground=C.BORDER, highlightcolor=C.BORDER,
            font=FONT_MONO,
            bd=0,
        )
        lb.pack(fill="both", expand=True, pady=(6, 0))
        return lb

    def _text(self, parent, height=8, mono=True, readonly=False) -> scrolledtext.ScrolledText:
        font = tk_font(FONT_MONO if mono else FONT)
        t = scrolledtext.ScrolledText(
            parent, height=height, bg=C.INPUT_BG, fg=C.TEXT2,
            insertbackground=C.ACCENT, relief="flat",
            highlightthickness=1, highlightbackground=C.BORDER,
            font=font, wrap="word" if not mono else "none",
        )
        t.pack(fill="both", expand=True, pady=(6, 0))
        if readonly:
            t.configure(state="disabled")
        return t

    def _log_panel(self, parent) -> scrolledtext.ScrolledText:
        outer = tk.Frame(parent, bg=C.BORDER, padx=1, pady=1)
        outer.pack(fill="both", expand=True)

        inner = tk.Frame(outer, bg=C.SURFACE, padx=12, pady=10)
        inner.pack(fill="both", expand=True)
        inner.grid_rowconfigure(1, weight=1)
        inner.grid_columnconfigure(0, weight=1)

        tk.Label(inner, text="CONSOLE", font=FONT_SM, fg=C.TEXT3,
                 bg=C.SURFACE, anchor="w").grid(row=0, column=0, sticky="ew", pady=(0, 6))

        log = scrolledtext.ScrolledText(
            inner, height=10, bg=C.LOG_BG, fg=C.LOG_FG,
            insertbackground=C.LOG_FG, relief="flat",
            highlightthickness=0, font=FONT_MONO,
            wrap="none",
        )
        log.grid(row=1, column=0, sticky="nsew")
        return log

    def _info_row(self, parent, label: str, value: str = "—") -> tk.Label:
        row = tk.Frame(parent, bg=C.SURFACE)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=FONT_SM, fg=C.TEXT3, bg=C.SURFACE, width=14, anchor="w").pack(side="left")
        lbl = tk.Label(row, text=value, font=FONT_MONO, fg=C.TEXT, bg=C.SURFACE, anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        return lbl

    def _hint(self, parent, text: str, bg: str | None = None):
        wrap = getattr(self, "_hint_wrap", 900)
        tk.Label(
            parent,
            text=text,
            font=FONT_SM,
            fg=C.TEXT3,
            bg=bg or C.SURFACE,
            justify="left",
            wraplength=wrap,
        ).pack(fill="x", pady=(0, 8))

    def _scrollable_panel(self, parent) -> tk.Frame:
        """Scrollable inner frame — parent must use grid with row weight on container."""
        container = tk.Frame(parent, bg=C.BG)
        container.grid(row=1, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(container, bg=C.BG, highlightthickness=0, borderwidth=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        inner = tk.Frame(canvas, bg=C.BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(win, width=event.width)

        inner.bind("<Configure>", _on_inner_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _wheel(event):
            delta = 0
            if hasattr(event, "delta") and event.delta:
                delta = -1 * int(event.delta / 120)
            elif getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            if delta:
                canvas.yview_scroll(delta, "units")

        def _bind_wheel(_event=None):
            canvas.bind_all("<MouseWheel>", _wheel)
            canvas.bind_all("<Button-4>", _wheel)
            canvas.bind_all("<Button-5>", _wheel)

        def _unbind_wheel(_event=None):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                canvas.unbind_all(seq)

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)
        return inner

    def _action_toolbar(self, parent, title: str = "Actions") -> tk.Frame:
        """Fixed top toolbar (does not scroll). Parent: grid row=0."""
        bar = tk.Frame(parent, bg=C.BORDER, padx=1, pady=1)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        inner = tk.Frame(bar, bg=C.ELEVATED, padx=12, pady=10)
        inner.pack(fill="x")
        tk.Label(
            inner, text=title.upper(), font=FONT_SM, fg=C.TEXT3, bg=C.ELEVATED, anchor="w",
        ).pack(fill="x", pady=(0, 8))
        btn_row = tk.Frame(inner, bg=C.ELEVATED)
        btn_row.pack(fill="x")
        return btn_row
