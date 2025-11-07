import json
import asyncio
import re
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.state import StateFilter
from aiogram.enums import ParseMode
import os
from dotenv import load_dotenv
from aiogram.types import Message

emoji_pattern = re.compile(
    "[" 
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)

def remove_emoji(text: str) -> str:
    return emoji_pattern.sub("", text).strip()

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

# --- Экранирование для MarkdownV2 ---
def escape_md(text: str) -> str:
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

# --- Состояния для добавления аниме ---
class AddAnime(StatesGroup):
    title = State()
    link = State()
    season = State()
    genre = State()
    year = State()
    episodes = State()
    description = State()

# --- Команда /start ---
@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🔍 Поискать", switch_inline_query_current_chat="")
        ]]
    )

    welcome_text = (
        "👋 Привет! Добро пожаловать в Anihub — твой пропуск в мир качественного аниме! \n\n"
        "Здесь ты можешь найти:\n"
        "🎬 Любимые классические и новые аниме в 4К качестве\n"
        "🎭 Топовые подборки по жанрам: сёнэн, сёдзё, ужасы, фэнтези, комедии и многое другое\n\n"
        "Нажми кнопку ниже, чтобы сразу начать поиск любимого аниме:"
    )

    await message.answer(
        escape_md(welcome_text),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2
    )

# --- Команда /add ---
@dp.message(Command("add"))
async def add_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Только админ может добавлять аниме.")
    await message.answer("Введите название аниме:")
    await state.set_state(AddAnime.title)

# --- Пошаговое добавление ---
@dp.message(StateFilter(AddAnime))
async def add_wizard(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state == AddAnime.title.state:
        await state.update_data(title=message.text)
        await message.answer("Введите ссылку на аниме:")
        await state.set_state(AddAnime.link)

    elif current_state == AddAnime.link.state:
        await state.update_data(link=message.text)
        await message.answer("Введите сезон (числом, если нет — оставьте пустым):")
        await state.set_state(AddAnime.season)

    elif current_state == AddAnime.season.state:
        season = int(message.text) if message.text.isdigit() else None
        await state.update_data(season=season)
        await message.answer("Введите жанр:")
        await state.set_state(AddAnime.genre)

    elif current_state == AddAnime.genre.state:
        await state.update_data(genre=message.text)
        await message.answer("Введите год выпуска:")
        await state.set_state(AddAnime.year)

    elif current_state == AddAnime.year.state:
        year = int(message.text) if message.text.isdigit() else None
        await state.update_data(year=year)
        await message.answer("Введите количество серий (если неизвестно — оставьте пустым):")
        await state.set_state(AddAnime.episodes)

    elif current_state == AddAnime.episodes.state:
        episodes = int(message.text) if message.text.isdigit() else None
        await state.update_data(episodes=episodes)
        await message.answer("Введите описание аниме:")
        await state.set_state(AddAnime.description)

    elif current_state == AddAnime.description.state:
        await state.update_data(description=message.text)
        data = await state.get_data()
        anime = load_anime()
        anime.append({
            "title": data.get("title"),
            "link": data.get("link"),
            "season": data.get("season"),
            "genre": data.get("genre"),
            "year": data.get("year"),
            "episodes": data.get("episodes"),
            "description": data.get("description")
        })

        # --- Сортировка по title ---
        anime.sort(key=lambda x: x["title"].lower())

        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(anime, f, ensure_ascii=False, indent=2)

        await message.answer(f"✅ Аниме **{data.get('title')}** успешно добавлено!")
        await state.clear()

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
            anime.sort(key=lambda x: x["title"].lower())
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
            genre_list = item.get("genre", [])
            genre = ", ".join(genre_list) if isinstance(genre_list, list) else str(genre_list)
            year = item.get("year", "—")
            link = item.get("link", "")
            text = f"🎬 {title}\n👉 Ссылка: {link}"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Поискать ещё", switch_inline_query_current_chat="")]
            ])

            results.append(
                InlineQueryResultArticle(
                    id=str(i),
                    title=title,
                    description=f"{year} | {genre}",
                    input_message_content=InputTextMessageContent(message_text=text),
                    reply_markup=keyboard
                )
            )

    if not results and query:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Поискать ещё", switch_inline_query_current_chat="")]
        ])
        results.append(
            InlineQueryResultArticle(
                id="0",
                title="❌ Ничего не найдено",
                input_message_content=InputTextMessageContent("Аниме не найдено в базе."),
                reply_markup=keyboard
            )
        )

    await inline_query.answer(results, cache_time=1, is_personal=True)

# --- Обработка постов канала ---
@dp.channel_post()
async def channel_handler(message: Message):
    if message.chat.username != CHANNEL_USERNAME:
        return

    text = message.text or ""
    if not any(tag in text for tag in ["📜", "🎙", "🍜", "сезон"]):
        return

    anime = load_anime()
    lines = text.splitlines()

    # Title без эмодзи
    title_line = next((l.strip() for l in lines if l and "🟠" not in l), None)
    title = re.sub(r'[^\w\s\d.,!?-]', '', title_line).strip() if title_line else "Без названия"

    # Description
    desc = text.split("📜")[1].split("🎙")[0].strip() if "📜" in text and "🎙" in text else ""

    # Voice
    voice = []
    if "🎙" in text:
        vblock = text.split("🎙")[1].split("\n")[1].strip()
        voice = [v.replace("#", "").strip() for v in re.split(r'[,\s]+', vblock) if v.startswith("#")]

    # Genre
    genre = []
    if "🍜" in text:
        gblock = text.split("🍜")[1].split("\n")[1]
        genre = [
            g.replace("#", "").replace(",", "").strip()  # убираем # и запятые
            for g in gblock.split() if g.startswith("#")
        ]

    # Season / Year
    season = None
    year = None
    for line in lines:
        if "сезон" in line.lower():
            match = re.search(r"(\d+)\s*сезон", line.lower())
            if match:
                season = int(match.group(1))
        if "#" in line:
            match = re.search(r"#(\d{4})", line)
            if match:
                year = int(match.group(1))

    link = f"https://t.me/{message.chat.username}/{message.message_id}"

    anime.append({
        "title": title,
        "link": link,
        "season": season,
        "genre": genre,
        "year": year,
        "voice": voice,
        "description": desc
    })

    # --- Сортировка по title ---
    anime.sort(key=lambda x: x["title"].lower())

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(anime, f, ensure_ascii=False, indent=2)

    await bot.send_message(
        ADMIN_ID,
        f"✅ Добавлено новое аниме:\n\n"
        f"Название: {title}\n"
        f"Сезон: {season if season else '—'}\n"
        f"Жанр: {', '.join(genre) if genre else '—'}\n"
        f"Год: {year if year else '—'}\n"
        f"Озвучка: {', '.join(voice) if voice else '—'}\n"
        f"Описание: {desc if desc else '—'}\n"
        f"Ссылка на пост: {link}"
    )

# --- Запуск бота ---
async def main():
    print("Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
