import discord
from discord.ext import commands, tasks
from pymongo import MongoClient
from datetime import datetime, timezone
import re
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Конфигурация
TOKEN = os.getenv('DISCORD_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME')
VIP_CHANNEL_ID = os.getenv('VIP_CHANNEL_ID')
CLAN_VIP_CHANNEL_ID = os.getenv('CLAN_VIP_CHANNEL_ID')
CLAN_CREATION_CHANNEL_ID = os.getenv('CLAN_CREATION_CHANNEL_ID')
STATS_CHANNEL_ID = os.getenv('STATS_CHANNEL_ID')
WEBSITE_URL = os.getenv('WEBSITE_URL')
CLAN_WEBSITE_URL = os.getenv('CLAN_WEBSITE_URL')
CFG_FILES_PATH = os.getenv('CFG_FILES_PATH')
VIP_ROLE = os.getenv('VIP_ROLE')
ENTRY_REGEX = os.getenv('ENTRY_REGEX')
YOUR_GUILD_ID = os.getenv('YOUR_GUILD_ID')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MongoDBLogger")

# Подключение к базе данных
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users = db.users
clans = db.clans
usertemp = db.usertemp
clantemp = db.clantemp
squadjs = db.Player

# Подключение к базе данных
try:
    client = MongoClient(MONGO_URI)
    logger.info("Подключено к MongoDB")

    # Получаем базу данных
    db = client[DB_NAME]

    # Проверяем доступные коллекции
    collections = db.list_collection_names()
    logger.info(f"Доступные коллекции: {collections}")

except Exception as e:
    logger.error(f"Ошибка подключения к MongoDB: {e}")

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def update_config_file(steam_id):
    """Обновление конфигурационного файла"""
    for file_path in CFG_FILES_PATH:
        try:
            if not os.path.exists(file_path):
                print(f"Файл не найден: {file_path}")
                continue

            with open(file_path, 'r') as cfg_file:
                lines = cfg_file.readlines()

            with open(file_path, 'w') as cfg_file:
                for line in lines:
                    if steam_id not in line:
                        cfg_file.write(line)
            print(f"Удалена запись VIP для {steam_id}")
            return True
        except Exception as e:
            print(f"Ошибка при удалении из cfg: {e}")
            return False


async def add_vip_to_cfg(steam_id):
    """Добавление Steam ID в cfg файлы (только новые записи)"""
    for file_path in CFG_FILES_PATH:
        try:
            if not os.path.exists(file_path):
                print(f"Файл не найден: {file_path}")
                continue

            with open(file_path, 'r') as cfg_file:
                lines = cfg_file.readlines()

            # Проверяем, существует ли запись
            existing_entry = any(re.match(ENTRY_REGEX, line) and steam_id in line for line in lines)

            if not existing_entry:
                with open(file_path, 'a') as cfg_file:
                    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                    cfg_file.write(f"\nAdmin={steam_id}:VIP // {today}")
                    print(f"Добавлена новая запись для {steam_id} в {file_path}")
            else:
                print(f"Запись для {steam_id} уже существует в {file_path}")
        except Exception as e:
            print(f"Ошибка при обновлении файла {file_path}: {e}")


# Кнопки для VIP
class VIPButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # self.add_item(discord.ui.Button(
        #     label="Получить VIP",
        #     style=discord.ButtonStyle.link,
        #     url=WEBSITE_URL
        # ))
        self.add_item(SteamIDButton())  # Кнопка привязки Steam ID

    # @discord.ui.button(label="Проверить VIP статус", style=discord.ButtonStyle.blurple)
    # async def check_vip(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     user = users.find_one({"discord_id": interaction.user.id})

    #     response = []
    #     if user and user.get("vip_end"):
    #         end_date = user["vip_end"].strftime("%Y-%m-%d %H:%M")
    #         response.append(f"✅ Личный VIP активен до: {end_date}")

    #     await interaction.response.send_message(
    #         "\n".join(response) if response else "❌ VIP статус не активирован",
    #         ephemeral=True
    #     )


