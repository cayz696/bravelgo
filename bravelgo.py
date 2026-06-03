#!/usr/bin/env python3
"""
BravelGo — Professional VM Profile Manager
Variant A + Modern UI | Ubuntu 24.04 | UTM | Firefox APT
sudo python3 bravelgo.py
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

if "/.local/share/Trash/" in BASE_DIR:
    print(f"ERROR: running BravelGo from Trash:\n  {BASE_DIR}")
    print("Restore or copy the project to ~/Desktop/google, then run:")
    print("  sudo python3 ~/Desktop/google/bravelgo.py")
    sys.exit(1)

from bravelgo.countries import (  # noqa: E402
    COUNTRY_PROFILES,
    country_profile,
    fingerprint_summary,
    generate_fingerprint,
)
from bravelgo.ff_profile import create_profile, launch_profile, write_user_js  # noqa: E402
from bravelgo.proxy_geo import (  # noqa: E402
    BRIDGE_PORT,
    get_proxy_country,
    start_bridge,
    stop_bridge,
    test_proxy,
    write_bridge,
)
from bravelgo.registry import (  # noqa: E402
    ff_profile_name,
    register_vm,
    registry_path,
    registry_summary,
    unique_fingerprint,
    unique_mac,
)
from bravelgo.ui_theme import C, FONT_MONO, ModernApp, tk_font  # noqa: E402

FONT_MONO = tk_font(FONT_MONO)

if os.geteuid() != 0:
    print("❌ sudo python3 bravelgo.py")
    sys.exit(1)

REAL_USER = os.environ.get("SUDO_USER") or "ubuntu"
USER_HOME = f"/home/{REAL_USER}"
CONFIG_F = f"{USER_HOME}/.bravelgo.json"
MOUNT_PT = f"{USER_HOME}/MacFolder"


def _run(cmd: str) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def cfg_load() -> dict:
    try:
        if os.path.exists(CONFIG_F):
            with open(CONFIG_F, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    from bravelgo.publish.config import default_publish_config

    return {
        "proxies": [],
        "active_proxy": "",
        "proxy_type": "HTTP",
        "fingerprint": {},
        "ff_profile": "",
        "publish": default_publish_config(),
    }


def cfg_save(c: dict) -> None:
    with open(CONFIG_F, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    _run(f"chown {REAL_USER}:{REAL_USER} '{CONFIG_F}'")


def ensure_locale(locale: str, log=None) -> str:
    """Generate locale if needed; return locale or en_US.UTF-8 fallback."""
    fallback = "en_US.UTF-8"
    target = locale or fallback

    _run(f"sed -i 's/^# \\({target}\\)/\\1/' /etc/locale.gen")
    _run(f"grep -q '^{target}' /etc/locale.gen || echo '{target} UTF-8' >> /etc/locale.gen")
    _run(f"sed -i 's/^# \\({fallback}\\)/\\1/' /etc/locale.gen")
    _run(f"grep -q '^{fallback}' /etc/locale.gen || echo '{fallback} UTF-8' >> /etc/locale.gen")
    _run("locale-gen")

    rc, _ = _run(f"locale -a | grep -F '{target}'")
    if rc == 0:
        return target
    if log:
        log(f"Locale {target} unavailable — keeping {fallback} for system UI")
    return fallback


def apply_locale(cp: dict, log=None) -> str:
    """Apply timezone + locale safely (bad locale breaks GDM → black screen)."""
    locale = ensure_locale(cp["locale"], log)
    _run(f"timedatectl set-timezone '{cp['timezone']}'")
    _run(f"update-locale LANG={locale} LC_ALL={locale}")
    _run("sed -i '/^LANG=/d;/^LC_ALL=/d' /etc/environment")
    with open("/etc/environment", "a", encoding="utf-8") as f:
        f.write(f"\nLANG={locale}\nLC_ALL={locale}\n")
    _run(f"localectl set-x11-keymap {cp['keyboard']} 2>/dev/null || true")
    if log:
        log(f"Locale → {locale} / {cp['timezone']}")
    return locale


class App(ModernApp):
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BravelGo")
        self.cfg = cfg_load()
        self._init_theme(root)
        self._apply_window_geometry(root, ratio=0.70)
        self._header(root)

        shell = tk.Frame(root, bg=C.BG)
        shell.pack(fill="both", expand=True)
        shell.grid_rowconfigure(0, weight=3)
        shell.grid_rowconfigure(1, weight=2)
        shell.grid_columnconfigure(0, weight=1)

        body = tk.Frame(shell, bg=C.BG)
        body.grid(row=0, column=0, sticky="nsew", padx=16, pady=(8, 4))
        _, frames = self._tab_bar(
            body,
            [
                ("full", " Uniquify "),
                ("proxy", " Proxy "),
                ("profile", " Profile "),
                ("hw", " Hardware "),
                ("disk", " Disk "),
                ("warmup", " Warmup "),
                ("publish", " Publish "),
            ],
        )
        self.tab_full = frames["full"]
        self.tab_proxy = frames["proxy"]
        self.tab_profile = frames["profile"]
        self.tab_hw = frames["hw"]
        self.tab_disk = frames["disk"]
        self.tab_warmup = frames["warmup"]
        self.tab_publish = frames["publish"]

        self._build_full()
        self._build_proxy()
        self._build_profile()
        self._build_hw()
        self._build_disk()
        self._build_warmup()
        self._build_publish()

        log_wrap = tk.Frame(shell, bg=C.BG)
        log_wrap.grid(row=1, column=0, sticky="nsew", padx=16, pady=(4, 14))
        self.log_box = self._log_panel(log_wrap)

        if self.cfg.get("fingerprint"):
            self._fp_display(self.cfg["fingerprint"])

        threading.Thread(target=self._consistency_check, daemon=True).start()

    def log(self, msg: str) -> None:
        self.log_box.insert(tk.END, f"[*] {msg}\n")
        self.log_box.see(tk.END)
        self.root.update_idletasks()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _parse_proxy(self, raw: str):
        raw = str(raw).strip().replace("socks5://", "").replace("http://", "")
        parts = raw.split(":")
        if len(parts) == 4 and parts[1].isdigit():
            return parts
        return None

    def _active_proxy_str(self):
        sel = self.lb_proxy.curselection()
        if sel:
            return self.lb_proxy.get(sel[0])
        raw = self.ent_proxy.get().strip().replace("socks5://", "").replace("http://", "")
        if not raw:
            raw = self.cfg.get("active_proxy", "").replace("socks5://", "").replace("http://", "")
        ptype = self.combo_ptype.get() or self.cfg.get("proxy_type", "HTTP")
        if self._parse_proxy(raw):
            return f"socks5://{raw}" if ptype == "SOCKS5" else raw
        saved = self.cfg.get("active_proxy", "").strip()
        return saved if saved else None

    def _iface(self):
        _, out = _run("ip route show default")
        m = re.search(r"dev (\S+)", out)
        return m.group(1) if m else ""

    def _active_profile_dir(self) -> str:
        p = self.cfg.get("ff_profile", "")
        return p if p and os.path.isdir(p) else ""

    # ── FULL UNIQUIFY ─────────────────────────────────────────────────────────
    def _build_full(self):
        p = self.tab_full
        self._hint(self._card(p, "One-click clone reset"), 
                   "Proxy country drives locale, timezone and Firefox language.\n"
                   "Variant A: honest Linux Firefox — no fake UA/GPU.")

        cf = self._card(p, "Steps")
        steps = tk.Frame(cf, bg=C.SURFACE)
        steps.pack(fill="x")
        self.v_f_hw = tk.BooleanVar(value=True)
        self.v_f_locale = tk.BooleanVar(value=True)
        self.v_f_ipv6 = tk.BooleanVar(value=True)
        self.v_f_ssh = tk.BooleanVar(value=True)
        self.v_f_cache = tk.BooleanVar(value=True)
        self.v_f_journal = tk.BooleanVar(value=True)
        self.v_f_ffprofile = tk.BooleanVar(value=True)
        self.v_f_proxy = tk.BooleanVar(value=True)
        for i, (var, txt) in enumerate([
            (self.v_f_hw, "MAC + Machine-ID + Hostname"),
            (self.v_f_locale, "Locale + TZ + keyboard from proxy"),
            (self.v_f_ipv6, "Disable IPv6"),
            (self.v_f_ssh, "Regenerate SSH keys"),
            (self.v_f_cache, "Clear user cache"),
            (self.v_f_journal, "Clear systemd journal"),
            (self.v_f_ffprofile, "New Firefox profile"),
            (self.v_f_proxy, "Apply proxy via bridge"),
        ]):
            ttk.Checkbutton(steps, text=txt, variable=var).grid(row=i // 2, column=i % 2, sticky="w", padx=8, pady=3)

        ck = self._card(p, "Consistency check")
        self.txt_consistency = self._text(ck, height=10, mono=True, readonly=True)

        bf = tk.Frame(p, bg=C.BG)
        bf.pack(fill="x", pady=(0, 8))
        self._btn(bf, "Run check", lambda: threading.Thread(target=self._consistency_check, daemon=True).start(),
                  variant="ghost", side="left", padx=(0, 8))
        self._btn(bf, "Full uniquify", lambda: threading.Thread(target=self._full_unique, daemon=True).start(),
                  variant="primary", side="left", padx=(0, 8))
        self._btn(bf, "Launch Firefox", self._launch_ff, variant="ghost", side="left")

    def _consistency_check(self):
        lines, issues = [], []
        proxy_str = self._active_proxy_str()
        cc, proxy_tz = "?", "?"
        if proxy_str:
            parts = self._parse_proxy(proxy_str)
            if parts:
                cc, proxy_tz = get_proxy_country(
                    parts[0], parts[1], parts[2], parts[3],
                    proxy_str.startswith("socks5://"), self.log,
                )
        _, os_tz = _run("timedatectl show --property=Timezone --value")
        _, os_lang = _run("grep -E '^LANG=' /etc/default/locale 2>/dev/null | cut -d= -f2")
        _, hn = _run("hostname")
        _, mid = _run("cat /etc/machine-id")
        fp = self.cfg.get("fingerprint", {})
        fp_tz, fp_cc = fp.get("timezone", "?"), fp.get("country_code", "?")
        fp_hn = fp.get("hostname", "?")
        lines.append(f"Proxy   : {cc}  TZ={proxy_tz}")
        lines.append(f"OS      : TZ={os_tz}  LANG={os_lang or '?'}")
        lines.append(f"Profile : {fp_cc}  TZ={fp_tz}  host={fp_hn}")
        lines.append(f"System  : host={hn}  mid={mid[:12]}…")
        _, ipv6 = _run("ip -6 addr show scope global 2>/dev/null")
        lines.append(f"IPv6    : {'ACTIVE' if ipv6.strip() else 'off'}")
        prof = self._active_profile_dir()
        lines.append(f"FF dir  : {os.path.basename(prof) if prof else 'none'}")
        lines.append(registry_summary(registry_path(USER_HOME, MOUNT_PT)))
        if cc != "?" and fp_cc != "?" and cc != fp_cc:
            issues.append(f"Country mismatch proxy={cc} profile={fp_cc}")
        if proxy_tz != "?" and os_tz != "?" and proxy_tz != os_tz:
            issues.append(f"TZ mismatch proxy={proxy_tz} OS={os_tz}")
        if fp_hn != "?" and hn and fp_hn != hn:
            issues.append(f"Hostname mismatch profile={fp_hn} system={hn}")
        if fp_tz != "?" and os_tz != "?" and fp_tz != os_tz:
            issues.append(f"TZ mismatch profile={fp_tz} OS={os_tz}")
        if ipv6.strip():
            issues.append("IPv6 leak risk")
        lines.append("")
        lines.append("Issues:" if issues else "All consistent")
        lines.extend(issues or ["none"])
        self._set_readonly(self.txt_consistency, "\n".join(lines), C.DANGER if issues else C.SUCCESS)

    def _set_readonly(self, widget, text, color=None):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        if color:
            widget.configure(fg=color)
        widget.configure(state="disabled")

    def _full_unique(self):
        self.log("=== FULL UNIQUIFY ===")
        self.set_status("Working…", "warn")
        proxy_str = self._active_proxy_str()
        cc, proxy_tz = "?", "?"
        if proxy_str:
            parts = self._parse_proxy(proxy_str)
            if parts:
                cc, proxy_tz = get_proxy_country(
                    parts[0], parts[1], parts[2], parts[3],
                    proxy_str.startswith("socks5://"), self.log,
                )
        if cc == "?":
            cc = self.cfg.get("fingerprint", {}).get("country_code", "FR")
            self.log(f"Geo fallback → {cc} (no proxy geo)")
        else:
            self.log(f"Country from proxy geo → {cc} (Profile dropdown ignored by Full uniquify)")
        tz_use = proxy_tz if proxy_tz != "?" else None
        reg = registry_path(USER_HOME, MOUNT_PT)
        self.log(registry_summary(reg))
        fp = unique_fingerprint(cc, tz_use, reg, self.log)
        self.cfg["fingerprint"] = fp
        cfg_save(self.cfg)
        self.root.after(0, lambda: self._fp_display(fp))
        cp = country_profile(cc, tz_use or fp.get("timezone"))
        mac = ""

        if self.v_f_hw.get():
            hn = fp["hostname"]
            _run(f"hostnamectl set-hostname '{hn}'")
            _run("sed -i '/127.0.1.1/d' /etc/hosts")
            _run(f"echo '127.0.1.1\\t{hn}' >> /etc/hosts")
            _run("rm -f /etc/machine-id /var/lib/dbus/machine-id")
            _run("systemd-machine-id-setup && ln -sf /etc/machine-id /var/lib/dbus/machine-id")
            iface = self._iface()
            if iface:
                mac = unique_mac(reg)
                _run(f"ip link set dev {iface} down && ip link set dev {iface} address {mac} && ip link set dev {iface} up")
                os.makedirs("/etc/NetworkManager/conf.d", exist_ok=True)
                with open("/etc/NetworkManager/conf.d/bravelgo-mac.conf", "w") as f:
                    f.write(f"[connection]\nethernet.cloned-mac-address={mac}\nwifi.cloned-mac-address={mac}\n")
                _run("systemctl reload NetworkManager")
            self.log(f"Hardware OK → {hn}")

        if self.v_f_locale.get():
            apply_locale(cp, self.log)

        if self.v_f_ipv6.get():
            with open("/etc/sysctl.d/99-bravelgo-noipv6.conf", "w") as f:
                f.write("net.ipv6.conf.all.disable_ipv6=1\nnet.ipv6.conf.default.disable_ipv6=1\n")
            _run("sysctl -p /etc/sysctl.d/99-bravelgo-noipv6.conf")
            self.log("IPv6 off")

        if self.v_f_ssh.get():
            _run("rm -f /etc/ssh/ssh_host_* && ssh-keygen -A 2>/dev/null")
            self.log("SSH keys reset")

        if self.v_f_cache.get():
            for d in (f"{USER_HOME}/.cache", f"{USER_HOME}/.thumbnails"):
                if os.path.isdir(d):
                    _run(f"find '{d}' -mindepth 1 -not -name '*.socket' -delete 2>/dev/null || true")
            _run(f"truncate -s 0 {USER_HOME}/.bash_history 2>/dev/null || true")
            self.log("Cache cleared")

        if self.v_f_journal.get():
            _run("journalctl --rotate 2>/dev/null; journalctl --vacuum-time=1s 2>/dev/null")
            self.log("Journal cleared")

        profile_dir = self._active_profile_dir()
        if self.v_f_ffprofile.get():
            profile_dir = create_profile(USER_HOME, REAL_USER, fp, self.log)
            self.cfg["ff_profile"] = profile_dir
            cfg_save(self.cfg)

        proxy_on = False
        if self.v_f_proxy.get() and proxy_str:
            parts = self._parse_proxy(proxy_str)
            if parts:
                self._apply_proxy_parts(parts, proxy_str.startswith("socks5://"))
                proxy_on = True

        if profile_dir:
            write_user_js(profile_dir, fp, REAL_USER, proxy_on, self.log)
        elif proxy_on:
            self.log("⚠ Create Firefox profile first for isolated prefs")

        _, mid = _run("cat /etc/machine-id")
        if not mac:
            iface = self._iface()
            if iface:
                _, mac = _run(f"cat /sys/class/net/{iface}/address")
        register_vm(
            reg,
            hostname=fp["hostname"],
            machine_id=mid or "",
            mac=mac or "",
            ff_profile=ff_profile_name(fp) if profile_dir else "",
            country=fp.get("country_code", cc),
            timezone=fp.get("timezone", ""),
            real_user=REAL_USER,
            log=self.log,
        )

        self.set_status(f"Done · {cc}", "ok")
        self.log("=== DONE — reboot for machine-id, restart Firefox ===")
        threading.Thread(target=self._consistency_check, daemon=True).start()
        self.root.after(
            0,
            lambda: self.show_info(
                "Uniquify done",
                f"Country: {fp.get('country_name', cp['name'])} ({fp.get('country_code', cc)})\n"
                f"TZ: {fp.get('timezone', '?')}\n"
                f"Host: {fp['hostname']}\n\n"
                "Source: active proxy geo (recommended).\n"
                "Profile tab dropdown is preview only.\n\n"
                "Next: reboot VM, then Proxy → Apply, then Warmup.",
            ),
        )

    def _launch_ff(self):
        launch_profile(REAL_USER, self._active_profile_dir(), self.log)

    # ── WARMUP TAB ────────────────────────────────────────────────────────────
    def _build_warmup(self):
        p = self.tab_warmup
        self._hint(
            self._card(p, "Human-like warmup"),
            "Selenium warmup · robot icon only while script runs.\n"
            "NEVER log into Google during warmup. Use Launch Firefox for Google/Play login.\n"
            "Recommended: «Skip Google» ON — geo sites + Maps (places/photos by proxy country).",
        )
        opts = self._card(p, "Session")
        row = tk.Frame(opts, bg=C.SURFACE)
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text="Search language", fg=C.TEXT2, bg=C.SURFACE).pack(side="left")
        self.combo_warmup_lang = ttk.Combobox(
            row,
            values=["geo — local language (recommended)", "mixed — local + English dev", "en — English only"],
            state="readonly",
            width=34,
        )
        self.combo_warmup_lang.set("geo — local language (recommended)")
        self.combo_warmup_lang.pack(side="left", padx=(8, 16))
        tk.Label(row, text="Max sites", fg=C.TEXT2, bg=C.SURFACE).pack(side="left")
        self.spin_warmup_sites = ttk.Spinbox(row, from_=3, to=12, width=4)
        self.spin_warmup_sites.set("6")
        self.spin_warmup_sites.pack(side="left", padx=(6, 16))
        tk.Label(row, text="Minutes", fg=C.TEXT2, bg=C.SURFACE).pack(side="left")
        self.spin_warmup_min = ttk.Spinbox(row, from_=8, to=45, width=4)
        self.spin_warmup_min.set("15")
        self.spin_warmup_min.pack(side="left", padx=6)

        flags = tk.Frame(opts, bg=C.SURFACE)
        flags.pack(fill="x")
        self.v_warmup_images = tk.BooleanVar(value=True)
        self.v_warmup_maps = tk.BooleanVar(value=True)
        self.v_warmup_bg = tk.BooleanVar(value=True)
        self.v_warmup_detached = tk.BooleanVar(value=False)
        self.v_warmup_skip_google = tk.BooleanVar(value=True)
        for txt, var in [
            ("Skip Google search/images (recommended — keeps Maps + geo sites)", self.v_warmup_skip_google),
            ("Google Images (needs Skip Google OFF)", self.v_warmup_images),
            ("Google Maps — geo places + view/download 2–3 photos", self.v_warmup_maps),
            ("Background-safe (minimize OK)", self.v_warmup_bg),
            ("Detached — survives BravelGo close", self.v_warmup_detached),
        ]:
            ttk.Checkbutton(flags, text=txt, variable=var).pack(anchor="w", pady=1)

        sf = self._card(p, "Geo sites preview", expand=True)
        from bravelgo.warmup_geo import pick_sites

        cc = self.cfg.get("fingerprint", {}).get("country_code", "FR")
        preview = pick_sites(cc, 8)
        self.txt_warmup_urls = self._text(sf, height=8, mono=True, readonly=False)
        self.txt_warmup_urls.insert(tk.END, "\n".join(preview))

        bf = tk.Frame(p, bg=C.BG)
        bf.pack(fill="x", pady=(0, 8))
        self._btn(bf, "Refresh URLs from profile country", self._warmup_refresh_urls, variant="ghost", side="left", padx=(0, 8))
        self._btn(bf, "Reinstall Firefox", self._warmup_reinstall_ff, variant="ghost", side="left", padx=(0, 8))
        self._btn(bf, "Start warmup", self._warmup_thread, variant="primary", side="left", padx=(0, 8))
        self._btn(bf, "Tail log", self._warmup_tail_log, variant="ghost", side="left")

    def _warmup_lang_mode(self) -> str:
        v = self.combo_warmup_lang.get()
        if v.startswith("en"):
            return "en"
        if v.startswith("mixed"):
            return "mixed"
        return "geo"

    def _warmup_refresh_urls(self):
        from bravelgo.warmup_geo import pick_sites
        cc = self.cfg.get("fingerprint", {}).get("country_code", "FR")
        urls = pick_sites(cc, int(self.spin_warmup_sites.get()))
        self.txt_warmup_urls.configure(state="normal")
        self.txt_warmup_urls.delete("1.0", tk.END)
        self.txt_warmup_urls.insert(tk.END, "\n".join(urls))
        self.txt_warmup_urls.configure(state="normal")

    def _warmup_thread(self):
        threading.Thread(target=self._warmup_run, daemon=True).start()

    def _warmup_reinstall_ff(self):
        def work():
            from bravelgo.deps import reinstall_firefox, install_geckodriver, install_selenium

            self.log("=== Reinstall Firefox stack ===")
            ok = reinstall_firefox(self.log)
            ok = install_geckodriver(self.log) and ok
            ok = install_selenium(REAL_USER, self.log) and ok
            self.set_status("Firefox OK" if ok else "Install failed", "ok" if ok else "idle")

        threading.Thread(target=work, daemon=True).start()

    def _warmup_run(self):
        profile = self._active_profile_dir()
        if not profile:
            self.root.after(0, lambda: self.show_error("Warmup", "No Firefox profile — run Full uniquify first"))
            return

        from bravelgo.deps import ensure_warmup_deps

        if not ensure_warmup_deps(self.log, REAL_USER):
            self.set_status("Warmup blocked — install deps", "idle")
            return

        _, bridge = _run("systemctl is-active bravelgo-bridge 2>/dev/null")
        if bridge.strip() != "active":
            self.log("⚠ Bridge not active — apply proxy first (Proxy tab)")
        _run("killall -9 firefox firefox-esr 2>/dev/null")
        time.sleep(2)
        prof = self._active_profile_dir()
        if prof:
            for lock in ("lock", ".parentlock", "parent.lock"):
                try:
                    os.remove(os.path.join(prof, lock))
                except OSError:
                    pass

        fp = self.cfg.get("fingerprint", {})
        cc = fp.get("country_code", "FR")
        lang = self._warmup_lang_mode()
        max_sites = int(self.spin_warmup_sites.get())
        minutes = int(self.spin_warmup_min.get())

        urls_file = f"{USER_HOME}/.bravelgo-warmup-urls.txt"
        urls_text = self.txt_warmup_urls.get("1.0", tk.END).strip()
        with open(urls_file, "w", encoding="utf-8") as f:
            f.write(urls_text + "\n")
        _run(f"chown {REAL_USER}:{REAL_USER} '{urls_file}'")

        script = os.path.join(BASE_DIR, "bravelgo", "run_warmup.py")
        log_path = f"{USER_HOME}/.bravelgo-warmup.log"
        cmd = [
            "sudo", "-u", REAL_USER,
            "env", "DISPLAY=:0", f"HOME={USER_HOME}",
            "python3", script,
            "--profile-dir", profile,
            "--country", cc,
            "--max-sites", str(max_sites),
            "--lang-mode", lang,
            "--bridge-port", str(BRIDGE_PORT),
            "--minutes", str(minutes),
            "--urls-file", urls_file,
        ]
        if not self.v_warmup_images.get():
            cmd.append("--no-images")
        if not self.v_warmup_maps.get():
            cmd.append("--no-maps")
        if not self.v_warmup_bg.get():
            cmd.append("--no-background-safe")
        if not self.v_warmup_skip_google.get():
            cmd.append("--google")

        self.log(f"Warmup start · {cc} · {lang} · {max_sites} sites · {minutes} min")
        self.set_status("Warmup running…", "warn")

        if self.v_warmup_detached.get():
            with open(log_path, "w", encoding="utf-8") as lf:
                lf.write(f"Warmup started · {cc}\n")
            _run(f"chown {REAL_USER}:{REAL_USER} '{log_path}'")
            with open(log_path, "a", encoding="utf-8") as lf:
                proc = subprocess.Popen(
                    cmd,
                    stdout=lf,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
            self.log(f"Detached PID {proc.pid} → {log_path}")
            self.log("Watch progress: Tail log · or tail -f ~/.bravelgo-warmup.log")
            self.set_status("Warmup detached", "ok")
            self.root.after(8000, self._warmup_tail_log)
            return

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
            for line in proc.stdout or []:
                line = line.rstrip()
                if line:
                    self.log(line.lstrip("[*] ").lstrip("* "))
            proc.wait()
            if proc.returncode == 0:
                self.set_status("Warmup done", "ok")
            else:
                self.set_status("Warmup failed", "idle")
                self.log(f"Exit code {proc.returncode}")
        except Exception as exc:
            self.log(f"Warmup error: {exc}")
            self.set_status("Warmup error", "idle")

    def _warmup_tail_log(self):
        log_path = f"{USER_HOME}/.bravelgo-warmup.log"
        if not os.path.isfile(log_path):
            self.log("No warmup log yet")
            return
        try:
            with open(log_path, encoding="utf-8") as f:
                tail = f.read()[-3000:]
            for ln in tail.splitlines()[-25:]:
                self.log(ln)
        except Exception as exc:
            self.log(f"Log read error: {exc}")

    # ── PUBLISH TAB ───────────────────────────────────────────────────────────
    def _build_publish(self):
        from bravelgo.publish.config import merge_publish_config

        p = self.tab_publish
        pub = merge_publish_config(self.cfg)
        self._hint(
            self._card(p, "Play publish (UI automation)"),
            "System Firefox (deb) + auto-detected Mozilla profile · Playwright.\n"
            "Gemini Vision for any UI language · detached background like Warmup.\n"
            "Opens browser → you go to Play Console → Continue → Docs + Console tasks.",
        )

        pf = self._card(p, "Firefox profile (auto)")
        self.lbl_pub_profile = tk.Label(pf, text="", fg=C.TEXT2, bg=C.SURFACE, justify="left", anchor="w")
        self.lbl_pub_profile.pack(fill="x")
        self._publish_show_profile()

        acc = self._card(p, "Account & app")
        g = tk.Frame(acc, bg=C.SURFACE)
        g.pack(fill="x")
        def _pub_entry(parent, width=40):
            e = tk.Entry(
                parent, width=width, bg=C.INPUT_BG, fg=C.INPUT_FG, insertbackground=C.ACCENT,
                relief="flat", highlightthickness=1,
                highlightbackground=C.BORDER, highlightcolor=C.BORDER_FOCUS,
                font=FONT_MONO,
            )
            e.pack(side="left", fill="x", expand=True, ipady=6)
            return e

        for label, attr, width in (
            ("Account email", "ent_pub_email", 42),
            ("Package name", "ent_pub_package", 42),
            ("App name", "ent_pub_app", 36),
        ):
            row = tk.Frame(g, bg=C.SURFACE)
            row.pack(fill="x", pady=(0, 6))
            tk.Label(row, text=label, fg=C.TEXT2, bg=C.SURFACE, width=14, anchor="w").pack(side="left")
            setattr(self, attr, _pub_entry(row, width))
        self.ent_pub_email.insert(0, pub.get("account_email", ""))
        self.ent_pub_package.insert(0, pub.get("package_name", ""))
        self.ent_pub_app.insert(0, pub.get("app_name", ""))

        row2 = tk.Frame(acc, bg=C.SURFACE)
        row2.pack(fill="x", pady=(4, 0))
        self.v_pub_app_exists = tk.BooleanVar(value=bool(pub.get("app_already_exists")))
        ttk.Checkbutton(
            row2,
            text="App already exists in Console (skip Create application)",
            variable=self.v_pub_app_exists,
        ).pack(anchor="w")
        self.v_pub_vision = tk.BooleanVar(value=bool(pub.get("use_vision", True)))
        ttk.Checkbutton(row2, text="Gemini Vision (any Console language)", variable=self.v_pub_vision).pack(anchor="w")
        self.v_pub_wait = tk.BooleanVar(value=bool(pub.get("wait_for_console", True)))
        ttk.Checkbutton(
            row2,
            text="Wait for Play Console before automation (Continue button)",
            variable=self.v_pub_wait,
        ).pack(anchor="w")
        self.v_pub_detached = tk.BooleanVar(value=bool(pub.get("detached", True)))
        ttk.Checkbutton(
            row2,
            text="Detached — runs in background (like Warmup)",
            variable=self.v_pub_detached,
        ).pack(anchor="w")

        gf = self._card(p, "Gemini API (per VM profile)")
        kr = tk.Frame(gf, bg=C.SURFACE)
        kr.pack(fill="x")
        tk.Label(kr, text="API key", fg=C.TEXT2, bg=C.SURFACE, width=14, anchor="w").pack(side="left")
        self.ent_pub_gemini = tk.Entry(
            kr, width=48, show="*", bg=C.INPUT_BG, fg=C.INPUT_FG, insertbackground=C.ACCENT,
            relief="flat", highlightthickness=1,
            highlightbackground=C.BORDER, highlightcolor=C.BORDER_FOCUS,
            font=FONT_MONO,
        )
        self.ent_pub_gemini.pack(side="left", fill="x", expand=True, ipady=6)
        self.ent_pub_gemini.insert(0, pub.get("gemini_api_key", ""))

        gr = tk.Frame(gf, bg=C.SURFACE)
        gr.pack(fill="x", pady=(8, 0))
        tk.Label(gr, text="Graphics folder", fg=C.TEXT2, bg=C.SURFACE, width=14, anchor="w").pack(side="left")
        self.ent_pub_graphics = tk.Entry(
            gr, width=48, bg=C.INPUT_BG, fg=C.INPUT_FG, insertbackground=C.ACCENT,
            relief="flat", highlightthickness=1,
            highlightbackground=C.BORDER, highlightcolor=C.BORDER_FOCUS,
            font=FONT_MONO,
        )
        self.ent_pub_graphics.pack(side="left", fill="x", expand=True, ipady=6)
        self.ent_pub_graphics.insert(0, pub.get("graphics_dir", ""))

        pf = self._card(p, "Listing prompt (editable)", expand=True)
        self.txt_pub_listing_prompt = self._text(pf, height=8, mono=True, readonly=False)
        self.txt_pub_listing_prompt.insert(tk.END, pub.get("listing_prompt", ""))

        pp = self._card(p, "Privacy prompt (editable)", expand=True)
        self.txt_pub_privacy_prompt = self._text(pp, height=6, mono=True, readonly=False)
        self.txt_pub_privacy_prompt.insert(tk.END, pub.get("privacy_prompt", ""))

        out = self._card(p, "Last run")
        tk.Label(out, text="Privacy URL", fg=C.TEXT2, bg=C.SURFACE).pack(anchor="w")
        self.ent_pub_privacy_url = tk.Entry(
            out, bg=C.INPUT_BG, fg=C.INPUT_FG, insertbackground=C.ACCENT,
            relief="flat", highlightthickness=1,
            highlightbackground=C.BORDER, highlightcolor=C.BORDER_FOCUS,
            font=FONT_MONO,
        )
        self.ent_pub_privacy_url.pack(fill="x", pady=(4, 6), ipady=6)
        self.ent_pub_privacy_url.insert(0, pub.get("last_privacy_url", ""))
        self.lbl_pub_listing = tk.Label(out, text="", fg=C.TEXT2, bg=C.SURFACE, justify="left", anchor="w")
        self.lbl_pub_listing.pack(fill="x")
        self._publish_refresh_listing_label(pub)

        cf = tk.Frame(p, bg=C.BG)
        cf.pack(fill="x", pady=(0, 6))
        self._btn(
            cf,
            "Continue — I'm on Console",
            self._publish_continue_signal,
            variant="primary",
            side="left",
            padx=(0, 8),
        )
        self._hint(
            cf,
            "While publish runs: open play.google.com/console, then press Continue.",
        )

        bf = tk.Frame(p, bg=C.BG)
        bf.pack(fill="x", pady=(0, 8))
        self._btn(bf, "Save settings", self._publish_save, variant="ghost", side="left", padx=(0, 6))
        self._btn(bf, "Generate texts", self._publish_thread_generate, variant="ghost", side="left", padx=(0, 6))
        self._btn(bf, "Docs only", self._publish_thread_docs, variant="ghost", side="left", padx=(0, 6))
        self._btn(bf, "Console only", self._publish_thread_console, variant="ghost", side="left", padx=(0, 6))
        self._btn(bf, "Full publish", self._publish_thread_full, variant="primary", side="left", padx=(0, 6))
        self._btn(bf, "Tail log", self._publish_tail_log, variant="ghost", side="left")

    def _publish_collect(self) -> dict:
        from bravelgo.publish.config import merge_publish_config

        pub = merge_publish_config(self.cfg)
        pub["account_email"] = self.ent_pub_email.get().strip()
        pub["package_name"] = self.ent_pub_package.get().strip()
        pub["app_name"] = self.ent_pub_app.get().strip()
        pub["gemini_api_key"] = self.ent_pub_gemini.get().strip()
        pub["graphics_dir"] = self.ent_pub_graphics.get().strip()
        pub["listing_prompt"] = self.txt_pub_listing_prompt.get("1.0", tk.END).strip()
        pub["privacy_prompt"] = self.txt_pub_privacy_prompt.get("1.0", tk.END).strip()
        pub["app_already_exists"] = self.v_pub_app_exists.get()
        pub["use_vision"] = self.v_pub_vision.get()
        pub["wait_for_console"] = self.v_pub_wait.get()
        pub["detached"] = self.v_pub_detached.get()
        pub["last_privacy_url"] = self.ent_pub_privacy_url.get().strip()
        return pub

    def _publish_show_profile(self):
        from bravelgo.publish.profile_resolve import resolve_profile_dir

        prof = resolve_profile_dir(USER_HOME, self.cfg, None)
        if hasattr(self, "lbl_pub_profile"):
            if prof:
                self.lbl_pub_profile.configure(text=f"Using: {prof}")
            else:
                self.lbl_pub_profile.configure(
                    text="No profile found — run Full uniquify or Launch Firefox"
                )

    def _publish_continue_signal(self):
        from bravelgo.publish.wait_console import touch_continue_flag

        touch_continue_flag()
        _run(f"chown {REAL_USER}:{REAL_USER} '{USER_HOME}/.bravelgo-publish-go'")
        self.log("Continue signal sent — publish worker will proceed")
        self.set_status("Continue sent", "ok")

    def _publish_save(self):
        from bravelgo.publish.config import save_publish_section

        pub = self._publish_collect()
        save_publish_section(self.cfg, pub)
        cfg_save(self.cfg)
        self._publish_refresh_listing_label(pub)
        self.log("Publish settings saved")
        self.set_status("Publish settings saved", "ok")

    def _publish_refresh_listing_label(self, pub: dict):
        listing = pub.get("last_listing") or {}
        short = listing.get("short", "")
        full = listing.get("full", "")
        self.lbl_pub_listing.configure(
            text=f"Listing cached: short {len(short)}/80 · full {len(full)}/4000"
            if short or full
            else "Listing cached: (none — run Generate texts)"
        )

    def _publish_thread_generate(self):
        threading.Thread(target=lambda: self._publish_run(step="generate"), daemon=True).start()

    def _publish_thread_docs(self):
        threading.Thread(target=lambda: self._publish_run(step="docs"), daemon=True).start()

    def _publish_thread_console(self):
        threading.Thread(target=lambda: self._publish_run(step="console"), daemon=True).start()

    def _publish_thread_full(self):
        threading.Thread(target=lambda: self._publish_run(step="all"), daemon=True).start()

    def _publish_run(self, step: str = "all"):
        from bravelgo.publish.config import save_publish_section
        from bravelgo.publish.deps import ensure_publish_deps
        from bravelgo.publish.profile_resolve import resolve_profile_dir
        from bravelgo.publish.wait_console import clear_continue_flag

        profile = self._active_profile_dir() or resolve_profile_dir(USER_HOME, self.cfg, self.log)
        if not profile:
            self.root.after(
                0,
                lambda: self.show_error(
                    "Publish",
                    "Firefox profile not found — run Full uniquify or Launch Firefox once",
                ),
            )
            return

        pub = self._publish_collect()
        save_publish_section(self.cfg, pub)
        cfg_save(self.cfg)
        self._publish_show_profile()

        if step != "generate" and not ensure_publish_deps(self.log, REAL_USER):
            self.set_status("Publish blocked — install Playwright", "idle")
            return

        clear_continue_flag()

        self.log(f"Publish start · step={step} · {pub.get('package_name')}")
        self.log(f"Profile: {profile}")
        if step != "generate":
            self.log("Firefox will open via Playwright — go to Play Console, then Continue")
        self.set_status("Publish running…", "warn")

        script = os.path.join(BASE_DIR, "bravelgo", "run_publish.py")
        log_path = f"{USER_HOME}/.bravelgo-publish.log"
        cmd = [
            "sudo", "-u", REAL_USER,
            "env", "DISPLAY=:0", f"HOME={USER_HOME}",
            "python3", script,
            "--profile-dir", profile,
            "--step", step,
        ]
        if pub.get("app_already_exists"):
            cmd.append("--skip-create")
        if not pub.get("use_vision", True):
            cmd.append("--no-vision")
        if not pub.get("wait_for_console", True):
            cmd.append("--no-wait-console")

        detached = pub.get("detached", True)

        try:
            with open(log_path, "w", encoding="utf-8") as lf:
                lf.write(f"Publish {step} · detached={detached}\n")
            _run(f"chown {REAL_USER}:{REAL_USER} '{log_path}'")

            if detached:
                with open(log_path, "a", encoding="utf-8") as lf:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=lf,
                        stderr=subprocess.STDOUT,
                        text=True,
                        start_new_session=True,
                    )
                self.log(f"Detached PID {proc.pid} → {log_path}")
                self.log("Press «Continue — I'm on Console» when ready · Tail log for progress")
                self.set_status("Publish detached", "ok")
                self.root.after(8000, self._publish_tail_log)
                return

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout or []:
                line = line.rstrip()
                if line:
                    self.log(line.lstrip("[*] ").lstrip("* "))
            proc.wait()
            self.cfg = cfg_load()
            pub2 = self.cfg.get("publish", {})
            self.root.after(0, lambda: self._publish_apply_results(pub2))
            if proc.returncode == 0:
                self.set_status("Publish done", "ok")
            else:
                self.set_status("Publish failed", "idle")
                self.log(f"Exit code {proc.returncode}")
        except Exception as exc:
            self.log(f"Publish error: {exc}")
            self.set_status("Publish error", "idle")

    def _publish_apply_results(self, pub: dict):
        url = pub.get("last_privacy_url", "")
        if url:
            self.ent_pub_privacy_url.delete(0, tk.END)
            self.ent_pub_privacy_url.insert(0, url)
        self._publish_refresh_listing_label(pub)

    def _publish_tail_log(self):
        log_path = f"{USER_HOME}/.bravelgo-publish.log"
        if not os.path.isfile(log_path):
            self.log("No publish log yet")
            return
        try:
            with open(log_path, encoding="utf-8") as f:
                tail = f.read()[-4000:]
            for ln in tail.splitlines()[-30:]:
                self.log(ln)
        except Exception as exc:
            self.log(f"Log read error: {exc}")

    # ── PROFILE TAB ───────────────────────────────────────────────────────────
    def _build_profile(self):
        p = self.tab_profile
        self._hint(self._card(p, "Variant A"),
                   "Full uniquify uses **proxy geo**, not this dropdown.\n"
                   "For Netherlands: NL proxy + Test + Apply, then Full uniquify.\n"
                   "Apply country = preview only (saved until uniquify).")
        inf = self._card(p, "Current profile")
        self.fp_text = self._text(inf, height=7, mono=False, readonly=True)
        gf = self._card(p, "Generate")
        row = tk.Frame(gf, bg=C.SURFACE)
        row.pack(fill="x")
        self._btn(row, "Detect from proxy", lambda: threading.Thread(target=self._fp_from_proxy, daemon=True).start(),
                 variant="primary", side="left", padx=(0, 8))
        self.combo_country = ttk.Combobox(
            row, values=[f"{c} — {v['name']}" for c, v in COUNTRY_PROFILES.items()],
            state="readonly", width=22,
        )
        self.combo_country.set("FR — France")
        self.combo_country.pack(side="left", padx=8)
        self._btn(row, "Apply country", self._fp_manual, variant="ghost", side="left")
        df = self._card(p, "JSON", expand=True)
        self.fp_detail = self._text(df, height=10, mono=True, readonly=True)

    def _fp_display(self, fp):
        self._set_readonly(self.fp_text, fingerprint_summary(fp))
        self._set_readonly(self.fp_detail, json.dumps(fp, ensure_ascii=False, indent=2))

    def _fp_from_proxy(self):
        raw = self._active_proxy_str()
        cc, tz = "?", "?"
        if raw:
            parts = self._parse_proxy(raw)
            if parts:
                cc, tz = get_proxy_country(parts[0], parts[1], parts[2], parts[3], raw.startswith("socks5://"), self.log)
        if cc == "?":
            cc = "FR"
        fp = generate_fingerprint(cc, tz if tz != "?" else None)
        self.cfg["fingerprint"] = fp
        cfg_save(self.cfg)
        self.root.after(0, lambda: self._fp_display(fp))

    def _fp_manual(self):
        cc = self.combo_country.get().split(" — ")[0].strip()
        fp = generate_fingerprint(cc)
        self.cfg["fingerprint"] = fp
        cfg_save(self.cfg)
        self._fp_display(fp)

    # ── PROXY ─────────────────────────────────────────────────────────────────
    def _build_proxy(self):
        p = self.tab_proxy
        lf = self._card(p, "Saved proxies", expand=True)
        self._hint(lf, "IP:PORT:USER:PASS")
        self.lb_proxy = self._listbox(lf, height=6)
        for x in self.cfg.get("proxies", []):
            self.lb_proxy.insert(tk.END, x)
        self.lb_proxy.bind("<<ListboxSelect>>", self._on_proxy_select)
        br = tk.Frame(lf, bg=C.SURFACE)
        br.pack(fill="x", pady=(8, 0))
        self._btn(br, "Edit", self._proxy_edit, variant="ghost", side="left", padx=(0, 6))
        self._btn(br, "Delete", self._proxy_delete, variant="danger", side="left")

        af = self._card(p, "Add / edit")
        tk.Label(af, text="Proxy", fg=C.TEXT2, bg=C.SURFACE).pack(anchor="w")
        self.ent_proxy = self._entry(af)
        self.ent_proxy.insert(0, self.cfg.get("active_proxy", "").replace("socks5://", ""))
        r2 = tk.Frame(af, bg=C.SURFACE)
        r2.pack(fill="x", pady=(10, 0))
        tk.Label(r2, text="Type", fg=C.TEXT2, bg=C.SURFACE).pack(side="left")
        self.combo_ptype = ttk.Combobox(r2, values=["HTTP", "SOCKS5"], state="readonly", width=10)
        self.combo_ptype.set(self.cfg.get("proxy_type", "HTTP"))
        self.combo_ptype.pack(side="left", padx=(8, 16))
        self._btn(r2, "Save", self._proxy_add, variant="ghost", side="left")

        df = self._card(p, "Deploy")
        self._hint(df, f"Local bridge 127.0.0.1:{BRIDGE_PORT} → Firefox (HTTP + SOCKS5 upstream)")
        row = tk.Frame(df, bg=C.SURFACE)
        row.pack(fill="x")
        self._btn(row, "Test", self._proxy_test_thread, variant="ghost", side="left", padx=(0, 8))
        self._btn(row, "Apply", self._proxy_apply_thread, variant="primary", side="left", padx=(0, 8))
        self._btn(row, "Disable", self._proxy_disable_thread, variant="danger", side="left")
        self.lbl_proxy_status = tk.Label(df, text="—", font=FONT_MONO, fg=C.TEXT3, bg=C.SURFACE, anchor="w")
        self.lbl_proxy_status.pack(fill="x", pady=(10, 0))

    def _on_proxy_select(self, _=None):
        sel = self.lb_proxy.curselection()
        if not sel:
            return
        val = self.lb_proxy.get(sel[0])
        self.combo_ptype.set("SOCKS5" if val.startswith("socks5://") else "HTTP")
        self.ent_proxy.delete(0, tk.END)
        self.ent_proxy.insert(0, val.replace("socks5://", ""))

    def _proxy_add(self):
        raw = self.ent_proxy.get().strip().replace("socks5://", "")
        if not self._parse_proxy(raw):
            self.show_error("Error", "IP:PORT:USER:PASS")
            return
        entry = f"socks5://{raw}" if self.combo_ptype.get() == "SOCKS5" else raw
        if entry not in self.cfg["proxies"]:
            self.cfg["proxies"].append(entry)
            self.lb_proxy.insert(tk.END, entry)
        self.cfg["active_proxy"] = entry
        self.cfg["proxy_type"] = self.combo_ptype.get()
        cfg_save(self.cfg)

    def _proxy_delete(self):
        sel = self.lb_proxy.curselection()
        if not sel:
            return
        self.lb_proxy.delete(sel[0])
        self.cfg["proxies"].pop(sel[0])
        cfg_save(self.cfg)

    def _proxy_edit(self):
        sel = self.lb_proxy.curselection()
        if not sel:
            return
        val = self.lb_proxy.get(sel[0])
        self.lb_proxy.delete(sel[0])
        self.cfg["proxies"].pop(sel[0])
        cfg_save(self.cfg)
        self.ent_proxy.delete(0, tk.END)
        self.ent_proxy.insert(0, val.replace("socks5://", ""))
        self.combo_ptype.set("SOCKS5" if val.startswith("socks5://") else "HTTP")

    def _proxy_test_thread(self):
        threading.Thread(target=self._proxy_test, daemon=True).start()

    def _proxy_test(self):
        raw = self._active_proxy_str()
        if not raw:
            self.root.after(0, lambda: self.show_error("Proxy", "Select proxy"))
            return
        parts = self._parse_proxy(raw)
        is_socks = raw.startswith("socks5://")
        try:
            ip = test_proxy(parts[0], parts[1], parts[2], parts[3], is_socks)
            self.log(f"Test OK → {ip}")
            self.lbl_proxy_status.configure(text=f"OK · {ip}", fg=C.SUCCESS)
            self.set_status(f"Proxy {ip}", "ok")
        except Exception as e:
            self.log(f"Test fail: {e}")
            self.lbl_proxy_status.configure(text=str(e)[:60], fg=C.DANGER)

    def _apply_proxy_parts(self, parts, is_socks: bool):
        write_bridge(parts[0], parts[1], parts[2], parts[3], is_socks, self.log)
        start_bridge(self.log)

    def _proxy_apply_thread(self):
        threading.Thread(target=self._proxy_apply, daemon=True).start()

    def _proxy_apply(self):
        raw = self._active_proxy_str()
        if not raw:
            self.root.after(0, lambda: self.show_error("Proxy", "Select proxy"))
            return
        parts = self._parse_proxy(raw)
        is_socks = raw.startswith("socks5://")
        self._apply_proxy_parts(parts, is_socks)
        fp = self.cfg.get("fingerprint") or generate_fingerprint("FR")
        prof = self._active_profile_dir()
        if not prof:
            prof = create_profile(USER_HOME, REAL_USER, fp, self.log)
            self.cfg["ff_profile"] = prof
        write_user_js(prof, fp, REAL_USER, True, self.log)
        self.cfg["active_proxy"] = raw
        self.cfg["proxy_type"] = "SOCKS5" if is_socks else "HTTP"
        cfg_save(self.cfg)
        _run("killall -9 firefox 2>/dev/null")
        self.lbl_proxy_status.configure(text=f"Active · {parts[0]}:{parts[1]}", fg=C.SUCCESS)
        self.set_status("Proxy active", "ok")
        self.log("Proxy applied — restart Firefox")

    def _proxy_disable_thread(self):
        threading.Thread(target=self._proxy_disable, daemon=True).start()

    def _proxy_disable(self):
        stop_bridge(self.log)
        fp = self.cfg.get("fingerprint") or generate_fingerprint("FR")
        prof = self._active_profile_dir()
        if prof:
            write_user_js(prof, fp, REAL_USER, False, self.log)
        _run("killall -9 firefox 2>/dev/null")
        self.lbl_proxy_status.configure(text="Disabled", fg=C.WARN)
        self.set_status("Proxy off", "idle")

    # ── HW ────────────────────────────────────────────────────────────────────
    def _build_hw(self):
        p = self.tab_hw
        inf = self._card(p, "Identifiers")
        self.lbl_hn = self._info_row(inf, "Hostname")
        self.lbl_mid = self._info_row(inf, "Machine-ID")
        self.lbl_mac = self._info_row(inf, "MAC")
        self.lbl_tz = self._info_row(inf, "Timezone")
        self.lbl_ipv6 = self._info_row(inf, "IPv6")
        self._btn(inf, "Refresh", self._hw_refresh, variant="ghost", anchor="w", pady=(8, 0))
        ch = self._card(p, "Manual reset")
        tk.Label(ch, text="Hostname (auto if empty)", fg=C.TEXT2, bg=C.SURFACE).pack(anchor="w")
        self.ent_hn = self._entry(ch)
        self.v_mac = tk.BooleanVar(value=True)
        self.v_mid = tk.BooleanVar(value=True)
        self.v_hn = tk.BooleanVar(value=True)
        for t, v in [("MAC", self.v_mac), ("Machine-ID", self.v_mid), ("Hostname", self.v_hn)]:
            ttk.Checkbutton(ch, text=t, variable=v).pack(anchor="w")
        self._btn(ch, "Apply", lambda: threading.Thread(target=self._hw_apply, daemon=True).start(),
                  variant="primary", fill="x", pady=(10, 0))
        self._hw_refresh()

    def _hw_refresh(self):
        _, hn = _run("hostname")
        _, mid = _run("cat /etc/machine-id")
        iface = self._iface()
        _, mac = _run(f"cat /sys/class/net/{iface}/address") if iface else (0, "—")
        _, tz = _run("timedatectl show --property=Timezone --value")
        _, ipv6 = _run("ip -6 addr show scope global 2>/dev/null | head -1")
        self.lbl_hn.configure(text=hn or "—")
        self.lbl_mid.configure(text=(mid or "—")[:32])
        self.lbl_mac.configure(text=f"{mac or '—'} [{iface}]")
        self.lbl_tz.configure(text=tz or "—")
        self.lbl_ipv6.configure(text="active" if ipv6.strip() else "off")

    def _hw_apply(self):
        if self.v_hn.get():
            hn = self.ent_hn.get().strip() or "DESKTOP-" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=5))
            _run(f"hostnamectl set-hostname '{hn}'")
            _run(f"sed -i '/127.0.1.1/d' /etc/hosts && echo '127.0.1.1\\t{hn}' >> /etc/hosts")
            self.log(f"Hostname → {hn}")
        if self.v_mid.get():
            _run("rm -f /etc/machine-id /var/lib/dbus/machine-id && systemd-machine-id-setup")
            self.log("Machine-ID reset")
        if self.v_mac.get():
            iface = self._iface()
            if iface:
                b = [random.randint(0, 255) for _ in range(6)]
                b[0] = (b[0] & 0xFC) | 0x02
                mac = ":".join(f"{x:02x}" for x in b)
                _run(f"ip link set dev {iface} down && ip link set dev {iface} address {mac} && ip link set dev {iface} up")
                self.log(f"MAC → {mac}")
        self.root.after(200, self._hw_refresh)

    # ── DISK ──────────────────────────────────────────────────────────────────
    def _build_disk(self):
        p = self.tab_disk
        inf = self._card(p, "UTM VirtIO 9p")
        self._hint(inf, "Mount shared folder → ~/MacFolder")
        self.lbl_disk = tk.Label(inf, text="—", font=FONT_MONO, fg=C.TEXT2, bg=C.SURFACE, anchor="w")
        self.lbl_disk.pack(fill="x")
        self.v_fstab = tk.BooleanVar(value=True)
        self.v_bookmark = tk.BooleanVar(value=True)
        ttk.Checkbutton(inf, text="Add to fstab", variable=self.v_fstab).pack(anchor="w", pady=4)
        ttk.Checkbutton(inf, text="Nautilus bookmark", variable=self.v_bookmark).pack(anchor="w")
        row = tk.Frame(p, bg=C.BG)
        row.pack(fill="x")
        self._btn(row, "Status", self._disk_check, variant="ghost", side="left", padx=(0, 8))
        self._btn(row, "Mount", lambda: threading.Thread(target=self._disk_mount, daemon=True).start(),
                  variant="primary", side="left", padx=(0, 8))
        self._btn(row, "Unmount", self._disk_umount, variant="danger", side="left")
        self._disk_check()

    def _disk_check(self):
        if os.path.ismount(MOUNT_PT):
            self.lbl_disk.configure(text=f"Mounted → {MOUNT_PT}", fg=C.SUCCESS)
        else:
            self.lbl_disk.configure(text="Not mounted", fg=C.DANGER)

    def _disk_mount(self):
        os.makedirs(MOUNT_PT, exist_ok=True)
        _run(f"umount -f '{MOUNT_PT}' 2>/dev/null; umount -l share 2>/dev/null")
        _run(f"mount -t 9p -o trans=virtio,version=9p2000.L,uid=1000,gid=1000,dmode=0777,fmode=0777,nofail share '{MOUNT_PT}'")
        if os.path.ismount(MOUNT_PT):
            _run(f"chmod -R 777 '{MOUNT_PT}' && chown -R {REAL_USER}:{REAL_USER} '{MOUNT_PT}'")
            if self.v_fstab.get():
                _run("sed -i '/^share[[:space:]]/d' /etc/fstab")
                with open("/etc/fstab", "a") as f:
                    f.write(f"share\t{MOUNT_PT}\t9p\ttrans=virtio,version=9p2000.L,uid=1000,gid=1000,dmode=0777,fmode=0777,nofail\t0\t0\n")
            if self.v_bookmark.get():
                bm = f"{USER_HOME}/.config/gtk-3.0/bookmarks"
                os.makedirs(os.path.dirname(bm), exist_ok=True)
                ex = open(bm).read() if os.path.exists(bm) else ""
                if MOUNT_PT not in ex:
                    with open(bm, "a") as f:
                        f.write(f"file://{MOUNT_PT} MacFolder\n")
                    _run(f"chown {REAL_USER}:{REAL_USER} '{bm}'")
            self.log(f"Mounted {MOUNT_PT}")
        else:
            self.log("VirtIO share not found in UTM")
        self.root.after(0, self._disk_check)

    def _disk_umount(self):
        _run(f"umount '{MOUNT_PT}' 2>/dev/null; sed -i '/^share[[:space:]]/d' /etc/fstab")
        self.log("Unmounted")
        self._disk_check()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
