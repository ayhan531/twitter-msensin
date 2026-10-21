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

def get_default_session_dir() -> Path:
    """Detects persistent disk mount paths on Render or returns local sessions dir"""
    for p in ["/var/data", "/data", os.getenv("RENDER_DISK_PATH", "")]:
        if p and os.path.exists(p) and os.path.isdir(p):
            p_dir = Path(p) / "x_bist_bot" / "sessions"
            p_dir.mkdir(parents=True, exist_ok=True)
            return p_dir
    return Path(__file__).resolve().parent.parent / "sessions"

class TwitterBrowserManager:
    def __init__(self, session_dir: Optional[str] = None):
        if session_dir is None:
            self.session_dir = get_default_session_dir()
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

        # Check for proxy (env or config)
        proxy_url = os.getenv("PROXY_URL") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
        launch_kwargs = {
            "headless": headless,
            "args": launch_args
        }
        if proxy_url:
            launch_kwargs["proxy"] = {"server": proxy_url}

        # Launch chromium
        self.browser = self.playwright.chromium.launch(**launch_kwargs)

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

    def save_session(self, context: BrowserContext, account_name: str) -> Dict[str, str]:
        """Saves full browser storage state and extracts latest auth_token/ct0"""
        session_file = self.get_session_file(account_name)
        context.storage_state(path=str(session_file))
        
        # Extract latest tokens from storage state
        latest_tokens = {"auth_token": "", "ct0": ""}
        try:
            cookies = context.cookies()
            for c in cookies:
                if c.get("name") == "auth_token" and c.get("value"):
                    latest_tokens["auth_token"] = c["value"]
                elif c.get("name") == "ct0" and c.get("value"):
                    latest_tokens["ct0"] = c["value"]
        except Exception:
            pass
        return latest_tokens

    def create_session_from_cookies(self, account_name: str, auth_token: str, ct0: Optional[str] = None):
        """
        Generates a robust, multi-domain session file compatible with both .x.com and .twitter.com.
        Includes essential security cookies to prevent session invalidation by Twitter.
        """
        token = auth_token.strip()
        csrf = ct0.strip() if ct0 else ""
        far_future_expiry = int(time.time()) + 315360000  # ~10 years
        
        # Domains Twitter expects
        domains = [".x.com", ".twitter.com"]
        cookies = []

        for d in domains:
            # Main Auth Token
            cookies.append({
                "name": "auth_token",
                "value": token,
                "domain": d,
                "path": "/",
                "expires": far_future_expiry,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None"
            })
            # CSRF Token
            if csrf:
                cookies.append({
                    "name": "ct0",
                    "value": csrf,
                    "domain": d,
                    "path": "/",
                    "expires": far_future_expiry,
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax"
                })
            # Essential Anti-Bot Fingerprint Cookies
            cookies.append({
                "name": "night_mode",
                "value": "2",
                "domain": d,
                "path": "/",
                "expires": far_future_expiry,
                "httpOnly": False,
                "secure": False,
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

    def verify_and_refresh_session(self, account_name: str) -> Dict[str, Any]:
        """
        Validates whether the session for account_name is active on X (Twitter).
        Refreshes ct0 token if rotated and updates stored session state.
        Returns:
            {"valid": bool, "username": str, "auth_token": str, "ct0": str, "error": Optional[str]}
        """
        self.start()
        clean_name = account_name.strip().lstrip("@")
        context = self.launch_context(clean_name, headless=True)
        try:
            page = context.new_page()
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=35000)
            time.sleep(3)
            cur_url = page.url
            
            # Check if redirected to login
            if "login" in cur_url or "i/flow" in cur_url:
                return {
                    "valid": False, 
                    "username": clean_name, 
                    "error": "Oturum zaman aşımına uğramış veya geçersiz (Login sayfasına yönlendirildi)"
                }
            
            # Check if home feed or nav elements are visible
            logged_in = False
            if "x.com/home" in cur_url or "twitter.com/home" in cur_url:
                logged_in = True
            elif page.locator("a[data-testid='AppTabBar_Home_Link'], div[data-testid='tweetTextarea_0']").count() > 0:
                logged_in = True

            if not logged_in:
                return {"valid": False, "username": clean_name, "error": f"Bilinmeyen sayfa durumu: {cur_url}"}

            # Save updated storage state with new ct0
            latest = self.save_session(context, clean_name)
            return {
                "valid": True,
                "username": clean_name,
                "auth_token": latest.get("auth_token", ""),
                "ct0": latest.get("ct0", ""),
                "message": f"@{clean_name} oturumu aktif ve doğrulandı."
            }
        except Exception as e:
            return {"valid": False, "username": clean_name, "error": str(e)}
        finally:
            try:
                context.close()
            except Exception:
                pass
            self.stop()

    def interactive_login(self, account_name: str = "") -> Dict[str, Any]:
        """
        Opens a visible browser for the user to log in to X manually.
        Detects when login is complete, auto-detects username if omitted,
        saves session state, extracts auth_token/ct0, and exits cleanly.
        """
        display_name = account_name if account_name else "Yeni Hesap"
        print(f"\n[+] {display_name} için etkileşimli giriş tarayıcısı açılıyor...")
        print("[!] Lütfen açılan pencerede X (Twitter) hesabınıza normal şekilde giriş yapın.")
        print("[!] Giriş tamamlandığında sistem bunu otomatik algılayıp oturumu kaydedecektir.\n")
        
        self.start()
        # Use a temporary context name if none given
        temp_id = account_name or f"temp_login_{int(time.time())}"
        context = self.launch_context(temp_id, headless=False)
        page = context.new_page()
        
        try:
            page.goto("https://x.com/login", wait_until="domcontentloaded")
            
            # Wait up to 300 seconds (5 minutes) for user to log in
            logged_in = False
            detected_uname = account_name.strip().lstrip("@") if account_name else ""

            for _ in range(150):
                time.sleep(2)
                cur_url = page.url
                
                # Check URL for home or profile
                if any(x in cur_url for x in ["x.com/home", "twitter.com/home", "x.com/i/flow/"]):
                    if "x.com/home" in cur_url or "twitter.com/home" in cur_url:
                        logged_in = True
                        break

                # Check for home feed or compose elements
                try:
                    if page.locator("a[data-testid='AppTabBar_Home_Link']").count() > 0 or \
                       page.locator("div[data-testid='tweetTextarea_0']").count() > 0 or \
                       page.locator("a[data-testid='AppTabBar_Profile_Link']").count() > 0:
                        logged_in = True
                        break
                except Exception:
                    pass

            if logged_in:
                # Give 2 seconds for cookies to settle
                time.sleep(2)

                # Try to auto-detect username from profile link if not provided
                if not detected_uname:
                    try:
                        profile_link = page.locator("a[data-testid='AppTabBar_Profile_Link']").first
                        if profile_link.count() > 0:
                            href = profile_link.get_attribute("href")
                            if href:
                                detected_uname = href.strip("/").split("/")[0]
                    except Exception:
                        pass

                # If still empty, try to check cookies for twid
                cookies = context.cookies()
                auth_token = next((c["value"] for c in cookies if c["name"] == "auth_token"), "")
                ct0 = next((c["value"] for c in cookies if c["name"] == "ct0"), "")

                if not detected_uname:
                    detected_uname = f"x_user_{int(time.time()) % 10000}"

                print(f"\n[✓] Giriş başarıyla tespit edildi! @{detected_uname} oturumu kaydediliyor...")
                self.save_session(context, detected_uname)
                print(f"[✓] Oturum başarıyla kaydedildi: {self.get_session_file(detected_uname)}")

                return {
                    "success": True,
                    "username": detected_uname,
                    "auth_token": auth_token,
                    "ct0": ct0,
                    "message": f"@{detected_uname} hesabı başarıyla bağlandı!"
                }
            else:
                print("\n[!] Giriş zaman aşımına uğradı veya tamamlanmadı.")
                return {
                    "success": False,
                    "error": "Giriş zaman aşımına uğradı (5 dakika içinde tamamlanmadı)."
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            try:
                context.close()
            except Exception:
                pass
            self.stop()

    def automated_login(self, username_or_email: str, password: str, verify_credential: Optional[str] = None, headless: bool = True) -> Dict[str, Any]:
        """
        Fully automated headless / headed login with username/email and password.
        Handles verification challenges (e.g. entering username when email was used).
        """
        self.start()
        uname_clean = username_or_email.strip().lstrip("@")
        context = self.launch_context(uname_clean, headless=headless)
        page = context.new_page()

        try:
            print(f"[+] @{uname_clean} için otomatik giriş başlatılıyor...")
            page.goto("https://x.com/i/flow/login", wait_until="domcontentloaded")
            time.sleep(3)

            # Step 1: Username / Email
            username_input = page.locator("input[autocomplete='username'], input[name='text']").first
            username_input.wait_for(timeout=15000)
            username_input.fill(username_or_email)
            time.sleep(1)

            # Click Next or press Enter
            next_btn = page.locator("button:has-text('İleri'), button:has-text('Next')").first
            if next_btn.count() > 0:
                next_btn.click()
            else:
                username_input.press("Enter")
            time.sleep(3)

            # Step 2: Check for Challenge / Phone or Username confirmation
            challenge_input = page.locator("input[data-testid='ocfEnterTextTextInput'], input[name='text']").first
            if challenge_input.count() > 0 and page.locator("input[type='password']").count() == 0:
                print(f"[!] Doğrulama sorusu tespit edildi. Ek bilgi giriliyor...")
                fill_val = verify_credential or uname_clean
                challenge_input.fill(fill_val)
                time.sleep(1)
                challenge_next = page.locator("button:has-text('İleri'), button:has-text('Next')").first
                if challenge_next.count() > 0:
                    challenge_next.click()
                else:
                    challenge_input.press("Enter")
                time.sleep(3)

            # Step 3: Password
            password_input = page.locator("input[name='password'], input[type='password']").first
            password_input.wait_for(timeout=15000)
            password_input.fill(password)
            time.sleep(1)

            # Click Log in
            login_btn = page.locator("button[data-testid='LoginForm_Login_Button'], button:has-text('Giriş yap'), button:has-text('Log in')").first
            if login_btn.count() > 0:
                login_btn.click()
            else:
                password_input.press("Enter")
            time.sleep(5)

            # Check if login succeeded
            cur_url = page.url
            if "x.com/home" in cur_url or "twitter.com/home" in cur_url or page.locator("a[data-testid='AppTabBar_Home_Link']").count() > 0:
                # Save session
                self.save_session(context, uname_clean)
                cookies = context.cookies()
                auth_token = next((c["value"] for c in cookies if c["name"] == "auth_token"), "")
                ct0 = next((c["value"] for c in cookies if c["name"] == "ct0"), "")
                print(f"[✓] @{uname_clean} otomatik giriş başarılı ve kaydedildi!")
                return {
                    "success": True,
                    "username": uname_clean,
                    "auth_token": auth_token,
                    "ct0": ct0,
                    "message": f"@{uname_clean} hesabına başarıyla giriş yapıldı ve oturum kaydedildi!"
                }
            else:
                # Check for error message
                err_text = "Giriş başarısız oldu (Hatalı şifre veya 2FA/Güvenlik kodu gerekiyor)."
                err_el = page.locator("div[data-testid='toast'], span:has-text('Wrong password'), span:has-text('Yanlış şifre')").first
                if err_el.count() > 0:
                    err_text = err_el.inner_text()
                return {"success": False, "error": err_text}

        except Exception as e:
            return {"success": False, "error": f"Otomatik giriş sırasında hata: {str(e)}"}
        finally:
            try:
                context.close()
            except Exception:
                pass
            self.stop()
