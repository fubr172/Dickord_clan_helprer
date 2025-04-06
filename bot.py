import logging
import re
from venv import logger
import pytz
from datetime import timedelta, datetime
import aiohttp
from datetime import datetime
import asyncio
import discord
from discord.ext import commands, tasks
from discord.errors import HTTPException
from aiogram import Bot as TelegramBot, Dispatcher
from aiogram.types import Message
from pymongo import MongoClient
import requests
from dotenv import load_dotenv
import os

load_dotenv()

# Загрузка токенов из переменных окружения
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
STEAM_API_KEY = os.getenv('STEAM_API_KEY')
MONGO_URI = os.getenv('MONGO_URI')

# Замените на ваш ID каналов
LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID')
VACATION_CHANNEL_ID = os.getenv('VACATION_CHANNEL_ID')
CHANNEL_ID = os.getenv('CHANNEL_ID')
YOUR_GUILD_ID = os.getenv('YOUR_GUILD_ID')
ALLOWED_CHANNEL_ID = os.getenv('ALLOWED_CHANNEL_ID')
CHANNEL_ID_ROLL = os.getenv('CHANNEL_ID_ROLL')
CHECKED_CHANNEL_ID = os.getenv('CHECKED_CHANNEL_ID')
DISALLOWED_GUILDS = os.getenv('DISALLOWED_GUILS')
DISCORD_CHANNEL_ID_TG = os.getenv('DISCORD_CHANNEL_ID_TG')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ED_CHANNEL_ID = os.getenv('ED_CHANNEL_ID')
STEAM_CHANNEL_ID = os.getenv('STEAM_CHANNEL_ID')

# Константы
AFK_CHANNEL_NAME = "AFK"
CREATE_CHANNEL_NAME = "Создать канал"
VOICE_CHANNELS_CATEGORY_NAME = "Голосовые каналы"
NEW_MEMBER_ROLE_NAME = "Гость сообщества"  # Название роли для новых участников
WARNED_ROLE_NAME = "Предупрежден"  # Название роли, которая выдается при предупреждении
VACATION_ROLE_NAME = "Отпуск"  # Название роли для отпуска
ALLOWED_ROLES = ["🎖️│︎ Командующий клана", "⭐│︎Зам.Командующего", "🚨│︎Ст.Офицер", "🛡️│︎Администратор",
                 "✍️│︎Инструктор"]
CHECKED_ROLES = ["🎖️│︎ Командующий клана", "⭐│︎Зам.Командующего", "🚨│︎Ст.Офицер",
                 '✍️│︎Инструктор', "🔰│︎Офицер", "🪖│︎ Боец", '🔫│︎Новички']
INSTRUCTOR_ROLE_NAME = ["✍️│︎Инструктор", '🚨│︎Ст.Офицер']
LLOWED_ROLES = ['🔫│︎Новички', "🪖│︎ Боец", '⚙️│︎Представитель RISE', '🦅│︎Представитель Пятый Мотострелковый',
                '🗡️│︎Представитель ZARUBA', '🤝│︎Друзья клана', '📍│︎Академический состав', '🔖│︎Резервный состав',
                '🍺│︎Основной Состав']
ROLE_NAME = "🙂│︎ Гость"
last_message = None
DB_NAME = "SquadJS"
TARGET_GAME_ID = os.getenv('TARGET_GAME_ID')

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Настройка intents
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

# Discord bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Telegram bot
telegram_bot = TelegramBot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher()

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
vacations = db.vacation
steam = db.steam

# Логирование в Discord канал
class DiscordLogHandler(logging.Handler):
    """A handler class which writes logging records, to a discord channel."""
    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def send_log(self, message):
        try:
            await self.channel.send(message)
        except HTTPException as e:
            if e.status == 429:
                retry_after = int(e.retry_after)
                await asyncio.sleep(retry_after)
                await self.channel.send(message)

    def emit(self, record):
        msg = self.format(record)
        asyncio.create_task(self.send_log(msg))