class VIPButtonsClan(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="Клановый VIP",
            style=discord.ButtonStyle.link,
            url=CLAN_WEBSITE_URL
        ))
        self.add_item(SteamIDButton())  # Кнопка привязки Steam ID

    @discord.ui.button(label="Проверить VIP статус", style=discord.ButtonStyle.blurple)
    async def check_vip(self, interaction: discord.Interaction, button: discord.ui.Button):
        clan_vip = clans.find_one({"members.discord_id": interaction.user.id, "vip_end": {"$exists": True}})

        response = []

        if clan_vip:
            end_date = clan_vip["vip_end"].strftime("%Y-%m-%d %H:%M")
            response.append(f"✅ Клановый VIP активен до: {end_date} (Клан: {clan_vip['name']})")

        await interaction.response.send_message(
            "\n".join(response) if response else "❌ VIP статус не активированы",
            ephemeral=True
        )


@tasks.loop(hours=24)
async def check_vip_expiration():
    now = datetime.now(timezone.utc)

    # Проверка обычных пользователей
    expired_users = users.find({"vip_end": {"$lt": now}})
    for user in expired_users:
        await update_config_file(user["steam_id"])
        users.update_one({"_id": user["_id"]}, {"$set": {"vip_end": None}})
        print(f"У пользователя {user['discord_name']} истек VIP статус.")

    # Проверка кланов
    expired_clans = clans.find({"vip_end": {"$lt": now}})
    for clan in expired_clans:
        for member in clan["members"]:
            await update_config_file(member["steam_id"])
        clans.update_one({"_id": clan["_id"]}, {"$set": {"vip_end": None}})
        print(f"У клана {clan['name']} истек VIP статус.")


@tasks.loop(seconds=10)
async def monitor_payment_status():
    """
    Мониторинг изменений в статусе оплаты пользователей и кланов.
    Сравнивает коллекции `users` и `usertemp`, а также `clans` и `clantemp`.
    Если флаг оплаты изменился на True, обновляет файлы конфигурации,
    выдает роли VIP, а также обновляет временные коллекции.
    """
    guild = bot.get_guild(YOUR_GUILD_ID)  # Замените на ID вашего сервера

    # Проверка изменений в коллекции users
    for user in users.find():
        temp_user = usertemp.find_one({"discord_id": user["discord_id"]})

        # Если статус оплаты изменился на True
        if user["payment_status"] and (not temp_user or not temp_user["payment_status"]):
            steam_id = user.get("steam_id")
            discord_id = user.get("discord_id")

            if steam_id:
                # Обновляем файлы конфигурации
                await add_vip_to_cfg(steam_id)

            if discord_id:
                # Выдаем роль VIP
                member = await guild.fetch_member(discord_id)
                vip_role = discord.utils.get(guild.roles, name=VIP_ROLE)
                if vip_role and member:
                    await member.add_roles(vip_role)
                    print(f"Роль VIP выдана пользователю {member.display_name}.")

            # Обновляем временную коллекцию usertemp
            usertemp.update_one(
                {"discord_id": user["discord_id"]},
                {"$set": {"payment_status": True}},
                upsert=True
            )

    # Проверка изменений в коллекции clans
    for clan in clans.find():
        temp_clan = clantemp.find_one({"name": clan["name"]})

        # Если статус оплаты изменился на True
        if clan.get("vip_status") and (not temp_clan or not temp_clan.get("vip_status")):
            role_id = clan.get("role_id")
            role = guild.get_role(role_id)

            if role:
                print(f"VIP статус активирован для клана {clan['name']}.")

            # Обновляем временную коллекцию clantemp
            clantemp.update_one(
                {"name": clan["name"]},
                {"$set": {"vip_status": True}},
                upsert=True
            )

    # Добавление роли при добавлении участника в клан
    for clan in clans.find():
        for member in clan.get("members", []):
            discord_id = member.get("discord_id")
            role_id = clan.get("role_id")

            if discord_id and role_id:
                member_obj = await guild.fetch_member(discord_id)
                role = guild.get_role(role_id)

                if role and member_obj and role not in member_obj.roles:
                    await member_obj.add_roles(role)
                    print(f"Роль '{role.name}' выдана пользователю {member_obj.display_name}.")


