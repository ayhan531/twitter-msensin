"""
Twitter Actions Executor via Playwright (No API required)
Supports Tweet, Like, Retweet, Reply, and Feed Interaction.
"""

import os
import time
import random
from typing import Optional, Dict, Any
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

def safe_print(msg: str):
    """Safely prints message avoiding unicode terminal crashes"""
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode("ascii", errors="replace").decode("ascii"))
        except Exception:
            pass

def human_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Sleep with random jitter to simulate human interaction"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

def human_type(page: Page, locator, text: str):
    """Types text with natural human speed and micro-pauses to prevent bot detection"""
    locator.click()
    human_delay(0.4, 0.8)
    
    # Fast natural typing in word chunks or characters
    words = text.split(" ")
    for idx, word in enumerate(words):
        # Type word
        locator.press_sequentially(word + " ", delay=random.randint(25, 65))
        # Occasional micro-pause between sentences or long words
        if idx % random.randint(4, 7) == 0:
            time.sleep(random.uniform(0.15, 0.35))

class TwitterActions:
    def __init__(self, page: Page):
        self.page = page

    def warmup_browse(self, duration_sec: float = 5.0):
        """
        Simulates natural human timeline browsing to bypass X anti-bot telemetry.
        Scrolls feed, hovers on content, generates genuine mouse events.
        """
        try:
            scrolls = random.randint(2, 4)
            for _ in range(scrolls):
                scroll_y = random.randint(250, 600)
                self.page.mouse.wheel(0, scroll_y)
                time.sleep(random.uniform(1.2, 2.5))
                # Slight scroll up mimicking reading
                if random.random() < 0.4:
                    self.page.mouse.wheel(0, -random.randint(100, 200))
                    time.sleep(random.uniform(0.8, 1.5))
        except Exception:
            pass

    def is_logged_in(self) -> bool:
        """Check if current page is logged into X"""
        try:
            self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
            human_delay(2, 4)
            if "login" in self.page.url:
                return False
            # Check for home feed or sidebar
            if self.page.locator("a[data-testid='AppTabBar_Home_Link']").count() > 0 or \
               self.page.locator("div[data-testid='tweetTextarea_0']").count() > 0 or \
               self.page.locator("a[data-testid='AppTabBar_Profile_Link']").count() > 0:
                return True
        except Exception:
            pass
        return False

    def post_tweet(self, text: str, media_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Posts a new tweet with optional image/chart attachment without using Twitter API.
        """
        try:
            print(f"[+] Tweet hazırlanıyor: {text[:60]}...")
            self.page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
            human_delay(1.5, 3)
            # Anti-bot warm-up browse
            self.warmup_browse(3.0)

            # Find visible compose textarea on home feed or compose modal
            textarea = self.page.locator("div[data-testid='tweetTextarea_0']:visible").first
            if textarea.count() == 0:
                textarea = self.page.locator("div[role='textbox']:visible").first

            if textarea.count() == 0:
                # Try opening compose post modal
                self.page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=20000)
                human_delay(1.5, 3)
                textarea = self.page.locator("div[data-testid='tweetTextarea_0']:visible").first
                if textarea.count() == 0:
                    textarea = self.page.locator("div[role='textbox']:visible").first

            if textarea.count() == 0:
                return {"success": False, "error": "Tweet metin yazma alanı bulunamadı"}

            # Type text like a real human with natural keystroke timing
            human_type(self.page, textarea, text)
            human_delay(1, 2)

            # Attach media if provided (e.g. chart image)
            if media_path and os.path.exists(media_path):
                print(f"[+] Fotoğraf/Grafik ekleniyor: {media_path}")
                file_input = self.page.locator("input[data-testid='fileInput']").first
                if file_input.count() == 0:
                    file_input = self.page.locator("input[type='file']").first
                
                if file_input.count() > 0:
                    file_input.set_input_files(media_path)
                    print("[+] Fotoğraf yüklendi, önizleme bekleniyor...")
                    human_delay(3, 5)
                else:
                    print("[!] Dosya yükleme inputu bulunamadı, metin olarak devam ediliyor.")

            # Find visible Post button
            post_button = self.page.locator("button[data-testid='tweetButtonInline']:visible").first
            if post_button.count() == 0 or not post_button.is_visible():
                post_button = self.page.locator("button[data-testid='tweetButton']:visible").first

            post_button.wait_for(state="visible", timeout=10000)
            
            # Check if button is enabled
            if post_button.is_disabled():
                return {"success": False, "error": "Tweet gönder butonu devre dışı (karakter sınırı veya boş metin)"}

            post_button.click()
            safe_print("[OK] Gonder butonuna tiklandi, tweet basariyla paylasildi!")
            human_delay(3, 6)

            return {"success": True, "text": text, "has_media": bool(media_path)}
        except PlaywrightTimeoutError:
            return {"success": False, "error": "Zaman aşımı: Tweet alanı veya butonu bulunamadı"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def like_tweet(self, tweet_url: str) -> Dict[str, Any]:
        """
        Likes a tweet given its URL.
        """
        try:
            safe_print(f"[+] Begeniliyor: {tweet_url}")
            self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=25000)
            human_delay(2, 4)

            # Check if already liked
            if self.page.locator("button[data-testid='unlike']").count() > 0:
                safe_print("[i] Tweet zaten begenilmis.")
                return {"success": True, "already_liked": True}

            like_btn = self.page.locator("button[data-testid='like']").first
            like_btn.wait_for(state="visible", timeout=12000)
            like_btn.click()
            human_delay(1.5, 3)
            safe_print("[OK] Tweet basariyla begenildi!")
            return {"success": True, "already_liked": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def retweet(self, tweet_url: str) -> Dict[str, Any]:
        """
        Retweets (reposts) a tweet given its URL.
        """
        try:
            safe_print(f"[+] Retweet yapiliyor: {tweet_url}")
            self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=25000)
            human_delay(2, 4)

            # Check if already retweeted (unretweet button)
            if self.page.locator("button[data-testid='unretweet']").count() > 0:
                safe_print("[i] Tweet zaten retweet edilmis.")
                return {"success": True, "already_retweeted": True}

            retweet_btn = self.page.locator("button[data-testid='retweet']").first
            retweet_btn.wait_for(state="visible", timeout=12000)
            retweet_btn.click()
            human_delay(1, 2)

            # Confirm retweet popup menu
            confirm_btn = self.page.locator("div[data-testid='retweetConfirm']").first
            confirm_btn.wait_for(state="visible", timeout=6000)
            confirm_btn.click()
            human_delay(1.5, 3)
            safe_print("[OK] Tweet basariyla retweet edildi!")
            return {"success": True, "already_retweeted": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reply_tweet(self, tweet_url: str, reply_text: str) -> Dict[str, Any]:
        """
        Replies (comments) to a tweet given its URL.
        """
        try:
            safe_print(f"[+] Yorum yaziliyor: {tweet_url} -> '{reply_text[:40]}...'")
            self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=25000)
            human_delay(2, 4)

            reply_box = self.page.locator("div[data-testid='tweetTextarea_0']").first
            if not reply_box.is_visible():
                # Click reply icon if inline textarea isn't open
                reply_btn = self.page.locator("button[data-testid='reply']").first
                if reply_btn.is_visible():
                    reply_btn.click()
                    human_delay(1, 2)
                    reply_box = self.page.locator("div[data-testid='tweetTextarea_0']").first

            reply_box.wait_for(state="visible", timeout=12000)
            human_type(self.page, reply_box, reply_text)
            human_delay(1, 2)

            # Send reply
            send_btn = self.page.locator("button[data-testid='tweetButtonInline']").first
            if not send_btn.is_visible():
                send_btn = self.page.locator("button[data-testid='tweetButton']").first

            send_btn.wait_for(state="visible", timeout=6000)
            send_btn.click()
            human_delay(2, 4)
            safe_print("[OK] Yorum basariyla gonderildi!")
            return {"success": True, "reply_text": reply_text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_latest_tweet_url_of_user(self, username: str) -> Optional[str]:
        """
        Navigates to user profile and grabs the URL of their most recent tweet.
        """
        clean_user = username.lstrip("@")
        profile_url = f"https://x.com/{clean_user}"
        try:
            self.page.goto(profile_url, wait_until="domcontentloaded", timeout=25000)
            human_delay(2, 4)

            # Select first tweet link in timeline
            tweet_links = self.page.locator("article[data-testid='tweet'] a[href*='/status/']").all()
            for link in tweet_links:
                href = link.get_attribute("href")
                if href and f"/{clean_user}/status/" in href and not "/analytics" in href and not "/photo/" in href:
                    full_url = f"https://x.com{href}" if href.startswith("/") else href
                    return full_url
        except Exception:
            pass
        return None
