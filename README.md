# 𝕏 (Twitter) BIST 100 AI Web Otomasyon & 100+ Hesap Kasma Paneli

Render.com üzerinde **%100 ÜCRETSİZ ($0)** olarak çalışabilen, **X Developer API ücreti ödemeden** 100'e kadar X hesabını birbirini kasması (beğeni, retweet, yapay zeka yorumu) için yöneten, **seçilen hedef hesapları sabitleyip yeni tweet attıklarında anında kasan**, anlık haberleri ve teknik grafikleri (RSI, EMA, Destek/Direnç) yorumlayan profesyonel Web Otomasyon Sistemi.

---

## 🚀 Yeni Eklenen Dev Özellikler

1. **🚀 100+ Hesap Toplu İçe Aktarma (Bulk Importer):**
   - Tek tek hesap eklemekle uğraşmayın. 100 hesabı birden şu formatta yapıştırıp tek tıkla sisteme bağlayabilirsiniz:
     ```text
     hesap1:auth_token1:ct01
     hesap2:auth_token2:ct02
     hesap3:auth_token3
     ```
   - Sistem tüm hesapların oturumlarını saniyeler içinde oluşturur ve RAM dostu ardışık kuyrukla çalıştırır.

2. **🎯 Sabit Hedef İzleme Listesi (Target Watchlist):**
   - İstediğiniz hesapları (örn: `@Borsagenci` veya piyasa fenomenlerini) listeye sabitleyin.
   - Sistem bu hesapları arka planda otomatik izler; **yeni bir tweet attıkları an, havuzdaki tüm hesaplarınız saniyeler içinde o tweeti beğenir, retweet yapar ve yapay zeka teyit yorumu atar!**

3. **💬 Yorum Stüdyosu (Comment & Tone Studio):**
   - Hesapların atacağı yorumları siz belirleyin:
     - **🤖 Sadece Yapay Zeka:** Tweetin içeriğine ve hisseye göre tamamen özgün yorumlar.
     - **📝 Hazır Yorum Havuzu:** Kendi yazdığınız cümle listesinden rastgele seçer.
     - **⚡ Hibrit Mod:** Hazır yorumlarla yapay zekayı harmanlar.
   - Yapay zeka üslubunu tek satırla değiştirin (örn: *"Samimi ol, tebrik et, kısa yaz"*).

4. **📸 Otomatik Teknik Grafik ve Fotoğraf Yükleme:**
   - Tweet atarken *"Grafiği Fotoğraf Olarak Ekle"* kutusunu işaretleyin; sistem hissenin **RSI, EMA9, EMA21, Destek ve Direnç** grafiğini otomatik çizip görsel olarak tweet'e iliştirir.

5. **🤖 Otomatik Pilot (Render Cloud 7/24 Worker):**
   - Bilgisayarınız kapalı olsa bile Render üzerinde 7/24 çalışır. Hem sabit hedefleri kollar hem de düzenli BIST analizleri paylaşır.

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
