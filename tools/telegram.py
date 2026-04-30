from dataclasses import dataclass
import json
from typing import Iterable
from urllib import parse, request

from pipeline.schemas import ApprovalItem


@dataclass
class TelegramClient:
    bot_token: str
    chat_id: str

    def send_approval_bundle(self, run_id: str, items: Iterable[ApprovalItem], dry_run: bool = False) -> None:
        items = list(items)
        summary = f"Run {run_id} generated {len(items)} approval candidates."
        self._send_text(summary, dry_run=dry_run)
        for item in items:
            body = (
                f"{item.title}\n"
                f"clip_id={item.clip_id}\n"
                f"video={item.video_path}\n"
                f"caption={item.caption_suggestion}\n"
                f"metadata={item.metadata}\n"
                "Reply with: approve <clip_id> | reject <clip_id> | revise <clip_id>"
            )
            self._send_text(body, dry_run=dry_run)

    def parse_callback(self, message_text: str) -> tuple:
        parts = message_text.strip().split()
        if len(parts) != 2:
            raise ValueError("Expected '<decision> <clip_id>' format.")
        decision, clip_id = parts
        decision = decision.lower()
        if decision not in ("approve", "reject", "revise"):
            raise ValueError("Decision must be one of: approve, reject, revise")
        return decision, clip_id

    def _send_text(self, text: str, dry_run: bool) -> None:
        if dry_run or not self.bot_token or not self.chat_id:
            return
        endpoint = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = parse.urlencode({"chat_id": self.chat_id, "text": text}).encode()
        req = request.Request(endpoint, data=data, method="POST")
        with request.urlopen(req) as response:
            payload = json.loads(response.read().decode())
            if not payload.get("ok", False):
                raise RuntimeError(f"Telegram API error: {payload}")

