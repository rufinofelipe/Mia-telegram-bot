import sys
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import openai
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8355097375:AAGS1RmvuDeuyIdAK9RLH8n2fGaCPmNJzD8")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "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")
OPENAI_MODEL       = os.getenv("OPENAI_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS         = int(os.getenv("MAX_TOKENS", "2000"))
TEMPERATURE        = float(os.getenv("TEMPERATURE", "0.7"))

_raw = os.getenv("ALLOWED_TELEGRAM_USERIDS", "")
ALLOWED_TELEGRAM_USERIDS = [uid.strip() for uid in _raw.split(",") if uid.strip()]

CHAT_MODES = {
    "assistant": {
        "name": "Asistente",
        "emoji": "🤖",
        "welcome_message": "¡Hola! Soy Mia, tu asistente de IA. ¿En qué puedo ayudarte?",
        "prompt_start": "Eres Mia, una asistente de IA amigable, inteligente y útil. Responde siempre en el mismo idioma que el usuario.",
    },
    "code": {
        "name": "Programadora",
        "emoji": "👩🏻‍💻",
        "welcome_message": "¡Lista para programar! Dime qué necesitas.",
        "prompt_start": "Eres Mia, una experta programadora. Ayudas con código, debugging y buenas prácticas. Responde en el idioma del usuario.",
    },
    "english_tutor": {
        "name": "Tutora de inglés",
        "emoji": "🇬🇧",
        "welcome_message": "Hello! I'm Mia, your English tutor!",
        "prompt_start": "You are Mia, an English language tutor. Help the user improve their English. If they write in Spanish, respond in both languages.",
    },
    "creative_writer": {
        "name": "Escritora creativa",
        "emoji": "✍️",
        "welcome_message": "¡Listos para crear! ¿Qué historia o texto quieres escribir?",
        "prompt_start": "Eres Mia, una escritora creativa. Ayudas a escribir historias, poemas y guiones. Responde en el idioma del usuario.",
    },
    "psychologist": {
        "name": "Psicóloga",
        "emoji": "🧠",
        "welcome_message": "Hola, estoy aquí para escucharte. ¿Cómo te sientes hoy?",
        "prompt_start": "Eres Mia, una psicóloga empática. Escuchas activamente y ofreces apoyo emocional. No das diagnósticos médicos.",
    },
    "translator": {
        "name": "Traductora",
        "emoji": "🌍",
        "welcome_message": "¡Hola! Dime qué idioma necesitas y el texto a traducir.",
        "prompt_start": "Eres Mia, una traductora profesional experta en múltiples idiomas. Traduce con precisión y naturalidad.",
    },
    "chef": {
        "name": "Chef",
        "emoji": "👨‍🍳",
        "welcome_message": "¡Bienvenido a la cocina! ¿Qué quieres cocinar hoy?",
        "prompt_start": "Eres Mia, una chef profesional. Sugieres recetas y explicas técnicas culinarias. Responde en el idioma del usuario.",
    },
}

# ── Database (en memoria) ─────────────────────────────────────────────────────

class Database:
    def __init__(self):
        self._users = {}
        self._dialogs = {}
        self._dialog_counter = 0

    def _ensure_user(self, user_id: int):
        if user_id not in self._users:
            self._users[user_id] = {
                "current_chat_mode": "assistant",
                "current_dialog_id": None,
                "total_tokens": 0,
                "last_seen": datetime.now().isoformat(),
            }

    def get_user_attribute(self, user_id: int, key: str) -> Optional[Any]:
        self._ensure_user(user_id)
        return self._users[user_id].get(key)

    def set_user_attribute(self, user_id: int, key: str, value: Any):
        self._ensure_user(user_id)
        self._users[user_id][key] = value

    def start_new_dialog(self, user_id: int):
        self._ensure_user(user_id)
        self._dialog_counter += 1
        dialog_id = self._dialog_counter
        self._dialogs[dialog_id] = {"user_id": user_id, "messages": []}
        self._users[user_id]["current_dialog_id"] = dialog_id

    def get_dialog_messages(self, user_id: int) -> list:
        self._ensure_user(user_id)
        dialog_id = self._users[user_id].get("current_dialog_id")
        if not dialog_id:
            self.start_new_dialog(user_id)
            dialog_id = self._users[user_id]["current_dialog_id"]
        return self._dialogs.get(dialog_id, {}).get("messages", [])

    def set_dialog_messages(self, user_id: int, messages: list):
        dialog_id = self._users[user_id].get("current_dialog_id")
        if dialog_id and dialog_id in self._dialogs:
            self._dialogs[dialog_id]["messages"] = messages


# ── OpenAI ────────────────────────────────────────────────────────────────────

class OpenAIHelper:
    def __init__(self):
        self.client = openai.AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
        

    async def send_message(self, message: str, dialog_messages: list, system_prompt: str) -> tuple[str, int]:
        messages = [{"role": "system", "content": system_prompt}]
        messages += dialog_messages
        messages.append({"role": "user", "content": message})
        response = await self.client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        return response.choices[0].message.content.strip(), response.usage.total_tokens

    async def generate_image(self, prompt: str) -> str:
        response = await self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url

    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        with open(audio_path, "rb") as f:
            transcript = await self.client.audio.transcriptions.create(model="whisper-1", file=f)
        return transcript.text.strip() if transcript.text else None


# ── Init ──────────────────────────────────────────────────────────────────────

db = Database()
openai_helper = OpenAIHelper()


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_allowed(user_id: int) -> bool:
    if not ALLOWED_TELEGRAM_USERIDS:
        return True
    return str(user_id) in ALLOWED_TELEGRAM_USERIDS


# ── Commands ──────────────────────────────────────────────────────────────────

async def start_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        await update.message.reply_text("⛔ No tienes acceso a Mia.")
        return
    db.set_user_attribute(user.id, "last_seen", datetime.now().isoformat())
    await update.message.reply_text(
        f"👋 ¡Hola, *{user.first_name}*! Soy *Mia*, tu asistente de IA.\n\n"
        "📌 *Comandos:*\n"
        "• /new — Nueva conversación\n"
        "• /mode — Cambiar modo de chat\n"
        "• /image `<descripción>` — Generar imagen\n"
        "• /retry — Reintentar última respuesta\n"
        "• /balance — Ver uso de tokens\n"
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
    mode = CHAT_MODES.get(mode_key, {})
    await update.message.reply_text(
        f"🔄 ¡Nueva conversación iniciada!\nModo: *{mode.get('name','Asistente')}* {mode.get('emoji','')}",
        parse_mode=ParseMode.MARKDOWN,
    )

async def balance_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    tokens = db.get_user_attribute(user.id, "total_tokens") or 0
    cost = round(tokens / 1000 * 0.03, 5)
    await update.message.reply_text(
        f"📊 *Tu uso con Mia*\n\n🔢 Tokens: `{tokens:,}`\n💵 Costo estimado: `${cost}`",
        parse_mode=ParseMode.MARKDOWN,
    )

async def show_chat_modes_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    await _render_modes_keyboard(update, page=0)

async def _render_modes_keyboard(update: Update, page: int):
    modes = list(CHAT_MODES.items())
    per_page = 6
    start, end = page * per_page, (page + 1) * per_page
    keyboard, row = [], []
    for mode_key, mode_val in modes[start:end]:
        row.append(InlineKeyboardButton(f"{mode_val['emoji']} {mode_val['name']}", callback_data=f"set_mode|{mode_key}"))
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
    mode = CHAT_MODES.get(mode_key, {})
    await query.edit_message_text(
        f"{mode.get('emoji','🤖')} Modo *{mode.get('name', mode_key)}* activado.\n\n_{mode.get('welcome_message','')}_",
        parse_mode=ParseMode.MARKDOWN,
    )

async def mode_page_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _render_modes_keyboard(update, page=int(query.data.split("|")[1]))

async def image_handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id):
        return
    prompt = " ".join(context.args) if context.args else None
    if not prompt:
        await update.message.reply_text("🎨 Uso: `/image <descripción>`", parse_mode=ParseMode.MARKDOWN)
        return
    await update.effective_chat.send_action(ChatAction.UPLOAD_PHOTO)
    try:
        image_url = await openai_helper.generate_image(prompt)
        await update.message.reply_photo(photo=image_url, caption=f"🎨 _{prompt}_", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Image error: {e}")
        await update.message.reply_text("❌ Error al generar la imagen.")

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
        await update.message.reply_text(f"🎤 *Escuché:* _{transcript}_", parse_mode=ParseMode.MARKDOWN)
        update.message.text = transcript
        await message_handle(update, context)
    except Exception as e:
        logger.error(f"Voice error: {e}")
        await update.message.reply_text("❌ Error al procesar el audio.")
    finally:
        if os.path.exists(voice_path):
            os.remove(voice_path)

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
    system = CHAT_MODES.get(mode_key, {}).get("prompt_start", "Eres Mia, una asistente de IA útil.")
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
        await placeholder.edit_text("❌ Ocurrió un error. Usa /new para reiniciar.")

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

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("/new",     "🔄 Nueva conversación"),
        BotCommand("/mode",    "🎭 Cambiar modo de chat"),
        BotCommand("/image",   "🎨 Generar imagen"),
        BotCommand("/retry",   "🔁 Reintentar última respuesta"),
        BotCommand("/balance", "📊 Ver uso de tokens"),
        BotCommand("/help",    "❓ Ayuda"),
    ])

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start",   start_handle))
    app.add_handler(CommandHandler("help",    help_handle))
    app.add_handler(CommandHandler("new",     new_dialog_handle))
    app.add_handler(CommandHandler("mode",    show_chat_modes_handle))
    app.add_handler(CommandHandler("image",   image_handle))
    app.add_handler(CommandHandler("retry",   retry_handle))
    app.add_handler(CommandHandler("balance", balance_handle))
    app.add_handler(CallbackQueryHandler(set_chat_mode_handle, pattern="^set_mode"))
    app.add_handler(CallbackQueryHandler(mode_page_handle,     pattern="^mode_page"))
    app.add_handler(MessageHandler(filters.VOICE,                   voice_handle))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handle))
    logger.info("🤖 Mia Bot iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        def log_message(self, format, *args):
            pass

    def start_health_server():
        server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
        server.serve_forever()

    threading.Thread(target=start_health_server, daemon=True).start()
    run_bot()
