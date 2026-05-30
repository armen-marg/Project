"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PARDON SOCIAL - ULTIMATE EDITION v1.0                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  __Modern Social Media Platfor__                                             ║
║                                                                              ║
║  FEATURES:                                                                   ║
║  • User Authentication & Profiles                                            ║
║  • Short Video Feed                                                          ║
║  • Likes, Comments & Shares                                                  ║
║  • Real-Time Direct Messages (DM)                                            ║
║  • Notifications System                                                      ║
║  • Follow / Unfollow Users                                                   ║
║  • Hashtags & Search                                                         ║
║  • Content Moderation & Profanity Filter                                     ║
║  • Media Uploads (Images & Videos)                                           ║
║  • Socket.IO Real-Time Communication                                         ║
║  • MySQL Database Backend                                                    ║
║  • Cloudinary Media Storage                                                  ║
║                                                                              ║
║  TECHNOLOGIES:                                                               ║
║  • Python 3.14                                                               ║
║  • Flask                                                                     ║
║  • Flask-SocketIO                                                            ║
║  • MySQL                                                                     ║
║  • Cloudinary                                                                ║
║  • HTML / CSS / JavaScript                                                   ║
║                                                                              ║
║  DEVELOPER: Armen Margaryan , Arshak Tonoyan                                 ║
║  STUDIO: Pardon Studio                                                       ║
║  VERSION: 1.0                                                                ║
║                                                                              ║
║  © 2026 Pardon Studio. All Rights Reserved.                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, jsonify, Response, send_file, abort)
from flask_socketio import SocketIO, emit, join_room, leave_room
from mysql.connector import pooling, Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from collections import defaultdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from logging.handlers import RotatingFileHandler
from better_profanity import profanity 
from urllib.parse import urlparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from functools import wraps 
from pyngrok import ngrok
import dns.resolver
import dns.exception
import smtplib
import logging
import secrets
import time
import re
import os
import io 
import tempfile
import cloudinary
import cloudinary.uploader
import unicodedata

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=7)
app.json.ensure_ascii = False

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

profanity.load_censor_words()

# ── КОНФИГ ───────────────────────────────────────────────────────────────────

cloudinary.config(
    cloud_name=os.getenv("CLOUD_NAME", ""),
    api_key=os.getenv("CLOUD_API", ""),
    api_secret=os.getenv("CLOUD_API_SECRET", "")
)

MYSQL_HOST     = os.getenv("MYSQL_HOST", "localhost")
MYSQL_USER     = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "chatapp")

NGROK_TOKEN    = os.getenv("NGROK_TOKEN", "")
GMAIL_USER     = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS", "")

RESET_TOKEN_EXPIRE_MINUTES = 30
ALLOWED_EXT    = {"mp4", "webm", "mov"}
MAX_VIDEO_SIZE = 200 * 1024 * 1024   # 200 МБ

MIME_MAP = {
    "mp4":  "video/mp4",
    "webm": "video/webm",
    "mov":  "video/quicktime",
}

# ── BANNED WORDS ─────────────────────────────────────────────────────────────

# Запрещённые имена пользователей (точное совпадение или вхождение)
BANNED_USERNAMES: set[str] = {
    "admin", "administrator", "moderator", "moder", "mod",
    "support", "official", "pardon", "system", "root",
    "superuser", "staff", "help", "service", "bot",
    "null", "undefined", "anonymous", "anon", "guest",
    "test", "tester", "demo", "unknown", "owner", "developer",
    "dev", "manager", "operator", "staffs", "team", "security",
    "securityteam", "helpdesk", "contact", "info", "mail",
    "webmaster", "postmaster", "noreply", "no-reply",
    "rootuser", "sysadmin", "administrator1", "admin1",
}

# Запрещённые подстроки в именах пользователей (case-insensitive)
BANNED_USERNAME_SUBSTRINGS: list[str] = [
    # English slurs / severe profanity
    "nigger", "nigga", "niga", "n1gger", "n1gga",
    "faggot", "fagg0t", "fag", "GITLER", "Gitler",
    "hitler", "nazi", "n4zi",
    "chink", "spic", "kike", "wetback", "gook", "raghead",
    "cunt", "c0nt",
    "whore", "wh0re", "Trans",
    "bitch", "b1tch",
    "retard", "ret4rd",
    "rape", "r4pe",
    "pedo", "pedophile",
    "nonce",
    "tranny",
    "kkk",

    # more English profanity / toxic words
    "fuck", "fck", "fuk", "fvck", "phuck",
    "motherfucker", "mothafucka", "mf", "mfer",
    "shit", "sh1t", "shitt", "shithead", "shitheads",
    "asshole", "assh0le", "arsehole",
    "dick", "d1ck", "dickhead",
    "pussy", "pussi", "pussi0",
    "slut", "slutty",
    "whore", "slag",
    "bastard", "b4stard",
    "idiot", "moron", "loser", "trash",
    "suck", "sux", "suxx", "sucker",
    "stupid", "dumb", "ugly",
    "porn", "porno", "sex", "sexy", "nude", "nudity",
    "xxx", "18+", "nsfw",

    # scam / spam / impersonation
    "free money", "giveaway", "airdrop", "crypto scam", "scam",
    "hack", "hacker", "phish", "phishing", "stealer",
    "spam", "bot", "boost", "followers", "followback",
    "onlyfans", "telegram", "whatsapp", "discord",
    "cashapp", "paypal", "bitcoin", "btc", "usdt",

    # Russian slurs / severe profanity (transliterated)
    "huy", "khuy", "hui", "хуй",
    "pizda", "пизда",
    "ebat", "ebal", "ебать", "ебал",
    "pidar", "pidor", "pidoras", "пидор", "пидорас",
    "suka", "сука",
    "blyad", "blyat", "блядь", "блять",
    "zalupa", "залупа",
    "mudak", "мудак",
    "shlyuha", "шлюха",
    "ублюдок", "ublyudok",
    "мразь", "mraz",
    "ёбаный", "yobany",
    "курва", "kurva",
    "гандон", "gandon",
    "даун", "daun",
    "урод", "urod",
    "чурка", "churka",
    "хохол", "hohkol",
    "кацап", "katsap",

    # extra Russian profanity / toxic variants
    "сукин", "сукинс", "sukin",
    "сволочь", "svoloch",
    "дебил", "debil",
    "кретин", "cretin",
    "идиот", "idiot",
    "тупой", "tupoy",
    "мудач", "mudach",
    "пидр", "пидора",
    "бля", "blya",
    "ебан", "yeban",
    "хуе", "khuye",
    "хуйн", "huyn",
]

# Запрещённые слова в подписях/комментариях/DM (подстрока, case-insensitive)
BANNED_CONTENT_WORDS: list[str] = [
    # ── English severe profanity ──────────────────────────────────────────
    "nigger", "nigga", "n1gger", "n1gga",
    "faggot", "fagg0t",
    "chink", "spic", "kike", "wetback", "gook", "raghead",
    "cunt", "c0nt",
    "whore", "wh0re",
    "bitch", "b1tch",
    "retard", "ret4rd",
    "pedo", "pedophile",
    "nonce",
    "kkk",
    "rape",
    "tranny",
    "slut",
    "cocksucker",
    "motherfucker", "mf",
    "shithead", "shitheads",
    "asshole", "assh0le",
    "dickhead",
    "fuckface",

    # ── more English profanity / variants ────────────────────────────────
    "fuck", "fck", "fuk", "fvck", "phuck",
    "fucked", "fucking", "fucker", "fuckers",
    "shit", "sh1t", "shitty", "shittiest",
    "piss", "pissed", "pissing",
    "damn", "dammit", "hell",
    "bastard", "b4stard",
    "dick", "d1ck", "dickhead",
    "pussy", "pussies",
    "slut", "slutty",
    "whore", "whores",
    "ass", "a55", "arse",
    "moron", "idiot", "stupid", "dumb",
    "loser", "trash", "garbage",
    "nutsack", "ballsack",
    "porn", "porno", "pornhub", "xvideos", "xhamster",
    "sex", "sexy", "nude", "nudity", "nsfw", "18+",

    # ── English spam / dangerous ──────────────────────────────────────────
    "onlyfans.com",
    "pornhub.com",
    "xvideos.com",
    "xhamster.com",
    "cam4.com",
    "onlyfans",
    "escort",
    "escorts",
    "adultfriendfinder",
    "camgirl",
    "webcam",
    "giveaway",
    "free followers",
    "free money",
    "airdrop",
    "crypto scam",
    "scam",
    "phishing",
    "hack",
    "hacking",
    "stealer",
    "malware",
    "virus",
    "botnet",

    # ── Russian severe profanity (Cyrillic) ───────────────────────────────
    "хуй", "хуя", "хуев", "хуйня",
    "пизда", "пизды", "пиздец",
    "ебать", "ебал", "ёбаный", "ёб",
    "пидор", "пидорас", "пидр",
    "блядь", "блять", "бляди",
    "залупа",
    "мудак", "мудаки",
    "шлюха", "шлюхи",
    "ублюдок",
    "мразь",
    "курва",
    "гандон",
    "ёбтвоюмать",
    "сукасын",
    "чурка", "чурки",
    "хохол", "хохлы",
    "кацап",

    # ── Russian severe profanity (transliterated) ─────────────────────────
    "huy", "khuy", "hui",
    "pizda", "pizdets",
    "ebat", "ebal", "yobany",
    "pidar", "pidor", "pidoras",
    "blyad", "blyat",
    "zalupa",
    "mudak",
    "shlyuha",
    "ublyudok",
    "mraz",
    "kurva",
    "gandon",
    "churka",
    "hohkol",
    "katsap",

    # ── extra Russian toxic / spam / 18+ ─────────────────────────────────
    "секс", "порно", "голый", "обнаж",
    "дроч", "дрочить", "дрочер",
    "ебан", "ебуч", "хуе", "хуета",
    "мразота", "сволочь", "дебил", "кретин", "идиот",
    "тупой", "лох", "клоун", "чмо",
    "спам", "скам", "мошен",
    "телеграм", "вацап", "whatsapp",
    "бот", "накрутка"
]

