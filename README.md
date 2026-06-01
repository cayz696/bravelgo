# BravelGo — VM Profile Manager

Variant A · Ubuntu 24.04 · UTM · Firefox deb (не snap)

---

## Частина 1 — один раз на Mac (UTM)

### 1.1 Золотий шаблон VM

1. UTM → New VM → **Ubuntu 24.04 Desktop** (ARM64 на Apple Silicon)
2. RAM **4–8 GB**, CPU **3–4**, диск **40+ GB**
3. Створи користувача, напр. `ahmed`

### 1.2 Спільна папка (реєстр клонів)

1. UTM → VM → **Sharing** → Directory Sharing
2. Папка на Mac, tag share: **`share`**
3. Після монтування в VM: `~/MacFolder` → `.bravelgo-registry.json`

### 1.3 Snapshot

Після першого налаштування (частина 2) — **snapshot** «golden» для клонування.

---

## Частина 2 — один раз у VM (перше встановлення)

```bash
sudo apt update
sudo apt install -y git curl python3 python3-pip python3-tk jq

git clone https://github.com/cayz696/bravelgo.git ~/Desktop/google
cd ~/Desktop/google

sudo python3 bravelgo.py
```

> Запускай **тільки** з `~/Desktop/google`, не з Trash.

BravelGo завжди через **sudo** — змінює MAC, locale, apt-пакети.

---

## Країна — автовизначення чи вручну?

**Завжди через проксі (авто)** — це правильний шлях.

| Крок | Дія |
|---|---|
| 1 | Proxy → **NL проксі** → Save → **Test** (має показати NL) |
| 2 | Proxy → **Apply** |
| 3 | Profile → **Detect from proxy** (опційно, перегляд) |
| 4 | Uniquify → **Full uniquify** → країна з проксі |
| 5 | **Run check** → all green |

Profile → dropdown **NL** без NL-проксі uniquify **не змінить** — це лише preview.

---

```
Mac: Clone VM
  ↓
BravelGo: Disk → Mount MacFolder
  ↓
Proxy → Save → Test → Apply
  ↓
Uniquify → Full uniquify → Run check (green)
  ↓
Reboot
  ↓
BravelGo знову → Proxy Apply → Disk Mount
  ↓
Warmup → Reinstall Firefox (перший раз) → Start warmup ×3–5
  ↓
Launch Firefox → Google / Play Console
```

---

## Вкладки BravelGo — покроково

### Disk

1. Увімкни **Add to fstab** + **Nautilus bookmark**
2. **Mount** → `Mounted → /home/ahmed/MacFolder`

### Proxy

1. Формат: `IP:PORT:USER:PASS`
2. Тип: HTTP або SOCKS5
3. **Save** → **Test** → **Apply**
4. Bridge: `127.0.0.1:8118`

Після кожного **reboot** — знову **Apply**.

### Uniquify

1. Усі галочки увімкнені
2. **Full uniquify**
3. **Run check** → `All consistent` / `Issues: none`
4. **Reboot**

### Warmup

| Параметр | Значення |
|---|---|
| Skip Google | **ON** (обов'язково) |
| Max sites | 6 |
| Minutes | 15 |
| Search language | geo |

**Перший раз на новій VM:**

1. **Reinstall Firefox** — ставить deb Firefox + geckodriver + selenium  
   (snap Firefox видаляється автоматично — з Selenium не працює)
2. У логах: `Firefox OK: /usr/lib/firefox/firefox` + `Warmup ready`
3. **Start warmup** ×3–5 сесій

Warmup **закриває браузер сам** — це нормально.  
**Не логінься в Google** під warmup (Selenium = іконка робота).

### Launch Firefox

Після warmup → **Launch Firefox** → Google / Play Console вручну.  
Без іконки робота.

---

## Firefox — важливо

| | Snap Firefox | Deb Firefox |
|---|---|---|
| Шлях | `/snap/firefox/...` | `/usr/lib/firefox/firefox` |
| Warmup | ❌ не працює | ✅ працює |
| BravelGo | видаляє snap | ставить через Mozilla apt |

Якщо щось зламалось — вкладка **Warmup → Reinstall Firefox**.

Ручна перевірка:

```bash
firefox --version
ls /usr/lib/firefox/firefox
which geckodriver   # /usr/local/bin/geckodriver або /usr/bin/geckodriver
python3 -c "import selenium; print('OK')"
```

---

## Оновлення BravelGo

```bash
cd ~/Desktop/google
git pull
sudo python3 bravelgo.py
```

---

## Файли

| Файл | Що зберігає |
|---|---|
| `~/.bravelgo.json` | проксі, fingerprint, шлях FF-профілю |
| `~/MacFolder/.bravelgo-registry.json` | MAC, machine-id між клонами |
| `~/.bravelgo-warmup.log` | лог warmup |
| `~/.mozilla/firefox/ubuntu-xxxxx/` | Firefox-профіль BravelGo |

---

## Типові проблеми

### Чорний екран після reboot

TTY `Ctrl+Alt+F3`:

```bash
sudo sed -i '/^LANG=/d;/^LC_ALL=/d' /etc/environment
echo 'LANG=en_US.UTF-8' | sudo tee -a /etc/environment
echo 'LC_ALL=en_US.UTF-8' | sudo tee -a /etc/environment
sudo reboot
```

Потім знову **Full uniquify**.

### Google `/sorry/` (CAPTCHA)

Warmup з Google увімкненим → Google бачить Selenium.  
**Skip Google ON** + Google тільки через **Launch Firefox**.

### apt / Firefox не ставиться

```bash
sudo snap remove firefox 2>/dev/null
sudo apt update
sudo apt install -y --allow-downgrades firefox
```

Або **Reinstall Firefox** в BravelGo.

### Permission denied після sudo

```bash
sudo chown -R $USER:$USER ~/Desktop/google
```

---

## BrowserLeaks (опційно)

Після warmup + Launch Firefox перевір:

- WebRTC — No Leak
- Language — `fr-FR` (або країна проксі)
- WebGL — `llvmpipe`
- webdriver — false
- Proxy headers — не виявлені

Еталон: `baselines/clone-001-2026-05-30.json`
