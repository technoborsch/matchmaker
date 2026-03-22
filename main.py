import os
import logging
import random
import pickle
import atexit
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

# ==================== КОНФИГУРАЦИЯ ====================
BOT_NAME = "MatchMaker"
BOT_TAG = "@cs_maps_bot"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TIMEZONE = pytz.timezone('Europe/Moscow')

# Константы
RANDOM_OPTION = "🎲Случайная карта не из этого списка"

# Советы
CS2_PRO_TIPS = [
    # Очень базовые / очевидные, но важные
    "Pro tip: всегда покупай броню и шлем, если хватает денег. Без шлема многие смерти — это мгновенный хедшот.",
    "Pro tip: не стой на месте дольше 3–4 секунд — постоянное движение сильно снижает шансы получить хедшот",
    "Pro tip: используй голосовую связь или пиши в чат, где враги. Молчаливая команда почти всегда проигрывает.",
    "Pro tip: не экономь на гранатах в пистолетке — одна удачная флешка может выиграть раунд.",
    "Pro tip: держи нож в руках, когда бежишь по безопасной зоне — скорость +2%.",
    "Pro tip: не стреляй на бегу, если это не пистолет или пистолет-пулемет на близкой дистанции.",
    "Pro tip: перезаряжай оружие только в безопасном месте и когда рядом нет врагов.",
    "Pro tip: не перезаряжай оружие без надобности. Десяти патронов часто достаточно для дуэли.",
    "Pro tip: не кидай гранаты вслепую без тренировки — чаще всего они попадут в тебя или в союзников.",
    "Pro tip: смотри на мини-карту каждые 5–7 секунд — знаешь, где враги - знаешь, куда перемещаться.",
    "Pro tip: если ты последний в живых — не геройствуй. Играй по времени и заставляй врагов нервничать.",

    # Средний уровень
    "Pro tip: на T-стороне тайминг важнее агрессии. Лучше прийти на точку на 1 секунду позже, но с гранатами.",
    "Pro tip: после смерти сразу пиши тиммейтам, сколько врагов видел и где примерно они стояли.",
    "Pro tip: на CT старайся не играть в одной и той же позиции два раунда подряд — тебя уже выучили.",
    "Pro tip: учи «shoulder peek» и «jiggle peek» — быстрые выглядывания дают информацию почти без риска.",
    "Pro tip: на пистолетке Tec-9 / Five-SeveN / CZ75 почти всегда лучше P250 по патронам и урону.",
    "Pro tip: если тебя пикнули первым — 90% вероятность, что тебя уже ждут. Меняй позицию.",
    "Pro tip: на AWP стреляй после первого шага остановки, а не на полном ходу.",
    "Pro tip: всегда проверяй, закрыты ли флешки на твоей позиции перед тем, как выходить.",
    "Pro tip: не покупай Defuse Kit, если ты играешь агрессивно на T-стороне или на пистолетке.",
    "Pro tip: на Mirage / Dust2 / Inferno контроль мида часто решает половину игры.",

    # Более продвинутые / ситуационные
    "Pro tip: учись кидать одну и ту же гранату с одной и той же позиции — постоянство важнее креатива.",
    "Pro tip: на Overpass и Ancient плохая ротация наказывается мгновенно — думай, кто закроет вторую точку.",
    "Pro tip: на Vertigo и Nuke вертикальный контроль (крыша / рампа / вентиляция) часто важнее горизонтального.",
    "Pro tip: right-hand / left-hand (cl_righthand 0/1) иногда спасает на определённых углах — экспериментируй.",
    "Pro tip: если у тебя стабильно 2–3 килла за матч — подумай о смене прицела или чувствительности.",
    "Pro tip: на Ancient не забывай про смок на бублик — он закрывает мид и даёт время на ротацию.",
    "Pro tip: на Inferno банан — это не про киллы, а про контроль тайминга и пространства.",
    "Pro tip: учись «fake plant / fake defuse» — заставляй врагов нервничать и делать ошибки.",
    "Pro tip: если тиммейт умер глупо — не ругайся в голосовом. Лучше скажи спокойно, где враг.",

    # Ещё более очевидные, но спасают жизни
    "Pro tip: не стой спиной к окну / двери / длинному углу, даже если «там никого не может быть».",
    "Pro tip: делай зум на AWP только когда точно уверен, что будешь стрелять.",
    "Pro tip: не кидай молотов в союзника, даже если «там враг» — лучше вообще не кидать.",
    "Pro tip: если у тебя мало HP — не иди в перестрелку. Лучше отойти и дождаться подмоги.",
    "Pro tip: на eco-раунде не покупай ничего, кроме пистолета и брони, если хочешь выиграть force-buy.",
    "Pro tip: смотри на радары врагов (kill feed + звук) — знаешь, кто остался и где примерно.",
    "Pro tip: не бегай с ножом, когда рядом может быть враг — секунда на переключение = смерть.",
    "Pro tip: если ты услышал шаг — замри на секунду. Часто враг тоже замирает — кто первый выглянет, тот и выиграет."
]

