import os
import logging
import random
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import List, Tuple
from enum import Enum
import pytz

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# Конфигурация
BOT_NAME = "MatchMaker"
BOT_TAG = "@cs_maps_bot"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = []  # ID администраторов для служебных команд
TIMEZONE = pytz.timezone('Europe/Moscow')  # Укажите свою временную зону


# Глобальные переменные для хранения данных
class MapStatus(Enum):
    AVAILABLE = "available"
    COOLDOWN = "cooldown"


# Список карт Counter-Strike (можно расширить)
ALL_MAPS = [
    "de_dust2", "de_mirage", "de_inferno", "de_nuke", "de_overpass",
    "de_vertigo", "de_ancient", "de_anubis", "de_cache", "de_cbble",
    "de_train", "de_tuscan", "de_season", "de_contra", "de_santorini",
    "de_zoo", "de_engage", "de_elysion", "de_biome", "de_mocha"
]

# Хранение данных
maps_cooldown = {}  # карта: сколько голосований в кд
active_polls = {}  # chat_id: данные опроса
map_wins_count = defaultdict(int)  # карта: количество побед
voting_history = deque(maxlen=5)  # история последних 5 победивших карт

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_available_maps() -> List[str]:
    """Получить список доступных карт (не в кд)"""
    available = []
    for map_name in ALL_MAPS:
        if map_name not in voting_history:
            available.append(map_name)
    return available if available else ALL_MAPS.copy()


def select_map_options() -> List[str]:
    """Выбрать 12 случайных карт из доступных"""
    available_maps = get_available_maps()
    return random.sample(available_maps, min(12, len(available_maps)))


async def schedule_map_announcement(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                                    scheduled_time: datetime, num_maps: int):
    """Запланировать публикацию результатов за 5 минут до времени"""
    announcement_time = scheduled_time - timedelta(minutes=5)
    current_time = datetime.now(TIMEZONE)

    if announcement_time > current_time:
        delay = (announcement_time - current_time).total_seconds()
        context.job_queue.run_once(
            announce_winner_maps,
            delay,
            chat_id=chat_id,
            data={'num_maps': num_maps, 'poll_data': active_polls.get(chat_id)}
        )


async def create_polls(chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                       num_maps: int, scheduled_time_str: str) -> Tuple[int, int]:
    """Создать два опроса и вернуть их message_id"""
    # Опрос регистрации
    registration_poll = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"Регистрация на игру в {scheduled_time_str}",
        options=["+", "-"],
        is_anonymous=False,
        allows_multiple_answers=False
    )

    # Опрос выбора карт
    map_options = select_map_options()
    map_poll = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"Выберите карты для игры в {scheduled_time_str}",
        options=map_options,
        is_anonymous=True,
        allows_multiple_answers=True
    )

    return registration_poll.message_id, map_poll.message_id


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Привет! Я бот для организации голосований за карты в CS.\n\n"
        "Чтобы начать голосование, упомяните меня в группе с командой:\n"
        f"{BOT_TAG} HH:MM количество_карт\n\n"
        f"Пример: {BOT_TAG} 16:00 2"
    )


async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик упоминания бота в группе"""
    if not update.message or not update.message.text:
        return

    # Проверяем, что сообщение содержит упоминание бота
    if not context.bot.username or f"@{context.bot.username}" not in update.message.text:
        return

    # Извлекаем команду после упоминания
    text = update.message.text.replace(f"@{context.bot.username}", "").strip()

    try:
        # Парсим время и количество карт
        time_str, num_maps_str = text.split()

        # Проверяем формат времени
        scheduled_time = datetime.strptime(time_str, "%H:%M").time()

        # Проверяем количество карт
        num_maps = int(num_maps_str)
        if num_maps < 1 or num_maps > 12:
            await update.message.reply_text("Количество карт должно быть от 1 до 12")
            return

        # Создаем дату с учетом сегодняшнего дня
        current_date = datetime.now(TIMEZONE).date()
        scheduled_datetime = datetime.combine(current_date, scheduled_time)
        scheduled_datetime = TIMEZONE.localize(scheduled_datetime)

        # Проверяем, что время в будущем
        if scheduled_datetime <= datetime.now(TIMEZONE):
            await update.message.reply_text("Укажите время в будущем!")
            return

        # Создаем опросы
        reg_poll_id, map_poll_id = await create_polls(
            update.message.chat_id,
            context,
            num_maps,
            time_str
        )

        # Сохраняем информацию об активном опросе
        active_polls[update.message.chat_id] = {
            'registration_poll_id': reg_poll_id,
            'map_poll_id': map_poll_id,
            'scheduled_time': scheduled_datetime,
            'num_maps': num_maps,
            'map_options': select_map_options()
        }

        # Планируем объявление результатов
        await schedule_map_announcement(
            context,
            update.message.chat_id,
            scheduled_datetime,
            num_maps
        )

    except ValueError as e:
        await update.message.reply_text(
            "Неверный формат команды. Используйте:\n"
            f"{BOT_TAG} HH:MM количество_карт\n"
            f"Пример: {BOT_TAG} 16:00 2"
        )
    except Exception as e:
        logger.error(f"Error creating polls: {e}")
        await update.message.reply_text("Произошла ошибка при создании опросов")


async def announce_winner_maps(context: ContextTypes.DEFAULT_TYPE):
    """Объявить победившие карты"""
    job = context.job
    chat_id = job.chat_id
    num_maps = job.data['num_maps']
    poll_data = job.data['poll_data']

    if not poll_data or chat_id not in active_polls:
        return

    try:
        # Получаем результаты опроса карт
        map_poll = await context.bot.stop_poll(
            chat_id,
            poll_data['map_poll_id']
        )

        # Сортируем карты по количеству голосов
        map_votes = [
            (option.text, option.voter_count)
            for option in map_poll.options
        ]

        # Сортируем: сначала по голосам (убывание), потом по количеству побед (возрастание)
        map_votes.sort(key=lambda x: (-x[1], map_wins_count[x[0]]))

        # Выбираем победителей
        winners = [map_name for map_name, _ in map_votes[:num_maps]]

        # Обновляем статистику
        for winner in winners:
            map_wins_count[winner] += 1

        # Добавляем в историю для кд
        voting_history.extend(winners)

        # Формируем сообщение с результатами
        winner_text = "\n".join([f"• {map_name}" for map_name in winners])
        message = (
            f"🏆 Победившие карты для сегодняшней игры:\n\n"
            f"{winner_text}\n\n"
            f"Удачной игры! 🎮"
        )

        await context.bot.send_message(chat_id=chat_id, text=message)

        # Удаляем информацию об опросе
        if chat_id in active_polls:
            del active_polls[chat_id]

    except Exception as e:
        logger.error(f"Error announcing winners: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="Произошла ошибка при подсчете результатов"
        )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус бота и статистику"""
    if update.effective_user.id not in ADMIN_IDS:
        return

    stats_text = "📊 Статистика бота:\n\n"
    stats_text += f"Всего карт в пуле: {len(ALL_MAPS)}\n"
    stats_text += f"Карт в кд: {len(voting_history)}\n"
    stats_text += f"Активных голосований: {len(active_polls)}\n\n"

    if map_wins_count:
        stats_text += "Победы карт:\n"
        for map_name, wins in sorted(map_wins_count.items(), key=lambda x: -x[1])[:10]:
            stats_text += f"{map_name}: {wins} побед\n"

    await update.message.reply_text(stats_text)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}")

    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла ошибка при обработке команды"
        )


def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Entity("mention"),
        handle_mention
    ))

    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print("Бот запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()