# Запрещённые email-домены (дополнительно к DISPOSABLE_DOMAINS)
EXTRA_BANNED_EMAIL_DOMAINS: set[str] = {
    # ── Взрослый контент / порно ──────────────────────────────────────────
    "pornhub.com", "onlyfans.com", "xvideos.com", "xhamster.com",
    "xnxx.com", "xnxxx.com", "cam4.com", "chaturbate.com",
    "brazzers.com", "redtube.com", "youporn.com", "tube8.com",
    "spankbang.com", "eporner.com", "tnaflix.com", "motherless.com",
    "hentaihaven.org", "nhentai.net", "rule34.xxx",
    "sex.com", "porn.com", "pussy.com", "dick.com",
    "escort.com", "escorts.com", "adultfriendfinder.com",
    "ashleymadison.com", "fling.com", "alt.com",
    "flirt4free.com", "livejasmin.com", "imlive.com",
    "streamate.com", "bongacams.com", "stripchat.com", "camsoda.com",

    # extra adult / spam / impersonation domains
    "onlyfans.net", "onlyfans.org",
    "xhamster.net", "xvideos.net",
    "pornhub.net", "pornhub.org",
    "camgirls.com", "webcamsex.com",
    "fuckbook.com", "adultsearch.com",
    "sexsearch.com", "dirtyroulette.com",
    "freelancehentai.com",

    # ── Временные / одноразовые ───────────────────────────────────────────
    "guerrillamail.com", "sharklasers.com", "mailinator.com",
    "10minutemail.com", "10minutemail.net", "10minutemail.org",
    "temp-mail.org", "tempmail.com", "tempmail.net",
    "throwawaymail.com", "yopmail.com", "maildrop.cc",
    "getnada.com", "nada.ltd", "dispostable.com", "fakeinbox.com",
    "trashmail.com", "trashmail.me", "mintemail.com",
    "mailnesia.com", "moakt.com", "mailcatch.com",
    "mytemp.email", "inboxkitten.com", "dropmail.me",
    "e4ward.com", "spamgourmet.com", "burnermail.io",
    "simplelogin.co", "simplelogin.io", "anonaddy.com",
    "privaterelay.appleid.com",

    # extra disposable / relay
    "mail.tm", "getairmail.com", "sharklasers.net",
    "trashmail.net", "tempmail.xyz", "disposablemail.com",
    "fake-mail.net", "spambox.us", "tempinbox.com",
    "mailnull.com", "mailnesia.org", "spamex.com",
}


def contains_banned_content(text: str) -> bool:
    """Проверяет текст на наличие запрещённых слов для подписей/комментариев/DM."""
    if not text:
        return False
    # Normalize: NFKC + casefold
    normalized = unicodedata.normalize("NFKC", text).casefold()
    # Also check a leet-decoded version
    leet_map = str.maketrans({
        "0": "o", "1": "i", "3": "e", "4": "a",
        "5": "s", "7": "t", "@": "a", "$": "s",
        "!": "i", "|": "i",
    })
    decoded = normalized.translate(leet_map)
    for word in BANNED_CONTENT_WORDS:
        w = word.casefold()
        if w in normalized or w in decoded:
            return True
    # Also run better_profanity
    if profanity.contains_profanity(text):
        return True
    return False

def censor_text(text: str) -> str:
    """Заменяет запрещённые слова на *** в тексте сообщений."""
    if not text:
        return text

    # better_profanity цензура
    censored = profanity.censor(text)

    # Нормализуем для поиска но заменяем в оригинале
    normalized = unicodedata.normalize("NFKC", censored).casefold()

    leet_map = str.maketrans({
        "0": "o", "1": "i", "3": "e", "4": "a",
        "5": "s", "7": "t", "@": "a", "$": "s",
        "!": "i", "|": "i",
    })
    decoded = normalized.translate(leet_map)

    result = censored

    for word in BANNED_CONTENT_WORDS:
        w = word.casefold()
        if w not in normalized and w not in decoded:
            continue
        # Заменяем в оригинальном тексте без учёта регистра
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        result = pattern.sub("****", result)

    return result

def is_username_banned(username: str) -> tuple[bool, str]:
    """
    Проверяет имя пользователя на запрет.
    Возвращает (True, причина) если запрещено, иначе (False, "").
    """
    lower = username.lower()

    # Точное совпадение с зарезервированными именами
    if lower in BANNED_USERNAMES:
        return True, f"Имя «{username}» зарезервировано"

    # Вхождение запрещённого слова в имя
    for bad in BANNED_USERNAME_SUBSTRINGS:
        if bad in lower:
            return True, "Имя содержит недопустимые слова"

    return False, ""


def is_clean(text: str):
    if not text:
        return False, "Пустое значение"

    # 1) Нормализация
    original = text
    t = unicodedata.normalize("NFKC", text).strip()
    t = t.casefold()

    # 2) Удаление невидимых / управляющих символов
    t = re.sub(r"[\u200b-\u200f\u2060\u2066-\u2069\ufeff]", "", t)
    t = re.sub(r"[\x00-\x1f\x7f]", "", t)

    # 3) Запрет пустоты после очистки
    if not t:
        return False, "Ник пустой после очистки"

    # 4) Длина
    if len(t) < 3:
        return False, "Слишком короткий ник"
    if len(t) > 20:
        return False, "Слишком длинный ник"

    # 5) Email / ссылки
    if re.fullmatch(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", t):
        return False, "Email нельзя использовать как ник"

    if re.search(r"(https?://|www\.|[a-z0-9-]+\.(?:com|net|org|ru|io|app|me|xyz|site|top)\b)", t, re.I):
        return False, "Ссылки запрещены"

    # 6) Разрешённые символы для username
    if not re.fullmatch(r"[\w.-]+", t, flags=re.UNICODE):
        return False, "Недопустимые символы"

    # 7) Нельзя начинать/заканчивать на разделитель
    if re.search(r"(^[._-])|([._-]$)|([._-]{2,})", t):
        return False, "Плохое использование символов-разделителей"

    # 8) Запрет слишком повторяющихся символов
    if re.search(r"(.)\1{4,}", t):
        return False, "Слишком много одинаковых символов подряд"

    # 9) Leetspeak / обходы
    leet = t.translate(str.maketrans({
        "0": "o", "1": "i", "3": "e", "4": "a",
        "5": "s", "7": "t", "@": "a", "$": "s",
        "!": "i", "|": "i",
    }))

    leet = unicodedata.normalize("NFKD", leet)
    leet = "".join(ch for ch in leet if not unicodedata.combining(ch))
    compact = re.sub(r"[\W_]+", "", leet, flags=re.UNICODE)

    # 10) Смешение алфавитов
    scripts = set()
    for ch in compact:
        if ch.isalpha():
            name = unicodedata.name(ch, "")
            if "CYRILLIC" in name:
                scripts.add("cyrillic")
            elif "LATIN" in name:
                scripts.add("latin")
            elif "GREEK" in name:
                scripts.add("greek")
            else:
                scripts.add("other")

    if len(scripts) > 1:
        return False, "Смешение разных алфавитов запрещено"

    # 11) profanity на исходном и очищенном варианте
    if profanity.contains_profanity(original):
        return False, "Запрещённые слова"
    if profanity.contains_profanity(t):
        return False, "Запрещённые слова"
    if profanity.contains_profanity(compact):
        return False, "Обход фильтра через символы/leet"

    # 12) Зарезервированные имена
    reserved = {
        "admin", "administrator", "root", "support", "moderator",
        "system", "null", "undefined", "official", "team", "owner",
        "guest", "test", "bot"
    }
    if compact in reserved:
        return False, "Такой username зарезервирован"
    for word in reserved:
        if word in compact:
            return False, "Username содержит зарезервированное слово"

    # 13) Check against BANNED_USERNAME_SUBSTRINGS
    for bad in BANNED_USERNAME_SUBSTRINGS:
        if bad in t or bad in compact:
            return False, "Имя содержит недопустимые слова"

    return True, ""


def validate_username(u: str) -> tuple[bool, str | None]:
    if not u:
        return False, "Имя пользователя обязательно"

    # Нормализация
    raw = unicodedata.normalize("NFKC", u).strip()
    if not raw:
        return False, "Имя пользователя пустое"

    # Длина
    if len(raw) < 3:
        return False, "Минимум 3 символа"
    if len(raw) > 40:
        return False, "Максимум 40 символов"

    # Удаление невидимых и control-символов
    raw = re.sub(r"[\u200b-\u200f\u2060\u2066-\u2069\ufeff]", "", raw)
    raw = re.sub(r"[\x00-\x1f\x7f]", "", raw)

    if not raw:
        return False, "Имя пользователя пустое после очистки"

    # Разрешённые символы
    if not re.fullmatch(r"[\w.-]+", raw, flags=re.UNICODE):
        return False, "Разрешены только буквы, цифры, _, . и -"

    # Нельзя начинать/заканчивать разделителем или ставить их подряд
    if re.search(r"(^[._-])|([._-]$)|([._-]{2,})", raw):
        return False, "Плохое использование символов-разделителей"

    lowered = raw.casefold()

    # Email / ссылки
    if re.fullmatch(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", lowered):
        return False, "Email нельзя использовать как имя"

    if re.search(r"(https?://|www\.|[a-z0-9-]+\.(?:com|net|org|ru|io|app|me|xyz|site|top)\b)", lowered, re.I):
        return False, "Ссылки запрещены"

    # Leetspeak / обход фильтра
    leet = lowered.translate(str.maketrans({
        "0": "o", "1": "i", "3": "e", "4": "a",
        "5": "s", "7": "t", "@": "a", "$": "s",
        "!": "i", "|": "i",
    }))
    leet = unicodedata.normalize("NFKD", leet)
    leet = "".join(ch for ch in leet if not unicodedata.combining(ch))
    compact = re.sub(r"[\W_]+", "", leet, flags=re.UNICODE)

    # Смешение алфавитов
    scripts = set()
    for ch in compact:
        if ch.isalpha():
            name = unicodedata.name(ch, "")
            if "CYRILLIC" in name:
                scripts.add("cyrillic")
            elif "LATIN" in name:
                scripts.add("latin")
            elif "GREEK" in name:
                scripts.add("greek")
            else:
                scripts.add("other")

    if len(scripts) > 1:
        return False, "Смешение разных алфавитов запрещено"

    # Повторы
    if re.search(r"(.)\1{4,}", raw):
        return False, "Слишком много одинаковых символов подряд"

    # profanity
    if profanity.contains_profanity(raw):
        return False, "Запрещённые слова"
    if profanity.contains_profanity(compact):
        return False, "Обход фильтра через символы/leet"

    # Зарезервированные имена
    reserved = {
        "admin", "administrator", "root", "support", "moderator",
        "system", "null", "undefined", "official", "team", "owner",
        "guest", "test", "bot"
    }
    if compact in reserved:
        return False, "Такой username зарезервирован"
    for word in reserved:
        if word in compact:
            return False, "Username содержит зарезервированное слово"

    # Banned word lists (substrings)
    for bad in BANNED_USERNAME_SUBSTRINGS:
        bad_l = bad.casefold()
        if bad_l in lowered or bad_l in compact:
            return False, "Имя содержит недопустимые слова"

    # Existing banned usernames set
    banned, reason = is_username_banned(raw)
    if banned:
        return False, reason

    return True, None


# ── ЛОГИ ─────────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("chatapp")
logger.setLevel(logging.INFO)
_fh = RotatingFileHandler(
    "Project/logs/app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
)
_fh.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S"
))
if not logger.handlers:
    logger.addHandler(_fh)

