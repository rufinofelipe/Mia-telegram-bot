import os
import yaml

TELEGRAM_BOT_TOKEN = os.getenv("8355097375:AAGS1RmvuDeuyIdAK9RLH8n2fGaCPmNJzD8", "")
OPENAI_API_KEY     = os.getenv("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", "")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_TOKENS   = int(os.getenv("MAX_TOKENS", "2000"))
TEMPERATURE  = float(os.getenv("TEMPERATURE", "0.7"))

_raw = os.getenv("ALLOWED_TELEGRAM_USERIDS", "")
ALLOWED_TELEGRAM_USERIDS = [uid.strip() for uid in _raw.split(",") if uid.strip()]

_modes_path = os.path.join(os.path.dirname(__file__), "..", "config", "chat_modes.yml")
with open(_modes_path, "r", encoding="utf-8") as f:
    CHAT_MODES: dict = yaml.safe_load(f)