async def add_steam_id_to_user(discord_id, steam_id):
    """Добавляет Steam ID в коллекцию users на основе Discord ID."""
    users.update_one(
        {"discord_id": discord_id},
        {"$set": {"steam_id": steam_id}},
        upsert=True
    )

    usertemp.update_one(
        {"discord_id": discord_id},
        {"$set": {"steam_id": steam_id}},
        upsert=True
    )


async def remove_vip_from_cfg(steam_id):
    try:
        for file_path in CFG_FILES_PATH:
            if not os.path.exists(file_path):
                print(f"Файл не найден: {file_path}")
                continue

            with open(file_path, 'r') as cfg_file:
                lines = cfg_file.readlines()

            with open(file_path, 'w') as cfg_file:
                for line in lines:
                    if steam_id not in line:
                        cfg_file.write(line)
                print(f"Удалена запись VIP для {steam_id}")
        return True
    except Exception as e:
        print(f"Ошибка при удалении из cfg: {e}")
        return False


# Кнопка для привязки Steam ID
class SteamIDButton(discord.ui.Button):
    def __init__(self):
        # Устанавливаем параметры кнопки
        super().__init__(label="Привязать Steam ID", style=discord.ButtonStyle.green, custom_id="bind_steam_id")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SteamIDModal())


# Модальное окно для Steam ID
class SteamIDModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Привязка Steam ID")
        self.steam_id = discord.ui.TextInput(label="Введите ваш Steam ID",
                                             placeholder="76561198000000000", max_length=17)
        self.add_item(self.steam_id)

    async def on_submit(self, interaction: discord.Interaction):
        steam_id = self.steam_id.value
        if not re.match(r"^7656119\d{10}$", steam_id):
            await interaction.response.send_message("❌ Неверный формат Steam ID!", ephemeral=True)
            return

        # Сохраняем Steam ID
        users.update_one(
            {"discord_id": interaction.user.id},
            {"$set": {
                "steam_id": steam_id,
                "discord_name": interaction.user.display_name,
                "vip_end": None,
                "payment_status": False
            }},
            upsert=True
        )

        usertemp.update_one(
            {"discord_id": interaction.user.id},
            {"$set": {
                "steam_id": steam_id,
                "discord_name": interaction.user.display_name,
                "vip_end": None,
                "payment_status": False
            }},
            upsert=True
        )

        await interaction.response.send_message(f"✅ Steam ID {steam_id} привязан!", ephemeral=True)
        return


# Кнопка для создания клана
class ClanCreationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SteamIDButton())  # Добавляем кнопку SteamIDButton

    @discord.ui.button(label="Создать клан", style=discord.ButtonStyle.green, custom_id="create_clan_button")
    async def create_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ClanCreationModal())


# Модальное окно для создания клана
class ClanCreationModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Создание клана")
        self.clan_name = discord.ui.TextInput(label="Название клана", placeholder="Введите название", max_length=50)
        self.add_item(self.clan_name)

    async def on_submit(self, interaction: discord.Interaction):
        user_data = users.find_one({"discord_id": interaction.user.id})
        if not user_data or "steam_id" not in user_data:
            await interaction.response.send_message("❌ Сначала привяжите Steam ID!", ephemeral=True)
            return

        clan_name = self.clan_name.value

        if clans.find_one({"name": clan_name}):
            await interaction.response.send_message("❌ Клан с таким названием уже существует!", ephemeral=True)
            return

        role = await interaction.guild.create_role(name=clan_name, color=discord.Color.random())

        clan_data = {
            "name": clan_name,
            "leader": {"discord_id": interaction.user.id, "discord_name": interaction.user.display_name,
                       "steam_id": user_data["steam_id"]},
            "members": [{"discord_id": interaction.user.id, "discord_name": interaction.user.display_name,
                         "steam_id": user_data["steam_id"]}],
            "vip_members": [{"discord_id": interaction.user.id, "discord_name": interaction.user.display_name,
                             "steam_id": user_data["steam_id"]}],
            "role_id": role.id,
            "created_at": datetime.now(timezone.utc),
        }
        clantemp = {
            "name": clan_name,
            "leader": {"discord_id": interaction.user.id, "discord_name": interaction.user.display_name,
                       "steam_id": user_data["steam_id"]},
            "members": [{"discord_id": interaction.user.id, "discord_name": interaction.user.display_name,
                         "steam_id": user_data["steam_id"]}],
            "vip_members": [{"discord_id": interaction.user.id, "discord_name": interaction.user.display_name,
                             "steam_id": user_data["steam_id"]}],
            "role_id": role.id,
            "created_at": datetime.now(timezone.utc),
        }

        clans.insert_one(clan_data)
        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"✅ Клан '{clan_name}' создан!", ephemeral=True)


class ClanManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.add_item(discord.ui.Button(
            label="Проверить VIP статус",
            style=discord.ButtonStyle.blurple,
            custom_id="check_vip_status"
        ))


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.data.get('custom_id') == "check_vip_status":
        clan = clans.find_one({"leader.discord_id": interaction.user.id})

        if not clan or "vip_end" not in clan:
            await interaction.response.send_message("❌ Клан не имеет активного VIP.", ephemeral=True)
        else:
            end_date = clan["vip_end"].strftime("%Y-%m-%d %H:%M")
            await interaction.response.send_message(f"✅ Клановый VIP активен до: {end_date}", ephemeral=True)


# Команда для добавления участника в клан
@bot.tree.command(name="add_clan_member", description="Добавить участника в клан")
async def add_clan_member(interaction: discord.Interaction, member: discord.Member):
    clan = clans.find_one({"leader.discord_id": interaction.user.id})
    if interaction.channel.id != CLAN_CREATION_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Эту команду можно использовать только в канале <#{CLAN_CREATION_CHANNEL_ID}>!", ephemeral=True)
        return

    if not clan:
        await interaction.response.send_message("❌ Вы не лидер клана!", ephemeral=True)
        return

    user_data = users.find_one({"discord_id": member.id})
    if not user_data:
        await interaction.response.send_message("❌ Пользователь не привязал Steam ID!", ephemeral=True)
        return

    clans.update_one(
        {"name": clan["name"]},
        {"$push": {"members": {
            "discord_id": member.id,
            "discord_name": member.display_name,
            "steam_id": user_data.get("steam_id", "Не привязан")
        }}}
    )
    clantemp.update_one(
        {"name": clan["name"]},
        {"$push": {"members": {
            "discord_id": member.id,
            "discord_name": member.display_name,
            "steam_id": user_data.get("steam_id", "Не привязан")
        }}}
    )

    # Выдаем роль клана
    role = interaction.guild.get_role(clan["role_id"])
    await member.add_roles(role)

    await interaction.response.send_message(f"✅ {member.display_name} добавлен в клан!", ephemeral=True)


@bot.tree.command(name="add_clan_vip", description="Добавить участника в список VIP игроков клана")
async def add_clan_vip(interaction: discord.Interaction, member: discord.Member):
    clan = clans.find_one({"leader.discord_id": interaction.user.id})
    if interaction.channel.id != CLAN_CREATION_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Эту команду можно использовать только в канале <#{CLAN_CREATION_CHANNEL_ID}>!", ephemeral=True)
        return

    if not clan:
        await interaction.response.send_message("❌ Вы не лидер клана!", ephemeral=True)
        return

    user_data = users.find_one({"discord_id": member.id})
    if not user_data or not user_data.get("steam_id"):
        await interaction.response.send_message("❌ Пользователь не привязал Steam ID!", ephemeral=True)
        return

    clans.update_one(
        {"name": clan["name"]},
        {"$addToSet": {"vip_members": {
            "discord_id": member.id,
            "discord_name": member.display_name,
            "steam_id": user_data["steam_id"]
        }}}
    )
    clantemp.update_one(
        {"name": clan["name"]},
        {"$addToSet": {"vip_members": {
            "discord_id": member.id,
            "discord_name": member.display_name,
            "steam_id": user_data["steam_id"]
        }}}
    )

    # Добавляем запись только если ее нет
    await add_vip_to_cfg(user_data["steam_id"])

    await interaction.response.send_message(f"✅ {member.display_name} добавлен в VIP участников клана!", ephemeral=True)


