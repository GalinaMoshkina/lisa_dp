import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
USERS_PATH = DATA_DIR / "users.json"
SUBMISSIONS_PATH = DATA_DIR / "submissions.json"
LOGS_PATH = DATA_DIR / "logs.json"
ENV_PATH = BASE_DIR / ".env"
HASH_API_URL = "http://127.0.0.1:8091"

BRANCHES = [
    "Глава 1. Об издании DNS и проекте Клуб-DP",
    "Глава 2. Цифровизация естественно-научных дисциплин",
    "Глава 3. ИСО и социальные системы",
    "Глава 4. ФИНТЕХ системы и экономика",
    "Глава 5. ИИ и образование",
    "Глава 6. ИИ и здоровье",
    "Глава 7. Цифровые технологии в гуманитарных науках и искусстве",
    "Глава 8. Искусственный интеллект и цифровые технологии в торговле",
    "Глава 9. Цифровизация в ЖКХ, производственной и транспортной отраслях",
    "Глава 10. Разное интересное (по тематике)",
]

BTN_PUBLISH = "Опубликовать материал"
BTN_PROFILE = "Мой профиль"
BTN_SUBMISSIONS = "Мои материалы"
BTN_HELP = "Помощь"
BTN_CANCEL = "Отмена"

EDITABLE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".csv",
    ".rtf",
    ".odt",
    ".ods",
    ".odp",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".txt",
    ".md",
}


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("digital-parallels-bot")


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for path in (USERS_PATH, SUBMISSIONS_PATH, LOGS_PATH):
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
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def hash_api_url() -> str:
    return os.getenv("HASH_API_URL", HASH_API_URL).rstrip("/")


def read_json(path: Path) -> list[dict]:
    ensure_storage()
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: list[dict]) -> None:
    ensure_storage()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def user_by_chat(chat_id: int) -> dict | None:
    users = read_json(USERS_PATH)
    return next((user for user in users if user["chat_id"] == chat_id), None)


def upsert_user(user: dict) -> None:
    users = read_json(USERS_PATH)
    users = [item for item in users if item["chat_id"] != user["chat_id"]]
    users.append(user)
    write_json(USERS_PATH, users)


def add_submission(submission: dict) -> None:
    submissions = read_json(SUBMISSIONS_PATH)
    submissions.append(submission)
    write_json(SUBMISSIONS_PATH, submissions)