# 10 разных сообщений о победителях
WINNER_MESSAGES = [
    "🏆 В голосовании победили карты: 🏆\n\n{winner_text}\n\n{random_tip}",
    "🔥 Выбраны карты на катку! 🔥\n\n{winner_text}\n\n{random_tip}",
    "🎉 Итоги голосования: 🎉\n\n{winner_text}\n\n{random_tip}",
    "🏅 Победившие карты определены: 🏅\n\n{winner_text}\n\n{random_tip}",
    "🗺️ Карты на ближайшую игру: 🗺️\n\n{winner_text}\n\n{random_tip}",
    "📢 Голосование закрыто. Выбрано:\n\n{winner_text}\n\n{random_tip}",
    "💣 Бомба будет на:\n\n{winner_text}\n\n{random_tip}",
    "🌟 Самые популярные карты по голосам: 🌟\n\n{winner_text}\n\n{random_tip}",
    "🎲 Голоса + рандом = результат:\n\n{winner_text}\n\n{random_tip}",
    "🏆 Несмотря на здравый смысл, победили карты: 🏆\n\n{winner_text}\n\n{random_tip}",
]

# ==================== СПИСОК КАРТ ====================
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
    "🎖️Militia - Спасение заложников на ферме",
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

# ==================== ХРАНЕНИЕ ДАННЫХ ====================
active_polls = {}  # chat_id → данные опроса
map_wins_count = defaultdict(int)  # карта → количество побед
voting_history = deque(maxlen=10)  # последние 10 победивших карт (для отображения)
cooldowns = defaultdict(int)  # карта → оставшиеся голосования в КД

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def get_available_maps(exclude_list: List[str] = None) -> List[str]:
    if exclude_list is None:
        exclude_list = []
    available = [m for m in ALL_MAPS if m not in exclude_list and cooldowns.get(m, 0) <= 0]
    if not available:
        available = [m for m in ALL_MAPS if m not in exclude_list]
    return available


def select_map_options() -> List[str]:
    available = get_available_maps()
    selected = random.sample(available, min(11, len(available)))
    selected.append(RANDOM_OPTION)
    return selected


def get_random_map_not_in_list(exclude_list: List[str]) -> str:
    exclude = [item for item in exclude_list if item != RANDOM_OPTION]
    available = get_available_maps(exclude)
    if not available:
        candidates = [m for m in ALL_MAPS if m not in exclude]
        return random.choice(candidates) if candidates else ALL_MAPS[0]
    return random.choice(available)


# ==================== ПЕРСИСТЕНТНОСТЬ ====================
STATE_FILE = 'bot_state.pkl'


def load_state():
    if not os.path.exists(STATE_FILE):
        logger.info("Файл состояния не найден, начинаем с чистого листа")
        return
    try:
        with open(STATE_FILE, 'rb') as f:
            data = pickle.load(f)
        map_wins_count.update(data.get('map_wins_count', {}))
        voting_history.extend(data.get('voting_history', []))
        cooldowns.update(data.get('cooldowns', {}))
        active_polls.update(data.get('active_polls', {}))
        logger.info(f"Состояние загружено из {STATE_FILE}")
    except Exception as e:
        logger.warning(f"Ошибка при загрузке состояния: {e}")


