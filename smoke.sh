#!/usr/bin/env bash
# Быстрая проверка работоспособности obs_bot. Только чтение. Exit 0 = всё OK.

set -u

FAILED=0
pass() { printf "  PASS  %s\n" "$1"; }
fail() { printf "  FAIL  %s — %s\n" "$1" "$2"; FAILED=1; }
info() { printf "  INFO  %s\n" "$1"; }

echo "── obs_bot smoke ──"

# 1. systemd unit active
if systemctl is-active --quiet obs_bot; then
    pass "systemd: obs_bot active"
else
    fail "systemd" "obs_bot $(systemctl is-active obs_bot 2>&1)"
fi

# 2. Отсутствие Traceback / ERROR за последнюю минуту
ERRS=$(journalctl -u obs_bot --since "1 minute ago" --no-pager 2>/dev/null \
       | grep -E "Traceback|ERROR" | head -3)
if [ -z "$ERRS" ]; then
    pass "logs: чисто за последнюю минуту"
else
    fail "logs" "найдены ошибки (первые 3):"
    echo "$ERRS" | sed 's/^/        /'
fi

# 3. Порт OBS WebSocket — информационно
OBS_PORT_CHECK="${OBS_PORT:-4455}"
OBS_HOST_CHECK="${OBS_HOST:-127.0.0.1}"
if nc -z -w 1 "$OBS_HOST_CHECK" "$OBS_PORT_CHECK" 2>/dev/null; then
    info "obs: порт $OBS_HOST_CHECK:$OBS_PORT_CHECK открыт"
else
    info "obs: порт $OBS_HOST_CHECK:$OBS_PORT_CHECK закрыт (OBS не запущен или другой хост?)"
fi

# 4. MediaMTX unit active — информационно
if systemctl is-active --quiet mediamtx 2>/dev/null; then
    info "mediamtx: active"
else
    info "mediamtx: не запущен ($(systemctl is-active mediamtx 2>/dev/null || echo 'не установлен'))"
fi

echo "───────────────────"
if [ "$FAILED" = 0 ]; then
    echo "ALL OK"
    exit 0
else
    echo "FAILED"
    exit 1
fi
