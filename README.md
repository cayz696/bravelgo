# BravelGo — Professional VM Profile Manager

Variant A + Modern UI | Ubuntu 24.04 | UTM

## Install in VM (first time)

```bash
git clone https://github.com/cayz696/bravelgo.git ~/Desktop/google
cd ~/Desktop/google

sudo apt update
sudo apt install -y git curl firefox firefox-geckodriver \
  python3 python3-pip python3-tk jq

sudo python3 -m pip install selenium PySocks --break-system-packages
sudo python3 bravelgo.py
```

> On a bare Ubuntu, `python3-pip` is required — without it warmup fails with `No such file or directory: pip3`.

## Update later

```bash
cd ~/Desktop/google
git pull
sudo python3 bravelgo.py
```

## Structure

```
google/
  bravelgo.py           ← run this
  bravelgo/
    core/warmup.py      ← Selenium warmup (firefox-geckodriver)
    proxy_geo.py        ← geo lookup (PySocks) + bridge 127.0.0.1:8118
    ff_profile.py       ← Firefox profile (user.js)
```

## Workflow

1. UTM: clone VM → new MAC
2. Disk → Mount MacFolder
3. Proxy → Save → Test → Apply
4. Full uniquify → Run check → reboot
5. Warmup ×3–5 (**Skip Google ON**)
6. Launch Firefox → Google / Play Console

## Config

`~/.bravelgo.json` — proxies, fingerprint, ff_profile path  
`~/MacFolder/.bravelgo-registry.json` — cross-clone ID ledger