class MyView(discord.ui.View):
    def __init__(self, user: discord.Member, reason: str, end_date: str, timeout=None):
        super().__init__(timeout=timeout)
        self.user = user
        self.reason = reason
        self.end_date = end_date

    async def is_allowed_to_manage(self, interaction: discord.Interaction) -> bool:
        """Проверяет, может ли пользователь управлять заявкой."""
        if interaction.user == self.user:
            await interaction.response.send_message("Вы не можете управлять собственным отпуском.", ephemeral=True)
            return False

        allowed_roles = [discord.utils.get(interaction.guild.roles, name=role_name) for role_name in ALLOWED_ROLES]
        user_roles = set(interaction.user.roles)

        if not any(role in user_roles for role in allowed_roles):
            await interaction.response.send_message("У вас нет прав для управления этой заявкой на отпуск.",
                                                    ephemeral=True)
            return False

        return True

    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Подтверждает заявку на отпуск."""
        if not await self.is_allowed_to_manage(interaction):
            return

        guild = interaction.guild
        vacation_role = discord.utils.get(guild.roles, name=VACATION_ROLE_NAME)
        if not vacation_role:
            await interaction.response.send_message("Ошибка: роль отпуска не найдена. Пожалуйста, создайте её.")
            return

        try:
            await self.user.add_roles(vacation_role)
            confirmation_message = (
                f"Отпуск по причине '{self.reason}' до {self.end_date} подтвержден. "
                f"Роль '{VACATION_ROLE_NAME}' добавлена для {self.user.mention}."
            )
            await interaction.channel.send(confirmation_message)

            # Обновление статуса заявки в MongoDB
            db.vacation.update_one(
                {"user_id": self.user.id, "reason": self.reason, "end_date": self.end_date},
                {"$set": {"status": "approved"}}
            )

            # Деактивация кнопок
            self.confirm.disabled = True
            self.decline.disabled = True
            await interaction.response.edit_message(view=self)
        except Exception as e:
            await interaction.response.send_message("Ошибка при добавлении роли отпуска.")
            logging.error(f"Ошибка при добавлении роли '{VACATION_ROLE_NAME}' пользователю {self.user}: {e}")

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Отклоняет заявку на отпуск."""
        if not await self.is_allowed_to_manage(interaction):
            return

        await interaction.response.send_message("Отпуск был отклонён.")

        # Обновление статуса заявки в MongoDB
        db.vacation.update_one(
            {"user_id": self.user.id, "reason": self.reason, "end_date": self.end_date},
            {"$set": {"status": "rejected"}}
        )

        # Деактивация кнопок
        self.confirm.disabled = True
        self.decline.disabled = True
        await interaction.response.edit_message(view=self)

@bot.tree.command(name="отпуск", description="Запросить отпуск с указанием причины и даты окончания.")
async def vacation(interaction: discord.Interaction, reason: str, end_date: str):
    """Команда для запроса отпуска."""
    if interaction.channel_id != VACATION_CHANNEL_ID:
        await interaction.response.send_message("Эта команда доступна только в определённом канале.", ephemeral=True)
        return

    # Проверка формата даты
    if not re.match(r'^\d{1,2}\.\d{1,2}\.(\d{2}|\d{4})$', end_date):
        await interaction.response.send_message("Неверный формат даты. Используйте дд.мм.гг или дд.мм.гггг.",
                                                ephemeral=True)
        return

    try:
        end_date_obj = datetime.strptime(end_date, '%d.%m.%Y') if len(
            end_date.split('.')[-1]) == 4 else datetime.strptime(end_date, '%d.%m.%y')
    except ValueError:
        await interaction.response.send_message("Ошибка преобразования даты. Проверьте формат.", ephemeral=True)
        return

    roles_mentions = []
    for role_name in ALLOWED_ROLES:
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role:
            roles_mentions.append(role.mention)

    # Сохранение заявки в MongoDB
    try:
        vacation_request = {
            "user_id": interaction.user.id,
            "reason": reason,
            "end_date": end_date_obj.strftime('%d.%m.%Y'),
            "requested_at": datetime.now().strftime('%d.%m.%Y %H:%M'),
            "status": "pending"
        }
        result = vacations.insert_one(vacation_request)
        logging.info(f"Заявка на отпуск сохранена: {result.inserted_id}")
    except Exception as e:
        logging.error(f"Ошибка при сохранении заявки на отпуск: {e}")
        await interaction.response.send_message("Произошла ошибка при сохранении заявки.", ephemeral=True)
        return

    # Формируем сообщение о заявке на отпуск с упоминанием ролей в заголовке
    vacation_request_msg = (
        f"Заявка на отпуск ожидает ответа от: {', '.join(roles_mentions)}\n"
        f"Участник: {interaction.user.mention}\n"
        f"До: {end_date}\n"
        f"Причина: {reason}\n"
    )

    # Создаем экземпляр MyView и передаем его в сообщение
    view = MyView(interaction.user, reason, end_date_obj.strftime('%d.%m.%Y'))
    await interaction.channel.send(vacation_request_msg, view=view)

