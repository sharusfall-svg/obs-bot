# OBS Stream Bot

Telegram-бот для удалённого управления OBS Studio через WebSocket + медиа-сервер MediaMTX для ретрансляции потоков.

Управление ведётся через кнопки прямо в Telegram — без браузера, без веб-интерфейса, без VPN.

---

## Возможности

- **Управление трансляцией** — запуск и остановка стрима одной кнопкой
- **Переключение сцен** — основная сцена и сцена-заглушка (перерыв)
- **Скриншот** — мгновенный снимок текущей основной сцены прямо в чат
- **Статус** — версия OBS, состояние стрима, текущая сцена
- **Многопользовательский доступ** — белый список Telegram ID
- **Защита от посторонних** — ложный ответ об ошибке для заблокированных пользователей
- **Healthcheck** — автоматическая проверка доступности OBS каждые 30 секунд
- **MediaMTX** — встроенный медиа-сервер для RTSP/RTMP/HLS/WebRTC потоков

---

## Требования

- Ubuntu 20.04+ или Debian 11+
- Root-доступ (sudo)
- Python 3.10+
- OBS Studio на том же или удалённом ПК с включённым **WebSocket Server** (порт 4455)
- Открытые порты (если OBS на другом ПК): `4455` (OBS WebSocket)
- Для MediaMTX: `8554` (RTSP), `1935` (RTMP), `8888` (HLS/WebRTC), `8890` (SRT)

---

## Быстрая установка

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd <ИМЯ_РЕПО>
sudo chmod +x install.sh && sudo bash install.sh
```

---

## Настройка

После установки **обязательно** заполните все параметры в файле настроек:

```bash
nano /opt/obs-stream-bot/obs_bot.py
```

Смотрите полный список параметров: [CHANGES_REQUIRED.md](CHANGES_REQUIRED.md)

Минимальный набор для запуска:
- `TELEGRAM_TOKEN` — токен от @BotFather
- `ALLOWED_USER_IDS` — ваш Telegram ID (от @userinfobot)
- `OBS_HOST` / `OBS_PORT` / `OBS_PASSWORD` — данные OBS WebSocket
- `SCENE_MAIN` / `SCENE_BREAK` — имена сцен в OBS

---

## Запуск

```bash
# Включить автозапуск и запустить сразу
sudo systemctl enable --now mediamtx obs_bot

# Проверить статус
sudo systemctl status obs_bot
sudo systemctl status mediamtx

# Логи в реальном времени
journalctl -u obs_bot -f
journalctl -u mediamtx -f
```

### Запуск без systemd (отладка)

```bash
bash /opt/obs-stream-bot/start.sh
```

---

## Структура проекта

```
.
├── obs_bot.py          # Основной скрипт Telegram-бота
├── requirements.txt    # Python зависимости
├── mediamtx.yml        # Конфигурация медиа-сервера MediaMTX
├── obs_bot.service     # systemd-юнит для бота
├── mediamtx.service    # systemd-юнит для MediaMTX
├── install.sh          # Скрипт автоматической установки
├── start.sh            # Запуск без systemd (для отладки)
├── smoke.sh            # Быстрая проверка работоспособности
├── CHANGES_REQUIRED.md # Список параметров для заполнения
└── README.md           # Этот файл
```

---

## Обновление

```bash
# Обновить файлы из репозитория
git pull

# Скопировать обновлённый скрипт
sudo cp obs_bot.py /opt/obs-stream-bot/obs_bot.py

# Перезапустить
sudo systemctl restart obs_bot
```