# @bot.tree.command(name="delete_vip_members", description="Удалить участника из списка VIP игроков клана")
# async def delete_vip_members(interaction: discord.Interaction, member: discord.Member):
#     clan = clans.find_one({"leader.discord_id": interaction.user.id})
# if interaction.channel.id != CLAN_CREATION_CHANNEL_ID:
#         await interaction.response.send_message(f"❌ Эту команду можно использовать только в канале <#{CLAN_CREATION_CHANNEL_ID}>!", ephemeral=True)
#         return

#     if not clan:
#         await interaction.response.send_message("❌ Вы не лидер клана!", ephemeral=True)
#         return
#
#     clans.update_one(
#         {"name": clan["name"]},
#         {"$pull": {"vip_members": {"discord_id": member.id}}}
#     )
#
#     clantemp.update_one(
#         {"name": clan["name"]},
#         {"$pull": {"vip_members": {"discord_id": member.id}}}
#     )
#
#     user_data = users.find_one({"discord_id": member.id})
#     if user_data and user_data.get("steam_id"):
#         await update_config_file(user_data["steam_id"])
#
#     await interaction.response.send_message(f"✅ {member.display_name} удален из VIP участников клана!", ephemeral=True)


@bot.tree.command(name="members", description="Вывести состав клана")
async def members(interaction: discord.Interaction):
    if interaction.channel.id != CLAN_CREATION_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Эту команду можно использовать только в канале <#{CLAN_CREATION_CHANNEL_ID}>!", ephemeral=True)
        return

    clan = clans.find_one({"leader.discord_id": interaction.user.id})
    if not clan:
        await interaction.response.send_message("❌ Вы не лидер клана!", ephemeral=True)
        return

    members_list = "\n".join([f"- {member['discord_name']}" for member in clan["members"]])
    await interaction.response.send_message(f"Состав клана:\n{members_list}", ephemeral=True)


@bot.tree.command(name="members_vip", description="Вывести список VIP участников клана")
async def members_vip(interaction: discord.Interaction):
    clan = clans.find_one({"leader.discord_id": interaction.user.id})
    if interaction.channel.id != CLAN_CREATION_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Эту команду можно использовать только в канале <#{CLAN_CREATION_CHANNEL_ID}>!", ephemeral=True)
        return

    if not clan or not clan.get("vip_members"):
        await interaction.response.send_message("❌ В вашем клане нет VIP участников.", ephemeral=True)
        return

    vip_list = "\n".join([f"- {vip['discord_name']}" for vip in clan["vip_members"]])
    await interaction.response.send_message(f"VIP участники:\n{vip_list}", ephemeral=True)


@bot.tree.command(name="delete_player_clan", description="Удалить участника из клана")
async def delete_player_from_clan(interaction: discord.Interaction, member: discord.Member):
    clan = clans.find_one({"leader.discord_id": interaction.user.id})
    if interaction.channel.id != CLAN_CREATION_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Эту команду можно использовать только в канале <#{CLAN_CREATION_CHANNEL_ID}>!", ephemeral=True)
        return

    if not clan:
        await interaction.response.send_message("❌ Вы не лидер клана!", ephemeral=True)
        return

    member_data = next((m for m in clan["members"] if m["discord_id"] == member.id), None)

    if not member_data:
        await interaction.response.send_message("❌ Этот пользователь не найден в клане.", ephemeral=True)
        return

    # Проверка наличия в vip_members
    if any(vip["discord_id"] == member.id for vip in clan.get("vip_members", [])):
        clans.update_one(
            {"name": clan["name"]},
            {"$pull": {"vip_members": {"discord_id": member.id}}}
        )
        await update_config_file(member_data.get("steam_id", ""))  # Удаление из CFG

    clans.update_one(
        {"name": clan["name"]},
        {"$pull": {"members": {"discord_id": member.id}}}
    )

    role = interaction.guild.get_role(clan["role_id"])
    try:
        await member.remove_roles(role)
    except discord.errors.Forbidden:
        await interaction.response.send_message("❌ У бота недостаточно прав для удаления роли.", ephemeral=True)
        return
    except Exception as e:
        print(f"Ошибка при удалении роли: {e}")
        await interaction.response.send_message("❌ Произошла ошибка при удалении роли.", ephemeral=True)
        return

    await interaction.response.send_message(f"✅ {member.display_name} удален из клана!", ephemeral=True)


