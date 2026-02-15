from datetime import datetime
from typing import Any, Optional
import pymongo
import config


class Database:
    def __init__(self):
        self.client = pymongo.MongoClient(config.MONGODB_URI)
        self.db = self.client["mia_bot"]
        self.users = self.db["users"]
        self.dialogs = self.db["dialogs"]

    def _ensure_user(self, user_id: int):
        if not self.users.find_one({"_id": user_id}):
            self.users.insert_one({
                "_id": user_id,
                "current_chat_mode": "assistant",
                "current_dialog_id": None,
                "total_tokens": 0,
                "last_seen": datetime.now().isoformat(),
            })

    def get_user_attribute(self, user_id: int, key: str) -> Optional[Any]:
        self._ensure_user(user_id)
        user = self.users.find_one({"_id": user_id})
        return user.get(key) if user else None

    def set_user_attribute(self, user_id: int, key: str, value: Any):
        self._ensure_user(user_id)
        self.users.update_one({"_id": user_id}, {"$set": {key: value}})

    def start_new_dialog(self, user_id: int):
        self._ensure_user(user_id)
        dialog = self.dialogs.insert_one({
            "user_id": user_id,
            "messages": [],
            "created_at": datetime.now().isoformat(),
        })
        self.users.update_one(
            {"_id": user_id},
            {"$set": {"current_dialog_id": dialog.inserted_id}},
        )

    def get_dialog_messages(self, user_id: int) -> list:
        self._ensure_user(user_id)
        dialog_id = self.get_user_attribute(user_id, "current_dialog_id")
        if not dialog_id:
            self.start_new_dialog(user_id)
            dialog_id = self.get_user_attribute(user_id, "current_dialog_id")
        dialog = self.dialogs.find_one({"_id": dialog_id})
        return dialog["messages"] if dialog else []

    def set_dialog_messages(self, user_id: int, messages: list):
        dialog_id = self.get_user_attribute(user_id, "current_dialog_id")
        if dialog_id:
            self.dialogs.update_one(
                {"_id": dialog_id},
                {"$set": {"messages": messages}}
            )