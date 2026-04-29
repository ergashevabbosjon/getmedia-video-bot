"""
╔══════════════════════════════════════════════════════════════════╗
║         Universal Telegram Video Downloader Bot                  ║
║         Barcha kod bitta faylda — bot.py                       ║
║                                                                  ║
║  Qo'llab-quvvatlanadigan platformalar:                           ║
║  YouTube • Instagram • Facebook •                                ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ───────────────────────────────────────────────────────────────────
# STANDART KUTUBXONALAR
# ───────────────────────────────────────────────────────────────────
import asyncio
import logging
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

# ───────────────────────────────────────────────────────────────────
# TASHQI KUTUBXONALAR  (pip install -r requirements.txt)
# ───────────────────────────────────────────────────────────────────
import yt_dlp
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message


# ═══════════════════════════════════════════════════════════════════
# 1. KONFIGURATSIYA  ← shu qatorni o'zgartiring
# ═══════════════════════════════════════════════════════════════════

# ⬇️  @BotFather dan olingan tokeningizni shu yerga yozing
BOT_TOKEN: str = "7773318188:AAHycQYdqzPXw-qDOQVEw3SAH_QVL5B5kPU"

# Vaqtinchalik video fayllar saqlanadigan papka
TEMP_DIR: Path = Path("downloads")

# Telegram 50 MB limit (baytda)
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024

# Qo'llab-quvvatlanadigan domenlar
SUPPORTED_DOMAINS: tuple[str, ...] = (
    "youtube.com", "youtu.be",
    "instagram.com",
    "facebook.com", "fb.watch",
)

# Token tekshiruvi
if not BOT_TOKEN or BOT_TOKEN == "BU_YERGA_TOKENINGIZNI_YOZING":
    raise RuntimeError(
        "❌ BOT_TOKEN kiritilmagan!\n"
        "bot.py faylida BOT_TOKEN = '...' qatoriga tokeningizni yozing."
    )


# ═══════════════════════════════════════════════════════════════════
# 2. LOGGING
# ═══════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# 3. XATOLIK KLASSLARI
# ═══════════════════════════════════════════════════════════════════

class DownloadError(Exception):
    """Umumiy yuklash xatoligi"""

class UnsupportedURLError(DownloadError):
    """Qo'llab-quvvatlanmaydigan yoki noto'g'ri URL"""

class FileTooLargeError(DownloadError):
    """Eng past sifatda ham 50 MB dan oshiq"""

class PrivateContentError(DownloadError):
    """Yopiq profil yoki autentifikatsiya talab qilinadi"""


# ═══════════════════════════════════════════════════════════════════
# 4. NATIJA MA'LUMOT KLASSI
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DownloadResult:
    filepath: Path   # Yuklangan faylning to'liq yo'li
    title:    str    # Video sarlavhasi
    duration: int    # Davomiyligi (soniyalarda)
    filesize: int    # Hajmi (baytda)
    platform: str    # Platforma nomi (YouTube, ...)


# ═══════════════════════════════════════════════════════════════════
# 5. YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════════

# Matndan URL topish uchun regex
_URL_REGEX = re.compile(
    r"https?://(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}(?:/[^\s]*)?",
    re.IGNORECASE,
)


def extract_url(text: str) -> str | None:
    """Matndan birinchi URL ni ajratib oladi, topilmasa None"""
    match = _URL_REGEX.search(text)
    return match.group(0) if match else None


def is_supported_url(url: str) -> bool:
    """URL qo'llab-quvvatlanadigan platformaga tegishli ekanligini tekshiradi"""
    try:
        hostname = (urlparse(url).hostname or "").removeprefix("www.")
        return any(
            hostname == d or hostname.endswith(f".{d}")
            for d in SUPPORTED_DOMAINS
        )
    except Exception:
        return False


def get_platform_name(url: str) -> str:
    """URL dan platforma nomini aniqlaydi"""
    url_lower = url.lower()
    mapping = {
        "youtube.com": "YouTube",  "youtu.be":     "YouTube",
        "instagram.com": "Instagram",
        "facebook.com": "Facebook", "fb.watch":     "Facebook",
    }
    for domain, name in mapping.items():
        if domain in url_lower:
            return name
    return "Noma'lum"