# ── ПУЛ СОЕДИНЕНИЙ ───────────────────────────────────────────────────────────
pool = None


class get_db:
    def __enter__(self):
        self.conn = pool.get_connection()
        self.cur  = self.conn.cursor(dictionary=True)
        return self.conn, self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.conn.rollback()
        self.cur.close()
        self.conn.close()


def _add_column_if_missing(cur, table: str, column: str, definition: str):
    cur.execute("""
        SELECT COUNT(*) AS c FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
    """, (MYSQL_DATABASE, table, column))
    if not cur.fetchone()["c"]:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        logger.info(f"Добавлена колонка: {table}.{column}")


def init_db():
    global pool
    logger.info("Инициализация пула MySQL...")
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name="chatapp_pool",
            pool_size=10,
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            autocommit=False,
        )
        with get_db() as (conn, cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    username      VARCHAR(40)  NOT NULL UNIQUE,
                    email         VARCHAR(255) NOT NULL UNIQUE,
                    password_hash TEXT         NOT NULL,
                    is_new_user   TINYINT(1)   DEFAULT 1,
                    is_banned     TINYINT(1)   DEFAULT 0,
                    ban_reason    VARCHAR(255) DEFAULT NULL,
                    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS password_resets (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    user_id    INT          NOT NULL,
                    token      VARCHAR(128) NOT NULL UNIQUE,
                    expires_at DATETIME     NOT NULL,
                    used       TINYINT(1)   DEFAULT 0,
                    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    user_id      INT          NOT NULL,
                    caption      TEXT,
                    content_type VARCHAR(50)  NOT NULL DEFAULT 'video/mp4',
                    file_size    INT          NOT NULL DEFAULT 0,
                    video_data   LONGBLOB,
                    likes        INT          DEFAULT 0,
                    comments     INT          DEFAULT 0,
                    reposts      INT          DEFAULT 0,
                    is_hidden    TINYINT(1)   DEFAULT 0,
                    created_at   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS video_likes (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    user_id    INT NOT NULL,
                    video_id   INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_like (user_id, video_id),
                    FOREIGN KEY (user_id)  REFERENCES users(id)   ON DELETE CASCADE,
                    FOREIGN KEY (video_id) REFERENCES videos(id)  ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    from_user  INT NOT NULL,
                    video_id   INT,
                    reason     TEXT NOT NULL,
                    is_read    TINYINT(1) DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_user) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS video_reposts (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    user_id    INT NOT NULL,
                    video_id   INT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_repost (user_id, video_id),
                    FOREIGN KEY (user_id)  REFERENCES users(id)   ON DELETE CASCADE,
                    FOREIGN KEY (video_id) REFERENCES videos(id)  ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    user_id    INT  NOT NULL,
                    video_id   INT  NOT NULL,
                    text       TEXT NOT NULL,
                    is_hidden  TINYINT(1)   DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id)  REFERENCES users(id)   ON DELETE CASCADE,
                    FOREIGN KEY (video_id) REFERENCES videos(id)  ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    user_id    INT          NOT NULL,
                    from_user  INT          NOT NULL,
                    type       VARCHAR(20)  NOT NULL,
                    video_id   INT,
                    is_read    TINYINT(1)   DEFAULT 0,
                    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id)   REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (from_user) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reg_otps (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    email      VARCHAR(255) NOT NULL,
                    username   VARCHAR(40)  NOT NULL,
                    otp        VARCHAR(10)  NOT NULL,
                    expires_at DATETIME     NOT NULL,
                    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS follows (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    follower_id INT NOT NULL,
                    following_id INT NOT NULL,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_follow (follower_id, following_id),
                    FOREIGN KEY (follower_id)  REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS direct_messages (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    from_user   INT NOT NULL,
                    to_user     INT NOT NULL,
                    text        TEXT NOT NULL,
                    is_read     TINYINT(1) DEFAULT 0,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_user) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (to_user)   REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            
            _add_column_if_missing(cur, "videos",  "video_url",  "TEXT")
            _add_column_if_missing(cur, "videos",  "is_hidden",  "TINYINT(1) DEFAULT 0")
            _add_column_if_missing(cur, "users",   "is_banned",  "TINYINT(1) DEFAULT 0")
            _add_column_if_missing(cur, "users",   "ban_reason", "VARCHAR(255) DEFAULT NULL")
            _add_column_if_missing(cur, "comments","is_hidden",  "TINYINT(1) DEFAULT 0")
            conn.commit()
        logger.info("БД готова")
        return True
    except Error as e:
        logger.error(f"Ошибка БД: {e}")
        return False


# ── ВАЛИДАЦИЯ ─────────────────────────────────────────────────────────────────
EMAIL_REGEX = re.compile(
    r"^(?=[a-zA-Z0-9])[a-zA-Z0-9._%+\-]{1,64}(?<![._%+\-])"
    r"@(?=[a-zA-Z0-9])[a-zA-Z0-9\-]{1,63}(\.[a-zA-Z0-9\-]{1,63})*\.[a-zA-Z]{2,63}$"
)
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwam.com",
    "sharklasers.com", "spam4.me", "yopmail.com", "trashmail.com",
    "trashmail.me", "dispostable.com", "maildrop.cc", "fakeinbox.com",
    "10minutemail.com", "getnada.com", "temp-mail.org",
}
_dns_cache: dict = {}


def _check_mx(domain: str):
    if domain in _dns_cache:
        return _dns_cache[domain]
    try:
        dns.resolver.resolve(domain, "MX", lifetime=5)
        r = (True, None)
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        r = (False, "Домен email не существует")
    except dns.exception.Timeout:
        r = (True, None)
    except Exception as e:
        logger.warning(f"DNS: {e}")
        r = (False, "Недействительный домен")
    _dns_cache[domain] = r
    return r


def validate_email(email: str) -> tuple[bool, str | None]:
    if not email:              return False, "Email обязателен"
    if len(email) > 254:       return False, "Слишком длинный email"
    if not EMAIL_REGEX.match(email): return False, "Неверный формат email"
    domain = email.split("@", 1)[1].lower()
    if domain in DISPOSABLE_DOMAINS:         return False, "Временные email запрещены"
    if domain in EXTRA_BANNED_EMAIL_DOMAINS: return False, "Этот email-домен заблокирован"
    ok, err = _check_mx(domain)
    if not ok: return False, err
    return True, None


def validate_password(p: str, c: str) -> tuple[bool, str | None]:
    if len(p) < 6: return False, "Минимум 6 символов"
    if p != c:     return False, "Пароли не совпадают"
    return True, None


def sanitize_text(text: str, max_len: int = 500) -> str:
    """Обрезает и убирает лишние пробелы из текста."""
    return (text or "").strip()[:max_len]


# ── EMAIL ─────────────────────────────────────────────────────────────────────
def send_otp_email(to: str, otp: str) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASS:
        logger.error("GMAIL_USER / GMAIL_APP_PASS не заданы")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Ваш код подтверждения"
    msg["From"]    = GMAIL_USER
    msg["To"]      = to
    html = f"""
<html><body style="font-family:Arial,sans-serif;background:#0a0f1a;padding:30px;">
<div style="max-width:420px;margin:auto;background:#111827;border-radius:16px;
     padding:36px;text-align:center;border:1px solid rgba(255,255,255,0.08);">
  <h2 style="color:#fff;margin-bottom:8px;">Код подтверждения</h2>
  <p style="color:rgba(255,255,255,0.5);font-size:13px;margin-bottom:28px;">
    Действителен {RESET_TOKEN_EXPIRE_MINUTES} минут.</p>
  <div style="font-size:42px;font-weight:bold;letter-spacing:12px;color:#4a90d9;
       background:rgba(74,144,217,0.1);border-radius:10px;padding:20px 10px;">{otp}</div>
</div></body></html>"""
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_USER, GMAIL_APP_PASS)
            smtp.sendmail(GMAIL_USER, to, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Email ошибка: {e}")
        return False


# ── BRUTE-FORCE ───────────────────────────────────────────────────────────────
login_attempts: dict = defaultdict(list)
blocked_ips: dict    = {}
MAX_ATTEMPTS = 5
WINDOW       = timedelta(minutes=10)
BLOCK_TIME   = timedelta(minutes=15)


def is_blocked(ip: str) -> bool:
    if ip in blocked_ips:
        if datetime.utcnow() < blocked_ips[ip]:
            return True
        del blocked_ips[ip]
    return False


def record_fail(ip: str) -> str | None:
    now = datetime.utcnow()
    login_attempts[ip] = [t for t in login_attempts[ip] if now - t < WINDOW]
    login_attempts[ip].append(now)
    if len(login_attempts[ip]) >= MAX_ATTEMPTS:
        blocked_ips[ip] = now + BLOCK_TIME
        logger.warning(f"IP заблокирован: {ip}")
        return "Слишком много попыток. Попробуй через 15 минут."
    return None


def get_client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()


# ── ДЕКОРАТОРЫ ────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "Не авторизован"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def not_banned(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("is_banned"):
            reason = session.get("ban_reason", "нарушение правил")
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": f"Аккаунт заблокирован: {reason}", "banned": True}), 403
            flash(f"Аккаунт заблокирован: {reason}")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

ADMIN_USERNAMES = {"Armen_Admin"}

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session or session["username"] not in ADMIN_USERNAMES:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "Нет доступа"}), 403
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ── УТИЛИТЫ ───────────────────────────────────────────────────────────────────
def time_ago(dt: datetime) -> str:
    s = int((datetime.utcnow() - dt).total_seconds())
    if s < 60:    return f"{s}с"
    if s < 3600:  return f"{s//60}мин"
    if s < 86400: return f"{s//3600}ч"
    return f"{s//86400}д"


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def get_content_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else "mp4"
    return MIME_MAP.get(ext, "video/mp4")