def log_action(chat_id: int, action: str, details: dict | None = None) -> None:
    logs = read_json(LOGS_PATH)
    logs.append(
        {
            "chat_id": chat_id,
            "action": action,
            "details": details or {},
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    write_json(LOGS_PATH, logs)


def register_material_hash(target_path: Path, file_name: str, user: dict, branch: str, submission_id: str) -> dict:
    payload = {
        "file_path": str(target_path),
        "file_name": file_name,
        "author": user["fio"],
        "telegram_user_id": user["telegram_user_id"],
        "telegram_username": user.get("telegram_username"),
        "branch": branch,
        "source": "tgbot",
        "submission_id": submission_id,
    }
    request = urllib.request.Request(
        f"{hash_api_url()}/api/v1/documents/register",
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


def publish_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Опубликовать материал", callback_data="publish")]]
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_PUBLISH)],
            [KeyboardButton(BTN_PROFILE), KeyboardButton(BTN_SUBMISSIONS)],
            [KeyboardButton(BTN_HELP), KeyboardButton(BTN_CANCEL)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def branch_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(branch, callback_data=f"branch:{index}")]
        for index, branch in enumerate(BRANCHES)
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    if user_by_chat(update.effective_chat.id):
        context.user_data["step"] = "registered"
        await update.message.reply_text(
            "Вы уже зарегистрированы. Выберите действие в меню ниже.",
            reply_markup=main_menu_keyboard(),
        )
        return

    context.user_data["step"] = "fio"
    log_action(update.effective_chat.id, "start")
    await update.message.reply_text(
        "Здравствуйте! Я бот регистрации Digital Parallels.\n\n"
        "Укажите, пожалуйста, ФИО полностью: фамилия, имя и отчество."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    step = context.user_data.get("step")
    text = update.message.text.strip()

    if text == BTN_PUBLISH:
        await start_publish_from_message(update, context)
        return

    if text == BTN_PROFILE:
        await profile(update, context)
        return

    if text == BTN_SUBMISSIONS:
        await my_submissions(update, context)
        return

    if text == BTN_HELP:
        await help_message(update, context)
        return

    if text == BTN_CANCEL:
        await cancel(update, context)
        return

    if step == "fio":
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("Пожалуйста, укажите хотя бы фамилию и имя.")
            return

        context.user_data["fio"] = text
        context.user_data["step"] = "phone"
        await update.message.reply_text(
            "Теперь отправьте номер телефона. Можно нажать кнопку ниже или написать номер текстом.",
            reply_markup=phone_keyboard(),
        )
        return

    if step == "phone":
        await save_registered_user(update, context, phone=text)
        return

    await update.message.reply_text(
        "Выберите действие в меню ниже.",
        reply_markup=main_menu_keyboard(),
    )


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    phone = update.message.contact.phone_number
    await save_registered_user(update, context, phone=phone)


async def save_registered_user(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str) -> None:
    fio = context.user_data.get("fio")
    if not fio:
        context.user_data["step"] = "fio"
        await update.message.reply_text("Сначала укажите ФИО.")
        return

    user = {
        "chat_id": update.effective_chat.id,
        "telegram_user_id": update.effective_user.id,
        "telegram_username": update.effective_user.username,
        "fio": fio,
        "phone": phone,
        "registered_at": datetime.now().isoformat(timespec="seconds"),
    }
    upsert_user(user)
    log_action(
        update.effective_chat.id,
        "user_registered",
        {
            "fio": fio,
            "phone": phone,
            "telegram_username": update.effective_user.username,
        },
    )
    context.user_data["step"] = "registered"

    await update.message.reply_text(
        "Регистрация завершена. Теперь вы можете отправить материал для публикации.",
        reply_markup=main_menu_keyboard(),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "publish":
        if not user_by_chat(query.message.chat_id):
            context.user_data["step"] = "fio"
            await query.message.reply_text("Для публикации сначала нужно зарегистрироваться. Укажите ФИО.")
            return

        await start_publish(query.message.chat_id, context, query.message.reply_text)
        return

    if query.data.startswith("branch:"):
        pending_file = context.user_data.get("pending_file")
        if not pending_file:
            await query.message.reply_text("Сначала отправьте редактируемый файл материала.")
            return

        index = int(query.data.split(":", 1)[1])
        branch = BRANCHES[index]
        user = user_by_chat(query.message.chat_id)
        submission_id = f"submission-{int(datetime.now().timestamp())}"
        hash_registration = register_material_hash(
            BASE_DIR / pending_file["file_path"],
            pending_file["file_name"],
            user,
            branch,
            submission_id,
        )
        submission = {
            "id": submission_id,
            "chat_id": query.message.chat_id,
            "fio": user["fio"],
            "phone": user["phone"],
            "branch": branch,
            "file_name": pending_file["file_name"],
            "file_path": pending_file["file_path"],
            "hash_registration": hash_registration,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        add_submission(submission)
        log_action(
            query.message.chat_id,
            "submission_created",
            {
                "submission_id": submission["id"],
                "branch": branch,
                "file_name": submission["file_name"],
                "hash_registration": hash_registration,
            },
        )
        context.user_data["step"] = "registered"
        context.user_data.pop("pending_file", None)

        hash_text = ""
        if hash_registration.get("sha256"):
            annotation = hash_registration.get("annotation") or {}
            annotation_text = ""
            if annotation.get("text"):
                annotation_text = f"\n\nАвтоматическая аннотация:\n{annotation['text']}"
            hash_text = (
                "\n\n"
                f"Хэш SHA256: {hash_registration['sha256']}\n"
                f"Статус фиксации: {hash_registration.get('status', 'registered')}"
                f"{annotation_text}"
            )
        else:
            hash_text = "\n\nФиксация хэша временно недоступна. Материал сохранен, повторить фиксацию можно позже."

        await query.message.reply_text(
            "Материал принят.\n\n"
            f"Ветка: {branch}\n"
            f"Файл: {submission['file_name']}"
            f"{hash_text}",
            reply_markup=main_menu_keyboard(),
        )


async def start_publish_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not user_by_chat(update.effective_chat.id):
        context.user_data["step"] = "fio"
        await update.message.reply_text("Для публикации сначала нужно зарегистрироваться. Укажите ФИО.")
        return

    await start_publish(update.effective_chat.id, context, update.message.reply_text)


async def start_publish(chat_id: int, context: ContextTypes.DEFAULT_TYPE, reply) -> None:
    context.user_data["step"] = "waiting_material"
    context.user_data.pop("pending_file", None)
    log_action(chat_id, "publish_started")
    await reply(
        "Пришлите редактируемый файл материала: Word, PowerPoint, Excel, OpenDocument, RTF, TXT или Markdown.",
        reply_markup=main_menu_keyboard(),
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("step") != "waiting_material":
        await update.message.reply_text(
            "Чтобы отправить материал, нажмите кнопку «Опубликовать материал».",
            reply_markup=main_menu_keyboard(),
        )
        return

    document = update.message.document
    file_name = document.file_name or "material"
    extension = Path(file_name).suffix.lower()
    if extension not in EDITABLE_EXTENSIONS:
        allowed = ", ".join(sorted(EDITABLE_EXTENSIONS))
        await update.message.reply_text(
            "Пожалуйста, пришлите файл в редактируемом формате.\n\n"
            f"Поддерживаются: {allowed}",
            reply_markup=main_menu_keyboard(),
        )
        return

    telegram_file = await document.get_file()
    safe_name = "".join(char for char in file_name if char.isalnum() or char in "._- ").strip()
    target_dir = UPLOADS_DIR / str(update.effective_chat.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{int(datetime.now().timestamp())}_{safe_name}"
    await telegram_file.download_to_drive(custom_path=target_path)

    context.user_data["pending_file"] = {
        "file_name": file_name,
        "file_path": str(target_path.relative_to(BASE_DIR)),
    }
    context.user_data["step"] = "waiting_branch"
    log_action(
        update.effective_chat.id,
        "material_uploaded",
        {
            "file_name": file_name,
            "file_path": str(target_path.relative_to(BASE_DIR)),
        },
    )

    await update.message.reply_text(
        "Файл получен. Теперь выберите ветку, к которой нужно опубликовать материал.",
        reply_markup=branch_keyboard(),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.clear()
    log_action(update.effective_chat.id, "cancel")
    await update.message.reply_text("Действие отменено. Выберите действие в меню.", reply_markup=main_menu_keyboard())


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = user_by_chat(update.effective_chat.id)
    if not user:
        await update.message.reply_text("Вы пока не зарегистрированы. Отправьте /start.")
        return

    await update.message.reply_text(
        "Ваш профиль:\n\n"
        f"ФИО: {user['fio']}\n"
        f"Телефон: {user['phone']}\n"
        f"Telegram: @{user['telegram_username'] or 'не указан'}",
        reply_markup=main_menu_keyboard(),
    )


async def my_submissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    submissions = [
        item for item in read_json(SUBMISSIONS_PATH)
        if item["chat_id"] == update.effective_chat.id
    ]
    if not submissions:
        await update.message.reply_text("У вас пока нет отправленных материалов.", reply_markup=main_menu_keyboard())
        return

    lines = ["Ваши отправленные материалы:"]
    for index, submission in enumerate(submissions, start=1):
        lines.append(
            f"\n{index}. {submission['file_name']}\n"
            f"Ветка: {submission['branch']}\n"
            f"Дата: {submission['created_at']}"
        )
        hash_registration = submission.get("hash_registration") or {}
        if hash_registration.get("sha256"):
            lines.append(f"SHA256: {hash_registration['sha256']}")
            annotation = hash_registration.get("annotation") or {}
            if annotation.get("text"):
                lines.append(f"Аннотация: {annotation['text']}")
    await update.message.reply_text("\n".join(lines), reply_markup=main_menu_keyboard())


async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Что можно сделать:\n\n"
        "• Опубликовать материал — отправить редактируемый файл и выбрать главу.\n"
        "• Мой профиль — посмотреть регистрационные данные.\n"
        "• Мои материалы — посмотреть отправленные материалы.\n"
        "• Отмена — сбросить текущий сценарий.",
        reply_markup=main_menu_keyboard(),
    )


def main() -> None:
    ensure_storage()
    load_local_env()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не найден BOT_TOKEN. Укажите токен бота в переменной окружения.")

    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
    )
    app = Application.builder().token(token).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("my_submissions", my_submissions))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Digital Parallels bot started")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        bootstrap_retries=-1,
        timeout=30,
    )


if __name__ == "__main__":
    main()
