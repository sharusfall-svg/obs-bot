import asyncio
import websockets
import json
import base64
import hashlib
import logging
import sys
from io import BytesIO
from datetime import datetime
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler,
    MessageHandler, filters, ContextTypes,
)
from telegram.error import TelegramError
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler("./obs_bot.log", maxBytes=5*1024*1024, backupCount=2, encoding="utf-8"),
    ],
)
log = logging.getLogger("obs_bot")
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ═══════════════════════════════════════════════════════════
# НАСТРОЙКИ — заполните перед запуском
# ═══════════════════════════════════════════════════════════

# TODO: Telegram bot token.
# Где взять: написать @BotFather → /newbot → следовать инструкции →
# скопировать выданный токен вида 1234567890:ABCdefGhIjKlmNoPQRstuVwxYZ.
TELEGRAM_TOKEN = "REPLACE_ME_BOT_TOKEN"

# TODO: Telegram ID пользователей, которым разрешено управление ботом.
# Где взять: написать @userinfobot в Telegram → он пришлёт ваш числовой ID.
# Если администраторов несколько — перечислите через запятую: [123456, 789012].
ALLOWED_USER_IDS = [0]  # REPLACE_ME: список числовых Telegram ID

# TODO: Telegram ID пользователя, которому бот будет показывать ложное сообщение
# об ошибке системы вместо «Доступ запрещён». Оставьте 0 чтобы отключить функцию.
BLOCKED_USER_ID  = 0   # REPLACE_ME
BLOCKED_RESPONSE = "00x1549828 - Ошибка доступа к операции обработки запроса на возврат."

# TODO: Настройки подключения к OBS WebSocket на основном ПК.
# Замените на свои значения. Порт и пароль настраиваются в OBS:
# Инструменты → WebSocket Server Settings.
OBS_HOST     = "REPLACE_ME_OBS_HOST"      # IP или hostname ПК с OBS (127.0.0.1 если OBS на этом же сервере)
OBS_PORT     = 4455                        # порт WebSocket (по умолчанию 4455)
OBS_PASSWORD = "REPLACE_ME_OBS_PASSWORD"  # пароль из настроек OBS WebSocket (пусто "" если без пароля)

# TODO: Имя основной сцены трансляции в OBS (точно как в OBS, с учётом регистра).
# Используется для кнопки «Основная сцена» и команды «Скриншот».
SCENE_MAIN  = ""  # REPLACE_ME, например: "Main" или "Трансляция"

# TODO: Имя сцены-заглушки / перерыва в OBS (точно как в OBS, с учётом регистра).
# Используется для кнопки «Сцена перерыв».
SCENE_BREAK = ""  # REPLACE_ME, например: "BRB" или "Перерыв"

OBS_TIMEOUT          = 10
HEALTHCHECK_INTERVAL = 30

# ═══════════════════════════════════════════════════════════
# OBS WebSocket
# ═══════════════════════════════════════════════════════════

async def obs_request(request_type: str, request_data: dict | None = None) -> dict:
    uri = f"ws://{OBS_HOST}:{OBS_PORT}"
    try:
        async with websockets.connect(uri, open_timeout=OBS_TIMEOUT) as ws:
            raw   = await asyncio.wait_for(ws.recv(), timeout=OBS_TIMEOUT)
            hello = json.loads(raw)
            if hello.get("op") != 0:
                return {"error": f"Expected Hello, got op={hello.get('op')}"}
            identify_d = {"rpcVersion": 1}
            if "authentication" in hello["d"]:
                challenge = hello["d"]["authentication"]["challenge"]
                salt      = hello["d"]["authentication"]["salt"]
                secret    = base64.b64encode(hashlib.sha256((OBS_PASSWORD + salt).encode()).digest()).decode()
                auth      = base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()
                identify_d["authentication"] = auth
            await ws.send(json.dumps({"op": 1, "d": identify_d}))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=OBS_TIMEOUT)
                msg = json.loads(raw)
                if msg.get("op") == 2: break
                if msg.get("op") == 0: return {"error": "Auth failed"}
            await ws.send(json.dumps({"op": 6, "d": {
                "requestType": request_type, "requestId": "1",
                "requestData": request_data or {},
            }}))
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=OBS_TIMEOUT)
                msg = json.loads(raw)
                if msg.get("op") == 5: continue
                if msg.get("op") == 7 and msg["d"].get("requestId") == "1":
                    status = msg["d"].get("requestStatus", {})
                    if not status.get("result", False):
                        return {"error": f"OBS error: {status.get('comment', 'unknown')}"}
                    return msg
    except asyncio.TimeoutError:       return {"error": "Timeout — OBS не отвечает"}
    except ConnectionRefusedError:     return {"error": "OBS WebSocket недоступен"}
    except websockets.exceptions.ConnectionClosedError as e: return {"error": f"Соединение закрыто: {e}"}
    except Exception as e:
        log.exception("OBS ошибка [%s]", request_type)
        return {"error": f"{type(e).__name__}: {e}"}


