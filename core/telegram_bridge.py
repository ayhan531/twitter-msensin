"""
Telegram to X (Twitter) Bridge with Smart 5-Minute Batching Window
Aggregates messages and media sent within 5 minutes into a single tweet/thread,
downloads media, posts via Twitter Playwright automation, and cross-boosts with helper accounts.
"""

import os
import sys
import time
import json
import threading
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

TELEGRAM_MEDIA_DIR = ROOT_DIR / "web" / "static" / "telegram_media"
TELEGRAM_MEDIA_DIR.mkdir(parents=True, exist_ok=True)


class TelegramMessageBatch:
    def __init__(self, start_time: float):
        self.start_time = start_time
        self.last_msg_time = start_time
        self.items: List[Dict[str, Any]] = []  # [{text, media_path, date, msg_id}]

    def add(self, text: str, media_path: Optional[str] = None, msg_id: int = 0, date: float = 0):
        self.last_msg_time = time.time()
        self.items.append({
            "text": text.strip(),
            "media_path": media_path,
            "msg_id": msg_id,
            "date": date or self.last_msg_time
        })

    def is_expired(self, window_seconds: int = 300) -> bool:
        """Returns True if window_seconds has passed since the LAST message was added"""
        return (time.time() - self.last_msg_time) >= window_seconds

    def get_combined_text(self) -> str:
        texts = [item["text"] for item in self.items if item.get("text")]
        # Deduplicate identical consecutive texts if any
        clean_texts = []
        for t in texts:
            if not clean_texts or clean_texts[-1] != t:
                clean_texts.append(t)
        return "\n\n".join(clean_texts).strip()

    def get_media_paths(self) -> List[str]:
        return [item["media_path"] for item in self.items if item.get("media_path") and os.path.exists(item["media_path"])]


