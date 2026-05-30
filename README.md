# BravelGo — Professional VM Profile Manager

Variant A + Modern UI | Ubuntu 24.04 | UTM

## Install in VM

```bash
# First time — clone from GitHub
git clone https://github.com/YOUR_USER/bravelgo.git ~/Desktop/google
cd ~/Desktop/google
sudo apt install -y python3 python3-tk curl
pip3 install playwright --break-system-packages
python3 -m playwright install firefox
sudo python3 bravelgo.py

# Update later (replace files)
cd ~/Desktop/google
git pull
```

## Structure

```
google/
  bravelgo.py           ← run this
  bravelgo/
    ui_theme.py         ← modern dark UI
    countries.py        ← country profiles + fingerprint
    proxy_geo.py        ← geo lookup (PySocks) + bridge
    ff_profile.py       ← Firefox profile (user.js only)
```

## Features

- **Full uniquify** — MAC, machine-id, locale/TZ from proxy country, IPv6 off, new FF profile
- **Variant A** — honest Linux Firefox (no fake UA/GPU)
- **Proxy** — HTTP + SOCKS5 via local bridge `127.0.0.1:8118`
- **Warmup** — Playwright, geo sites, Google Images/Maps, background-safe
- **Registry** — `~/MacFolder/.bravelgo-registry.json` avoids ID reuse

## Workflow

1. UTM: clone VM → new MAC
2. Save proxy → **Test**
3. **Full uniquify**
4. **Run check** → all green
5. Reboot VM
6. **Launch Firefox**
7. Warm up → Google login

## Config

`~/.bravelgo.json` — proxies, fingerprint, ff_profile path