@bot.tree.command(name="stats", description="Показать статистику игрока")
async def stats(interaction: discord.Interaction, steam_id: str):
    # Проверка наличия определенной роли у пользователя
    required_role_name = VIP_ROLE
    user_roles = [role.name for role in interaction.user.roles]

    if required_role_name not in user_roles:
        await interaction.response.send_message("❌ У вас нет доступа к этой команде. Требуется роль VIP.",
                                                ephemeral=True)
        return

    # Получение статистики из базы данных
    player_stats = squadjs.find_one({"_id": steam_id})  # Используем squadjs

    if not player_stats:
        await interaction.response.send_message("❌ Игрок не найден.", ephemeral=True)
        return

    # Вычисление любимой роли и оружия
    favorite_role = max(player_stats["roles"].items(), key=lambda x: x[1], default=("Нет данных", 0))
    favorite_weapon = max(player_stats["weapons"].items(), key=lambda x: x[1], default=("Нет данных", 0))

    # Формирование сообщения со статистикой
    stats_message = (
        f"Никнейм: {player_stats['name']}\n"
        f"Убийств: {player_stats['kills']}\n"
        f"Смерти: {player_stats['death']}\n"
        f"КД: {player_stats['kd']}\n"
        f"Кол-во матчей: {player_stats['matches']['matches']}\n"
        f"Винрейт: {player_stats['matches']['winrate']}%\n"
        f"Любимая роль: {favorite_role[0]} ({favorite_role[1]})\n"
        f"Тимкилл: {player_stats['teamkills']}\n"
        f"Любимое оружие: {favorite_weapon[0]} ({favorite_weapon[1]})"
    )

    stats_embed = discord.Embed(
        title=f"Статистика игрока {player_stats['name']}",
        color=discord.Color.blue())

    stats_embed.add_field(name="Убийства", value=player_stats['kills'], inline=True)
    stats_embed.add_field(name="Смерти", value=player_stats['death'], inline=True)
    stats_embed.add_field(name="К/Д", value=player_stats['kd'], inline=False)
    stats_embed.add_field(name="Тимкиллы", value=player_stats['teamkills'])
    stats_embed.add_field(name="Количество матчей", value={player_stats['matches']['matches']}, inline=False)
    stats_embed.add_field(name="Винрейт", value=f"{player_stats['matches']['winrate']}%", inline=False)
    stats_embed.add_field(name="Любимая роль", value=f"{favorite_role[0]} ({favorite_role[1]})")
    stats_embed.add_field(name="Любимое оружие", value=f"{favorite_weapon[0]} ({favorite_weapon[1]})")
    stats_embed.set_footer(text='ZAVOD', icon_url='https://imgur.com/gPFMQFs.png')

    # Отправка сообщения пользователю
    await interaction.response.send_message(embed=stats_embed, ephemeral=False)


@bot.event
async def on_ready():
    print(f"Бот {bot.user.name} готов к работе!")

    # Запускаем задачи
    check_vip_expiration.start()
    monitor_payment_status.start()

    # Синхронизация команд
    try:
        synced = await bot.tree.sync()
        print(f"Синхронизировано {len(synced)} команд")
    except Exception as e:
        print(f"Ошибка синхронизации команд: {e}")

    # Отправка кнопок в каналы
    vip_channel = bot.get_channel(VIP_CHANNEL_ID)
    if vip_channel:
        await vip_channel.send("Привязка Steam ID и проверка VIP:", view=VIPButtons())

    clan_vip_channel = bot.get_channel(CLAN_VIP_CHANNEL_ID)
    if clan_vip_channel:
        await clan_vip_channel.send("Привязка Steam ID и проверка кланового VIP:", view=VIPButtonsClan())

    clan_creation_channel = bot.get_channel(CLAN_CREATION_CHANNEL_ID)
    if clan_creation_channel:
        await clan_creation_channel.send("Создание клана:", view=ClanCreationView())


bot.run(TOKEN)
