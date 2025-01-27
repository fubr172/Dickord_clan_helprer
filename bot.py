import logging
import re
from datetime import datetime
import asyncio
from venv import logger
import discord
from discord.ext import commands
from discord.errors import HTTPException
from aiogram import Bot as TelegramBot, Dispatcher
from aiogram.types import Message

# Загрузка токенов из переменных окружения
DISCORD_TOKEN = "you_discord_token"
TELEGRAM_TOKEN = 'you_telegram_token'


# Константы
AFK_CHANNEL_NAME = "AFK"
CREATE_CHANNEL_NAME = "Создать канал"
VOICE_CHANNELS_CATEGORY_NAME = "Голосовые каналы"
NEW_MEMBER_ROLE_NAME = "Гость сообщества"  # Название роли для новых участников
WARNED_ROLE_NAME = "Предупрежден"  # Название роли, которая выдается при предупреждении
VACATION_ROLE_NAME = "Отпуск"  # Название роли для отпуска
ALLOWED_ROLES = []
CHECKED_ROLES = []
INSTRUCTOR_ROLE_NAME = []
LLOWED_ROLES = []
last_message = None

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

# Данные об отпусках
vacation_data = {}


# Логирование в Discord канал
class DiscordLogHandler(logging.Handler):
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



# Замените на ваш ID каналов
LOG_CHANNEL_ID = 'you id chanel'
VACATION_CHANNEL_ID = 'you id chanel'
CHANNEL_ID = 'you id chanel'
YOUR_GUILD_ID = 'you id chanel'
ALLOWED_CHANNEL_ID = 'you id chanel'
CHANNEL_ID_ROLL = 'you id chanel'
CHECKED_CHANNEL_ID = 'you id chanel'
DISALLOWED_GUILDS = 'you id chanel'
DISCORD_CHANNEL_ID_TG = "you id chanel"
TELEGRAM_CHAT_ID = 'you id chanel TG'


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
        logging.info(f'Бот {bot.user.name} успешно запущен!')
    except Exception as e:
        logging.error(f'Ошибка синхронизации команд: {e}')

class MyView(discord.ui.View):
    def __init__(self, user: discord.Member, reason: str, end_date: str, timeout=None):
        super().__init__(timeout=timeout)
        self.user = user
        self.reason = reason
        self.end_date = end_date

    async def is_allowed_to_manage(self, interaction: discord.Interaction) -> bool:
        # Проверяем, что инициатор - не сам пользователь, подающий заявку, и имеет одну из разрешенных ролей
        if interaction.user == self.user:
            await interaction.response.send_message("Вы не можете управлять собственным отпуском.", ephemeral=True)
            return False

        allowed_roles = [discord.utils.get(interaction.guild.roles, name=role_name) for role_name in ALLOWED_ROLES]
        user_roles = set(interaction.user.roles)

        if not any(role in user_roles for role in allowed_roles):
            await interaction.response.send_message("У вас нет прав для управления этой заявкой на отпуск.", ephemeral=True)
            return False

        return True

    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_allowed_to_manage(interaction):
            return

        guild = interaction.guild
        vacation_role = discord.utils.get(guild.roles, name=VACATION_ROLE_NAME)
        if not vacation_role:
            await interaction.response.send_message(">>> Ошибка: роль отпуска не найдена. Пожалуйста, создайте ее.")
            return

        try:
            await self.user.add_roles(vacation_role)
            confirmation_message = (
                f">>> Отпуск по причине '{self.reason}' до {self.end_date} подтвержден. "
                f"Роль '{VACATION_ROLE_NAME}' добавлена для {self.user.mention}."
            )
            await interaction.channel.send(confirmation_message)
            logging.info(f">>> Роль '{VACATION_ROLE_NAME}' добавлена пользователю {self.user} для отпуска.")

            # Деактивация кнопок "Подтвердить" и "Отклонить"
            self.confirm.disabled = True
            self.decline.disabled = True
            await interaction.response.edit_message(view=self)
        except Exception as e:
            await interaction.response.send_message("Ошибка при добавлении роли отпуска.")
            logging.error(f">>> Ошибка при добавлении роли '{VACATION_ROLE_NAME}' пользователю {self.user}: {e}")

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_allowed_to_manage(interaction):
            return

        await interaction.response.send_message("Отпуск был отклонён.")
        logging.info(f">>> Отпуск пользователя {self.user} был отклонён.")

        # Деактивация кнопок "Подтвердить" и "Отклонить"
        self.confirm.disabled = True
        self.decline.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Снять досрочно", style=discord.ButtonStyle.blurple)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.is_allowed_to_manage(interaction):
            return

        guild = interaction.guild
        vacation_role = discord.utils.get(guild.roles, name=VACATION_ROLE_NAME)
        if not vacation_role or vacation_role not in self.user.roles:
            await interaction.response.send_message(f">>> Роль '{VACATION_ROLE_NAME}' не найдена или не назначена.")
            return

        try:
            await self.user.remove_roles(vacation_role)
            await interaction.response.send_message(">>> Роль отпуска снята досрочно.")
            logging.info(f">>> Роль '{VACATION_ROLE_NAME}' снята у пользователя {self.user} досрочно.")
            await interaction.response.edit_message(view=self)
        except Exception as e:
            await interaction.response.send_message(">>> Ошибка при снятии роли отпуска.", ephemeral=True)
            logging.error(f">>> Ошибка при снятии роли '{VACATION_ROLE_NAME}' у пользователя {self.user}: {e}")


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