def fmt_duration(seconds: int) -> str:
    """Soniyalarni HH:MM:SS yoki MM:SS formatga o'tkazadi"""
    if seconds <= 0:
        return "noma'lum"
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_size(nb: int) -> str:
    """Baytlarni o'qilishi qulay formatga o'tkazadi"""
    if nb < 1024:        return f"{nb} B"
    if nb < 1024 ** 2:   return f"{nb/1024:.1f} KB"
    return f"{nb / 1024**2:.1f} MB"


def safe_remove(path: Path | None) -> None:
    """Xavfsiz tarzda faylni o'chiradi (xatolikni yutadi)"""
    if path and path.exists():
        try:
            path.unlink()
            logger.debug("Fayl o'chirildi: %s", path)
        except OSError as e:
            logger.warning("Faylni o'chirib bo'lmadi: %s", e)


# ═══════════════════════════════════════════════════════════════════
# 6. YT-DLP YUKLOVCHI
# ═══════════════════════════════════════════════════════════════════

def _ydl_opts(output_template: str, quality: str) -> dict:
    """
    Berilgan sifat darajasiga mos yt-dlp opsiyalarini qaytaradi.
    quality: "best" | "medium" | "low"
    """
    fmt = {
        "best": (
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=720]+bestaudio"
            "/best[height<=720]/best"
        ),
        "medium": (
            "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=480]+bestaudio"
            "/best[height<=480]/best"
        ),
        "low": (
            "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=360]+bestaudio"
            "/best[height<=360]/worst"
        ),
    }
    return {
        "format":               fmt.get(quality, fmt["best"]),
        "merge_output_format":  "mp4",
        "outtmpl":              output_template,
        "noplaylist":           True,
        "quiet":                True,
        "no_warnings":          True,
        "socket_timeout":       30,
        "retries":              3,
        "fragment_retries":     3,
        "postprocessors": [{
            "key":             "FFmpegVideoConvertor",
            "preferedformat":  "mp4",
        }],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    }


def _sync_download(url: str, output_dir: Path) -> DownloadResult:
    """
    Sinxron video yuklash (to'g'ridan-to'g'ri chaqirilmaydi).
    asyncio.to_thread() orqali alohida thread'da ishga tushiriladi.

    Hajm 50 MB dan oshsa sifat avtomatik pasaytiriladi:
      720p  →  480p  →  360p
    """
    uid      = uuid.uuid4().hex[:10]
    template = str(output_dir / f"{uid}_%(id)s.%(ext)s")

    for quality in ("best", "medium", "low"):
        logger.info("Yuklash urinishi | sifat=%s | url=%s", quality, url)
        downloaded: Path | None = None

        try:
            with yt_dlp.YoutubeDL(_ydl_opts(template, quality)) as ydl:
                info = ydl.extract_info(url, download=True)

                # Haqiqiy fayl nomini topamiz
                base = Path(ydl.prepare_filename(info))
                for ext in ("mp4", "mkv", "webm", "mov", "m4v"):
                    c = base.with_suffix(f".{ext}")
                    if c.exists():
                        downloaded = c
                        break

                # Papkadan qidiruv (zaxira)
                if downloaded is None:
                    matches = list(output_dir.glob(f"{uid}_*"))
                    if matches:
                        downloaded = max(matches, key=lambda p: p.stat().st_size)

                if not downloaded or not downloaded.exists():
                    raise DownloadError("Fayl yuklab bo'lingandan keyin topilmadi.")

                size = downloaded.stat().st_size
                logger.info("Yuklandi: %.2f MB | %s", size / 1024**2, downloaded.name)

                if size <= MAX_FILE_SIZE_BYTES:
                    # ✅ Telegram limitiga mos — muvaffaqiyatli qaytarish
                    return DownloadResult(
                        filepath = downloaded,
                        title    = info.get("title") or info.get("id") or "Video",
                        duration = int(info.get("duration") or 0),
                        filesize = size,
                        platform = get_platform_name(url),
                    )

                # ❌ Hajm oshdi — faylni o'chirib, quyi sifatga o'tish
                logger.warning("%.2f MB > 50 MB. Sifat pasaytirilmoqda...", size / 1024**2)
                safe_remove(downloaded)

        except yt_dlp.utils.DownloadError as exc:
            safe_remove(downloaded)
            msg = str(exc).lower()

            if any(k in msg for k in ("private", "login", "authentication", "sign in")):
                raise PrivateContentError(
                    "Bu kontent yopiq profilda yoki kirish uchun login talab qilinadi."
                ) from exc

            if any(k in msg for k in ("unsupported url", "no video formats", "not a video")):
                raise UnsupportedURLError(
                    "Bu URL qo'llab-quvvatlanmaydi yoki video topilmadi."
                ) from exc

            if quality == "low":
                raise DownloadError(f"Video yuklab bo'lmadi: {exc}") from exc

            # Keyingi sifat darajasiga o'tamiz
            continue

    raise FileTooLargeError(
        "Video eng past sifatda (360p) ham 50 MB dan oshib ketdi.\n"
        "Telegram bu o'lchamdagi faylni qabul qila olmaydi."
    )


