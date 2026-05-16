#!/usr/bin/env bash
# Запуск бота без systemd (для отладки, в foreground).
# Использование: bash start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ищем venv рядом со скриптом или в /opt/obs-stream-bot
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
elif [ -f "/opt/obs-stream-bot/venv/bin/python" ]; then
    PYTHON="/opt/obs-stream-bot/venv/bin/python"
else
    echo "❌ venv не найден. Запустите сначала: sudo bash install.sh"
    exit 1
fi

cd "$SCRIPT_DIR"
echo "▶️  Запуск obs_bot.py через $PYTHON"
echo "   Нажмите Ctrl+C для остановки."
echo ""
exec "$PYTHON" obs_bot.py
