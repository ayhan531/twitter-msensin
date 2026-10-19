"""
Twitter Actions Executor via Playwright (No API required)
Supports Tweet, Like, Retweet, Reply, and Feed Interaction.
"""

import time
import random
from typing import Optional, Dict, Any
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

def human_delay(min_sec: float = 2.0, max_sec: float = 5.0):
    """Sleep with random jitter to simulate human interaction"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

class TwitterActions:
    def __init__(self, page: Page):
        self.page = page

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

    def post_tweet(self, text: str) -> Dict[str, Any]:
        """
        Posts a new tweet without using Twitter API.
        """
        try:
            print(f"[+] Tweet atılıyor: {text[:60]}...")
            self.page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=25000)
            human_delay(2, 4)

            # Wait for textarea
            textarea = self.page.locator("div[data-testid='tweetTextarea_0']").first
            textarea.wait_for(state="visible", timeout=15000)
            textarea.click()
            human_delay(0.5, 1.2)

            # Type text (using fill or press_sequentially for human feel)
            # For longer text, fill is faster and reliable, then trigger input
            textarea.fill(text)
            human_delay(1, 2)

            # Find Post button
            post_button = self.page.locator("button[data-testid='tweetButton']").first
            if not post_button.is_visible():
                post_button = self.page.locator("button[data-testid='tweetButtonInline']").first

            post_button.wait_for(state="visible", timeout=8000)
            
            # Check if button is enabled
            if post_button.is_disabled():
                return {"success": False, "error": "Tweet gönder butonu devre dışı (karakter sınırı veya boş metin)"}

            post_button.click()
            print("[+] Gönder butonuna tıklandı, onay bekleniyor...")
            human_delay(3, 5)

            # Check if compose modal closed or redirect occurred
            return {"success": True, "text": text}
        except PlaywrightTimeoutError:
            return {"success": False, "error": "Zaman aşımı: Tweet alanı veya butonu bulunamadı"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def like_tweet(self, tweet_url: str) -> Dict[str, Any]:
        """
        Likes a tweet given its URL.
        """
        try:
            print(f"[+] Beğeniliyor: {tweet_url}")
            self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=25000)
            human_delay(2, 4)

            # Check if already liked
            if self.page.locator("button[data-testid='unlike']").count() > 0:
                print("[i] Tweet zaten beğenilmiş.")
                return {"success": True, "already_liked": True}

            like_btn = self.page.locator("button[data-testid='like']").first
            like_btn.wait_for(state="visible", timeout=12000)
            like_btn.click()
            human_delay(1.5, 3)
            print("[✓] Tweet başarıyla beğenildi!")
            return {"success": True, "already_liked": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def retweet(self, tweet_url: str) -> Dict[str, Any]:
        """
        Retweets (reposts) a tweet given its URL.
        """
        try:
            print(f"[+] Retweet yapılıyor: {tweet_url}")
            self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=25000)
            human_delay(2, 4)

            # Check if already retweeted (unretweet button)
            if self.page.locator("button[data-testid='unretweet']").count() > 0:
                print("[i] Tweet zaten retweet edilmiş.")
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
            print("[✓] Tweet başarıyla retweet edildi!")
            return {"success": True, "already_retweeted": False}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def reply_tweet(self, tweet_url: str, reply_text: str) -> Dict[str, Any]:
        """
        Replies (comments) to a tweet given its URL.
        """
        try:
            print(f"[+] Yorum yazılıyor: {tweet_url} -> '{reply_text[:40]}...'")
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
            reply_box.click()
            human_delay(0.5, 1)
            reply_box.fill(reply_text)
            human_delay(1, 2)

            # Send reply
            send_btn = self.page.locator("button[data-testid='tweetButtonInline']").first
            if not send_btn.is_visible():
                send_btn = self.page.locator("button[data-testid='tweetButton']").first

            send_btn.wait_for(state="visible", timeout=6000)
            send_btn.click()
            human_delay(2, 4)
            print("[✓] Yorum başarıyla gönderildi!")
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