def check_user_banned(user_id: int) -> tuple[bool, str]:
    try:
        with get_db() as (conn, cur):
            cur.execute("SELECT is_banned, ban_reason FROM users WHERE id=%s", (user_id,))
            row = cur.fetchone()
            if row and row["is_banned"]:
                return True, row["ban_reason"] or "нарушение правил"
    except Exception:
        pass
    return False, ""


# ── АВТОРИЗАЦИЯ ───────────────────────────────────────────────────────────────
@app.route("/")
def logo():
    if "user_id" in session: return redirect(url_for("start"))
    return render_template("logo.html")


@app.route("/home")
def index():
    if "user_id" in session: return redirect(url_for("start"))
    return render_template("index.html")

@app.route('/messages')
@login_required  # если используешь login_required
def messages_page():
    return render_template('messages.html')

@app.route("/home/login", methods=["GET", "POST"])
def login():
    if "user_id" in session: return redirect(url_for("start"))
    if request.method != "POST": return render_template("login.html")

    identifier = (request.form.get("identifier") or
                  request.form.get("username") or
                  request.form.get("email") or "").strip()
    password   = (request.form.get("password") or "").strip()
    ip         = get_client_ip()

    if is_blocked(ip):
        flash("Слишком много попыток. Попробуй позже.")
        return redirect(url_for("login"))

    if not identifier or not password:
        flash("Заполните все поля")
        return redirect(url_for("login"))

    with get_db() as (conn, cur):
        cur.execute(
            "SELECT * FROM users WHERE username=%s OR email=%s LIMIT 1",
            (identifier, identifier)
        )
        user = cur.fetchone()

    def _fail():
        msg = record_fail(ip)
        flash(msg or "Неверный логин или пароль")
        return redirect(url_for("login"))

    if not user: return _fail()
    if not check_password_hash(user["password_hash"], password): return _fail()

    if user.get("is_banned"):
        reason = user.get("ban_reason") or "нарушение правил"
        flash(f"Аккаунт заблокирован: {reason}")
        logger.warning(f"Попытка входа забаненного: {user['username']}")
        return redirect(url_for("login"))

    session.permanent    = True
    session["user_id"]   = user["id"]
    session["username"]  = user["username"]
    session["is_new"]    = bool(user.get("is_new_user", 0))
    session["is_banned"] = bool(user.get("is_banned", 0))

    if user.get("is_new_user"):
        with get_db() as (conn, cur):
            cur.execute("UPDATE users SET is_new_user=0 WHERE id=%s", (user["id"],))
            conn.commit()

    login_attempts.pop(ip, None)
    logger.info(f"LOGIN | {user['username']} | ip={ip}")
    return redirect(url_for("start"))


@app.route("/home/register")
def register():
    if "user_id" in session: return redirect(url_for("start"))
    return render_template("register.html")


@app.route("/register-send-otp", methods=["POST"])
def register_send_otp():
    username = request.form.get("username", "").strip()
    email    = request.form.get("email",    "").strip()
    password = request.form.get("password", "").strip()
    confirm  = request.form.get("confirm",  "").strip()

    ip = get_client_ip()
    if is_blocked(ip):
        return jsonify({"ok": False, "error": "Слишком много запросов. Подождите."})

    # ✅ validate_username called here (step 1 of registration)
    for fn, args in [
        (validate_username, (username,)),
        (validate_email,    (email,)),
        (validate_password, (password, confirm)),
    ]:
        ok, err = fn(*args)
        if not ok: return jsonify({"ok": False, "error": err})

    with get_db() as (conn, cur):
        cur.execute("SELECT id FROM users WHERE BINARY username=%s", (username,))
        if cur.fetchone(): return jsonify({"ok": False, "error": "Имя занято"})
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone(): return jsonify({"ok": False, "error": "Email занят"})

        otp = str(secrets.randbelow(90000) + 10000)
        exp = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
        cur.execute("DELETE FROM reg_otps WHERE email=%s", (email,))
        cur.execute(
            "INSERT INTO reg_otps (email,username,otp,expires_at) VALUES(%s,%s,%s,%s)",
            (email, username, otp, exp)
        )
        conn.commit()

    if not send_otp_email(email, otp):
        return jsonify({"ok": False, "error": "Не удалось отправить письмо"})
    return jsonify({"ok": True})


@app.route("/register-verify-otp", methods=["POST"])
def register_verify_otp():
    otp      = request.form.get("otp",      "").strip()
    email    = request.form.get("email",    "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    confirm  = request.form.get("confirm",  "").strip()

    # ✅ validate_username called again here (race-condition / double-submit guard)
    ok_u, err_u = validate_username(username)
    if not ok_u:
        return jsonify({"ok": False, "error": err_u})

    with get_db() as (conn, cur):
        cur.execute("""
            SELECT * FROM reg_otps
            WHERE email=%s AND otp=%s AND expires_at>UTC_TIMESTAMP()
        """, (email, otp))
        if not cur.fetchone():
            return jsonify({"ok": False, "error": "Неверный/просроченный код"})

        cur.execute("SELECT id FROM users WHERE BINARY username=%s", (username,))
        if cur.fetchone():
            cur.execute("DELETE FROM reg_otps WHERE email=%s", (email,))
            conn.commit()
            return jsonify({"ok": False, "error": "Имя занято"})

        ok_p, err_p = validate_password(password, confirm)
        if not ok_p: return jsonify({"ok": False, "error": err_p})

        try:
            cur.execute(
                "INSERT INTO users (username,email,password_hash,is_new_user)"
                " VALUES(%s,%s,%s,1)",
                (username, email, generate_password_hash(password))
            )
            cur.execute("DELETE FROM reg_otps WHERE email=%s", (email,))
            conn.commit()
            logger.info(f"REGISTER | {username} | {email}")
            return jsonify({"ok": True})
        except Exception as e:
            conn.rollback()
            logger.error(e)
            return jsonify({"ok": False, "error": "Ошибка сервера"})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── СБРОС ПАРОЛЯ ──────────────────────────────────────────────────────────────
@app.route("/home/forgot")
def forgot_password():
    if "user_id" in session: return redirect(url_for("start"))
    return render_template("forgot.html")


@app.route("/emailForm", methods=["POST"])
def forgot_email():
    email = request.form.get("email", "").strip()
    ok, err = validate_email(email)
    if not ok: return jsonify({"ok": False, "error": err})

    with get_db() as (conn, cur):
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        if not user: return jsonify({"ok": True})  # don't reveal existence

        otp = str(secrets.randbelow(90000) + 10000)
        exp = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
        cur.execute("DELETE FROM password_resets WHERE user_id=%s AND used=0", (user["id"],))
        cur.execute(
            "INSERT INTO password_resets (user_id,token,expires_at) VALUES(%s,%s,%s)",
            (user["id"], otp, exp)
        )
        conn.commit()

    if not send_otp_email(email, otp): return jsonify({"ok": False, "error": "Ошибка отправки"})
    return jsonify({"ok": True})


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    otp, email = request.form.get("otp", "").strip(), request.form.get("email", "").strip()
    with get_db() as (conn, cur):
        cur.execute("""
            SELECT pr.* FROM password_resets pr
            JOIN users u ON u.id=pr.user_id
            WHERE pr.token=%s AND pr.used=0 AND pr.expires_at>UTC_TIMESTAMP() AND u.email=%s
        """, (otp, email))
        reset = cur.fetchone()
        if not reset: return jsonify({"ok": False, "error": "Неверный код"})

        real = secrets.token_urlsafe(64)
        cur.execute("UPDATE password_resets SET token=%s WHERE id=%s", (real, reset["id"]))
        conn.commit()
    return jsonify({"ok": True, "token": real})


@app.route("/reset-password/<token>", methods=["POST"])
def reset_password(token):
    with get_db() as (conn, cur):
        cur.execute("""
            SELECT pr.* FROM password_resets pr
            WHERE pr.token=%s AND pr.used=0 AND pr.expires_at>UTC_TIMESTAMP()
        """, (token,))
        reset = cur.fetchone()
        if not reset: return jsonify({"ok": False, "error": "Ссылка недействительна"})

        ok, err = validate_password(
            request.form.get("password", "").strip(),
            request.form.get("confirm",  "").strip()
        )
        if not ok: return jsonify({"ok": False, "error": err})

        try:
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE id=%s",
                (generate_password_hash(request.form["password"]), reset["user_id"])
            )
            cur.execute("UPDATE password_resets SET used=1 WHERE token=%s", (token,))
            conn.commit()
            return jsonify({"ok": True})
        except Exception as e:
            conn.rollback()
            logger.error(e)
            return jsonify({"ok": False, "error": "Ошибка сервера"})


# ── ОСНОВНОЕ ПРИЛОЖЕНИЕ ───────────────────────────────────────────────────────
@app.route("/start")
@login_required
@not_banned
def start():
    is_new = session.pop("is_new", False)
    return render_template("start.html", is_new=is_new)


@app.route("/created_by")
def created_by():
    return render_template("created_by.html")


@app.route("/settings")
@login_required
@not_banned
def settings():
    return render_template("settings.html")


