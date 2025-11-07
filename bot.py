import json
import asyncio
import re
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

# --- Экранирование эмодзи ---
emoji_pattern = re.compile(
    "[" 
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)
def remove_emoji(text: str) -> str:
    return emoji_pattern.sub("", text).strip()

# --- Загрузка .env ---
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
FILE = "anime_list.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- Загрузка базы ---
def load_anime():
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# --- Экранирование MarkdownV2 ---
def escape_md(text: str) -> str:
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

# --- Команда /start ---
@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔍 Поискать", switch_inline_query_current_chat="")]]
    )
    welcome_text = (
        "👋 Привет! Добро пожаловать в Anihub — твой пропуск в мир качественного аниме! \n\n"
        "Здесь ты можешь найти:\n"
        "🎬 Любимые классические и новые аниме в 4К качестве\n"
        "🎭 Топовые подборки по жанрам: сёнэн, сёдзё, ужасы, фэнтези, комедии и многое другое\n\n"
        "Нажми кнопку ниже, чтобы сразу начать поиск любимого аниме:"
    )
    await message.answer(escape_md(welcome_text), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)

# --- Команда /delete ---
@dp.message()
async def delete_anime(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text.lower().startswith("/delete"):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Используй: /delete <название аниме>")
    title = parts[1].strip()
    anime = load_anime()
    for item in anime:
        if item["title"].lower() == title.lower():
            anime.remove(item)
            with open(FILE, "w", encoding="utf-8") as f:
                json.dump(anime, f, ensure_ascii=False, indent=2)
            return await message.answer(f"🗑 Аниме **{title}** удалено.")
    await message.answer(f"❌ Аниме **{title}** не найдено в базе.")

# --- Инлайн-поиск ---
@dp.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query.lower()
    anime = load_anime()
    results = []

    for i, item in enumerate(anime):
        title = item.get("title", "")
        if query in title.lower():
            # --- Жанр ---
            genre_list = item.get("genre", [])
            genre = ", ".join(genre_list) if isinstance(genre_list, list) else str(genre_list)

            # --- Сезон ---
            season_list = item.get("season", [])
            season = ", ".join(map(str, season_list)) if season_list else "—"

            # --- Год ---
            year_list = item.get("year", [])
            year = ", ".join(map(str, year_list)) if year_list else "—"

            # --- Эпизоды ---
            episodes_list = item.get("episodes", [])
            episodes = ", ".join(map(str, episodes_list)) if episodes_list else "—"

            # --- Рейтинг ---
            rating_list = item.get("rating", [])
            rating = ", ".join(map(str, rating_list)) if rating_list else "—"

            # --- Ссылка ---
            link = item.get("link", "")

            text = (
                f"🎬 {title}\n"
                f"📅 Год: {year}\n"
                f"🎭 Жанр: {genre}\n"
                f"📺 Сезоны: {season}\n"
                f"📝 Эпизоды: {episodes}\n"
                f"⭐️ Рейтинг: {rating}\n"
                f"👉 Ссылка: {link}"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔍 Поискать ещё",
                    switch_inline_query_current_chat=""
                )
            ]])

            results.append(
                InlineQueryResultArticle(
                    id=str(i),
                    title=title,
                    description=f"{year} | {genre}",
                    input_message_content=InputTextMessageContent(
                        message_text=text
                    ),
                    reply_markup=keyboard
                )
            )

    if not results and query:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔍 Поискать ещё",
                switch_inline_query_current_chat=""
            )
        ]])
        results.append(
            InlineQueryResultArticle(
                id="0",
                title="❌ Ничего не найдено",
                input_message_content=InputTextMessageContent("Аниме не найдено в базе."),
                reply_markup=keyboard
            )
        )

    await inline_query.answer(results, cache_time=1, is_personal=True)


# --- Обработка канала ---
@dp.channel_post()
async def channel_handler(message: Message):
    if message.chat.username != CHANNEL_USERNAME:
        return

    text = message.text or ""
    if not any(tag in text for tag in ["📜", "🎙", "🍜", "сезон"]):
        return

    anime = load_anime()
    lines = text.splitlines()

    # --- Title без эмодзи ---
    title_line = next((l.strip() for l in lines if l and "🟠" not in l), None)
    title = re.sub(r'[^\w\s\d.,!?-]', '', title_line).strip() if title_line else "Без названия"

    # --- Description ---
    desc = ""
    if "📜" in text and "🎙" in text:
        desc = text.split("📜")[1].split("🎙")[0].strip()

    # --- Озвучка ---
    voice = []
    if "🎙" in text:
        vblock = text.split("🎙")[1].split("\n")[1].strip()
        voice = [v.replace("#", "").strip() for v in re.split(r'[,\s]+', vblock) if v.startswith("#")]

    # --- Жанры ---
    genre = []
    if "🍜" in text:
        gblock = text.split("🍜")[1].split("\n")[1]
        genre = [g.replace("#", "").replace(",", "").strip() for g in gblock.split() if g.startswith("#")]

    # --- Сезоны, эпизоды, годы, рейтинг ---
    season_list = []
    episodes_list = []
    year_list = []
    rating_list = []

    for line in lines:
        # Сезон
        if "сезон" in line.lower():
            match = re.search(r"(\d+)\s*сезон", line.lower())
            if match:
                season_list.append(int(match.group(1)))

            # Эпизоды и рейтинг
            ep_match = re.search(r"(\d+)/\d+", line)
            if ep_match:
                episodes_list.append(int(ep_match.group(1)))

            rate_match = re.search(r"⭐️([\d.]+)", line)
            if rate_match:
                rating_list.append(float(rate_match.group(1)))

            # Год
            year_match = re.search(r"#(\d{4})", line)
            if year_match:
                year_list.append(int(year_match.group(1)))

    # --- Ссылка на пост ---
    link = f"https://t.me/{message.chat.username}/{message.message_id}"

    # --- Добавляем в JSON ---
    anime.append({
        "title": title,
        "link": link,
        "season": season_list,
        "episodes": episodes_list,
        "genre": genre,
        "year": year_list,
        "voice": voice,
        "rating": rating_list,
        "description": desc
    })

    # Сортировка по title
    anime = sorted(anime, key=lambda x: x["title"].lower())

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(anime, f, ensure_ascii=False, indent=2)

    await bot.send_message(
        ADMIN_ID,
        f"✅ Добавлено новое аниме:\n\n"
        f"Название: {title}\n"
        f"Сезон: {', '.join(map(str, season_list)) if season_list else '—'}\n"
        f"Жанр: {', '.join(genre) if genre else '—'}\n"
        f"Год: {', '.join(map(str, year_list)) if year_list else '—'}\n"
        f"Озвучка: {', '.join(voice) if voice else '—'}\n"
        f"Эпизоды: {', '.join(map(str, episodes_list)) if episodes_list else '—'}\n"
        f"Рейтинг: {', '.join(map(str, rating_list)) if rating_list else '—'}\n"
        f"Ссылка на пост: {link}"
    )


# --- Запуск бота ---
async def main():
    print("Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())