async def get_stream_status():
    r = await obs_request("GetStreamStatus")
    if "error" in r: return None, r["error"]
    return r["d"]["responseData"].get("outputActive", False), None

async def get_current_scene():
    r = await obs_request("GetCurrentProgramScene")
    if "error" in r: return None
    return r["d"]["responseData"].get("sceneName")

async def set_scene(name: str) -> dict:
    return await obs_request("SetCurrentProgramScene", {"sceneName": name})

async def get_scene_screenshot(scene: str) -> tuple[bytes | None, str | None]:
    r = await obs_request("GetSourceScreenshot", {
        "sourceName": scene, "imageFormat": "jpg",
        "imageWidth": 1280, "imageHeight": 720, "imageCompressionQuality": 75,
    })
    if "error" in r: return None, r["error"]
    img = r["d"]["responseData"].get("imageData", "")
    if not img: return None, "OBS вернул пустой скриншот"
    if "," in img: img = img.split(",", 1)[1]
    try:    return base64.b64decode(img), None
    except Exception as e: return None, f"Ошибка декодирования: {e}"

async def get_obs_version():
    r = await obs_request("GetVersion")
    if "error" in r: return False, None, r["error"]
    return True, r["d"]["responseData"].get("obsVersion", "?"), None

# ═══════════════════════════════════════════════════════════
# Healthcheck
# ═══════════════════════════════════════════════════════════

async def healthcheck_loop() -> None:
    while True:
        try:    await asyncio.sleep(HEALTHCHECK_INTERVAL)
        except asyncio.CancelledError: log.info("Healthcheck остановлен"); return
        try:
            result = await obs_request("GetVersion")
            if "error" in result:
                log.error("❌ OBS НЕДОСТУПЕН: %s", result["error"])
            else:
                ver = result["d"]["responseData"].get("obsVersion", "?")
                log.info("✅ OBS v%s (%s)", ver, datetime.now().strftime("%H:%M:%S"))
        except asyncio.CancelledError: log.info("Healthcheck остановлен"); return
        except Exception as e: log.exception("Healthcheck ошибка: %s", e)

# ═══════════════════════════════════════════════════════════
# Telegram handlers
# ═══════════════════════════════════════════════════════════

def is_allowed(uid: int) -> bool:
    return uid in ALLOWED_USER_IDS

EM_START       = "▶️ Включить стрим"
EM_STOP        = "⏹ Выключить стрим"
EM_SCENE_MAIN  = "🌅 Основная сцена"
EM_SCENE_BREAK = "💤 Сцена перерыв"
EM_SCREENSHOT  = "📷 Скриншот"
EM_STATUS      = "📊 Статус"

ALL_BUTTONS = {EM_START, EM_STOP, EM_SCENE_MAIN, EM_SCENE_BREAK, EM_SCREENSHOT, EM_STATUS}