# ── СМЕНА ИМЕНИ ПОЛЬЗОВАТЕЛЯ (settings) ──────────────────────────────────────
@app.route("/api/settings/change-username", methods=["POST"])
@login_required
@not_banned
def change_username():
    """
    Allows a logged-in user to change their username.
    Validates with validate_username before saving.
    """
    user_id      = session["user_id"]
    new_username = (request.get_json(silent=True) or {}).get("username", "").strip()

    # ✅ validate_username called for username change in settings
    ok, err = validate_username(new_username)
    if not ok:
        return jsonify({"ok": False, "error": err})

    try:
        with get_db() as (conn, cur):
            # Check availability (case-sensitive)
            cur.execute("SELECT id FROM users WHERE BINARY username=%s AND id!=%s",
                        (new_username, user_id))
            if cur.fetchone():
                return jsonify({"ok": False, "error": "Имя занято"})

            cur.execute("UPDATE users SET username=%s WHERE id=%s", (new_username, user_id))
            conn.commit()

        session["username"] = new_username
        logger.info(f"USERNAME CHANGE | user={user_id} → {new_username}")
        return jsonify({"ok": True, "username": new_username})

    except Error as e:
        logger.error(f"Ошибка смены имени: {e}")
        return jsonify({"ok": False, "error": "Ошибка сервера"})


# ── ЗАГРУЗКА ВИДЕО ────────────────────────────────────────────────────────────
@app.route("/upload-video", methods=["POST"])
@login_required
@not_banned
def upload_video():
    user_id = session["user_id"]

    if "video" not in request.files:
        return jsonify({"ok": False, "error": "Файл не найден"})

    file    = request.files["video"]
    caption = sanitize_text(request.form.get("caption", ""), 300)

    if contains_banned_content(caption):
        logger.warning(f"Запрещённый контент в подписи: user={user_id}")
        return jsonify({"ok": False, "error": "Подпись содержит недопустимые слова"})

    if not file or not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "Неверный тип файла (MP4, WebM, MOV)"})

    content_type = get_content_type(file.filename)
    tmp_dir   = tempfile.gettempdir()
    safe_name = secure_filename(file.filename)
    tmp_path  = os.path.join(tmp_dir, f"{secrets.token_hex(8)}_{safe_name}")
    file_size = 0

    try:
        file.stream.seek(0)
        file.save(tmp_path)
        file_size = os.path.getsize(tmp_path)

        if file_size == 0:
            return jsonify({"ok": False, "error": "Файл пустой — попробуй ещё раз"})

        if file_size > MAX_VIDEO_SIZE:
            return jsonify({
                "ok": False,
                "error": f"Файл слишком большой (макс {MAX_VIDEO_SIZE // 1024 // 1024} МБ)"
            })

        logger.info(f"Загружаем файл: {tmp_path}, размер: {file_size} байт")

        result = cloudinary.uploader.upload(
            tmp_path,
            resource_type="video",
            folder="pardon_videos",
        )

        if not result:
            raise Exception("Cloudinary вернул пустой ответ")

        video_url = result["secure_url"]

        with get_db() as (conn, cur):
            cur.execute("""
                INSERT INTO videos (user_id, caption, content_type, file_size, video_url)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, caption, content_type, file_size, video_url))
            conn.commit()
            video_id = cur.lastrowid

        socketio.emit("new_video", {"username": session["username"]})
        logger.info(f"Видео загружено: user={user_id} id={video_id} size={file_size}B")
        return jsonify({"ok": True, "video_id": video_id, "video_url": video_url})

    except Exception as e:
        import traceback
        logger.error(f"Ошибка загрузки: {traceback.format_exc()}")
        return jsonify({"ok": False, "error": str(e)})
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except:
                pass


# ── СТРИМИНГ ВИДЕО ────────────────────────────────────────────────────────────
@app.route("/video/<int:video_id>")
def serve_video(video_id):
    # Если не авторизован — редирект на логин
    if "user_id" not in session:
        return redirect(url_for("login"))

    with get_db() as (conn, cur):
        cur.execute("""
            SELECT v.content_type, v.video_url, v.caption, u.username
            FROM videos v
            JOIN users u ON u.id = v.user_id
            WHERE v.id=%s AND v.is_hidden=0
        """, (video_id,))
        row = cur.fetchone()

    if not row or not row["video_url"]:
        return Response("Видео не найдено", status=404)

    # Отдаём HTML-страницу с плеером
    video_url = row["video_url"]
    caption   = row["caption"] or ""
    username  = row["username"]

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>@{username} — Pardon</title>
  <meta property="og:type"         content="video.other"/>
  <meta property="og:url"          content="{request.url}"/>
  <meta property="og:video"        content="{video_url}"/>
  <meta property="og:video:type"   content="{row['content_type']}"/>
  <meta property="og:title"        content="@{username} на Pardon"/>
  <meta property="og:description"  content="{caption}"/>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#000;display:flex;flex-direction:column;align-items:center;
          justify-content:center;min-height:100vh;font-family:sans-serif;color:#fff}}
    .wrap{{width:100%;max-width:420px;position:relative}}
    video{{width:100%;max-height:90vh;display:block;border-radius:0}}
    .info{{padding:14px 16px;background:#111}}
    .uname{{font-weight:700;font-size:15px;color:#4a90d9;margin-bottom:4px;
            text-decoration:none;display:block}}
    .uname:hover{{text-decoration:underline}}
    .caption{{font-size:13px;color:rgba(255,255,255,.75);line-height:1.5}}
    .back{{display:inline-block;margin-top:14px;padding:10px 24px;
           background:linear-gradient(135deg,#4a90d9,#7b5cfa);
           border-radius:20px;text-decoration:none;color:#fff;
           font-size:13px;font-weight:600}}
  </style>
</head>
<body>
  <div class="wrap">
    <video src="{video_url}" controls autoplay playsinline loop
           preload="auto" controlsList="nodownload"></video>
    <div class="info">
      <a class="uname" href="/start">@{username}</a>
      <div class="caption">{caption}</div>
      <a class="back" href="/start">← Открыть Pardon</a>
    </div>
  </div>
</body>
</html>"""

    return Response(html, mimetype="text/html")


# ── ФИД ───────────────────────────────────────────────────────────────────────
@app.route("/api/feed")
@login_required
@not_banned
def api_feed():
    user_id = session["user_id"]
    tab = request.args.get("tab", "foryou")
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0
    limit = 10

    with get_db() as (conn, cur):
        if tab == "following":
            # Только видео тех, на кого подписан. Свои НЕ показываем.
            cur.execute("""
                SELECT
                    v.id, v.caption, v.likes, v.comments, v.reposts,
                    v.content_type, v.video_url, v.created_at,
                    u.username, u.id AS user_id,
                    MAX(CASE WHEN vl.user_id = %s THEN 1 ELSE 0 END) AS user_liked,
                    MAX(CASE WHEN vr.user_id = %s THEN 1 ELSE 0 END) AS user_reposted
                FROM videos v
                JOIN users u ON u.id = v.user_id
                JOIN follows f ON f.following_id = v.user_id AND f.follower_id = %s
                LEFT JOIN video_likes vl ON vl.video_id = v.id AND vl.user_id = %s
                LEFT JOIN video_reposts vr ON vr.video_id = v.id AND vr.user_id = %s
                WHERE v.is_hidden = 0
                  AND u.is_banned = 0
                  AND v.user_id != %s
                GROUP BY v.id, v.caption, v.likes, v.comments, v.reposts,
                         v.content_type, v.video_url, v.created_at,
                         u.username, u.id
                ORDER BY v.created_at DESC
                LIMIT %s OFFSET %s
            """, (user_id, user_id, user_id, user_id, user_id, user_id, limit, offset))
        else:
            # For You — все видео кроме своих
            cur.execute("""
                SELECT
                    v.id, v.caption, v.likes, v.comments, v.reposts,
                    v.content_type, v.video_url, v.created_at,
                    u.username, u.id AS user_id,
                    MAX(CASE WHEN vl.user_id = %s THEN 1 ELSE 0 END) AS user_liked,
                    MAX(CASE WHEN vr.user_id = %s THEN 1 ELSE 0 END) AS user_reposted
                FROM videos v
                JOIN users u ON u.id = v.user_id
                LEFT JOIN video_likes vl ON vl.video_id = v.id AND vl.user_id = %s
                LEFT JOIN video_reposts vr ON vr.video_id = v.id AND vr.user_id = %s
                WHERE v.is_hidden = 0
                  AND u.is_banned = 0
                GROUP BY v.id, v.caption, v.likes, v.comments, v.reposts,
                         v.content_type, v.video_url, v.created_at,
                         u.username, u.id
                ORDER BY v.created_at DESC
                LIMIT %s OFFSET %s
            """, (user_id, user_id, user_id, user_id, limit, offset))

        videos = cur.fetchall()

    return jsonify([{
        "id":            v["id"],
        "caption":       v["caption"] or "",
        "username":      v["username"],
        "user_id":       v["user_id"],
        "likes":         v["likes"],
        "comments":      v["comments"],
        "reposts":       v["reposts"],
        "user_liked":    bool(v["user_liked"]),
        "user_reposted": bool(v["user_reposted"]),
        "time_ago":      time_ago(v["created_at"]),
        "video_url":     v["video_url"],
        "content_type":  v["content_type"],
    } for v in videos])

# ── ЛАЙК ──────────────────────────────────────────────────────────────────────
@app.route("/api/like/<int:video_id>", methods=["POST"])
@login_required
@not_banned
def toggle_like(video_id):
    user_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute("SELECT user_id FROM videos WHERE id=%s AND is_hidden=0", (video_id,))
        v = cur.fetchone()
        if not v:
            return jsonify({"ok": False, "error": "Видео не найдено"}), 404

        cur.execute(
            "SELECT id FROM video_likes WHERE user_id=%s AND video_id=%s",
            (user_id, video_id)
        )
        if cur.fetchone():
            cur.execute("DELETE FROM video_likes WHERE user_id=%s AND video_id=%s", (user_id, video_id))
            cur.execute("UPDATE videos SET likes=GREATEST(0,likes-1) WHERE id=%s", (video_id,))
            liked = False
        else:
            cur.execute("INSERT INTO video_likes (user_id,video_id) VALUES(%s,%s)", (user_id, video_id))
            cur.execute("UPDATE videos SET likes=likes+1 WHERE id=%s", (video_id,))
            liked = True
            if v["user_id"] != user_id:
                cur.execute(
                    "INSERT INTO notifications (user_id,from_user,type,video_id) VALUES(%s,%s,'like',%s)",
                    (v["user_id"], user_id, video_id)
                )
                socketio.emit("notification", {"type": "like"}, room=f"user_{v['user_id']}")

        cur.execute("SELECT likes FROM videos WHERE id=%s", (video_id,))
        count = cur.fetchone()["likes"]
        conn.commit()

    return jsonify({"ok": True, "liked": liked, "count": count})


# ── РЕПОСТ ─────────────────────────────────────────────────────────────────────
@app.route("/api/repost/<int:video_id>", methods=["POST"])
@login_required
@not_banned
def toggle_repost(video_id):
    user_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute("SELECT user_id FROM videos WHERE id=%s AND is_hidden=0", (video_id,))
        v = cur.fetchone()
        if not v:
            return jsonify({"ok": False, "error": "Видео не найдено"}), 404

        cur.execute(
            "SELECT id FROM video_reposts WHERE user_id=%s AND video_id=%s",
            (user_id, video_id)
        )
        if cur.fetchone():
            cur.execute("DELETE FROM video_reposts WHERE user_id=%s AND video_id=%s", (user_id, video_id))
            cur.execute("UPDATE videos SET reposts=GREATEST(0,reposts-1) WHERE id=%s", (video_id,))
            reposted = False
        else:
            cur.execute("INSERT INTO video_reposts (user_id,video_id) VALUES(%s,%s)", (user_id, video_id))
            cur.execute("UPDATE videos SET reposts=reposts+1 WHERE id=%s", (video_id,))
            reposted = True
            if v["user_id"] != user_id:
                cur.execute(
                    "INSERT INTO notifications (user_id,from_user,type,video_id) VALUES(%s,%s,'repost',%s)",
                    (v["user_id"], user_id, video_id)
                )
                socketio.emit("notification", {"type": "repost"}, room=f"user_{v['user_id']}")

        cur.execute("SELECT reposts FROM videos WHERE id=%s", (video_id,))
        count = cur.fetchone()["reposts"]
        conn.commit()

    return jsonify({"ok": True, "reposted": reposted, "count": count})


# ── КОММЕНТАРИИ ───────────────────────────────────────────────────────────────
@app.route("/api/comments/<int:video_id>")
@login_required
def get_comments(video_id):
    with get_db() as (conn, cur):
        cur.execute("""
            SELECT c.text, c.created_at, u.username
            FROM comments c
            JOIN users u ON u.id=c.user_id
            WHERE c.video_id=%s AND c.is_hidden=0 AND u.is_banned=0
            ORDER BY c.created_at DESC LIMIT 50
        """, (video_id,))
        rows = cur.fetchall()
    return jsonify([{
        "username": r["username"],
        "text":     r["text"],
        "time":     time_ago(r["created_at"])
    } for r in rows])


@app.route("/api/comments/<int:video_id>", methods=["POST"])
@login_required
@not_banned
def post_comment(video_id):
    user_id = session["user_id"]
    text    = sanitize_text((request.get_json(silent=True) or {}).get("text", ""), 500)

    if not text:
        return jsonify({"ok": False, "error": "Пустой комментарий"})

    # ✅ Check comment for banned content (uses enhanced contains_banned_content)
    if contains_banned_content(text):
        logger.warning(f"Запрещённый контент в комментарии: user={user_id}")
        return jsonify({"ok": False, "error": "Комментарий содержит недопустимые слова"})

    with get_db() as (conn, cur):
        cur.execute("SELECT user_id FROM videos WHERE id=%s AND is_hidden=0", (video_id,))
        v = cur.fetchone()
        if not v:
            return jsonify({"ok": False, "error": "Видео не найдено"}), 404

        cur.execute(
            "INSERT INTO comments (user_id,video_id,text) VALUES(%s,%s,%s)",
            (user_id, video_id, text)
        )
        cur.execute("UPDATE videos SET comments=comments+1 WHERE id=%s", (video_id,))

        if v["user_id"] != user_id:
            cur.execute(
                "INSERT INTO notifications (user_id,from_user,type,video_id) VALUES(%s,%s,'comment',%s)",
                (v["user_id"], user_id, video_id)
            )
            socketio.emit("notification", {"type": "comment"}, room=f"user_{v['user_id']}")
        conn.commit()

    socketio.emit("new_comment", {
        "video_id": video_id,
        "username": session["username"],
        "text":     text
    })
    return jsonify({"ok": True})


# ── УВЕДОМЛЕНИЯ ───────────────────────────────────────────────────────────────
@app.route("/api/notifications")
@login_required
def get_notifications():
    user_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute("""
            SELECT n.*, u.username AS from_username
            FROM notifications n
            JOIN users u ON u.id=n.from_user
            WHERE n.user_id=%s
            ORDER BY n.created_at DESC LIMIT 200
    """, (user_id,))
        rows = cur.fetchall()
        # Помечаем как прочитанные (но НЕ удаляем)
        cur.execute("UPDATE notifications SET is_read=1 WHERE user_id=%s AND is_read=0", (user_id,))
        conn.commit()

    return jsonify([{
        "from_username": r["from_username"],
        "type":          r["type"],
        "video_id":      r["video_id"],
        "is_read":       bool(r["is_read"]),
        "time":          time_ago(r["created_at"])
    } for r in rows])


@app.route("/api/notifications/unread")
@login_required
def unread_count():
    user_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE user_id=%s AND is_read=0",
            (user_id,)
        )
        count = cur.fetchone()["c"]
    return jsonify({"count": count})


