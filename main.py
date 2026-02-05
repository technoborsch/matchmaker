import os
import logging
import random
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import List, Tuple
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

# Константы
RANDOM_OPTION = "🎲Случайная карта не из этого списка"

# Список карт Counter-Strike
ALL_MAPS = [
    "🏢Agency - Офисное здание с современным дизайном",
    "🌴🗿Ancient - Археологические раскопки в джунглях с ацтекскими руинами",
    "🏺Anubis - Музейный комплекс на руинах древнеегипетского храма",
    "🏭Assault - Классическая асимметричная карта со складом",
    "✈️Assembly - Площадка сборки пассажирского самолёта",
    "🌿Aztec - Древние руины в джунглях с мостами и храмами",
    "🏦Bank - Банк на улице по соседству с магазином и автомастерской",
    "⚓Barnblitz (TF2) - Портовый комплекс, адаптированный из Team Fortress 2",
    "🗻Basalt - Маленький поселок с маяком на базальтовом острове",
    "🔬Biome - Большая теплица под куполом",
    "⚓Boyard - Маленькая морская крепость с напряжёнными перестрелками",
    "☢️Cache - Заброшенная промзона в Чернобыльской зоне",
    "🇮🇹Canals - Венецианский стиль с каналами и узкими улочками",
    "🏰Cobblestone - Средневековый замок с каменными постройками",
    "🌍Debris - Маленький городок на озере в Африке с лемурами",
    "🏜️Dust - Пустынный город на Ближнем Востоке",
    "🏜️Dust II - Знаменитая пустынная карта с туннелями и длинными путями",
    "🏭Echolab - Заброшенный завод",
    "🏘️Edin - Современный шотландский город с каменными домами и узкими улицами",
    "🌿El Dorado - Маленький храм в джунглях",
    "🏘️Fachwerk - Центральноевропейский город с фахверковыми домами",
    "🎥Flick - Студия для съёмок фильмов с различными декорациями",
    "🇮🇹Ganny - Маленький итальянский город с одной точкой закладки бомбы",
    "⛏️Golden - Золотая шахта в китайском городке",
    "🍌Inferno - Карта в средиземноморском стиле с узкими улочками и знаменитым 'бананом'",
    "🍕Italy - Итальянский городок с рынком и кафе",
    "🛶Lake - Озёрный домик и пристань в лесистой местности",
    "🏡Manor - Загородный особняк с прилегающими постройками",
    "🏛️Mansion - Большой классический особняк с садом",
    "🏰Marble - Большой каменный замок",
    "💒Memento - Свадьба в замке у моря с непробиваемым тортом",
    "🎖️Militia - Усадьба в лесу с тренировочной базой",
    "🇳🇱Mills - Городок в Голландии с ветряными мельницами",
    "⛏️Minecraft - Карта, вдохновлённая стилем игры Minecraft",
    "🕌Mirage - Пустынный город с центральным двором и каналами",
    "🏔️Neptune - Военная база в северных горах",
    "☢️Nuke - Атомная электростанция с крышей и подвалом",
    "💼Office - Офисное здание с открытым планированием",
    "🌳Overpass - Мост, канал и парк в немецком городе",
    "🏖️Palacio - Португальский дворец на берегу моря",
    "🏙️Palais - Крыши домов во французском городе",
    "🚉Panama - Станция метро с переходами",
    "⛲Piranesi - Итальянская вилла с садами и фонтанами",
    "🏖️Poseidon - СПА-комплекс в Греции на берегу моря",
    "🏙️Rooftop - Крыша небоскрёба в городе",
    "🇮🇹Roonac - Маленькая карта в Тосканском дворике",
    "🏠Safehouse - Конспиративная квартира в одиноком жилом доме",
    "📚Scholar - Университетская библиотека и кампус",
    "⚓Seaside - Складской комплекс у моря",
    "⚡Short dust - Укороченная версия Dust для быстрых игр",
    "🌴Siege - Спасение заложников на заброшенной фабрике в джунглях",
    "🌴St. Marc - Маленькая карта на улочке в городе у моря с пальмами",
    "🛒Totem Lake - Закладка бомбы в торговом центре",
    "🚂Train - Железнодорожная станция с вагонами",
    "🚇Transit - Маленькая карта с проезжающим поездом",
    "🏗️Vertigo - Строящийся небоскрёб на большой высоте",
    "🚉Whistle - Маленькая карта на железнодорожной станции"
]

# Хранение данных
active_polls = {}  # chat_id: данные опроса
map_wins_count = defaultdict(int)  # карта: количество побед
voting_history = deque(maxlen=5)  # история последних 5 победивших карт

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_available_maps(exclude_list: List[str] = None) -> List[str]:
    """Получить список доступных карт (не в кд)"""
    if exclude_list is None:
        exclude_list = []

    available = []
    for map_name in ALL_MAPS:
        if map_name not in voting_history and map_name not in exclude_list:
            available.append(map_name)

    # Если все карты в кд, возвращаем все кроме тех что в exclude_list
    if not available:
        available = [map_name for map_name in ALL_MAPS if map_name not in exclude_list]

    return available


