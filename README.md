# BravelGo — Professional VM Profile Manager

Variant A + Modern UI | Ubuntu 24.04 | UTM

## Install in VM (first time)

```bash
git clone https://github.com/cayz696/bravelgo.git ~/Desktop/google
cd ~/Desktop/google

sudo apt update
sudo apt install -y git curl python3 python3-pip python3-tk jq

sudo python3 bravelgo.py
```

On first **Start warmup**, BravelGo (as root) will:
- remove snap Firefox (if any) and install **deb Firefox**
- install **geckodriver** (apt or download from GitHub if package missing)
- install **selenium** for your desktop user (`pip install --user`)

Or click **Reinstall Firefox** on the Warmup tab.

## Update later

```bash
cd ~/Desktop/google && git pull
sudo python3 bravelgo.py
```

## Workflow

1. UTM clone → Disk Mount → Proxy Apply
2. Full uniquify → reboot → Proxy Apply
3. Warmup ×3–5 (**Skip Google ON**)
4. Launch Firefox → Google / Play Console

## Config

`~/.bravelgo.json` — proxies, fingerprint, ff_profile path