async def check_vacations():
    """Проверяет заявки на отпуск каждый день в 00:00 по московскому времени."""
    while True:
        # Получаем текущее время в часовом поясе Москвы
        moscow_tz = pytz.timezone("Europe/Moscow")
        now = datetime.now(moscow_tz)

        # Рассчитываем время до следующего запуска (00:00 следующего дня)
        next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        time_until_next_run = (next_run - now).total_seconds()
        logging.info(f'Дата следующий проверки:{time_until_next_run}')

        # Ждём до следующего запуска
        await asyncio.sleep(time_until_next_run)

        # Выполняем проверку заявок на отпуск
        for vacation_request in vacation.find({"status": "approved"}):
            end_date_obj = datetime.strptime(vacation_request["end_date"], '%d.%m.%Y')

            if end_date_obj < now:
                guilds = bot.guilds  # Получаем все серверы бота (если несколько серверов)

                for guild in guilds:
                    member = guild.get_member(vacation_request["user_id"])
                    if member:
                        role = discord.utils.get(guild.roles, name=VACATION_ROLE_NAME)
                        if role and role in member.roles:
                            await member.remove_roles(role)
                            logging.info(f"Роль '{VACATION_ROLE_NAME}' была удалена у пользователя {member.name}.")

                # Обновляем статус заявки в MongoDB на 'completed'
                try:
                    vacation.update_one({"_id": vacation_request["_id"]}, {"$set": {"status": "completed"}})
                except Exception as e:
                    logging.error(f"Ошибка при обновлении статуса отпуска: {e}")

@bot.event
async def on_member_join(member):

    if member.guild.id in DISALLOWED_GUILDS:
        return

    logging.info(f"{member.name} присоединился к серверу.")

    # Получаем роль "Гость сообщества"
    role = discord.utils.get(member.guild.roles, name="Гость сообщества")

    # Проверка наличия роли на сервере
    if role is None:
        logging.warning(f"Роль 'Гость сообщества' не найдена на сервере.")
        return

    # Добавление роли новому участнику
    try:
        await member.add_roles(role)
        logging.info(f"Добавлена роль 'Гость сообщества' участнику {member.name}")
    except discord.Forbidden:
        logging.warning(f"Нет прав на добавление роли 'Гость сообщества' участнику {member.name}.")
    except discord.HTTPException as e:
        logging.error(f"Ошибка при добавлении роли 'Гость сообщества' участнику {member.name}: {e}")

@bot.tree.command(name="warn", description="Предупредить пользователя")
async def warn(interaction: discord.Interaction, user: discord.Member, *, reason: str):
    # Проверка канала
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Эта команда доступна только в определённом канале.", ephemeral=True)
        return

    # Проверка ролей
    member = interaction.guild.get_member(interaction.user.id)
    if not any(role.name in ALLOWED_ROLES for role in member.roles):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    # Получение роли предупреждения
    warned_role = discord.utils.get(interaction.guild.roles, name=WARNED_ROLE_NAME)
    if not warned_role:
        warned_role = await interaction.guild.create_role(name=WARNED_ROLE_NAME)

    # Добавление роли предупреждения пользователю
    await user.add_roles(warned_role)
    await interaction.response.send_message(f">>> Пользователь {user.mention} был предупрежден за:\n**{reason}**")
    logging.info(f"{user.name} был предупрежден за: {reason}")

    # Автоматическое снятие предупреждения через 30 дней
    await asyncio.sleep(30 * 24 * 60 * 60)  # 30 дней в секундах
    if warned_role in user.roles:
        await user.remove_roles(warned_role)
        logging.info(f"Роль '{warned_role.name}' была удалена у пользователя {user.name} через 30 дней.")
        await user.send(f"Ваше предупреждение отменено через 30 дней.")


