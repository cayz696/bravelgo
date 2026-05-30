#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

if os.geteuid() != 0:
    print("❌ Запускай через sudo: sudo ./run.sh")
    sys.exit(1)

REAL_USER = os.environ.get("SUDO_USER") or os.environ.get("USER", "")
if not REAL_USER or REAL_USER == "root":
    print("❌ Запускай через sudo від звичайного користувача: sudo ./run.sh")
    sys.exit(1)

USER_HOME = f"/home/{REAL_USER}"

from bravelgo.core.disk import mount_shared_disk
from bravelgo.core.firefox import create_profile
from bravelgo.core.gost import (
    install_gost_service,
    load_proxy_config,
    save_proxy_config,
    stop_gost,
    verify_proxy,
)
from bravelgo.core.identity import reset_identity
from bravelgo.core.proxy import ProxyConfig
from bravelgo.core.warmup import DEFAULT_WARMUP_URLS


def _pwd_uid(name: str) -> int:
    import pwd

    return pwd.getpwnam(name).pw_uid


def _pwd_gid(name: str) -> int:
    import pwd

    return pwd.getpwnam(name).pw_gid


class BravelGoApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BravelGo — Профіль UTM / Ubuntu")
        self.root.geometry("820x780")
        self.root.minsize(820, 780)

        style = ttk.Style()
        style.configure("TButton", font=("Helvetica", 10, "bold"), padding=6)
        style.configure("Action.TButton", font=("Helvetica", 11, "bold"))

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_main = ttk.Frame(self.notebook)
        self.tab_warmup = ttk.Frame(self.notebook)
        self.tab_ideas = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_main, text=" Налаштування ")
        self.notebook.add(self.tab_warmup, text=" Прогрів ")
        self.notebook.add(self.tab_ideas, text=" Чеклист ")

        self.profile_dir: str | None = None
        self._build_main()
        self._build_warmup()
        self._build_ideas()
        self._load_saved_settings()

    def _build_main(self) -> None:
        proxy_frame = ttk.LabelFrame(self.tab_main, text=" Проксі (IP:PORT:USER:PASS) ")
        proxy_frame.pack(fill="x", padx=15, pady=8, ipady=5)

        ttk.Label(
            proxy_frame,
            text="Рядок проксі — зберігається локально в ~/.config/bravelgo/proxy.json",
            font=("Helvetica", 9),
        ).pack(anchor="w", padx=10, pady=2)

        self.entry_proxy = ttk.Entry(proxy_frame, font=("Courier", 10), width=70)
        self.entry_proxy.pack(fill="x", padx=10, pady=5)

        proxy_btns = ttk.Frame(proxy_frame)
        proxy_btns.pack(fill="x", padx=10, pady=5)
        ttk.Button(proxy_btns, text="Зберегти проксі", command=self.save_proxy_only).pack(
            side="left", padx=4
        )
        ttk.Button(proxy_btns, text="Перевірити проксі", command=self.test_proxy_thread).pack(
            side="left", padx=4
        )
        ttk.Button(proxy_btns, text="Зупинити gost", command=self.stop_proxy).pack(
            side="left", padx=4
        )

        sys_frame = ttk.LabelFrame(self.tab_main, text=" Профіль та геолокація ")
        sys_frame.pack(fill="x", padx=15, pady=8, ipady=5)
        grid = ttk.Frame(sys_frame)
        grid.pack(fill="x", padx=10, pady=5)

        ttk.Label(grid, text="Країна:", font=("Helvetica", 9, "bold")).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        self.combo_locale = ttk.Combobox(
            grid,
            values=["UA", "FR", "USA", "PL", "NO", "BR", "EST", "NZL"],
            width=10,
            state="readonly",
        )
        self.combo_locale.set("FR")
        self.combo_locale.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(grid, text="Ім'я профілю (UTM):", font=("Helvetica", 9, "bold")).grid(
            row=0, column=2, padx=15, pady=5, sticky="w"
        )
        self.entry_profile = ttk.Entry(grid, width=22, font=("Helvetica", 10))
        self.entry_profile.insert(0, "V748-FR")
        self.entry_profile.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        btns = ttk.Frame(self.tab_main)
        btns.pack(fill="x", padx=15, pady=5)

        ttk.Button(btns, text="Підключити диск (9p)", command=self.mount_disk).pack(
            side="left", expand=True, fill="x", padx=5
        )
        self.btn_setup = ttk.Button(
            btns,
            text="Повне налаштування (identity + proxy + Firefox)",
            style="Action.TButton",
            command=self.setup_thread,
        )
        self.btn_setup.pack(side="right", expand=True, fill="x", padx=5)

        log_frame = ttk.LabelFrame(self.tab_main, text=" Лог ")
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=16, bg="#1c1c1c", fg="#00ff00", font=("Courier", 9)
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def _build_warmup(self) -> None:
        frame = ttk.LabelFrame(self.tab_warmup, text=" URL для прогріву ")
        frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.txt_urls = scrolledtext.ScrolledText(frame, height=16, font=("Courier", 9))
        self.txt_urls.pack(fill="both", expand=True, padx=5, pady=5)
        self.txt_urls.insert("1.0", "\n".join(DEFAULT_WARMUP_URLS))

        opts = ttk.Frame(self.tab_warmup)
        opts.pack(fill="x", padx=15, pady=5)
        ttk.Label(opts, text="Макс. сайтів за сесію:").pack(side="left", padx=5)
        self.spin_max_sites = ttk.Spinbox(opts, from_=3, to=15, width=5)
        self.spin_max_sites.set("8")
        self.spin_max_sites.pack(side="left")

        self.btn_warmup = ttk.Button(
            self.tab_warmup,
            text="Запустити якісний прогрів (Playwright)",
            command=self.warmup_thread,
        )
        self.btn_warmup.pack(fill="x", padx=15, pady=15)

    def _build_ideas(self) -> None:
        text = scrolledtext.ScrolledText(self.tab_ideas, font=("Helvetica", 10), wrap=tk.WORD)
        text.pack(fill="both", expand=True, padx=15, pady=15)
        checklist = """
BravelGo — чеклист перед Google / Play Console
===============================================

НА MAC (UTM) — ПЕРЕД КЛОНОМ:
  • Згенеруй новий MAC Address для VM (Network → Advanced)
  • Клонуй golden image ДО першого входу в Google
  • Не шарь Firefox profile між VM через shared folder

В UBUNTU — ПІСЛЯ КЛОНУ (кнопка «Повне налаштування»):
  ✓ Новий hostname + machine-id
  ✓ Timezone + locale під країну проксі
  ✓ IPv6 вимкнено
  ✓ Gost → локальний SOCKS 127.0.0.1:1080
  ✓ Окремий Firefox profile

ПЕРЕВІРКИ ПІСЛЯ НАЛАШТУВАННЯ:
  • browserleaks.com/ip — IP = країна проксі
  • dnsleaktest.com — DNS не палить UTM
  • time.is — час збігається з timezone

ЯКІСНИЙ ПРОГРІВ (ідеї):
  • 3–7 окремих сесій по 15–30 хв, не одна на 2 хвилини
  • Google пошук мовою країни профілю
  • 5–8 сайтів за сесію, не 16 вкладок одразу
  • Scroll + кліки по лінках (Playwright робить це автоматично)
  • YouTube: перегляд 2–5 хв одного dev-відео вручну після прогріву
  • Не логінитись у Google одразу — дай профілю «пожити» 1–3 дні

ДОДАТКОВІ ІДЕІ:
  • Golden snapshot після налаштування, до Google login
  • Один проксі = одна країна = один timezone (завжди)
  • Оплата Play Console — окрема картка / billing per account
  • Не використовуй той самий номер телефону для recovery
  • Різний email provider (не всі Gmail)
  • Ручний перегляд Play Console Help Center перед першим login

ВАЖЛИВО:
  Жоден софт не гарантує 100% «невидимість». Google аналізує
  поведінку, платежі, контент, зв'язки між акаунтами.
  BravelGo дає технічно чисте середовище — решта залежить від процесу.
"""
        text.insert("1.0", checklist.strip())
        text.config(state="disabled")

    def log(self, message: str) -> None:
        self.log_text.insert(tk.END, f"[*] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _load_saved_settings(self) -> None:
        saved = load_proxy_config(REAL_USER)
        if not saved:
            return
        if saved.get("proxy"):
            self.entry_proxy.delete(0, tk.END)
            self.entry_proxy.insert(0, saved["proxy"])
        if saved.get("profile"):
            self.entry_profile.delete(0, tk.END)
            self.entry_profile.insert(0, saved["profile"])

        identity_path = os.path.join(USER_HOME, ".config/bravelgo/identity.json")
        if os.path.exists(identity_path):
            with open(identity_path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.log(f"Останній профіль: {data.get('hostname', '?')}")

    def save_proxy_only(self) -> None:
        try:
            proxy = ProxyConfig.parse(self.entry_proxy.get())
        except ValueError as exc:
            messagebox.showerror("Помилка", str(exc))
            return
        save_proxy_config(REAL_USER, self.entry_proxy.get(), self.entry_profile.get())
        self.log(f"Проксі збережено: {proxy.masked()}")
        messagebox.showinfo("Збережено", "Проксі записано в ~/.config/bravelgo/proxy.json")

    def stop_proxy(self) -> None:
        stop_gost(self.log)

    def mount_disk(self) -> None:
        mount_shared_disk(REAL_USER, USER_HOME, self.log)

    def test_proxy_thread(self) -> None:
        threading.Thread(target=self._test_proxy, daemon=True).start()

    def _test_proxy(self) -> None:
        try:
            proxy = ProxyConfig.parse(self.entry_proxy.get())
        except ValueError as exc:
            self.root.after(0, lambda: messagebox.showerror("Помилка", str(exc)))
            return
        install_gost_service(REAL_USER, proxy.upstream_url(), self.log)
        ok = verify_proxy(self.log)
        if ok:
            self.root.after(0, lambda: messagebox.showinfo("OK", "Проксі працює"))
        else:
            self.root.after(0, lambda: messagebox.showwarning("Помилка", "Проксі не відповідає"))

    def setup_thread(self) -> None:
        self.btn_setup.config(state="disabled")
        threading.Thread(target=self._full_setup, daemon=True).start()

    def _full_setup(self) -> None:
        try:
            proxy_raw = self.entry_proxy.get().strip()
            proxy = ProxyConfig.parse(proxy_raw)
            country = self.combo_locale.get()
            profile_name = self.entry_profile.get().strip() or "profile"

            save_proxy_config(REAL_USER, proxy_raw, profile_name)
            self.log(f"=== Повне налаштування: {profile_name} ===")

            if not os.path.exists("/usr/bin/firefox"):
                self.log("Встановлення Firefox...")
                os.system("apt-get update -qq && apt-get install -y firefox")

            identity = reset_identity(REAL_USER, country, profile_name, self.log)
            self.mount_disk()

            self.log("Запуск gost forwarder...")
            install_gost_service(REAL_USER, proxy.upstream_url(), self.log)
            verify_proxy(self.log)

            profile_path = create_profile(
                REAL_USER,
                profile_name,
                identity["accept_languages"],
                self.log,
            )
            self.profile_dir = str(profile_path)

            self.log("✅ Готово. Запусти прогрів на вкладці «Прогрів».")
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "Успіх",
                    "Профіль налаштовано.\nДалі: вкладка «Прогрів» → запусти сесію.",
                ),
            )
        except Exception as exc:
            self.log(f"Помилка: {exc}")
            self.root.after(0, lambda: messagebox.showerror("Помилка", str(exc)))
        finally:
            self.root.after(0, lambda: self.btn_setup.config(state="normal"))

    def warmup_thread(self) -> None:
        self.btn_warmup.config(state="disabled")
        threading.Thread(target=self._warmup, daemon=True).start()

    def _warmup(self) -> None:
        import subprocess
        from pathlib import Path

        try:
            if not self.profile_dir:
                candidate = os.path.join(USER_HOME, ".config/bravelgo/identity.json")
                if not os.path.exists(candidate):
                    raise RuntimeError("Спочатку виконай «Повне налаштування»")

            profile_dir = self.profile_dir
            if not profile_dir:
                profiles = list(
                    Path(USER_HOME).glob(".config/bravelgo/firefox-profiles/*")
                )
                if not profiles:
                    raise RuntimeError("Firefox профіль не знайдено")
                profile_dir = str(sorted(profiles)[-1])

            urls = [
                u.strip()
                for u in self.txt_urls.get("1.0", tk.END).splitlines()
                if u.strip()
            ]
            max_sites = int(self.spin_max_sites.get())

            urls_file = os.path.join(USER_HOME, ".config/bravelgo/warmup_urls.txt")
            os.makedirs(os.path.dirname(urls_file), exist_ok=True)
            with open(urls_file, "w", encoding="utf-8") as fh:
                fh.write("\n".join(urls))
            os.chown(urls_file, _pwd_uid(REAL_USER), _pwd_gid(REAL_USER))

            display = os.environ.get("DISPLAY", ":0")
            venv_py = "/opt/bravelgo/venv/bin/python3"
            python_bin = venv_py if os.path.exists(venv_py) else sys.executable
            script_dir = os.path.dirname(os.path.abspath(__file__))
            env = {"DISPLAY": display, "HOME": USER_HOME}

            self.log("Запуск Playwright від імені користувача...")
            proc = subprocess.Popen(
                [
                    "sudo",
                    "-u",
                    REAL_USER,
                    "env",
                    f"DISPLAY={display}",
                    f"HOME={USER_HOME}",
                    python_bin,
                    os.path.join(script_dir, "run_warmup.py"),
                    "--profile-dir",
                    profile_dir,
                    "--country",
                    self.combo_locale.get(),
                    "--max-sites",
                    str(max_sites),
                    "--urls-file",
                    urls_file,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env={**os.environ, **env},
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self.log(line.rstrip())
            code = proc.wait()
            if code != 0:
                raise RuntimeError(f"Прогрів завершився з кодом {code}")

            self.root.after(
                0, lambda: messagebox.showinfo("Готово", "Сесію прогріву завершено")
            )
        except Exception as exc:
            self.log(f"Помилка прогріву: {exc}")
            self.root.after(0, lambda: messagebox.showerror("Помилка", str(exc)))
        finally:
            self.root.after(0, lambda: self.btn_warmup.config(state="normal"))


def main() -> None:
    root = tk.Tk()
    BravelGoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
