"""
Playwright Browser & Session Manager for X (Twitter)
Handles persistent cookies, stealth configuration, human-like typing, and login automation.
"""

import os
import json
import time
import random
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

class TwitterBrowserManager:
    def __init__(self, session_dir: Optional[str] = None):
        if session_dir is None:
            self.session_dir = Path(__file__).resolve().parent.parent / "sessions"
        else:
            self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.playwright = None
        self.browser: Optional[Browser] = None

    def get_session_file(self, account_name: str) -> Path:
        sanitized = "".join(c for c in account_name if c.isalnum() or c in ("_", "-"))
        return self.session_dir / f"session_{sanitized}.json"

    def has_session(self, account_name: str) -> bool:
        session_file = self.get_session_file(account_name)
        return session_file.exists() and session_file.stat().st_size > 50

    def start(self):
        if not self.playwright:
            self.playwright = sync_playwright().start()

    def stop(self):
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    def launch_context(self, account_name: str, headless: bool = True) -> BrowserContext:
        """
        Launches an isolated browser context loaded with the account's session state.
        """
        self.start()
        session_file = self.get_session_file(account_name)
        
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1280,800",
            "--lang=tr-TR,tr,en-US,en"
        ]

        # Launch chromium
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            args=launch_args
        )

        context_options = {
            "user_agent": DEFAULT_USER_AGENT,
            "viewport": {"width": 1280, "height": 800},
            "locale": "tr-TR",
            "timezone_id": "Europe/Istanbul",
        }

        if session_file.exists():
            context_options["storage_state"] = str(session_file)

        context = self.browser.new_context(**context_options)
        
        # Inject anti-detect stealth scripts
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = {
                runtime: {}
            };
        """)

        return context

    def save_session(self, context: BrowserContext, account_name: str):
        session_file = self.get_session_file(account_name)
        context.storage_state(path=str(session_file))

    def create_session_from_cookies(self, account_name: str, auth_token: str, ct0: Optional[str] = None):
        """
        Allows instantly generating session file if user supplies auth_token from browser cookies!
        """
        cookies = [
            {
                "name": "auth_token",
                "value": auth_token.strip(),
                "domain": ".x.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
                "sameSite": "None"
            }
        ]
        if ct0:
            cookies.append({
                "name": "ct0",
                "value": ct0.strip(),
                "domain": ".x.com",
                "path": "/",
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax"
            })
            
        storage_data = {
            "cookies": cookies,
            "origins": []
        }
        session_file = self.get_session_file(account_name)
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(storage_data, f, indent=2)
        return session_file

    def interactive_login(self, account_name: str) -> bool:
        """
        Opens a visible browser for the user to log in to X manually.
        Detects when login is complete, saves session state and exits cleanly.
        """
        print(f"\n[+] {account_name} hesabı için giriş tarayıcısı açılıyor...")
        print("[!] Lütfen açılan pencerede X (Twitter) hesabınıza giriş yapın.")
        print("[!] Giriş tamamlandığında sistem bunu otomatik algılayıp çerezleri kaydedecektir.\n")
        
        self.start()
        context = self.launch_context(account_name, headless=False)
        page = context.new_page()
        
        try:
            page.goto("https://x.com/login", wait_until="domcontentloaded")
            
            # Wait up to 300 seconds (5 minutes) for user to log in
            logged_in = False
            for _ in range(150):
                time.sleep(2)
                cur_url = page.url
                if "x.com/home" in cur_url or "twitter.com/home" in cur_url:
                    logged_in = True
                    break
                # Check for home feed or compose elements
                try:
                    if page.locator("a[data-testid='AppTabBar_Home_Link']").count() > 0 or \
                       page.locator("div[data-testid='tweetTextarea_0']").count() > 0:
                        logged_in = True
                        break
                except Exception:
                    pass

            if logged_in:
                print(f"\n[✓] Giriş başarıyla tespit edildi! {account_name} oturumu kaydediliyor...")
                time.sleep(2)
                self.save_session(context, account_name)
                print(f"[✓] Oturum başarıyla kaydedildi: {self.get_session_file(account_name)}")
                return True
            else:
                print("\n[!] Giriş zaman aşımına uğradı veya tamamlanmadı.")
                return False
        finally:
            context.close()
            self.stop()