@bot.tree.command(name="unwarn", description="Снять предупреждение с пользователя")
async def unwarn(interaction: discord.Interaction, user: discord.Member):
    # Проверка канала
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message("Эта команда доступна только в определённом канале.", ephemeral=True)
        return

    # Проверка ролей
    member = interaction.guild.get_member(interaction.user.id)
    if not any(role.name in ALLOWED_ROLES for role in member.roles):
        await interaction.response.send_message("У вас нет прав для использования этой команды.", ephemeral=True)
        return

    # Снятие роли предупреждения
    warned_role = discord.utils.get(interaction.guild.roles, name=WARNED_ROLE_NAME)
    if warned_role in user.roles:
        await user.remove_roles(warned_role)
        await interaction.response.send_message(f">>> С пользователя {user.mention} снято предупреждение.")
        logging.info(f"С пользователя {user.name} снято предупреждение.")
    else:
        await interaction.response.send_message(f"У пользователя {user.mention} нет активного предупреждения.")


@bot.tree.command(name="удалить", description="Удалить роль")
async def delete_role(interaction: discord.Interaction, member: discord.Member):
    # Проверка, что команда была вызвана в разрешенном канале
    if interaction.channel_id != CHECKED_CHANNEL_ID:
        await interaction.response.send_message("Эта команда доступна только в определённом канале.", ephemeral=True)
        return

    # Получаем роль по имени из константы
    role = discord.utils.get(interaction.guild.roles, name=ROLE_NAME)

    if role is None:
        await interaction.response.send_message(f'Роль "{ROLE_NAME}" не найдена.', ephemeral=True)
        return

    # Проверяем, есть ли у пользователя эта роль
    if role in member.roles:
        await member.remove_roles(role)
        await interaction.response.send_message(f'Роль {role.name} была удалена у {member.display_name}.',
                                                ephemeral=True)
    else:
        await interaction.response.send_message(f'У {member.display_name} нет роли {role.name}.', ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    # Проверяем права на управление каналами у бота
    if not member.guild.me.guild_permissions.manage_channels:
        logging.warning("У бота нет прав на управление каналами.")
        return


    # Проверка, если пользователь заходит в канал "Создать канал"
    if after.channel and after.channel.name == CREATE_CHANNEL_NAME:
        logging.info(f"{member.name} подключился к каналу 'Создать канал'")
        category = after.channel.category
        if category is not None:
            # Проверяем, существует ли уже канал с таким именем
            existing_channel = discord.utils.get(category.voice_channels, name=f"{member.display_name}")
            if existing_channel is None:
                new_channel = await category.create_voice_channel(name=f"{member.display_name}")
                await member.move_to(new_channel)
                logging.info(f"Создан новый канал: {new_channel.name} для {member.name}")
            else:
                await member.move_to(existing_channel)  # Перемещаем пользователя в существующий канал
                logging.info(f"Перемещен в существующий канал: {existing_channel.name} для {member.name}")

    # Удаляем пустые каналы, кроме канала "Создать канал"
    if (before.channel and before.channel.members == [] and
        before.channel.name not in {CREATE_CHANNEL_NAME, AFK_CHANNEL_NAME}):
        await check_and_delete_channel(before.channel)

    # Проверка, если пользователь покидает голосовой канал
    elif after.channel is None and before.channel is not None:
        await check_and_delete_channel(before.channel)

    # Проверка, если пользователь перемещается между каналами
    elif after.channel is not None and before.channel is not None and before.channel != after.channel:
        await check_and_delete_channel(before.channel)

async def check_and_delete_channel(channel):
    category = discord.utils.get(channel.guild.categories, name=VOICE_CHANNELS_CATEGORY_NAME)
    if (channel.category == category and len(channel.members) == 0
        and channel.name not in {CREATE_CHANNEL_NAME, AFK_CHANNEL_NAME}):
        await delete_channel(channel)

async def delete_channel(channel):
    # Проверка, что канал не является AFK или каналом "Создать канал"
    if channel.name not in {AFK_CHANNEL_NAME, CREATE_CHANNEL_NAME}:
        try:
            await channel.delete()
            logging.info(f"Удален канал: {channel.name}")
        except discord.Forbidden:
            logging.warning(f"Не удалось удалить канал: {channel.name}. Недостаточно прав.")
        except discord.HTTPException as e:
            logging.error(f"Ошибка при удалении канала: {channel.name}. Ошибка: {e}")
    else:
        logging.info(f"Канал {channel.name} не будет удален.")


@bot.tree.command(name="состав", description="Показывает состав пользователей с определёнными ролями")
async def состав(interaction: discord.Interaction):
    global last_message

    # Проверка ролей пользователя, запускающего команду
    user_roles = [role.name for role in interaction.user.roles]
    if not any(role in ALLOWED_ROLES for role in user_roles):
        await interaction.response.send_message("У вас нет прав для выполнения этой команды.", ephemeral=True)
        return

    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("Не удалось найти сервер.", ephemeral=True)
        return

    # Создаём словарь для хранения пользователей по ролям
    roles_users = {role_name: [] for role_name in CHECKED_ROLES}
    for member in guild.members:
        user_roles = [role for role in member.roles if role.name in CHECKED_ROLES]
        if user_roles:
            highest_role = max(user_roles, key=lambda r: r.position)
            roles_users[highest_role.name].append(member.display_name)

    # Получаем канал
    channel = bot.get_channel(CHANNEL_ID_ROLL)
    if not channel:
        await interaction.response.send_message("Канал для отправки сообщения не найден.", ephemeral=True)
        return

    try:
        # Создаем общий синий Embed
        embed = discord.Embed(color=0x0000ff, title="Состав пользователей")  # Синий цвет
        embed.description = ""  # Инициализация описания

        # Добавляем информацию о каждой роли в общий Embed
        for role_name, users in roles_users.items():
            if users:
                users_list = "\n> ".join(users)

                # Добавляем информацию о роли и пользователях с пробелом между ролями
                embed.description += f"\n─── ⋆⋅☆⋅⋆ ──\n{role_name}:\n─── ⋆⋅☆⋅⋆ ──\n\n> {users_list}\n─── ⋆⋅☆⋅⋆ ──\n\n"

        # Путь к изображению (в папке code)
        image_path = 'Code/a639dcad-1664-4bba-b204-778bb5710a8f копия.jpg'  # Укажите правильный путь к изображению

        # Отправляем общий Embed и изображение в одном сообщении
        with open(image_path, 'rb') as image_file:
            await channel.send(embed=embed, file=discord.File(image_file, filename='image.jpg'))

    except discord.NotFound:
        await interaction.response.send_message("Ошибка: сообщение было удалено.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"Ошибка при отправке сообщения: {e}", ephemeral=True)


@bot.tree.command(name="роль", description="Выдать роль участнику")
async def роль(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    """Выдает указанную роль указанному участнику."""

    # Проверка канала
    if interaction.channel_id != CHECKED_CHANNEL_ID:
        await interaction.response.send_message("Эта команда доступна только в определённом канале.", ephemeral=True)
        return

    # Проверка прав пользователя
    instructor_role = discord.utils.get(interaction.guild.roles, name=INSTRUCTOR_ROLE_NAME)
    if not any(role.name in INSTRUCTOR_ROLE_NAME for role in interaction.user.roles):
        await interaction.response.send_message("У вас нет прав для выдачи ролей.", ephemeral=True)
        return

    # Проверка роли по названию
    if role.name not in LLOWED_ROLES:
        await interaction.response.send_message(f"Выдача роли '{role.name}' не разрешена.", ephemeral=True)
        return

    # Проверка прав бота
    bot_member = interaction.guild.me
    if role.position >= bot_member.top_role.position:
        await interaction.response.send_message("У меня нет прав для выдачи этой роли.", ephemeral=True)
        return

    try:
        await member.add_roles(role)
        await interaction.response.send_message(f'Роль {role.name} выдана {member.mention}.')
    except discord.Forbidden:
        await interaction.response.send_message("У меня нет прав для выдачи этой роли.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message("Произошла ошибка при выдаче роли.", ephemeral=True)

@bot.event
async def on_message(message):
    logger.info(f"Checking message from Discord - Channel: {message.channel.id} (Expected: {DISCORD_CHANNEL_ID_TG})")
    if message.channel.id == DISCORD_CHANNEL_ID_TG and not message.author.bot:
        try:
            logger.info(f"Received message from Discord: {message.author.name} "
                        f"({message.author.id}): {message.content}")
            if message.content.strip():  # Если сообщение не пустое
                await telegram_bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f'Сообщение из Discord: {message.author.display_name}: {message.content}'
                )
                logger.info("Message sent to Telegram successfully.")
            else:
                logger.warning(f"Received empty message from Discord from {message.author.name}.")
        except Exception as e:
            logger.error(f"Error sending message to Telegram: {e}")

def is_allowed_channel():
    """Проверка разрешенного канала."""
    def predicate(interaction: discord.Interaction):
        return interaction.channel.id == STEAM_CHANNEL_ID

    return predicate

async def get_steam_nickname(steam_id: str) -> str:
    """Gets Steam nickname from Steam ID."""
    url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_id}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                data = await response.json()
        except aiohttp.ClientError as e:
            logging.error(f"AIOHTTP error getting nickname for {steam_id}: {e}")
            return None  # Return None on error

    if data and data['response'] and data['response']['players']:
        return data['response']['players'][0]['personaname']
    return "Unknown"

def get_playtime(steam_id: str) -> int:
    """Gets playtime from Steam API."""
    url = (f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?"
           f"key={STEAM_API_KEY}&steamid={steam_id}&include_appinfo=true")
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
    except requests.exceptions.RequestException as e:
        logging.exception(f"Request error getting playtime for {steam_id}: {e}")
        return None
    except Exception as e:
        logging.exception(f"Error getting playtime for {steam_id}: {e}")
        return None

    if data and data['response'] and data['response'].get('games'):
        for game in data['response']['games']:
            if game['appid'] == TARGET_GAME_ID:
                return game['playtime_forever']
    return 0  # Return 0 if not found or an error occurred

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(f"🚫 Команды доступны только в канале <#{STEAM_CHANNEL_ID}>!", delete_after=10)
    else:
        await ctx.send(f"❌ Произошла ошибка: {str(error)}")

@bot.tree.command(name="add_steam", description="Add Steam ID to the tracked list")
async def add_steam(interaction: discord.Interaction, steam_id: str):
    """Adds Steam ID to the database (only in allowed channel)."""
    if interaction.channel.id != STEAM_CHANNEL_ID:
        await interaction.response.send_message(
            f"🚫 This command can only be used in <#{STEAM_CHANNEL_ID}>!", ephemeral=True
        )
        return

    try:
        steam_nick = await get_steam_nickname(steam_id)
        if steam_nick is None:
             await interaction.response.send_message(f"❌ Could not retrieve Steam nickname for {steam_id}.  Check the Steam ID and API key.", ephemeral=True)
             return

        initial_playtime = get_playtime(steam_id)
        if initial_playtime is None:
            await interaction.response.send_message(f"❌ Could not retrieve initial playtime for {steam_id}. Check the Steam ID and API key.", ephemeral=True)
            return


        steam.update_one(
            {"steam_id": steam_id},  # Use steam_id as unique identifier
            {
                "$set": {
                    "steam_nick": steam_nick,
                    "last_update": datetime.now(),
                    "discord_id": interaction.user.id,  # Store Discord ID
                    "initial_playtime": initial_playtime, #  Save initial playtime
                    "total_playtime": 0,
                    "daily_playtime": 0
                },
            },
            upsert=True
        )
        await interaction.response.send_message(
            f"✅ Steam ID {steam_id} ({steam_nick}) added", ephemeral=True
        )
    except Exception as e:
        logging.exception(f"Error in add_steam: {e}")
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@bot.tree.command(name="give_stats", description="Show the stats for a Steam user")
async def give_stats(interaction: discord.Interaction, steam_id: str):
    """Shows the stats (only in allowed channel)."""
    if interaction.channel.id != STEAM_CHANNEL_ID:
        await interaction.response.send_message(
            f"🚫 This command can only be used in <#{STEAM_CHANNEL_ID}>!", ephemeral=True
        )
        return

    user_data = steam.find_one({"steam_id": steam_id})

    if not user_data:
        await interaction.response.send_message(
            f"❌ No data found for Steam ID {steam_id}.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"Statistics for {user_data['steam_nick']}",
        color=0x00ff00,
        timestamp=datetime.now()
    )

    embed.add_field(name="Steam ID", value=user_data['steam_id'], inline=False)
    embed.add_field(name="Total Playtime", value=f"{user_data['initial_playtime']} minutes", inline=True)
    embed.add_field(name="Daily Playtime", value=f"{user_data['daily_playtime']} minutes", inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="delete_steam", description="Remove a user from tracking")
async def delete_steam(interaction: discord.Interaction, steam_id: str):
    """Removes Steam ID (only in allowed channel)."""
    if interaction.channel.id != STEAM_CHANNEL_ID:
        await interaction.response.send_message(
            f"🚫 This command can only be used in <#{STEAM_CHANNEL_ID}>!", ephemeral=True
        )
        return

    try:
        result = steam.delete_one({"steam_id": steam_id})
        if result.deleted_count > 0:
            await interaction.response.send_message(f"✅ Steam ID {steam_id} successfully removed.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Steam ID {steam_id} not found.", ephemeral=True)
    except Exception as e:
        logging.exception(f"Error in delete_steam: {e}")
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

@tasks.loop(hours=24)
async def update_stats():
    """Background task to update stats every 24 hours."""
    for player in steam.find():
        try:
            steam_id = player['steam_id']
            current_playtime = get_playtime(steam_id)

            if current_playtime is None:
                logging.warning(f"Could not retrieve current playtime for {steam_id}. Skipping update.")
                continue  # Skip to the next player

            initial_playtime = player.get('initial_playtime', 0) # Get initial playtime.  Default to 0 if not found.
            daily_playtime = current_playtime - initial_playtime

            steam.update_one(
                {"_id": player['_id']},
                {
                    "$set": {
                        "total_playtime": current_playtime, # Update total playtime with current playtime.
                        "daily_playtime": daily_playtime,  # Update daily playtime
                        "initial_playtime": current_playtime, #  Set new initial playtime for next day's calculation
                        "last_update": datetime.now()
                    }
                }
            )
            logging.info(f"Updated stats for {steam_id}. Total: {current_playtime}, Daily: {daily_playtime}")


        except Exception as e:
            logging.exception(f"Error updating stats for {player['steam_id']}: {e}")

#  Эту команду лучше удалить, она не нужна и не работает с tree commands
# @bot.command()
# @is_allowed_channel_steam()
# async def get_stats(ctx, steam_id: str):
#     """Получает статистику по-указанному Steam ID."""
#     try:
#         steam_nick = await get_steam_nickname(steam_id)
#         player_data = steam.find_one({"steam_id": steam_id})
#
#         if player_data:
#             embed = discord.Embed(
#                 title=f"Статистика игрока {steam_nick}",
#                 color=0x00ff00,
#                 timestamp=datetime.now()
#             )
#
#             embed.add_field(name="Steam ID", value=player_data['steam_id'], inline=False)
#             embed.add_field(name="Общее время", value=f"{player_data['total_playtime']} мин", inline=True)
#             embed.add_field(name="За сутки", value=f"{player_data['daily_playtime']} мин", inline=True)
#
#             await ctx.send(embed=embed)
#         else:
#             await ctx.send(f"❌ Игрок с Steam ID {steam_id} не найден.")
#     except Exception as e:
#         await ctx.send(f"❌ Ошибка получения статистики: {str(e)}")

@dispatcher.message()
@dispatcher.message()
async def handle_telegram_message(message: Message):
    discord_channel = bot.get_channel(DISCORD_CHANNEL_ID_TG)
    if discord_channel:
        await discord_channel.send(f"Сообщение из Telegram: {message.from_user.full_name}: {message.text}")

async def start_telegram_bot():
    await dispatcher.start_polling(telegram_bot)

# Запуск ботов
async def start_telegram_bot():
    await dispatcher.start_polling(telegram_bot)

# --- Discord Events ---
@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} подключен к Discord!')
    try:
        guild = discord.Object(id=YOUR_GUILD_ID)  # Замените YOUR_GUILD_ID на ID вашего сервера
        bot.tree.copy_global_to(guild=guild)  # Копируем глобальные команды на сервер
        synced = await bot.tree.sync(guild=guild)  # Синхронизируем команды с сервером
        print(f"Synced {len(synced)} command(s) to guild {guild.id}")
    except Exception as e:
        print(f"Error syncing commands: {e}")


async def main():
    """Main function to start both bots."""
    try:
        telegram_task = asyncio.create_task(start_telegram_bot())
        await bot.start(DISCORD_TOKEN)
        await telegram_task
    except Exception as e:
        logging.critical(f"Critical error starting bots: {e}")
    await check_vacations()
    await update_stats()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Terminating...")
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}")
