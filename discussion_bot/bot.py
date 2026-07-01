import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ChatJoinRequestHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ENV_PATH = BASE_DIR / ".env"
REGISTRATIONS_PATH = DATA_DIR / "registrations.json"
JOIN_REQUESTS_PATH = DATA_DIR / "join_requests.json"
LOGS_PATH = DATA_DIR / "logs.json"
CORE_API_URL = "http://127.0.0.1:8091"

BTN_PROFILE = "Моя регистрация"

DISCUSSION_GROUP_URL = "https://t.me/+DRbehXtIw0AwOTNi"


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dp-discussion-registration-bot")


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in (REGISTRATIONS_PATH, JOIN_REQUESTS_PATH, LOGS_PATH):
        if not path.exists():
            path.write_text("[]", encoding="utf-8")


def load_local_env() -> None:
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def core_api_url() -> str:
    return os.getenv("CORE_API_URL", os.getenv("HASH_API_URL", CORE_API_URL)).rstrip("/")


def read_json(path: Path) -> list[dict]:
    ensure_storage()
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: list[dict]) -> None:
    ensure_storage()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[BTN_PROFILE]],
        resize_keyboard=True,
        is_persistent=True,
    )


def group_link_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Перейти в группу", url=DISCUSSION_GROUP_URL)]]
    )


def log_action(user_id: int, action: str, details: dict | None = None) -> None:
    logs = read_json(LOGS_PATH)
    logs.append(
        {
            "telegram_user_id": user_id,
            "action": action,
            "details": details or {},
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    write_json(LOGS_PATH, logs)


def sync_registration_to_api(registration: dict) -> dict:
    payload = {
        **registration,
        "source": "discussion_bot",
    }
    request = urllib.request.Request(
        f"{core_api_url()}/api/v1/discussion-registrations",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        return {
            "status": "unavailable",
            "error": str(error),
        }


def registration_by_user_id(user_id: int) -> dict | None:
    registrations = read_json(REGISTRATIONS_PATH)
    return next((item for item in registrations if item["telegram_user_id"] == user_id), None)


def upsert_registration(registration: dict) -> None:
    registrations = read_json(REGISTRATIONS_PATH)
    registrations = [
        item for item in registrations
        if item["telegram_user_id"] != registration["telegram_user_id"]
    ]
    registrations.append(registration)
    write_json(REGISTRATIONS_PATH, registrations)


def add_join_request(record: dict) -> None:
    requests = read_json(JOIN_REQUESTS_PATH)
    requests.append(record)
    write_json(JOIN_REQUESTS_PATH, requests)


def is_valid_fio(text: str) -> bool:
    parts = [part for part in text.split() if part]
    return len(parts) >= 3 and all(len(part) >= 2 for part in parts[:3])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    existing = registration_by_user_id(user.id)
    if existing:
        await update.message.reply_text(
            "Вы уже прошли первый этап регистрации.\n\n"
            f"ФИО: {existing['fio']}\n\n"
            "Теперь можно перейти в дискуссионную группу.",
            reply_markup=menu_keyboard(),
        )
        await update.message.reply_text("Перейдите в группу по кнопке ниже:", reply_markup=group_link_keyboard())
        return

    context.user_data["step"] = "fio"
    log_action(user.id, "start")
    await update.message.reply_text(
        "Здравствуйте! Это бот первого этапа регистрации DP-Club.\n\n"
        "Чтобы получить доступ к дискуссионной группе, укажите ФИО полностью: "
        "фамилия, имя и отчество.",
        reply_markup=menu_keyboard(),
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    existing = registration_by_user_id(update.effective_user.id)
    if not existing:
        context.user_data["step"] = "fio"
        await update.message.reply_text("Регистрация еще не пройдена. Укажите ФИО полностью.")
        return

    await update.message.reply_text(
        "Первый этап регистрации пройден.\n\n"
        f"ФИО: {existing['fio']}\n"
        f"Telegram: @{existing['telegram_username'] or 'не указан'}\n"
        f"Дата: {existing['registered_at']}",
        reply_markup=menu_keyboard(),
    )
    await update.message.reply_text("Перейдите в группу по кнопке ниже:", reply_markup=group_link_keyboard())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    if text == BTN_PROFILE:
        await profile(update, context)
        return

    if not is_valid_fio(text):
        context.user_data["step"] = "fio"
        await update.message.reply_text(
            "Пожалуйста, укажите ФИО полностью: фамилия, имя и отчество.\n"
            "Например: Иванов Иван Иванович",
            reply_markup=menu_keyboard(),
        )
        return

    user = update.effective_user
    registration = {
        "telegram_user_id": user.id,
        "telegram_username": user.username,
        "fio": text,
        "registered_at": datetime.now().isoformat(timespec="seconds"),
    }
    upsert_registration(registration)
    api_sync = sync_registration_to_api(registration)
    context.user_data["step"] = "registered"
    log_action(
        user.id,
        "registered",
        {
            "fio": text,
            "telegram_username": user.username,
            "api_sync": api_sync,
        },
    )

    await update.message.reply_text(
        "Спасибо, регистрация сохранена.\n\n"
        "Теперь нажмите кнопку ниже, чтобы перейти в дискуссионную группу. "
        "Заявка будет принята автоматически.",
        reply_markup=menu_keyboard(),
    )
    await update.message.reply_text("Перейдите в группу по кнопке ниже:", reply_markup=group_link_keyboard())


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    request = update.chat_join_request
    user = request.from_user
    registration = registration_by_user_id(user.id)
    status = "approved" if registration else "pending_no_registration"

    record = {
        "telegram_user_id": user.id,
        "telegram_username": user.username,
        "chat_id": request.chat.id,
        "chat_title": request.chat.title,
        "status": status,
        "fio": registration["fio"] if registration else None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    add_join_request(record)
    log_action(user.id, "join_request", record)

    if registration:
        await request.approve()
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text="Ваша заявка в дискуссионную группу принята. Добро пожаловать!",
                reply_markup=menu_keyboard(),
            )
        except Exception:
            logger.info("Could not send private approval message to user %s", user.id)
        return

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=(
                "Ваша заявка в дискуссионную группу пока не принята автоматически.\n\n"
                "Сначала напишите этому боту ФИО полностью, затем повторите заявку."
            ),
            reply_markup=menu_keyboard(),
        )
    except Exception:
        logger.info("Could not send private registration reminder to user %s", user.id)


def main() -> None:
    ensure_storage()
    load_local_env()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не найден BOT_TOKEN. Укажите токен в .env или переменной окружения.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("DP discussion registration bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