# ── УДАЛЕНИЕ ВИДЕО ────────────────────────────────────────────────────────────
@app.route("/api/video/delete/<int:video_id>", methods=["DELETE"])
@login_required
@not_banned
def delete_video(video_id):
    user_id = session["user_id"]
    try:
        with get_db() as (conn, cur):
            cur.execute(
                "SELECT id, user_id, video_url FROM videos WHERE id=%s",
                (video_id,)
            )
            video = cur.fetchone()

            if not video:
                return jsonify({"ok": False, "error": "Видео не найдено"}), 404

            if video["user_id"] != user_id:
                logger.warning(f"Попытка удалить чужое видео: user={user_id} video={video_id}")
                return jsonify({"ok": False, "error": "Нет доступа"}), 403

            cur.execute("DELETE FROM video_likes   WHERE video_id=%s", (video_id,))
            cur.execute("DELETE FROM video_reposts WHERE video_id=%s", (video_id,))
            cur.execute("DELETE FROM comments      WHERE video_id=%s", (video_id,))
            cur.execute("DELETE FROM notifications WHERE video_id=%s", (video_id,))
            cur.execute(
                "DELETE FROM videos WHERE id=%s AND user_id=%s",
                (video_id, user_id)
            )
            conn.commit()
            logger.info(f"Видео удалено: video={video_id} by user={user_id}")

        socketio.emit("video_deleted", {"video_id": video_id})
        return jsonify({"ok": True})

    except Error as e:
        logger.error(f"Ошибка удаления видео {video_id}: {e}")
        return jsonify({"ok": False, "error": "Ошибка сервера"}), 500


