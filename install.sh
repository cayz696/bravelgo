#!/bin/bash
set -euo pipefail

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Запускай: sudo bash install.sh"
  exit 1
fi

REAL_USER="${SUDO_USER:-${USER}}"
USER_HOME="$(eval echo "~${REAL_USER}")"

echo "[*] Оновлення пакетів..."
apt-get update -qq
apt-get install -y curl firefox jq python3 python3-pip python3-tk python3-venv

echo "[*] Встановлення gost (локальний SOCKS forwarder)..."
GOST_BIN="/usr/local/bin/gost"
if [[ ! -x "$GOST_BIN" ]]; then
  if curl -fsSL https://github.com/go-gost/gost/raw/master/install.sh | bash -s -- --install; then
    echo "gost встановлено через офіційний install.sh"
  else
    ARCH="$(uname -m)"
    case "$ARCH" in
      x86_64) GOST_ARCH="amd64" ;;
      aarch64|arm64) GOST_ARCH="arm64" ;;
      *)
        echo "Непідтримувана архітектура: $ARCH"
        exit 1
        ;;
    esac
    GOST_VERSION="3.2.6"
    GOST_URL="https://github.com/go-gost/gost/releases/download/v${GOST_VERSION}/gost_${GOST_VERSION}_linux_${GOST_ARCH}.tar.gz"
    TMP_DIR="$(mktemp -d)"
    curl -fsSL "$GOST_URL" -o "$TMP_DIR/gost.tar.gz"
    tar -xzf "$TMP_DIR/gost.tar.gz" -C "$TMP_DIR"
    install -m 755 "$TMP_DIR/gost" "$GOST_BIN"
    rm -rf "$TMP_DIR"
  fi
fi

echo "[*] Python venv для BravelGo..."
VENV_DIR="/opt/bravelgo/venv"
mkdir -p /opt/bravelgo
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$(dirname "$0")/requirements.txt"
sudo -u "$REAL_USER" "$VENV_DIR/bin/playwright" install firefox
sudo -u "$REAL_USER" "$VENV_DIR/bin/playwright" install-deps firefox || true

install -m 755 "$(dirname "$0")/run.sh" /usr/local/bin/bravelgo
mkdir -p "$USER_HOME/.config/bravelgo"
chown -R "$REAL_USER:$REAL_USER" "$USER_HOME/.config/bravelgo"
loginctl enable-linger "$REAL_USER" 2>/dev/null || true

echo
echo "✅ BravelGo встановлено."
echo "   Запуск: sudo bravelgo"
echo "   або:    cd $(dirname "$0") && sudo ./run.sh"