@bot.tree.command(name="отпуск", description="Запросить отпуск с указанием причины и даты окончания.")
async def vacation(interaction: discord.Interaction, reason: str, end_date: str):
    if interaction.channel_id != VACATION_CHANNEL_ID:
        await interaction.response.send_message("Эта команда доступна только в определённом канале.", ephemeral=True)
        return

    # Проверка формата даты
    if not re.match(r'^\d{1,2}\.\d{1,2}\.(\d{2}|\d{4})$', end_date):
        await interaction.response.send_message("Неверный формат даты. Используйте дд.мм.гг или дд.мм.гггг.", ephemeral=True)
        return

    try:
        end_date_obj = datetime.strptime(end_date, '%d.%m.%Y') if len(end_date.split('.')[-1]) == 4 else datetime.strptime(end_date, '%d.%m.%y')
    except ValueError:
        await interaction.response.send_message("Ошибка преобразования даты. Проверьте формат.", ephemeral=True)
        return

    vacation_request = (
        f"Заявка на отпуск\n"
        f"Участник: {interaction.user.mention}\n"
        f"До: {end_date}\n"
        f"Причина: {reason}\n"
    )
    await interaction.channel.send(vacation_request)
    vacation_data[interaction.user.id] = end_date


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


@bot.event
async def on_voice_state_update(member, before, after):
    # Проверяем права на управление каналами у бота
    if not member.guild.me.guild_permissions.manage_channels:
        logging.warning("У бота нет прав на управление каналами.")
        return

    logging.info(f"{member.name} изменил состояние: {before.channel} -> {after.channel}")

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
            else:
                logging.info(f"Канал '{existing_channel.name}' уже существует для {member.name}")

    # Удаляем пустые каналы, кроме канала "Создать канал"
    if before.channel and before.channel.members == [] and before.channel.name not in {CREATE_CHANNEL_NAME, AFK_CHANNEL_NAME}:
        await check_and_delete_channel(before.channel)

    # Проверка, если пользователь покидает голосовой канал
    elif after.channel is None and before.channel is not None:
        await check_and_delete_channel(before.channel)

    # Проверка, если пользователь перемещается между каналами
    elif after.channel is not None and before.channel is not None and before.channel != after.channel:
        await check_and_delete_channel(before.channel)

async def check_and_delete_channel(channel):
    # Проверяем, находится ли канал в категории "Голосовые каналы" и не является ли он каналом "Создать канал" или AFK
    category = discord.utils.get(channel.guild.categories, name=VOICE_CHANNELS_CATEGORY_NAME)
    if channel.category == category and len(channel.members) == 0 and channel.name not in {CREATE_CHANNEL_NAME, AFK_CHANNEL_NAME}:
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
                embed.description += f"{role_name}:\n─── ⋆⋅☆⋅⋆ ──\n\n> {users_list}\n─── ⋆⋅☆⋅⋆ ──\n\n"  # Добавляем \n для пробела

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
            logger.info(f"Received message from Discord: {message.author.name} ({message.author.id}): {message.content}")
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


@dispatcher.message()
@dispatcher.message()
async def handle_telegram_message(message: Message):
    discord_channel = bot.get_channel(DISCORD_CHANNEL_ID_TG)
    if discord_channel:
        await discord_channel.send(f"Сообщение из Telegram: {message.from_user.full_name}: {message.text}")

async def start_telegram_bot():
    await dispatcher.start_polling(telegram_bot)

# Запуск бота
async def main():
    await asyncio.gather(
        dispatcher.start_polling(telegram_bot),
        bot.start(DISCORD_TOKEN),
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"Критическая ошибка: {e}")