def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(EM_START),       KeyboardButton(EM_STOP)],
            [KeyboardButton(EM_SCENE_MAIN),  KeyboardButton(EM_SCENE_BREAK)],
            [KeyboardButton(EM_SCREENSHOT),  KeyboardButton(EM_STATUS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Управление OBS",
    )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    log.info("/start от uid=%s", uid)
    if uid == BLOCKED_USER_ID:
        await update.message.reply_text(BLOCKED_RESPONSE); return
    if not is_allowed(uid):
        await update.message.reply_text("⛔ Доступ запрещён."); return
    await update.message.reply_text(
        "🎮 *OBS Управление*\nИспользуй кнопки для управления стримом.",
        parse_mode="Markdown", reply_markup=get_main_keyboard(),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    if uid == BLOCKED_USER_ID:
        await update.message.reply_text(BLOCKED_RESPONSE); return
    if not is_allowed(uid):
        await update.message.reply_text("⛔ Доступ запрещён."); return
    await update.message.reply_text(
        "🎮 *OBS Управление*\n"
        "▶️ Включить стрим — запустить трансляцию\n"
        "⏹ Выключить стрим — остановить трансляцию\n"
        "🌅 Основная сцена — переключить на основную сцену\n"
        "💤 Сцена перерыв — переключить на сцену-заглушку\n"
        "📷 Скриншот — снимок текущей основной сцены\n"
        "📊 Статус — состояние OBS и стрима",
        parse_mode="Markdown", reply_markup=get_main_keyboard(),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid  = update.effective_user.id
    text = update.message.text or ""
    if uid == BLOCKED_USER_ID:
        await update.message.reply_text(BLOCKED_RESPONSE); return
    if text not in ALL_BUTTONS: return
    if not is_allowed(uid):
        await update.message.reply_text("⛔ Доступ запрещён."); return

    kb = get_main_keyboard()

    if text == EM_START:
        is_live, err = await get_stream_status()
        if err:          msg = f"❌ Ошибка: `{err}`"
        elif is_live:    msg = "ℹ️ Стрим уже идёт."
        else:            await obs_request("StartStream"); msg = "✅ Стрим запущен."
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif text == EM_STOP:
        is_live, err = await get_stream_status()
        if err:           msg = f"❌ Ошибка: `{err}`"
        elif not is_live: msg = "ℹ️ Стрим уже остановлен."
        else:             await obs_request("StopStream"); msg = "✅ Стрим остановлен."
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif text == EM_SCENE_MAIN:
        if not SCENE_MAIN:
            await update.message.reply_text("⚠️ SCENE_MAIN не задана в настройках.", reply_markup=kb); return
        result = await set_scene(SCENE_MAIN)
        msg = f"✅ Сцена: {SCENE_MAIN}" if "error" not in result else f"❌ {result['error']}"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif text == EM_SCENE_BREAK:
        if not SCENE_BREAK:
            await update.message.reply_text("⚠️ SCENE_BREAK не задана в настройках.", reply_markup=kb); return
        result = await set_scene(SCENE_BREAK)
        msg = f"✅ Сцена: {SCENE_BREAK}" if "error" not in result else f"❌ {result['error']}"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif text == EM_SCREENSHOT:
        if not SCENE_MAIN:
            await update.message.reply_text("⚠️ SCENE_MAIN не задана в настройках.", reply_markup=kb); return
        await update.message.reply_text("📷 Делаю скриншот...", reply_markup=kb)
        img_bytes, err = await get_scene_screenshot(SCENE_MAIN)
        if err:
            await update.message.reply_text(f"❌ `{err}`", parse_mode="Markdown", reply_markup=kb)
        else:
            await update.message.reply_photo(
                photo=BytesIO(img_bytes),
                caption=f"📷 Сцена *{SCENE_MAIN}* — {datetime.now().strftime('%H:%M:%S')}",
                parse_mode="Markdown", reply_markup=kb,
            )

    elif text == EM_STATUS:
        is_online, obs_version, err = await get_obs_version()
        if not is_online:
            await update.message.reply_text(f"❌ OBS недоступен: `{err}`", parse_mode="Markdown", reply_markup=kb)
            return
        is_live, stream_err = await get_stream_status()
        scene = await get_current_scene()
        stream_str = "🔴 Идёт" if is_live else "⚫ Не идёт"
        if stream_err: stream_str = f"❓ {stream_err}"
        msg = (
            f"📊 *Статус OBS*\n"
            f"OBS: ✅ v{obs_version}\n"
            f"Стрим: {stream_str}\n"
            f"Сцена: `{scene or '—'}`\n"
            f"Время: {datetime.now().strftime('%H:%M:%S')}"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)


async def blocked_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user and update.effective_user.id == BLOCKED_USER_ID:
        await update.message.reply_text(BLOCKED_RESPONSE)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Telegram ошибка: %s", context.error, exc_info=context.error)

# ═══════════════════════════════════════════════════════════
# Точка входа
# ═══════════════════════════════════════════════════════════

def main() -> None:
    log.info("Запуск | OBS=%s:%s", OBS_HOST, OBS_PORT)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(
            f"^({'|'.join(t.replace('(', r'\(').replace(')', r'\)').replace('.', r'\.') for t in ALL_BUTTONS)})$"
        ),
        button_handler,
    ))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, blocked_user_handler))
    app.add_error_handler(error_handler)

    _hc_task: asyncio.Task | None = None

    async def post_init(application: Application) -> None:
        nonlocal _hc_task
        _hc_task = asyncio.create_task(healthcheck_loop(), name="obs_healthcheck")
        log.info("✅ Healthcheck запущен")

    async def post_stop(application: Application) -> None:
        nonlocal _hc_task
        if _hc_task and not _hc_task.done():
            _hc_task.cancel()
            try: await _hc_task
            except asyncio.CancelledError: pass
        log.info("Бот полностью остановлен")

    app.post_init = post_init
    app.post_stop = post_stop
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
