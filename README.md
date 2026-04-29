# 📥 Async Video Downloader Bot

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-green.svg)](https://docs.aiogram.dev/)
[![yt-dlp](https://img.shields.io/badge/Engine-yt--dlp-red.svg)](https://github.com/yt-dlp/yt-dlp)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

**Async Video Downloader** — bu Telegram foydalanuvchilari uchun ijtimoiy tarmoqlardan yuqori sifatli media fayllarni asinxron tarzda yuklab beruvchi aqlli mikroservis. 

*Ushbu loyiha ochiq kodli shablon (template) sifatida taqdim etilgan bo'lib, o'z Telegram botingizni yaratish uchun mustahkam poydevor vazifasini o'taydi.*

## ✨ Qo'llab-quvvatlanadigan Platformalar
Loyiha aniq va barqaror ishlashi uchun faqat eng yirik va talab yuqori bo'lgan 3 ta platformaga optimallashtirilgan:
* 🔴 **YouTube** (Videolar va Shorts)
* 🟣 **Instagram** (Reels va Postlar)
* 🔵 **Facebook** (Ommaviy videolar / fb.watch)

## 🚀 Arxitektura va Muhandislik Yechimlari
Bu loyiha yuqori yuklamalarga bardosh berishi uchun "Best Practices" (Eng yaxshi amaliyotlar) asosida yozilgan:

1. **Asynchronous Non-blocking IO:** `aiogram` va `asyncio.to_thread` orqali `yt-dlp` ning sinxron tabiatini asinxronlashtirishga erishildi. Bitta foydalanuvchining og'ir videosi boshqa foydalanuvchilarning navbatini bloklamaydi.
2. **Smart Quality Fallback (Aqlli Sifat Tushirish):** Telegram'ning **50 MB** lik qattiq fayl limitiga moslashish uchun algoritm yozilgan. Agar video hajm limiti oshib ketsa, kod avtomatik tarzda sifatni pasaytiradi (`720p -> 480p -> 360p`) va Telegram API limitlariga urilmasdan faylni yetkazib beradi.
3. **Memory Management (Xotira boshqaruvi):** Bepul va kichik xotirali serverlarda (VPS/Cloud) muammosiz ishlashi uchun, fayl Telegram'ga yuborilishi bilan server xotirasidan xavfsiz tarzda o'chirib yuboriladi (`safe_remove` mexanizmi).

## 💻 Mahalliy Kompyuterda Ishga Tushirish (Local Setup)

Loyihani o'zingizda sinab ko'rish uchun quyidagi qadamlarni bajaring:

1. **Repozitoriyani yuklab oling:**
```bash
git clone [https://github.com/SizningGithubUsername/getmedia-video-bot.git](https://github.com/SizningGithubUsername/getmedia-video-bot.git)
cd getmedia-video-bot
Kutubxonalarni o'rnating:

Bash
pip install -r requirements.txt
Muhitni sozlang:
bot.py faylini ochib, BOT_TOKEN o'zgaruvchisiga o'zingizning Telegram bot tokeningizni kiriting.

Botni ishga tushiring:

Bash
python bot.py
📜 Litsenziya
Ushbu loyiha ochiq kodli hisoblanadi va MIT Litsenziyasi ostida taqdim etiladi. Batafsil ma'lumot uchun LICENSE fayliga qarang.