# ── ПРОФИЛЬ ───────────────────────────────────────────────────────────────────
@app.route("/api/profile")
@login_required
def profile_data():
    user_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute("SELECT id, username, created_at FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()

        cur.execute("SELECT COUNT(*) AS c FROM videos WHERE user_id=%s AND is_hidden=0", (user_id,))
        video_count = cur.fetchone()["c"]

        cur.execute("""
            SELECT COUNT(*) AS c FROM video_reposts vr
            JOIN videos v ON v.id=vr.video_id
            WHERE vr.user_id=%s AND v.is_hidden=0
        """, (user_id,))
        repost_count = cur.fetchone()["c"]

        # ── НОВОЕ: подписчики и подписки ──
        cur.execute("SELECT COUNT(*) AS c FROM follows WHERE following_id=%s", (user_id,))
        followers_count = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM follows WHERE follower_id=%s", (user_id,))
        following_count = cur.fetchone()["c"]

        # Список для попапа
        cur.execute("""
            SELECT u.username FROM follows f
            JOIN users u ON u.id = f.follower_id
            WHERE f.following_id=%s AND u.is_banned=0
            ORDER BY f.created_at DESC LIMIT 100
        """, (user_id,))
        followers = cur.fetchall()

        cur.execute("""
            SELECT u.username FROM follows f
            JOIN users u ON u.id = f.following_id
            WHERE f.follower_id=%s AND u.is_banned=0
            ORDER BY f.created_at DESC LIMIT 100
        """, (user_id,))
        following = cur.fetchall()

        cur.execute("""
            SELECT v.id, v.caption, v.likes, v.video_url, v.created_at,
                   (SELECT COUNT(*) FROM video_reposts WHERE video_id=v.id AND user_id=%s) AS is_reposted
            FROM videos v
            WHERE v.user_id=%s AND v.is_hidden=0
            ORDER BY v.created_at DESC LIMIT 20
        """, (user_id, user_id))
        videos = cur.fetchall()

    return jsonify({
        "id":              user["id"],
        "username":        user["username"],
        "joined":          user["created_at"].strftime("%B %Y"),
        "video_count":     video_count,
        "repost_count":    repost_count,
        "followers_count": followers_count,
        "following_count": following_count,
        "followers":       [{"username": r["username"]} for r in followers],
        "following":       [{"username": r["username"]} for r in following],
        "videos": [{
            "id":          v["id"],
            "likes":       v["likes"],
            "is_reposted": bool(v["is_reposted"]),
            "video_url":   v["video_url"] or f"/video/{v['id']}",
        } for v in videos],
    })


# ── DM THREADS ────────────────────────────────────────────────────────────────
@app.route("/api/dm/threads")
@login_required
def dm_threads():
    my_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute("""
            SELECT
                u.id AS user_id,
                u.username,
                dm.text AS last_message,
                dm.created_at,
                dm.from_user,
                SUM(CASE WHEN dm2.is_read=0 AND dm2.to_user=%s THEN 1 ELSE 0 END) AS unread
            FROM (
                SELECT
                    CASE WHEN from_user=%s THEN to_user ELSE from_user END AS other_id,
                    MAX(id) AS last_id
                FROM direct_messages
                WHERE from_user=%s OR to_user=%s
                GROUP BY other_id
            ) latest
            JOIN direct_messages dm ON dm.id = latest.last_id
            JOIN users u ON u.id = latest.other_id
            LEFT JOIN direct_messages dm2
                ON dm2.from_user = latest.other_id AND dm2.to_user=%s
            WHERE u.is_banned=0
            GROUP BY u.id, u.username, dm.text, dm.created_at, dm.from_user
            ORDER BY dm.created_at DESC
        """, (my_id, my_id, my_id, my_id, my_id))
        threads = cur.fetchall()

    return jsonify([{
        "user_id":      t["user_id"],
        "username":     t["username"],
        "last_message": t["last_message"] or "",
        "time":         time_ago(t["created_at"]) if t["created_at"] else "",
        "unread":       int(t["unread"] or 0),
        "online":       False,
    } for t in threads])


# ── DM MESSAGES ───────────────────────────────────────────────────────────────
@app.route("/api/dm/messages/<int:other_id>")
@login_required
def dm_messages(other_id):
    my_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute("""
            SELECT id, from_user, to_user, text, is_read, created_at
            FROM direct_messages
            WHERE (from_user=%s AND to_user=%s)
               OR (from_user=%s AND to_user=%s)
            ORDER BY created_at ASC
            LIMIT 100
        """, (my_id, other_id, other_id, my_id))
        msgs = cur.fetchall()

        # Пометить как прочитанные
        cur.execute("""
            UPDATE direct_messages SET is_read=1
            WHERE from_user=%s AND to_user=%s AND is_read=0
        """, (other_id, my_id))
        conn.commit()

    VIDEO_LINK_RE = re.compile(r'.*/video/(\d+).*')

    result = []
    for m in msgs:
        msg_date = m["created_at"].strftime("%d %B %Y") if m["created_at"] else ""
        text = m["text"] or ""
        # Определяем тип сообщения
        vm = VIDEO_LINK_RE.match(text.strip())
        msg_type = "video" if vm else "text"
        video_id = int(vm.group(1)) if vm else None

        result.append({
            "id":       m["id"],
            "text":     text,
            "is_mine":  m["from_user"] == my_id,
            "time":     time_ago(m["created_at"]) if m["created_at"] else "",
            "date":     msg_date,
            "type":     msg_type,
            "video_id": video_id,
        })
    return jsonify(result)


# ── DM SEND ───────────────────────────────────────────────────────────────────
@app.route("/api/dm/send", methods=["POST"])
@login_required
@not_banned
def dm_send():
    my_id = session["user_id"]
    data  = request.get_json(silent=True) or {}
    text  = sanitize_text(data.get("text", ""), 1000)
    to_id = data.get("to_user_id")

    if not text:
        return jsonify({"ok": False, "error": "Пустое сообщение"})

    text = censor_text(text)

    if not to_id:
        return jsonify({"ok": False, "error": "Получатель не указан"})

    try:
        to_id = int(to_id)
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Неверный получатель"})

    if to_id == my_id:
        return jsonify({"ok": False, "error": "Нельзя писать себе"})

    with get_db() as (conn, cur):
        cur.execute("SELECT id FROM users WHERE id=%s AND is_banned=0", (to_id,))
        if not cur.fetchone():
            return jsonify({"ok": False, "error": "Пользователь не найден"})

        cur.execute(
            "INSERT INTO direct_messages (from_user, to_user, text) VALUES (%s,%s,%s)",
            (my_id, to_id, text)
        )
        conn.commit()
        msg_id = cur.lastrowid

    socketio.emit("new_message", {
        "from_user_id": my_id,
        "username":     session["username"],
        "text":         text,
        "time":         "сейчас",
    }, room=f"user_{to_id}")

    logger.info(f"DM | from={my_id} to={to_id} len={len(text)}")
    return jsonify({"ok": True, "id": msg_id})

# ── ПОИСК ПОЛЬЗОВАТЕЛЕЙ ДЛЯ DM ───────────────────────────────────────────────
@app.route("/api/users/search")
@login_required
@not_banned
def users_search():
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 1:
        return jsonify([])
    my_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute("""
            SELECT id, username FROM users
            WHERE username LIKE %s AND is_banned=0 AND id != %s
            ORDER BY username LIMIT 20
        """, (f"%{q}%", my_id))
        users = cur.fetchall()
    return jsonify([{"id": u["id"], "username": u["username"]} for u in users])

# ── SOCKET.IO ─────────────────────────────────────────────────────────────────
@socketio.on("join")
def on_join(data=None):
    user_id = session.get("user_id")
    if user_id:
        join_room(f"user_{user_id}")


# ── ПОИСК ─────────────────────────────────────────────────────────────────────
@app.route("/api/search")
@login_required
@not_banned
def api_search():
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 2:
        return jsonify({"videos": [], "users": []})

    like = f"%{q}%"
    user_id = session["user_id"]

    with get_db() as (conn, cur):
        # Поиск видео по подписи
        cur.execute("""
            SELECT v.id, v.caption, v.likes, v.video_url, u.username, u.id AS user_id
            FROM videos v
            JOIN users u ON u.id = v.user_id
            WHERE v.is_hidden = 0
              AND u.is_banned = 0
              AND v.caption LIKE %s
            ORDER BY v.likes DESC
            LIMIT 20
        """, (like,))
        videos = cur.fetchall()

        # Поиск пользователей по имени
        cur.execute("""
            SELECT u.id, u.username,
                   (SELECT COUNT(*) FROM videos WHERE user_id = u.id AND is_hidden = 0) AS video_count
            FROM users u
            WHERE u.is_banned = 0
              AND u.username LIKE %s
              AND u.id != %s
            ORDER BY video_count DESC
            LIMIT 10
        """, (like, user_id))
        users = cur.fetchall()

    return jsonify({
        "videos": [{
            "id":        v["id"],
            "caption":   v["caption"] or "",
            "likes":     v["likes"],
            "video_url": v["video_url"],
            "username":  v["username"],
            "user_id":   v["user_id"],
        } for v in videos],
        "users": [{
            "id":          u["id"],
            "username":    u["username"],
            "video_count": u["video_count"],
        } for u in users],
    })


# ── ПРОФИЛЬ ДРУГОГО ПОЛЬЗОВАТЕЛЯ ──────────────────────────────────────────────
@app.route("/api/user/<username>")
@login_required
@not_banned
def api_user_profile(username):
    my_id = session["user_id"]

    with get_db() as (conn, cur):
        cur.execute(
            "SELECT id, username, created_at FROM users WHERE username=%s AND is_banned=0",
            (username,)
        )
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        uid = user["id"]

        # Видео пользователя
        cur.execute("""
            SELECT id, caption, likes, video_url, created_at
            FROM videos
            WHERE user_id=%s AND is_hidden=0
            ORDER BY created_at DESC LIMIT 30
        """, (uid,))
        videos = cur.fetchall()

        # Количество репостов
        cur.execute("""
            SELECT COUNT(*) AS c FROM video_reposts vr
            JOIN videos v ON v.id = vr.video_id
            WHERE vr.user_id=%s AND v.is_hidden=0
        """, (uid,))
        repost_count = cur.fetchone()["c"]

        # Подписчики / подписки
        cur.execute("SELECT COUNT(*) AS c FROM follows WHERE following_id=%s", (uid,))
        followers_count = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM follows WHERE follower_id=%s", (uid,))
        following_count = cur.fetchone()["c"]

        # Подписан ли текущий пользователь
        cur.execute(
            "SELECT id FROM follows WHERE follower_id=%s AND following_id=%s",
            (my_id, uid)
        )
        is_following = cur.fetchone() is not None

    return jsonify({
        "id":              uid,
        "username":        user["username"],
        "joined":          user["created_at"].strftime("%B %Y"),
        "video_count":     len(videos),
        "repost_count":    repost_count,
        "followers_count": followers_count,
        "following_count": following_count,
        "is_following":    is_following,
        "videos": [{
            "id":        v["id"],
            "likes":     v["likes"],
            "video_url": v["video_url"] or f"/video/{v['id']}",
        } for v in videos],
    })


# ── ПОДПИСКИ / ФОЛЛОВЕРЫ ──────────────────────────────────────────────────────
@app.route("/api/follow/<username>", methods=["POST"])
@login_required
@not_banned
def toggle_follow(username):
    my_id = session["user_id"]

    with get_db() as (conn, cur):
        cur.execute(
            "SELECT id FROM users WHERE username=%s AND is_banned=0",
            (username,)
        )
        target = cur.fetchone()
        if not target:
            return jsonify({"ok": False, "error": "Пользователь не найден"}), 404

        target_id = target["id"]
        if target_id == my_id:
            return jsonify({"ok": False, "error": "Нельзя подписаться на себя"}), 400

        cur.execute(
            "SELECT id FROM follows WHERE follower_id=%s AND following_id=%s",
            (my_id, target_id)
        )
        existing = cur.fetchone()

        if existing:
            # Отписаться
            cur.execute(
                "DELETE FROM follows WHERE follower_id=%s AND following_id=%s",
                (my_id, target_id)
            )
            following = False
        else:
            # Подписаться
            cur.execute(
                "INSERT INTO follows (follower_id, following_id) VALUES (%s, %s)",
                (my_id, target_id)
            )
            # Уведомление
            cur.execute(
                "INSERT INTO notifications (user_id, from_user, type) VALUES (%s, %s, 'follow')",
                (target_id, my_id)
            )
            socketio.emit("notification", {"type": "follow"}, room=f"user_{target_id}")
            following = True

        conn.commit()

    logger.info(f"FOLLOW | user={my_id} → {username} | following={following}")
    return jsonify({"ok": True, "following": following})


# ── ДАННЫЕ ДЛЯ ПРОФИЛЯ (обновлённый — теперь с followers/following) ───────────
@app.route("/api/profile/extended")
@login_required
def profile_extended():
    user_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute("SELECT COUNT(*) AS c FROM follows WHERE following_id=%s", (user_id,))
        followers_count = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) AS c FROM follows WHERE follower_id=%s", (user_id,))
        following_count = cur.fetchone()["c"]

        # Список подписчиков
        cur.execute("""
            SELECT u.username FROM follows f
            JOIN users u ON u.id = f.follower_id
            WHERE f.following_id=%s AND u.is_banned=0
            ORDER BY f.created_at DESC LIMIT 100
        """, (user_id,))
        followers = cur.fetchall()

        # Список подписок
        cur.execute("""
            SELECT u.username FROM follows f
            JOIN users u ON u.id = f.following_id
            WHERE f.follower_id=%s AND u.is_banned=0
            ORDER BY f.created_at DESC LIMIT 100
        """, (user_id,))
        following = cur.fetchall()

    return jsonify({
        "followers_count": followers_count,
        "following_count": following_count,
        "followers":       [{"username": r["username"]} for r in followers],
        "following":       [{"username": r["username"]} for r in following],
    })