class TelegramBridgeManager:
    def __init__(self, browser_mgr, ai_gen, get_config_fn, save_config_fn, log_event_fn):
        self.browser_mgr = browser_mgr
        self.ai_gen = ai_gen
        self.get_config = get_config_fn
        self.save_config = save_config_fn
        self.log_event = log_event_fn

        self.current_batch: Optional[TelegramMessageBatch] = None
        self.running = False
        self.worker_thread = None
        self.lock = threading.Lock()

    def get_telegram_config(self) -> dict:
        cfg = self.get_config()
        return cfg.get("telegram", {
            "enabled": False,
            "bot_token": "",
            "channel_id": "",
            "batch_window_seconds": 300,  # 5 minutes
            "last_update_id": 0,
            "auto_boost": True,
            "account": "Borsagenci"
        })

    def save_telegram_config(self, tg_cfg: dict):
        cfg = self.get_config()
        cfg["telegram"] = tg_cfg
        self.save_config(cfg)

    def download_telegram_file(self, bot_token: str, file_id: str, prefix: str = "tg") -> Optional[str]:
        """Downloads a photo or file from Telegram Bot API and returns the local file path"""
        try:
            get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
            res = requests.get(get_file_url, timeout=15)
            if res.status_code == 200:
                file_path = res.json().get("result", {}).get("file_path")
                if file_path:
                    ext = os.path.splitext(file_path)[1] or ".jpg"
                    local_filename = f"{prefix}_{int(time.time())}_{file_id[:8]}{ext}"
                    local_dest = TELEGRAM_MEDIA_DIR / local_filename

                    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                    img_data = requests.get(download_url, timeout=25)
                    if img_data.status_code == 200:
                        with open(local_dest, "wb") as f:
                            f.write(img_data.content)
                        return str(local_dest)
        except Exception as e:
            self.log_event(f"Telegram görsel indirme hatası: {e}", "warning")
        return None

    def fetch_new_messages(self) -> List[Dict[str, Any]]:
        """Polls Telegram for new channel updates"""
        tg_cfg = self.get_telegram_config()
        bot_token = tg_cfg.get("bot_token", "").strip()
        last_id = tg_cfg.get("last_update_id", 0)

        if not bot_token:
            return []

        url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={last_id + 1}&timeout=10"
        try:
            res = requests.get(url, timeout=15)
            if res.status_code != 200:
                return []
            
            updates = res.json().get("result", [])
            messages_found = []

            for upd in updates:
                upd_id = upd.get("update_id", 0)
                if upd_id > last_id:
                    last_id = upd_id

                # Telegram channels use 'channel_post', regular chats use 'message'
                msg = upd.get("channel_post") or upd.get("message")
                if not msg:
                    continue

                # Filter by channel_id if specified
                target_chan = str(tg_cfg.get("channel_id", "")).strip().lstrip("@")
                if target_chan:
                    chat_info = msg.get("chat", {})
                    chat_username = str(chat_info.get("username", "")).lstrip("@")
                    chat_id = str(chat_info.get("id", ""))
                    if target_chan not in [chat_username, chat_id]:
                        continue

                text = msg.get("text") or msg.get("caption") or ""
                photo_path = None

                # Extract photo if present (Telegram provides multiple sizes, largest is last)
                photos = msg.get("photo", [])
                if photos:
                    largest_photo = photos[-1]
                    photo_path = self.download_telegram_file(bot_token, largest_photo.get("file_id"), f"tg_{upd_id}")

                messages_found.append({
                    "update_id": upd_id,
                    "msg_id": msg.get("message_id", 0),
                    "date": msg.get("date", time.time()),
                    "text": text,
                    "media_path": photo_path
                })

            if last_id > tg_cfg.get("last_update_id", 0):
                tg_cfg["last_update_id"] = last_id
                self.save_telegram_config(tg_cfg)

            return messages_found
        except Exception as e:
            return []

    def flush_batch_to_twitter(self, batch: TelegramMessageBatch, reason: str = "5 Dakika Doldu") -> bool:
        """Publishes the collected batch to X (Twitter) as a single tweet or thread"""
        combined_text = batch.get_combined_text()
        media_paths = batch.get_media_paths()

        if not combined_text and not media_paths:
            return False

        tg_cfg = self.get_telegram_config()
        cfg = self.get_config()
        accounts = cfg.get("accounts", [])
        
        target_account = tg_cfg.get("account") or next((a.get("username") for a in accounts if a.get("role") == "analyst"), "Borsagenci")
        helpers = [a.get("username") for a in accounts if a.get("username") != target_account and self.browser_mgr.has_session(a.get("username"))]

        self.log_event(f"📨 [Telegram Köprüsü] {len(batch.items)} mesaj birleştirildi ({reason}). @{target_account} üzerinden tweet atılıyor...", "info")

        # Primary media to attach (first downloaded photo in the batch)
        primary_media = media_paths[0] if media_paths else None

        # Check length & split into Thread if text > 280 chars
        tweets_to_send = []
        if len(combined_text) <= 280:
            tweets_to_send = [combined_text]
        else:
            # Smart chunking into thread
            words = combined_text.split(" ")
            curr_chunk = ""
            for word in words:
                if len(curr_chunk) + len(word) + 1 <= 270:
                    curr_chunk += (" " if curr_chunk else "") + word
                else:
                    tweets_to_send.append(curr_chunk)
                    curr_chunk = word
            if curr_chunk:
                tweets_to_send.append(curr_chunk)

        # Send via TwitterActions / EngagementPod
        from core.twitter_actions import TwitterActions
        from core.engagement_pod import EngagementPodManager

        try:
            ctx = self.browser_mgr.launch_context(target_account, headless=True)
            page = ctx.new_page()
            actions = TwitterActions(page)

            # Post Main Tweet
            first_tweet_text = tweets_to_send[0] if tweets_to_send else combined_text
            res = actions.post_tweet(first_tweet_text, media_path=primary_media)

            if res.get("success"):
                tweet_url = res.get("tweet_url") or f"https://x.com/{target_account}"
                self.log_event(f"✅ [Telegram -> 𝕏] Tweet başarıyla paylaşıldı: {first_tweet_text[:60]}...", "success")

                # If there are thread replies, post them sequentially
                if len(tweets_to_send) > 1 and tweet_url:
                    for reply_text in tweets_to_send[1:]:
                        time.sleep(3)
                        actions.post_comment(tweet_url, reply_text)

                ctx.close()

                # Cross-boost if enabled
                if tg_cfg.get("auto_boost", True) and helpers and tweet_url:
                    pod_mgr = EngagementPodManager(self.browser_mgr, self.ai_gen)
                    pod_mgr.boost_tweet(tweet_url, helpers, exclude_account=target_account, headless=True)

                return True
            else:
                ctx.close()
                self.log_event(f"❌ [Telegram -> 𝕏] Tweet atılamadı: {res.get('error')}", "error")
                return False
        except Exception as e:
            self.log_event(f"Telegram köprü paylaşım hatası: {e}", "error")
            return False

    def bridge_loop(self):
        """Background daemon polling Telegram and flushing 5-minute batches"""
        self.log_event("📡 Telegram -> 𝕏 Köprüsü arka plan dinleyicisi başlatıldı.", "success")
        while self.running:
            try:
                tg_cfg = self.get_telegram_config()
                if not tg_cfg.get("enabled", False):
                    time.sleep(10)
                    continue

                window_secs = int(tg_cfg.get("batch_window_seconds", 300))  # Default 5 min

                # 1. Fetch new messages from Telegram
                new_msgs = self.fetch_new_messages()
                if new_msgs:
                    with self.lock:
                        for m in new_msgs:
                            if not self.current_batch:
                                self.current_batch = TelegramMessageBatch(start_time=time.time())
                            self.current_batch.add(
                                text=m.get("text", ""),
                                media_path=m.get("media_path"),
                                msg_id=m.get("msg_id", 0),
                                date=m.get("date", time.time())
                            )
                            self.log_event(f"📥 Telegram'dan yeni mesaj alındı (5 dk havuzuna eklendi: '{m.get('text', '')[:40]}...')", "info")

                # 2. Check if active batch has reached the 5-minute inactivity threshold
                with self.lock:
                    if self.current_batch and self.current_batch.items:
                        if self.current_batch.is_expired(window_secs):
                            batch_to_flush = self.current_batch
                            self.current_batch = None
                            # Flush in worker
                            self.flush_batch_to_twitter(batch_to_flush, reason="5 Dakikalık Süre Doldu")

                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                self.log_event(f"Telegram köprü döngü hatası: {e}", "error")
                time.sleep(20)

    def start(self):
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self.bridge_loop, daemon=True)
            self.worker_thread.start()

    def stop(self):
        self.running = False

    def force_flush_now(self) -> dict:
        """Manually flush the pending batch immediately"""
        with self.lock:
            if not self.current_batch or not self.current_batch.items:
                return {"success": False, "error": "Bekleyen Telegram mesaj havuzu boş."}
            batch_to_flush = self.current_batch
            self.current_batch = None

        success = self.flush_batch_to_twitter(batch_to_flush, reason="Manuel Hemen Gönder")
        return {"success": success, "message": "Havuzdaki mesajlar hemen tweetlendi!" if success else "Tweetleme başarısız"}
