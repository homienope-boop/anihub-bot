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

# --- FSM Edit ---
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

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
CHANNEL_ID = os.getenv("CHANNEL_ID")
FILE = "anime_list.json"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

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

# --- Состояния FSM ---
class EditAnime(StatesGroup):
    choose_field = State()
    update_field = State()

# --- Команда /start с проверкой подписки ---
@dp.message(Command("start"))
async def start(message: types.Message):
    async def check_subscription(user_id):
        try:
            member = await bot.get_chat_member(chat_id=int(CHANNEL_ID), user_id=user_id)
            return member.status not in ("left", "kicked")
        except:
            return False

    if not await check_subscription(message.from_user.id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌟 Подписаться на Anihub", url=f"https://t.me/{CHANNEL_USERNAME}")],
            [InlineKeyboardButton(text="🔄 ✅ Проверить подписку", callback_data="check_sub")]
        ])
        await message.answer(
            "⛔ Бот доступен только для подписчиков Anihub.\n"
            "Подпишитесь на канал, чтобы использовать все функции бота.",
            reply_markup=keyboard
        )
        return

    # Если подписан
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

# --- Обработчик кнопки проверки подписки ---
@dp.callback_query(lambda c: c.data == "check_sub")
async def check_subscription_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=int(CHANNEL_ID), user_id=user_id)
        if member.status not in ("left", "kicked"):
            # Подписан
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔍 Поискать", switch_inline_query_current_chat="")]]
            )
            await callback.message.edit_text(
                "✅ Спасибо за подписку! Теперь вы можете использовать бот.",
                reply_markup=keyboard
            )
            return
    except:
        pass

    # Всё ещё не подписан
    await callback.answer("⛔ Вы всё ещё не подписаны на канал.", show_alert=True)

# --- Команда /edit ---
@dp.message(Command("edit"))
async def cmd_edit(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("⛔ У вас нет доступа.")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Используй: /edit <название аниме>")

    title = parts[1].strip().lower()
    anime = load_anime()

    for item in anime:
        if item["title"].lower() == title:
            await state.update_data(anime=item)
            await state.update_data(old_title=item["title"])
            return await show_edit_menu(message, state)

    await message.answer("❌ Аниме не найдено.")

# --- Меню выбора параметра с текущими значениями ---
async def show_edit_menu(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item = data["anime"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎭 Жанр: {', '.join(item.get('genre', []))}", callback_data="edit_genre")],
        [InlineKeyboardButton(text=f"📅 Год: {', '.join(map(str, item.get('year', []))) or '—'}", callback_data="edit_year")],
        [InlineKeyboardButton(text=f"📺 Сезоны: {', '.join(map(str, item.get('season', []))) or '—'}", callback_data="edit_season")],
        [InlineKeyboardButton(text=f"📝 Эпизоды: {', '.join(map(str, item.get('episodes', []))) or '—'}", callback_data="edit_episodes")],
        [InlineKeyboardButton(text=f"⭐ Рейтинг: {', '.join(map(str, item.get('rating', []))) or '—'}", callback_data="edit_rating")],
        [InlineKeyboardButton(text=f"🔊 Озвучка: {', '.join(item.get('voice', []))}", callback_data="edit_voice")],
        [InlineKeyboardButton(text=f"✏️ Описание", callback_data="edit_desc")],
        [InlineKeyboardButton(text="🚫 Удалить", callback_data="edit_delete")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel")]
    ])

    await state.set_state(EditAnime.choose_field)
    await message.answer(
        f"🔧 Редактируем: **{item['title']}**\nЧто изменить?",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2
    )

# --- Выбор поля с обработкой отмены ---
@dp.callback_query(EditAnime.choose_field)
async def choose_field(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    anime = data["anime"]

    action = callback.data.replace("edit_", "")

    # Обработка отмены
    if action == "cancel":
        await callback.message.edit_text("❌ Редактирование отменено.")
        await state.clear()
        return

    # Удаление
    if action == "delete":
        all_data = load_anime()
        all_data = [x for x in all_data if x["title"] != anime["title"]]
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        await callback.message.edit_text("🗑 Аниме удалено.")
        await state.clear()
        return

    await state.update_data(field=action)
    await state.set_state(EditAnime.update_field)
    await callback.message.answer(f"✏️ Введите новое значение для: **{action}**")


# --- Обновление значения ---
@dp.message(EditAnime.update_field)
async def update_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    field = data["field"]
    anime = data["anime"]
    new_value = message.text.strip()

    if field in ("genre", "voice"):
        new_value = [x.strip() for x in new_value.split(",")]
    elif field in ("year", "season", "episodes"):
        new_value = [int(x) for x in new_value.split(",")]
    elif field == "rating":
        new_value = [float(x) for x in new_value.split(",")]

    anime[field] = new_value

    all_data = load_anime()
    for i, item in enumerate(all_data):
        if item["title"] == data["old_title"]:
            all_data[i] = anime
            break

    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    await message.answer("✅ Изменения сохранены.")
    await show_edit_menu(message, state)

# --- Инлайн-запросы --- #
@dp.inline_query()
async def inline_search(inline_query: types.InlineQuery):
    user_id = inline_query.from_user.id

    # Проверяем подписку
    try:
        member = await bot.get_chat_member(chat_id=int(CHANNEL_ID), user_id=user_id)
        if member.status in ("left", "kicked"):
            # Пользователь не подписан
            results = [
                InlineQueryResultArticle(
                    id="not_sub",
                    title="⚠️ Только для подписчиков",
                    description="Подпишитесь на канал, чтобы использовать поиск",
                    input_message_content=InputTextMessageContent(
                        message_text="⛔ Бот доступен только для подписчиков Anihub.\n"
                                     "Подпишитесь на канал, чтобы использовать все функции."
                    ),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🌟 Подписаться на Anihub", url=f"https://t.me/{CHANNEL_USERNAME}")]
                    ])
                )
            ]
            await inline_query.answer(results, cache_time=1, is_personal=True)
            return
    except:
        results = [
            InlineQueryResultArticle(
                id="error",
                title="⚠️ Ошибка проверки подписки",
                description="Попробуйте ещё раз",
                input_message_content=InputTextMessageContent(
                    message_text="⚠️ Не удалось проверить подписку. Попробуйте позже."
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 ✅ Проверить подписку", callback_data="check_sub")]
                ])
            )
        ]
        await inline_query.answer(results, cache_time=1, is_personal=True)
        return

    # --- Пользователь подписан, показываем результаты поиска ---
    query = inline_query.query.lower()
    anime = load_anime()
    results = []

    for i, item in enumerate(anime):
        title = item.get("title", "")
        if query in title.lower():
            genre = ", ".join(item.get("genre", []))
            year = ", ".join(map(str, item.get("year", []))) or "—"
            season_list = item.get("season", [])
            season = ", ".join(map(str, season_list)) if season_list else "—"
            episodes = ", ".join(map(str, item.get("episodes", []))) or "—"
            rating_list = item.get("rating", [])
            rating = ", ".join(map(str, rating_list)) if rating_list else "—"
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
                InlineKeyboardButton(text="🔍 Поискать ещё", switch_inline_query_current_chat="") 
            ]])

            results.append(
                InlineQueryResultArticle(
                    id=str(i),
                    title=title,
                    description=f"{year} | {genre}",
                    input_message_content=InputTextMessageContent(message_text=text),
                    reply_markup=keyboard
                )
            )

    await inline_query.answer(results, cache_time=1, is_personal=True)