def save_state():
    state = {
        'map_wins_count': dict(map_wins_count),
        'voting_history': list(voting_history),
        'cooldowns': dict(cooldowns),
        'active_polls': active_polls.copy(),
    }
    try:
        with open(STATE_FILE, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"Состояние сохранено в {STATE_FILE}")
    except Exception as e:
        logger.error(f"Не удалось сохранить состояние: {e}")


# ==================== ЛОГИКА ГОЛОСОВАНИЙ ====================
async def schedule_map_announcement(
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        scheduled_time: datetime,
        num_maps: int
):
    now = datetime.now(TIMEZONE)
    time_left_seconds = (scheduled_time - now).total_seconds()

    if time_left_seconds <= 0:
        delay = 0
    elif time_left_seconds <= 300:
        delay = time_left_seconds
    else:
        announcement_time = scheduled_time - timedelta(minutes=5)
        delay = (announcement_time - now).total_seconds()

    delay = max(0, delay)

    context.job_queue.run_once(
        announce_winner_maps,
        delay,
        chat_id=chat_id,
        data={
            'num_maps': num_maps,
            'poll_data': active_polls.get(chat_id)
        }
    )


async def create_polls(chat_id: int, context: ContextTypes.DEFAULT_TYPE,
                       num_maps: int, scheduled_time_str: str) -> Tuple[int, int]:
    reg_poll = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"Буду в {scheduled_time_str}",
        options=["+", "+-", "-"],
        is_anonymous=False,
        allows_multiple_answers=False
    )

    map_options = select_map_options()
    map_poll = await context.bot.send_poll(
        chat_id=chat_id,
        question=f"Выберите карты для игры в {scheduled_time_str}",
        options=map_options,
        is_anonymous=True,
        allows_multiple_answers=True
    )

    return reg_poll.message_id, map_poll.message_id


async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.replace(f"@{context.bot.username}", "").strip()
    if not text:
        return

    try:
        time_str, num_maps_str = text.split()
        scheduled_time = datetime.strptime(time_str, "%H:%M").time()
        num_maps = int(num_maps_str)

        if num_maps < 1 or num_maps > 12:
            await update.message.reply_text("Количество карт должно быть от 1 до 12")
            return

        current_date = datetime.now(TIMEZONE).date()
        scheduled_datetime = datetime.combine(current_date, scheduled_time)
        scheduled_datetime = TIMEZONE.localize(scheduled_datetime)

        if scheduled_datetime <= datetime.now(TIMEZONE):
            await update.message.reply_text("Укажите время в будущем!")
            return

        reg_id, map_id = await create_polls(
            update.message.chat_id,
            context,
            num_maps,
            time_str
        )

        map_options = select_map_options()

        active_polls[update.message.chat_id] = {
            'registration_poll_id': reg_id,
            'map_poll_id': map_id,
            'scheduled_time': scheduled_datetime,
            'num_maps': num_maps,
            'map_options': map_options[:-1]  # без RANDOM_OPTION
        }

        await schedule_map_announcement(
            context,
            update.message.chat_id,
            scheduled_datetime,
            num_maps
        )

    except ValueError:
        await update.message.reply_text(
            f"Формат: {BOT_TAG} ЧЧ:ММ количество\n"
            f"Пример: {BOT_TAG} 16:00 2"
        )
    except Exception as e:
        logger.error(f"Ошибка при создании голосования: {e}")
        await update.message.reply_text("Произошла ошибка 😔")


