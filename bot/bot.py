import logging
import os
from datetime import datetime

import telegram
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from database import Database
from openai_helper import OpenAIHelper

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

db = Database()
openai_helper = OpenAIHelper()


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    if not config.ALLOWED_TELEGRAM_USERIDS:
        return True
    return str(user_id) in config.ALLOWED_TELEGRAM_USERIDS


# ── Commands ──────────────────────────────────────────────────────────────────

async def start_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a Mia.")
        return
    db.set_user_attribute(user.id, "last_seen", datetime.now().isoformat())
    await update.message.reply_text(
        f"👋 ¡Hola, *{user.first_name}*! Soy *Mia*, tu asistente de IA.\n\n"
        "Puedo ayudarte con preguntas, redacción, código, imágenes y mucho más.\n\n"
        "📌 *Comandos disponibles:*\n"
        "• /new — Nueva conversación\n"
        "• /mode — Cambiar modo de chat\n"
        "• /image `<descripción>` — Generar imagen\n"
        "• /retry — Reintentar última respuesta\n"
        "• /balance — Ver uso de tokens\n"
        "• /settings — Configuración\n"
        "• /help — Ayuda\n\n"
        "¡Escríbeme lo que necesites! 💬",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handle(update, context)


async def new_dialog_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    db.start_new_dialog(user.id)
    mode_key = db.get_user_attribute(user.id, "current_chat_mode") or "assistant"
    mode = config.CHAT_MODES.get(mode_key, {})
    await update.message.reply_text(
        f"🔄 ¡Nueva conversación iniciada!\nModo: *{mode.get('name', 'Asistente')}* {mode.get('emoji', '')}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def settings_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    mode_key = db.get_user_attribute(user.id, "current_chat_mode") or "assistant"
    mode = config.CHAT_MODES.get(mode_key, {})
    await update.message.reply_text(
        f"⚙️ *Configuración de Mia*\n\n"
        f"🤖 Modelo: `{config.OPENAI_MODEL}`\n"
        f"💬 Modo actual: {mode.get('emoji','')} *{mode.get('name','Asistente')}*\n"
        f"🎨 Imágenes: DALL·E 3\n"
        f"🎤 Voz: Whisper API",
        parse_mode=ParseMode.MARKDOWN,
    )


async def balance_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    tokens = db.get_user_attribute(user.id, "total_tokens") or 0
    cost = round(tokens / 1000 * 0.03, 5)
    await update.message.reply_text(
        f"📊 *Tu uso con Mia*\n\n"
        f"🔢 Tokens usados: `{tokens:,}`\n"
        f"💵 Costo estimado: `${cost}`",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── Chat Modes ────────────────────────────────────────────────────────────────

async def show_chat_modes_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    await _render_modes_keyboard(update, page=0)


async def _render_modes_keyboard(update: Update, page: int):
    modes = list(config.CHAT_MODES.items())
    per_page = 6
    start, end = page * per_page, (page + 1) * per_page
    page_modes = modes[start:end]

    keyboard, row = [], []
    for mode_key, mode_val in page_modes:
        row.append(InlineKeyboardButton(
            f"{mode_val['emoji']} {mode_val['name']}",
            callback_data=f"set_mode|{mode_key}",
        ))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"mode_page|{page-1}"))
    if end < len(modes):
        nav.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"mode_page|{page+1}"))
    if nav:
        keyboard.append(nav)

    markup = InlineKeyboardMarkup(keyboard)
    text = "🎭 *Elige un modo de chat:*"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def set_chat_mode_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode_key = query.data.split("|")[1]
    db.set_user_attribute(query.from_user.id, "current_chat_mode", mode_key)
    db.start_new_dialog(query.from_user.id)
    mode = config.CHAT_MODES.get(mode_key, {})
    await query.edit_message_text(
        f"{mode.get('emoji','🤖')} Modo *{mode.get('name', mode_key)}* activado.\n\n"
        f"_{mode.get('welcome_message','¡Listo para ayudarte!')}_",
        parse_mode=ParseMode.MARKDOWN,
    )


async def mode_page_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _render_modes_keyboard(update, page=int(query.data.split("|")[1]))


# ── Image Generation ──────────────────────────────────────────────────────────