async def download_video(url: str) -> DownloadResult:
    """
    Asosiy asinxron yuklash funksiyasi.

    yt-dlp bloklovchi (sinxron) bo'lgani uchun asyncio.to_thread()
    ishlatiladi — bot event loop'i bloklanmaydi va boshqa
    foydalanuvchilarga paralel javob berishda davom etadi.
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return await asyncio.to_thread(_sync_download, url, TEMP_DIR)


# ═══════════════════════════════════════════════════════════════════
# 7. TELEGRAM HANDLERLAR
# ═══════════════════════════════════════════════════════════════════

router = Router(name="main")


# ── /start ──────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    await msg.answer(
        f"👋 Salom, <b>{msg.from_user.full_name}</b>!\n\n"
        "🤖 Men <b>Universal Video Downloader Bot</b>man.\n\n"
        "📥 Quyidagi platformalardan video yuklab beraman:\n\n"
        "🎬 <b>YouTube</b> (Shorts ham)\n"
        "📸 <b>Instagram</b> (Reels &amp; Post)\n"
        "📘 <b>Facebook</b>\n"
        "📎 <b>Foydalanish:</b> Menga video havolasini yuboring!\n"
        "⚠️ <i>Maksimal fayl hajmi — 50 MB</i>"
    )


# ── /help ───────────────────────────────────────────────────────────
@router.message(Command("help"))
async def cmd_help(msg: Message) -> None:
    await msg.answer(
        "🆘 <b>Yordam</b>\n\n"
        "1️⃣ Video havolasini menga yuboring\n"
        "2️⃣ Men uni qayta ishlab tayyorlayman\n"
        "3️⃣ Video siz bilan ulashiladi\n\n"
        "<b>Xatoliklar sabablari:</b>\n"
        "• <i>Yopiq profil</i> — kirish imkoni yo'q\n"
        "• <i>50 MB dan katta</i> — Telegram limiti\n"
        "• <i>Qo'llab-quvvatlanmagan URL</i> — platforma ro'yxatda yo'q\n\n"
        "Muammo bo'lsa /start ni bosing."
    )


# ── Asosiy URL handler ───────────────────────────────────────────────
@router.message()
async def handle_url(msg: Message) -> None:
    """Foydalanuvchidan URL qabul qilib videoni yuklaydi va yuboradi"""

    # ── 1. Matn borligini tekshirish
    if not msg.text:
        await msg.answer(
            "❌ Iltimos, matnli havola yuboring.\n"
            "<code>https://www.youtube.com/watch?v=...</code>"
        )
        return

    # ── 2. URL ni matndan ajratib olish
    url = extract_url(msg.text)
    if not url:
        await msg.answer(
            "🔗 <b>Havola topilmadi.</b>\n\n"
            "To'g'ri URL yuboring. Masalan:\n"
            "<code>https://www.instagram.com/reel/abc123/</code>"
        )
        return

    # ── 3. Platforma qo'llab-quvvatlanishini tekshirish
    if not is_supported_url(url):
        await msg.answer(
            "⛔ <b>Bu platforma qo'llab-quvvatlanmaydi.</b>\n\n"
            "Ruxsat etilgan: YouTube • Instagram • Facebook\n\n"
            "/help — ko'proq ma'lumot"
        )
        return

    # ── 4. "Qayta ishlayapman..." xabarini yuborish
    proc_msg = await msg.answer(
        "⏳ <b>Videoni qayta ishlayapman...</b>\n"
        "<i>Biroz kuting, bu bir necha soniya olishi mumkin.</i>"
    )

    result: DownloadResult | None = None

    try:
        # ── 5. Asinxron yuklash (event loop bloklanmaydi)
        result = await download_video(url)

        logger.info(
            "✅ Tayyor | user=%s | platform=%s | size=%s",
            msg.from_user.id, result.platform, fmt_size(result.filesize),
        )

        # ── 6. Caption tuzish
        caption = (
            f"🎬 <b>{_trim(result.title, 100)}</b>\n\n"
            f"📡 Platforma:   <code>{result.platform}</code>\n"
            f"⏱ Davomiyligi: <code>{fmt_duration(result.duration)}</code>\n"
            f"📦 Hajmi:       <code>{fmt_size(result.filesize)}</code>\n\n"
            "🤖 <i>Video Downloader Bot</i>"
        )

        # ── 7. Videoni Telegram'ga yuborish
        await msg.answer_video(
            video=FSInputFile(result.filepath, filename="video.mp4"),
            caption=caption,
            supports_streaming=True,
        )

        # ── 8. "Qayta ishlayapman" xabarini o'chirish
        await proc_msg.delete()

    # ── Xatoliklar ────────────────────────────────────────────────
    except UnsupportedURLError as e:
        logger.warning("UnsupportedURL | user=%s | %s", msg.from_user.id, e)
        await proc_msg.edit_text(
            f"❌ <b>Video topilmadi.</b>\n\n<i>{e}</i>\n\n"
            "URL to'g'ri ekanligini tekshiring."
        )

    except PrivateContentError as e:
        logger.warning("PrivateContent | user=%s | %s", msg.from_user.id, e)
        await proc_msg.edit_text(
            f"🔒 <b>Kirish taqiqlangan.</b>\n\n<i>{e}</i>\n\n"
            "Faqat ochiq (public) kontentni yuklab olish mumkin."
        )

    except FileTooLargeError as e:
        logger.warning("FileTooLarge | user=%s | %s", msg.from_user.id, e)
        await proc_msg.edit_text(
            f"📦 <b>Fayl haddan katta.</b>\n\n<i>{e}</i>"
        )

    except DownloadError as e:
        logger.error("DownloadError | user=%s | %s", msg.from_user.id, e)
        await proc_msg.edit_text(
            f"⚠️ <b>Video yuklab bo'lmadi.</b>\n\n<i>{e}</i>\n\n"
            "Biroz kutib, qayta urinib ko'ring."
        )

    except Exception as e:
        logger.exception("Kutilmagan xatolik | user=%s", msg.from_user.id)
        await proc_msg.edit_text(
            "🚨 <b>Kutilmagan xatolik yuz berdi.</b>\n\n"
            "Iltimos, qayta urinib ko'ring yoki /start bosing."
        )

    finally:
        # ── 9. Vaqtinchalik faylni o'chirish — serverda qolmasin
        if result:
            safe_remove(result.filepath)


def _trim(text: str, max_len: int) -> str:
    """Matnni belgilangan uzunlikka qisqartiradi"""
    return (text[:max_len] + "…") if len(text) > max_len else text


# ═══════════════════════════════════════════════════════════════════
# 8. BOTNI ISHGA TUSHIRISH
# ═══════════════════════════════════════════════════════════════════

async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("🤖 Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("🛑 Bot to'xtatildi.")


if __name__ == "__main__":
    asyncio.run(main())