def select_map_options() -> List[str]:
    """Выбрать 11 случайных карт из доступных и добавить опцию случайной карты"""
    available_maps = get_available_maps()

    # Выбираем 11 случайных карт, если доступно столько
    selected_maps = random.sample(available_maps, min(11, len(available_maps)))

    # Добавляем опцию случайной карты
    selected_maps.append(RANDOM_OPTION)

    return selected_maps


def get_random_map_not_in_list(exclude_list: List[str]) -> str:
    """Получить случайную карту, которой нет в exclude_list и не в кд"""
    # Исключаем RANDOM_OPTION из списка
    exclude_list = [item for item in exclude_list if item != RANDOM_OPTION]

    available_maps = get_available_maps(exclude_list)

    if not available_maps:
        # Если нет доступных карт, возвращаем случайную из всех (кроме исключённых)
        all_maps_excluded = [map_name for map_name in ALL_MAPS if map_name not in exclude_list]
        if all_maps_excluded:
            return random.choice(all_maps_excluded)
        else:
            # Если все карты исключены, возвращаем первую из ALL_MAPS
            return ALL_MAPS[0]

    return random.choice(available_maps)


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
        map_options = select_map_options()
        active_polls[update.message.chat_id] = {
            'registration_poll_id': reg_poll_id,
            'map_poll_id': map_poll_id,
            'scheduled_time': scheduled_datetime,
            'num_maps': num_maps,
            'map_options': map_options[:-1]  # Сохраняем без RANDOM_OPTION
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
        map_votes.sort(key=lambda x: (-x[1], map_wins_count.get(x[0], 0)))

        # Выбираем победителей
        winners = []
        polled_maps = [option.text for option in map_poll.options if option.text != RANDOM_OPTION]

        for map_name, _ in map_votes:
            if len(winners) >= num_maps:
                break

            if map_name == RANDOM_OPTION:
                # Выбираем случайную карту, которой нет в опросе и не в кд
                random_map = get_random_map_not_in_list(polled_maps)
                winners.append(random_map)
                # Добавляем выбранную случайную карту в список, чтобы не выбирать её снова
                polled_maps.append(random_map)
            elif map_name not in winners:
                winners.append(map_name)

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
            f"Удачной игры!🎮"
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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        f"Привет! Я {BOT_NAME} - бот для организации голосований за карты в CS.\n\n"
        "Чтобы начать голосование, упомяните меня в группе с командой:\n"
        f"{BOT_TAG} HH:MM количество_карт\n\n"
        f"Пример: {BOT_TAG} 16:00 2\n\n"
        "В голосовании за карты всегда доступна опция '🎲 Случайная карта не из этого списка' "
        "для выбора случайной карты, которой нет в предложенных вариантах."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус бота и статистику"""
    if update.effective_user.id not in ADMIN_IDS:
        return

    stats_text = f"🤖 Статус {BOT_NAME}:\n\n"
    stats_text += f"Всего карт в пуле: {len(ALL_MAPS)}\n"
    stats_text += f"Карт в кд: {len(voting_history)}\n"
    stats_text += f"Активных голосований: {len(active_polls)}\n\n"

    if voting_history:
        stats_text += "Последние победившие карты:\n"
        for i, map_name in enumerate(voting_history, 1):
            stats_text += f"{i}. {map_name}\n"
        stats_text += "\n"

    if map_wins_count:
        stats_text += "Топ побед карт:\n"
        sorted_wins = sorted(map_wins_count.items(), key=lambda x: -x[1])[:10]
        for i, (map_name, wins) in enumerate(sorted_wins, 1):
            # Укорачиваем длинные названия для лучшей читаемости
            display_name = map_name.split(' - ')[0] if ' - ' in map_name else map_name[:20]
            stats_text += f"{i}. {display_name}: {wins} побед\n"

    await update.message.reply_text(stats_text)


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех карт"""
    maps_text = f"🗺️ Всего карт: {len(ALL_MAPS)}\n\n"

    # Разбиваем на группы по 10 для лучшей читаемости
    for i, map_name in enumerate(ALL_MAPS, 1):
        maps_text += f"{i}. {map_name}\n"

        # Добавляем разделитель каждые 10 карт
        if i % 10 == 0 and i != len(ALL_MAPS):
            maps_text += "\n"

    await update.message.reply_text(maps_text)


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
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Entity("mention"),
        handle_mention
    ))

    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    print(f"{BOT_NAME} запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()