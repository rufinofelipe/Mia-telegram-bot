from datetime import datetime
from typing import Any, Optional


class Database:
    def __init__(self):
        # Todo se guarda en memoria (se resetea si el bot se reinicia)
        self._users = {}
        self._dialogs = {}
        self._dialog_counter = 0

    # ── Users ──────────────────────────────────────────────────────────────────

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

    # ── Dialogs ────────────────────────────────────────────────────────────────

    def start_new_dialog(self, user_id: int):
        self._ensure_user(user_id)
        self._dialog_counter += 1
        dialog_id = self._dialog_counter
        self._dialogs[dialog_id] = {
            "user_id": user_id,
            "messages": [],
            "created_at": datetime.now().isoformat(),
        }
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