# --- Канал-парсер оставлен без изменений ---

@dp.channel_post()
async def channel_handler(message: Message):
    if message.chat.username != CHANNEL_USERNAME:
        return

    # ✅ Получаем текст правильно
    if message.caption:
        text = message.caption
    elif message.text:
        text = message.text
    else:
        return

    text = text.strip()

    if not any(tag in text for tag in ["📜", "🎙", "🍜", "сезон"]):
        return

    anime = load_anime()
    lines = text.splitlines()

    title_line = next((l.strip() for l in lines if l and "🟠" not in l), None)
    title = re.sub(r'[^\w\s\d.,!?-]', '', title_line).strip() if title_line else "Без названия"

    desc = ""
    if "📜" in text and "🎙" in text:
        desc = text.split("📜")[1].split("🎙")[0].strip()

    voice = []
    if "🎙" in text:
        vblock = text.split("🎙")[1].split("\n")[1].strip()
        voice = [v.replace("#", "").strip() for v in re.split(r'[,\s]+', vblock) if v.startswith("#")]

    genre = []
    if "🍜" in text:
        gblock = text.split("🍜")[1].split("\n")[1]
        genre = [g.replace("#", "").replace(",", "").strip() for g in gblock.split() if g.startswith("#")]

    season_list = []
    episodes_list = []
    year_list = []
    rating_list = []

    for line in lines:
        if "сезон" in line.lower():
            match = re.search(r"(\d+)\s*сезон", line.lower())
            if match:
                season_list.append(int(match.group(1)))

            ep_match = re.search(r"(\d+)/\d+", line)
            if ep_match:
                episodes_list.append(int(ep_match.group(1)))

            rate_match = re.search(r"⭐️([\d.]+)", line)
            if rate_match:
                rating_list.append(float(rate_match.group(1)))

            year_match = re.search(r"#(\d{4})", line)
            if year_match:
                year_list.append(int(year_match.group(1)))

    link = f"https://t.me/{message.chat.username}/{message.message_id}"

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