# ___DM-VIDEO____________________________________
@app.route("/api/video/url/<int:video_id>")
@login_required
def api_video_url(video_id):
    with get_db() as (conn, cur):
        cur.execute(
            "SELECT video_url FROM videos WHERE id=%s AND is_hidden=0",
            (video_id,)
        )
        row = cur.fetchone()
    if not row or not row["video_url"]:
        return jsonify({"ok": False}), 404
    return jsonify({"ok": True, "url": row["video_url"]})

# ── ADMIN API ─────────────────────────────────────────────────────────────────

@app.route("/api/admin/check")
@login_required
def admin_check():
    is_admin = session.get("username") in ADMIN_USERNAMES
    return jsonify({"is_admin": is_admin})

@app.route("/api/admin/stats")
@login_required
@admin_required
def admin_stats():
    with get_db() as (conn, cur):
        cur.execute("SELECT COUNT(*) AS c FROM users")
        users_count = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM videos WHERE is_hidden=0")
        videos_count = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM users WHERE is_banned=1")
        banned_count = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM reports WHERE is_read=0")
        reports_count = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM direct_messages")
        dm_count = cur.fetchone()["c"]
    return jsonify({
        "users": users_count,
        "videos": videos_count,
        "banned": banned_count,
        "reports": reports_count,
        "dms": dm_count
    })

@app.route("/api/admin/users")
@login_required
@admin_required
def admin_users():
    q = request.args.get("q", "").strip()
    with get_db() as (conn, cur):
        if q:
            cur.execute("""
                SELECT id, username, email, is_banned, ban_reason, created_at
                FROM users WHERE username LIKE %s OR email LIKE %s
                ORDER BY created_at DESC LIMIT 50
            """, (f"%{q}%", f"%{q}%"))
        else:
            cur.execute("""
                SELECT id, username, email, is_banned, ban_reason, created_at
                FROM users ORDER BY created_at DESC LIMIT 100
            """)
        users = cur.fetchall()
    return jsonify([{
        "id": u["id"],
        "username": u["username"],
        "email": u["email"],
        "is_banned": bool(u["is_banned"]),
        "ban_reason": u["ban_reason"] or "",
        "created_at": u["created_at"].strftime("%d.%m.%Y")
    } for u in users])

@app.route("/api/admin/ban/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def admin_ban(user_id):
    data = request.get_json(silent=True) or {}
    reason = sanitize_text(data.get("reason", "нарушение правил"), 255)
    with get_db() as (conn, cur):
        cur.execute("SELECT username FROM users WHERE id=%s", (user_id,))
        u = cur.fetchone()
        if not u:
            return jsonify({"ok": False, "error": "Пользователь не найден"}), 404
        if u["username"] in ADMIN_USERNAMES:
            return jsonify({"ok": False, "error": "Нельзя заблокировать админа"}), 403
        cur.execute(
            "UPDATE users SET is_banned=1, ban_reason=%s WHERE id=%s",
            (reason, user_id)
        )
        conn.commit()
    logger.info(f"ADMIN BAN | user={user_id} reason={reason}")
    return jsonify({"ok": True})

@app.route("/api/admin/unban/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def admin_unban(user_id):
    with get_db() as (conn, cur):
        cur.execute("UPDATE users SET is_banned=0, ban_reason=NULL WHERE id=%s", (user_id,))
        conn.commit()
    logger.info(f"ADMIN UNBAN | user={user_id}")
    return jsonify({"ok": True})

@app.route("/api/admin/delete-video/<int:video_id>", methods=["DELETE"])
@login_required
@admin_required
def admin_delete_video(video_id):
    with get_db() as (conn, cur):
        cur.execute("SELECT id FROM videos WHERE id=%s", (video_id,))
        if not cur.fetchone():
            return jsonify({"ok": False, "error": "Видео не найдено"}), 404
        cur.execute("DELETE FROM video_likes   WHERE video_id=%s", (video_id,))
        cur.execute("DELETE FROM video_reposts WHERE video_id=%s", (video_id,))
        cur.execute("DELETE FROM comments      WHERE video_id=%s", (video_id,))
        cur.execute("DELETE FROM notifications WHERE video_id=%s", (video_id,))
        cur.execute("DELETE FROM videos        WHERE id=%s", (video_id,))
        conn.commit()
    socketio.emit("video_deleted", {"video_id": video_id})
    logger.info(f"ADMIN DELETE VIDEO | video={video_id}")
    return jsonify({"ok": True})

@app.route("/api/admin/videos")
@login_required
@admin_required
def admin_videos():
    q = request.args.get("q", "").strip()
    with get_db() as (conn, cur):
        if q:
            cur.execute("""
                SELECT v.id, v.caption, v.likes, v.created_at, u.username, u.id AS user_id
                FROM videos v JOIN users u ON u.id=v.user_id
                WHERE v.is_hidden=0 AND (u.username LIKE %s OR v.caption LIKE %s)
                ORDER BY v.created_at DESC LIMIT 50
            """, (f"%{q}%", f"%{q}%"))
        else:
            cur.execute("""
                SELECT v.id, v.caption, v.likes, v.created_at, u.username, u.id AS user_id
                FROM videos v JOIN users u ON u.id=v.user_id
                WHERE v.is_hidden=0
                ORDER BY v.created_at DESC LIMIT 100
            """)
        videos = cur.fetchall()
    return jsonify([{
        "id": v["id"],
        "caption": v["caption"] or "",
        "likes": v["likes"],
        "username": v["username"],
        "user_id": v["user_id"],
        "created_at": v["created_at"].strftime("%d.%m.%Y")
    } for v in videos])

@app.route("/api/admin/reports")
@login_required
@admin_required
def admin_reports():
    with get_db() as (conn, cur):
        cur.execute("""
            SELECT r.id, r.reason, r.is_read, r.created_at,
                   u.username AS from_username, r.video_id
            FROM reports r
            JOIN users u ON u.id=r.from_user
            ORDER BY r.created_at DESC LIMIT 100
        """)
        reports = cur.fetchall()
        cur.execute("UPDATE reports SET is_read=1 WHERE is_read=0")
        conn.commit()
    return jsonify([{
        "id": r["id"],
        "reason": r["reason"],
        "is_read": bool(r["is_read"]),
        "from_username": r["from_username"],
        "video_id": r["video_id"],
        "created_at": r["created_at"].strftime("%d.%m.%Y %H:%M")
    } for r in reports])

@app.route("/api/admin/report", methods=["POST"])
@login_required
@not_banned
def submit_report():
    """Пользователь отправляет жалобу на видео."""
    data = request.get_json(silent=True) or {}
    video_id = data.get("video_id")
    reason = sanitize_text(data.get("reason", ""), 500)
    if not reason:
        return jsonify({"ok": False, "error": "Укажите причину"})
    with get_db() as (conn, cur):
        cur.execute(
            "INSERT INTO reports (from_user, video_id, reason) VALUES (%s,%s,%s)",
            (session["user_id"], video_id, reason)
        )
        conn.commit()
    # Уведомление админу через socket
    socketio.emit("admin_report", {"video_id": video_id, "reason": reason})
    return jsonify({"ok": True})

@app.route("/api/admin/dms")
@login_required
@admin_required
def admin_dms():
    q = request.args.get("q", "").strip()
    with get_db() as (conn, cur):
        if q:
            cur.execute("""
                SELECT dm.id, dm.text, dm.created_at,
                       u1.username AS from_username,
                       u2.username AS to_username
                FROM direct_messages dm
                JOIN users u1 ON u1.id=dm.from_user
                JOIN users u2 ON u2.id=dm.to_user
                WHERE u1.username LIKE %s OR u2.username LIKE %s
                ORDER BY dm.created_at DESC LIMIT 100
            """, (f"%{q}%", f"%{q}%"))
        else:
            cur.execute("""
                SELECT dm.id, dm.text, dm.created_at,
                       u1.username AS from_username,
                       u2.username AS to_username
                FROM direct_messages dm
                JOIN users u1 ON u1.id=dm.from_user
                JOIN users u2 ON u2.id=dm.to_user
                ORDER BY dm.created_at DESC LIMIT 200
            """)
        dms = cur.fetchall()
    return jsonify([{
        "id": d["id"],
        "text": d["text"],
        "from": d["from_username"],
        "to": d["to_username"],
        "time": d["created_at"].strftime("%d.%m.%Y %H:%M")
    } for d in dms])

@app.route("/api/admin/broadcast", methods=["POST"])
@login_required
@admin_required
def admin_broadcast():
    """Отправить сообщение всем пользователям от имени системы."""
    data = request.get_json(silent=True) or {}
    text = sanitize_text(data.get("text", ""), 1000)
    if not text:
        return jsonify({"ok": False, "error": "Пустое сообщение"})
    admin_id = session["user_id"]
    with get_db() as (conn, cur):
        cur.execute(
            "SELECT id FROM users WHERE is_banned=0 AND id != %s",
            (admin_id,)
        )
        users = cur.fetchall()
        for u in users:
            cur.execute(
                "INSERT INTO direct_messages (from_user, to_user, text) VALUES (%s,%s,%s)",
                (admin_id, u["id"], f"📢 {text}")
            )
            socketio.emit("new_message", {
                "from_user_id": admin_id,
                "username": "Armen_Admin",
                "text": f"📢 {text}",
                "time": "сейчас"
            }, room=f"user_{u['id']}")
        conn.commit()
    logger.info(f"ADMIN BROADCAST | len={len(users)} msg={text[:50]}")
    return jsonify({"ok": True, "sent_to": len(users)})

# ── ЗАПУСК ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if init_db():
        if NGROK_TOKEN:
            try:
                ngrok.set_auth_token(NGROK_TOKEN)
                ngrok.kill()
                time.sleep(2)
                tunnel = ngrok.connect(5000, bind_tls=True)
                logger.info(f"Публичный URL: {tunnel.public_url}")
            except Exception as e:
                logger.error(f"ngrok: {e}")
        socketio.run(app, host="0.0.0.0", port=5000, debug=False)
    else:
        logger.error("Не удалось подключиться к БД")