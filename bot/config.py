import os
import yaml

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_TOKENS   = int(os.getenv("MAX_TOKENS", "2000"))
TEMPERATURE  = float(os.getenv("TEMPERATURE", "0.7"))

_raw = os.getenv("ALLOWED_TELEGRAM_USERIDS", "")
ALLOWED_TELEGRAM_USERIDS = [uid.strip() for uid in _raw.split(",") if uid.strip()]

_modes_path = os.path.join(os.path.dirname(__file__), "..", "config", "chat_modes.yml")
with open(_modes_path, "r", encoding="utf-8") as f:
    CHAT_MODES: dict = yaml.safe_load(f)