async def image_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    prompt = " ".join(context.args) if context.args else None
    if not prompt:
        await update.message.reply_text(
            "🎨 Uso: `/image <descripción>`\n\nEjemplo:\n`/image un gato astronauta en el espacio`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        image_url = await openai_helper.generate_image(prompt)
        await update.message.reply_photo(
            photo=image_url,
            caption=f"🎨 _{prompt}_",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error(f"Image error: {e}")
        await update.message.reply_text("❌ Error al generar la imagen. Intenta con otra descripción.")


# ── Voice Messages ────────────────────────────────────────────────────────────

async def voice_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    await update.effective_chat.send_action(ChatAction.TYPING)
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    voice_path = f"/tmp/mia_voice_{user.id}.ogg"
    await voice_file.download_to_drive(voice_path)
    try:
        transcript = await openai_helper.transcribe_audio(voice_path)
        if not transcript:
            await update.message.reply_text("❌ No pude entender el audio.")
            return
        await update.message.reply_text(
            f"🎤 *Escuché:* _{transcript}_",
            parse_mode=ParseMode.MARKDOWN,
        )
        update.message.text = transcript
        await message_handle(update, context)
    except Exception as e:
        logger.error(f"Voice error: {e}")
        await update.message.reply_text("❌ Error al procesar el audio.")
    finally:
        if os.path.exists(voice_path):
            os.remove(voice_path)


# ── Main Message Handler ──────────────────────────────────────────────────────

async def message_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a Mia.")
        return
    text = update.message.text
    if not text:
        return

    await update.effective_chat.send_action(ChatAction.TYPING)
    placeholder = await update.message.reply_text("⏳ Mia está pensando...")

    dialog = db.get_dialog_messages(user.id)
    mode_key = db.get_user_attribute(user.id, "current_chat_mode") or "assistant"
    system = config.CHAT_MODES.get(mode_key, {}).get(
        "prompt_start",
        "Eres Mia, una asistente de IA amigable, inteligente y útil. Responde siempre en el mismo idioma que el usuario.",
    )

    try:
        answer, n_tokens = await openai_helper.send_message(text, dialog, system)
        dialog.append({"role": "user", "content": text})
        dialog.append({"role": "assistant", "content": answer})
        db.set_dialog_messages(user.id, dialog)
        total = (db.get_user_attribute(user.id, "total_tokens") or 0) + n_tokens
        db.set_user_attribute(user.id, "total_tokens", total)
        await placeholder.edit_text(answer, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Message error: {e}")
        await placeholder.edit_text("❌ Ocurrió un error. Usa /new para iniciar una nueva conversación.")


async def retry_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    dialog = db.get_dialog_messages(user.id)
    if not dialog or dialog[-1]["role"] != "assistant":
        await update.message.reply_text("⚠️ No hay nada que reintentar.")
        return
    last_user = next((m["content"] for m in reversed(dialog) if m["role"] == "user"), None)
    if not last_user:
        return
    db.set_dialog_messages(user.id, dialog[:-2])
    update.message.text = last_user
    await message_handle(update, context)


# ── App Setup ─────────────────────────────────────────────────────────────────

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("/new",      "🔄 Nueva conversación"),
        BotCommand("/mode",     "🎭 Cambiar modo de chat"),
        BotCommand("/image",    "🎨 Generar imagen"),
        BotCommand("/retry",    "🔁 Reintentar última respuesta"),
        BotCommand("/balance",  "📊 Ver uso de tokens"),
        BotCommand("/settings", "⚙️ Ver configuración"),
        BotCommand("/help",     "❓ Ayuda"),
    ])


def run_bot():
    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start",    start_handle))
    app.add_handler(CommandHandler("help",     help_handle))
    app.add_handler(CommandHandler("new",      new_dialog_handle))
    app.add_handler(CommandHandler("mode",     show_chat_modes_handle))
    app.add_handler(CommandHandler("image",    image_handle))
    app.add_handler(CommandHandler("retry",    retry_handle))
    app.add_handler(CommandHandler("settings", settings_handle))
    app.add_handler(CommandHandler("balance",  balance_handle))
    app.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_mode"))
    app.add_handler(CallbackQueryHandler(mode_page_handle,     pattern="^mode_page"))
    app.add_handler(MessageHandler(filters.VOICE,                   voice_handle))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handle))
    logger.info("🤖 Mia Bot iniciado correctamente.")
    app.run_polling()


if __name__ == "__main__":
    run_bot()