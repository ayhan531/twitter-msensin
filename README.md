# 𝕏 (Twitter) BIST 100 AI Web Otomasyon & Hesap Kasma Paneli

Render.com üzerinde **%100 ÜCRETSİZ ($0)** olarak çalışabilen, **X Developer API ücreti ödemeden** birden fazla X hesabının birbirini kasmasını (beğeni, retweet, yapay zeka yorumu) sağlayan, **anlık haberleri ve teknik grafikleri (RSI, EMA, Destek/Direnç)** yorumlayan tam teşekküllü Web Yönetim Sistemi.

---

## 🚀 Yeni Özellikler

1. **🌐 Modern Web Yönetim Paneli (FastAPI & Tailwind Dark UI):**
   - Her şeyi tarayıcınızdan tek tıkla yönetin.
   - Hesapları bağlayın, durumlarını görün.
   - Canlı BIST 100 endeksi ve hisseleri izleyin.
   - Tek tıkla tweet atın ve havuzdaki diğer hesapların o tweeti anında kasmasını sağlayın.

2. **📰 Anlık Borsa & KAP Haberleri:**
   - Google News RSS, KAP ve finans bültenlerinden 0 TL maliyetle anlık haberleri toplar.
   - Beğendiğiniz habere **"Yorumla & Tweetle"** diyerek yapay zekaya profesyonel finans analizi yazdırabilirsiniz.

3. **📈 Teknik Grafik & Gösterge Analizi:**
   - 1 aylık OHLCV fiyat geçmişi üzerinden **RSI (14), EMA 9, EMA 21, Destek ve Direnç** seviyelerini otomatik hesaplar.
   - Koyu temalı (dark mode) profesyonel teknik analiz grafiğini çizer.
   - Yapay zeka bu grafiği bir borsa uzmanı gibi yorumlayıp tweet hazırlar.

4. **🚀 Çapraz Hesap Kasma Havuzu (Boost Pod):**
   - Herhangi bir tweet linkini panele yapıştırın.
   - Havuzdaki tüm hesaplarınız doğal insan gecikmeleriyle (15-45 sn) sırayla o tweeti **beğensin, retweet yapsın ve yapay zeka ile teyit yorumu atsın**.

5. **🤖 Otomatik Pilot (Background Worker):**
   - Bilgisayarınız kapalı olsa bile Render Cloud üzerinde belirlediğiniz aralıklarla (örneğin saatte bir) otomatik olarak BIST analizi paylaşır ve diğer hesaplarla birbirini kasar.

6. **☁️ Render.com 1-Tıkla Ücretsiz Dağıtım (Docker & Blueprint):**
   - Hazır `Dockerfile` ve `render.yaml` ile Render'ın ücretsiz Docker Web Service planında sıfır maliyetle çalışır.

---

## 🛠️ Yerel Çalıştırma (Kendi Bilgisayarınızda)

```bash
cd C:\Users\Cem\.gemini\antigravity\scratch\x-bist-bot

# Windows'ta tek tıkla:
start.bat

# Veya komut satırından:
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```
Tarayıcınızda açın: **`http://localhost:8000`**

---

## ☁️ Render.com Üzerine Ücretsiz Deploy Etme (Adım Adım)

1. **GitHub Deposu Oluşturun:**
   - Proje dosyalarını (`x-bist-bot`) bir GitHub reposuna push edin:
   ```bash
   git init
   git add .
   git commit -m "feat: X BIST Bot Web Dashboard"
   git branch -M main
   git remote add origin https://github.com/KULLANICI_ADINIZ/x-bist-bot.git
   git push -u origin main
   ```

2. **Render.com'a Bağlayın:**
   - [render.com](https://render.com) adresine gidin (ücretsiz hesap açın).
   - **"New +" -> "Web Service"** seçeneğine tıklayın.
   - GitHub deponuzu seçin.
   - Render projeyi otomatik olarak algılayacaktır:
     - **Runtime:** `Docker` (otomatik algılanır)
     - **Instance Type:** `Free` (0 $/ay)
     - **Region:** `Frankfurt (EU)` (veya istediğiniz bölge)
   - İsteğe bağlı olarak **Environment Variables** bölümüne:
     - `GEMINI_API_KEY`: *(Google AI Studio'dan aldığınız ücretsiz anahtar - isteğe bağlıdır, girmeseniz de dahili finans motoru çalışır)*
     - `GROQ_API_KEY`: *(İsteğe bağlı)*
   - **"Create Web Service"** butonuna basın!

3. **Kullanıma Başlayın:**
   - Render birkaç dakika içinde Playwright ve Chromium container'ını kurar.
   - Size `https://x-bist-bot-xxxx.onrender.com` gibi ücretsiz bir web adresi verir.
   - Bu adrese telefonunuzdan veya bilgisayarınızdan girip hesaplarınızı bağlayabilir ve otomasyonu yönetebilirsiniz!

---

## 🔑 Hesapları Web Sitesinden Nasıl Bağlarım?

1. Web paneline girin (`/` veya Render adresiniz).
2. **"Hesaplar"** sekmesine geçin.
3. X (Twitter) hesabınızın `auth_token` çerezini girin:
   - Bilgisayarınızda Chrome/Edge tarayıcısında Twitter'ı açın.
   - Klavyeden `F12` basın -> **Application (Uygulama)** -> **Cookies (Çerezler)** -> `https://x.com` seçin.
   - `auth_token` satırını bulun ve karşısındaki uzun değeri kopyalayıp panele yapıştırın.
4. **"Hesabı Bağla"** butonuna tıklayın. Artık hesap güvenle sisteme kaydedilmiştir!

---

## ⚠️ Yasal ve Güvenlik Hatırlatması
- SPK (Sermaye Piyasası Kurulu) mevzuatına uygunluk için sistem tüm tweet ve yorumların sonuna **(YTD)** iliştirir.
- Anti-bot koruması için işlemler arasına insan benzeri rastgele bekleme süreleri (jitter) eklenmiştir.
