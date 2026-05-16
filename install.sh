#!/usr/bin/env bash
# Установочный скрипт OBS Stream Bot + MediaMTX
# Поддерживается: Ubuntu 20.04+, Debian 11+
# Запуск: sudo bash install.sh

set -e

INSTALL_DIR="/opt/obs-stream-bot"
MEDIAMTX_VERSION="1.17.1"
MEDIAMTX_ARCHIVE="mediamtx_v${MEDIAMTX_VERSION}_linux_amd64.tar.gz"
MEDIAMTX_URL="https://github.com/bluenviron/mediamtx/releases/download/v${MEDIAMTX_VERSION}/mediamtx_v${MEDIAMTX_VERSION}_linux_amd64.tar.gz"

# ── Цвета для вывода ────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✅  $*${NC}"; }
warn() { echo -e "${YELLOW}  ⚠️   $*${NC}"; }
err()  { echo -e "${RED}  ❌  $*${NC}"; exit 1; }
info() { echo -e "  ℹ️   $*"; }

echo ""
echo "══════════════════════════════════════════════"
echo "   OBS Stream Bot — установка"
echo "══════════════════════════════════════════════"
echo ""

# ── 1. Проверка прав root ────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    err "Запустите скрипт с правами root: sudo bash install.sh"
fi
ok "Права root подтверждены"

# ── 2. Определяем директорию репозитория ────────────────────
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
info "Директория репозитория: $REPO_DIR"

# ── 3. Установка системных зависимостей ─────────────────────
info "Обновление списка пакетов и установка зависимостей..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv ffmpeg git curl wget unzip
ok "Системные зависимости установлены"

# ── 4. Создание директории установки ────────────────────────
mkdir -p "$INSTALL_DIR"
ok "Директория установки: $INSTALL_DIR"

# ── 5. Копирование файлов бота ──────────────────────────────
info "Копирование файлов бота..."
cp "$REPO_DIR/obs_bot.py"    "$INSTALL_DIR/"
cp "$REPO_DIR/requirements.txt" "$INSTALL_DIR/"
ok "Файлы бота скопированы"

# ── 6. Подготовка MediaMTX ──────────────────────────────────
MEDIAMTX_DIR="$INSTALL_DIR/mediamtx"
mkdir -p "$MEDIAMTX_DIR"

if [ -f "$REPO_DIR/$MEDIAMTX_ARCHIVE" ]; then
    info "Найден архив MediaMTX в репозитории, распаковываю..."
    tar -xzf "$REPO_DIR/$MEDIAMTX_ARCHIVE" -C "$MEDIAMTX_DIR"
    ok "MediaMTX распакован из архива"
else
    warn "Архив $MEDIAMTX_ARCHIVE не найден. Скачиваю с GitHub..."
    if curl -fsSL "$MEDIAMTX_URL" -o "/tmp/$MEDIAMTX_ARCHIVE"; then
        tar -xzf "/tmp/$MEDIAMTX_ARCHIVE" -C "$MEDIAMTX_DIR"
        rm -f "/tmp/$MEDIAMTX_ARCHIVE"
        ok "MediaMTX v${MEDIAMTX_VERSION} скачан и распакован"
    else
        err "Не удалось скачать MediaMTX. Проверьте соединение с интернетом."
    fi
fi

# Копируем конфиг MediaMTX
if [ -f "$REPO_DIR/mediamtx.yml" ]; then
    cp "$REPO_DIR/mediamtx.yml" "$INSTALL_DIR/mediamtx.yml"
    ok "Конфиг mediamtx.yml скопирован"
fi

# ── 7. Python venv и зависимости ────────────────────────────
info "Создание Python виртуального окружения..."
python3 -m venv "$INSTALL_DIR/venv"
ok "venv создан"

info "Установка Python зависимостей..."
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
ok "Python зависимости установлены"

# ── 8. Systemd юниты ────────────────────────────────────────
info "Установка systemd-юнитов..."

# Подставляем путь установки в юниты
sed "s|/opt/obs-stream-bot|$INSTALL_DIR|g" "$REPO_DIR/obs_bot.service"  > /etc/systemd/system/obs_bot.service
sed "s|/opt/obs-stream-bot|$INSTALL_DIR|g" "$REPO_DIR/mediamtx.service" > /etc/systemd/system/mediamtx.service

systemctl daemon-reload
ok "Systemd юниты установлены (сервисы НЕ запущены)"

# ── 9. Права на скрипты ─────────────────────────────────────
find "$REPO_DIR" -name "*.sh" -exec chmod +x {} \;
ok "chmod +x для .sh файлов"

# ── 10. Итог ────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo -e "${GREEN}  ✅  Установка завершена!${NC}"
echo "══════════════════════════════════════════════"
echo ""
echo -e "${YELLOW}  ⚠️   Перед запуском откройте CHANGES_REQUIRED.md"
echo "      и заполните все TODO-параметры в obs_bot.py${NC}"
echo ""
echo "  Файл настроек: $INSTALL_DIR/obs_bot.py"
echo ""
echo "  ▶️   Запуск:"
echo "      sudo systemctl enable --now mediamtx obs_bot"
echo ""
echo "  📜  Логи бота:"
echo "      journalctl -u obs_bot -f"
echo ""
echo "  📜  Логи MediaMTX:"
echo "      journalctl -u mediamtx -f"
echo ""