async def announce_winner_maps(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    num_maps = job.data['num_maps']
    poll_data = job.data.get('poll_data')

    if not poll_data or chat_id not in active_polls:
        return

    try:
        map_poll = await context.bot.stop_poll(chat_id, poll_data['map_poll_id'])

        votes = [(opt.text, opt.voter_count) for opt in map_poll.options]
        votes.sort(key=lambda x: (-x[1], map_wins_count.get(x[0], 0)))

        winners = []
        polled_maps = [opt.text for opt in map_poll.options if opt.text != RANDOM_OPTION]

        for map_name, _ in votes:
            if len(winners) >= num_maps:
                break
            if map_name == RANDOM_OPTION:
                rand_map = get_random_map_not_in_list(polled_maps)
                winners.append(rand_map)
                polled_maps.append(rand_map)
            elif map_name not in winners:
                winners.append(map_name)

        # Обновляем статистику
        for w in winners:
            map_wins_count[w] += 1
        voting_history.extend(winners)

        # Кулдаун — 5 следующих голосований
        for m in list(cooldowns):
            cooldowns[m] -= 1
            if cooldowns[m] <= 0:
                del cooldowns[m]
        for w in winners:
            cooldowns[w] = 5

        # Сообщение
        winner_text = "\n".join(f"• {m}" for m in winners)

        # Выбираем случайное сообщение и случайный совет
        template = random.choice(WINNER_MESSAGES)
        tip = random.choice(CS2_PRO_TIPS)

        message = template.format(
            winner_text=winner_text,
            random_tip=tip
        )

        await context.bot.send_message(chat_id=chat_id, text=message)

        if chat_id in active_polls:
            del active_polls[chat_id]

    except Exception as e:
        logger.error(f"Ошибка при объявлении результатов: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="Не удалось подвести итоги голосования 😢"
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"Привет! Я {BOT_NAME} — помогаю выбирать карты для каток в CS.\n\n"
        f"Запуск голосования:\n"
        f"{BOT_TAG} ЧЧ:ММ количество_карт\n"
        f"Пример: {BOT_TAG} 20:15 2\n\n"
        "В опросе всегда есть опция «Случайная карта не из списка».\n"
        "Доступные команды:\n"
        "/status — статистика и кулдауны\n"
        "/list — полный список карт"
    )
    await update.message.reply_text(text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [f"🤖 {BOT_NAME} статус:\n"]
    lines.append(f"Всего карт в пуле: {len(ALL_MAPS)}")
    lines.append(f"Карт в кулдауне: {len(cooldowns)}")
    lines.append(f"Активных голосований: {len(active_polls)}\n")

    if voting_history:
        lines.append("Последние победители:")
        for i, m in enumerate(voting_history, 1):
            lines.append(f"{i}. {m}")
        lines.append("")

    if map_wins_count:
        lines.append("Топ по победам:")
        top = sorted(map_wins_count.items(), key=lambda x: -x[1])[:10]
        for i, (m, cnt) in enumerate(top, 1):
            short = m.split(" - ")[0] if " - " in m else m[:25]
            lines.append(f"{i}. {short}: {cnt}")

    await update.message.reply_text("\n".join(lines))


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"🗺️ Всего карт: {len(ALL_MAPS)}\n\n"
    for i, m in enumerate(ALL_MAPS, 1):
        text += f"{i}. {m}\n"
        if i % 10 == 0 and i < len(ALL_MAPS):
            text += "\n"
    await update.message.reply_text(text)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка в обработчике: {context.error}")
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла внутренняя ошибка бота"
        )


# ==================== ЗАПУСК ====================
def main():
    load_state()

    application = Application.builder().token(BOT_TOKEN).build()

    # Восстановление отложенных задач после перезапуска
    now = datetime.now(TIMEZONE)
    for chat_id, data in list(active_polls.items()):
        sched_time = data.get('scheduled_time')
        if not sched_time or sched_time <= now:
            del active_polls[chat_id]
            continue

        # Планируем заново с учётом текущего времени
        application.job_queue.run_once(
            announce_winner_maps,
            when=0,  # будет пересчитано внутри schedule_map_announcement
            chat_id=chat_id,
            data={'num_maps': data['num_maps'], 'poll_data': data}
        )
        # Лучше вызвать напрямую schedule_map_announcement
        context = application.create_task_context()
        application.create_task(
            schedule_map_announcement(
                context,
                chat_id,
                sched_time,
                data['num_maps']
            )
        )

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Entity("mention"),
        handle_mention
    ))
    application.add_error_handler(error_handler)

    atexit.register(save_state)

    print(f"{BOT_NAME} запущен...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()