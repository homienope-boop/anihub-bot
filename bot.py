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
from aiogram import types
import re

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
ADMIN_ID = os.getenv('ADMIN_ID')

ADMIN_ID = int(ADMIN_ID)
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

    # Экранирование для MarkdownV2 и указание parse_mode
    await message.answer(
        escape_md(welcome_text),
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2
    )

# --- Команда /add (старт пошагового ввода) ---
@dp.message(Command("add"))
async def add_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ Только админ может добавлять аниме.")
    await message.answer("Введите название аниме:")
    await state.set_state(AddAnime.title)

# --- Пошаговое добавление аниме ---
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
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(anime, f, ensure_ascii=False, indent=2)
        await message.answer(f"✅ Аниме **{data.get('title')}** успешно добавлено!")
        await state.clear()

# --- Команда /delete ---
@dp.message()
async def delete_anime(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    # Проверяем, что сообщение начинается с /delete
    if not message.text.lower().startswith("/delete"):
        return

    # Получаем всё, что идёт после команды
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

# --- Инлайн-поиск с безопасным Markdown ---
@dp.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query.lower()
    anime = load_anime()
    results = []

    for i, item in enumerate(anime):
        title = item.get("title", "")
        if query in title.lower():
            # Получаем жанры и превращаем в строку
            genre_list = item.get("genre", [])
            if isinstance(genre_list, list):
                genre = ", ".join(genre_list)
            else:
                genre = str(genre_list)

            year = item.get("year", "—")
            episodes = item.get("episodes", "—")
            description = item.get("description", "")
            link = item.get("link", "")

            text = (
                f"🎬 {title}\n"
                f"👉 Ссылка: {link}"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔍 Поискать ещё",
                    switch_inline_query_current_chat=""
                )]
            ])

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


    # Если ничего не найдено, тоже добавляем кнопку
    if not results and query:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔍 Поискать ещё",
                switch_inline_query_current_chat=""
            )]
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

@dp.channel_post()
async def channel_handler(message: Message):
    # --- Проверяем, что это нужный канал ---
    if message.chat.username != "anime_anihub_4k":
        return

    text = message.text or ""

    # --- Проверяем, есть ли аниме-контент ---
    if not any(tag in text for tag in ["📜", "🎙", "🍜", "сезон"]):
        # Если нет ключевых маркеров, игнорируем пост
        return

    anime = load_anime()

    # --- Title ---
    lines = text.splitlines()
    title_line = next((l.strip() for l in lines if l and "🟠" not in l), None)
    if title_line:
        # Убираем эмодзи
        title = re.sub(r'[^\w\s\d.,!?-]', '', title_line).strip()
    else:
        title = "Без названия"

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
        genre = [g.replace("#", "").strip() for g in gblock.split() if g.startswith("#")]

    # --- Эпизоды / Сезон / Год ---
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

    # --- Прямая ссылка на пост ---
    link = f"https://t.me/{message.chat.username}/{message.message_id}"

    # --- Добавляем запись в JSON ---
    anime.append({
        "title": title,
        "link": link,
        "season": season,
        "genre": genre,
        "year": year,
        "voice": voice,
        "description": desc
    })

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
