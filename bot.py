import discord
from discord.ext import commands
import os

# ==== НАСТРОЙКИ ====
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = 1433063812424274093
CATEGORY_ID = 1433065777824792636  # Основная категория для веток пруфов

OWN_ROLE_ID = 1378144494075248762  # Роль для видимости и доступа к кнопкам
OG_ROLE_ID = 1428837597270118631   # Вторая роль для видимости и доступа к кнопкам

# ОСНОВНАЯ РОЛЬ, КОТОРАЯ БУДЕТ ВЫДАВАТЬСЯ
ACCESS_ROLE_ID = 1381010515584618536

# ID ДЛЯ АРХИВАЦИИ
CATEGORY_ARCHIVE_ID = 1433080596179193999
RESTRICTED_ROLE_ID = 1433065303046361119

MAIN_EMBED_IMAGE_URL = "0.jpg"
LOCAL_PROOF_IMAGE_PATH = "dadsad.png"

# НОВЫЕ НАСТРОЙКИ ДЛЯ СООБЩЕНИЯ О РЕДУКСЕ
REDUX_CHANNEL_ID = 1431721606039867515
REDUX_IMAGE_PATH = "0.jpg"  # Файл 0.jpg в корне проекта
# ====================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def _archive_channel(channel: discord.TextChannel, guild: discord.Guild, interaction: discord.Interaction):
    """Перемещает канал в категорию архива и ограничивает доступ."""
    archive_category = guild.get_channel(CATEGORY_ARCHIVE_ID)
    restricted_role = guild.get_role(RESTRICTED_ROLE_ID)

    if not archive_category or not restricted_role:
        await interaction.followup.send(
            "Ошибка: Не найдена категория архива или роль для ограниченного доступа. Проверьте ID в настройках.",
            ephemeral=True
        )
        return False

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        restricted_role: discord.PermissionOverwrite(view_channel=True)
    }

    try:
        await channel.edit(
            category=archive_category,
            overwrites=overwrites,
            name=f"архив-{channel.name.replace('пруф-', '')}"
        )
        return True
    except Exception as e:
        await interaction.followup.send(f"Ошибка при архивации канала: {e}", ephemeral=True)
        return False


class ProofActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        og_role = interaction.guild.get_role(OG_ROLE_ID)
        own_role = interaction.guild.get_role(OWN_ROLE_ID)

        if isinstance(interaction.user, discord.Member):
            is_allowed = og_role in interaction.user.roles or own_role in interaction.user.roles
        else:
            is_allowed = False

        if not is_allowed:
            await interaction.response.send_message(
                "У тебя нет прав для использования этой кнопки (требуется роль OWN или OG).",
                ephemeral=True
            )
        return is_allowed

    @discord.ui.button(label="Выдать доступ", style=discord.ButtonStyle.green, custom_id="give_access_button")
    async def give_access(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel
        moderator = interaction.user

        try:
            user_id = int(channel.topic.split()[-1])
            member = guild.get_member(user_id)
        except (ValueError, AttributeError):
            await interaction.followup.send("Не удалось найти ID пользователя в топике канала.", ephemeral=True)
            return

        if not member:
            await interaction.followup.send("Пользователь не найден на сервере.", ephemeral=True)
            return

        access_role = guild.get_role(ACCESS_ROLE_ID)
        roles_to_give = [role for role in [access_role] if role and role not in member.roles]

        if roles_to_give:
            try:
                await member.add_roles(*roles_to_give, reason="Пруф принят.")
                role_names = ", ".join([r.name for r in roles_to_give])
                await channel.send(
                    f"**Пруф принят!**\n"
                    f"Модератор {moderator.mention} выдал пользователю {member.mention} роли: **{role_names}**."
                )
            except discord.Forbidden:
                await channel.send("Ошибка: У бота недостаточно прав для выдачи ролей.")
                return
            except Exception as e:
                await channel.send(f"Ошибка при выдаче ролей: {e}")
                return
        else:
            await channel.send(
                f"**Пруф принят!**\n"
                f"Модератор {moderator.mention} подтвердил — у {member.mention} уже есть роль."
            )

        success = await _archive_channel(channel, guild, interaction)
        if success:
            await interaction.followup.send(f"Ветка закрыта и перемещена в архив: {channel.mention}", ephemeral=True)
            self.stop()

    @discord.ui.button(label="Закрыть ветку", style=discord.ButtonStyle.red, custom_id="close_thread_button")
    async def close_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        moderator = interaction.user

        await channel.send(
            f"**Ветка закрыта без выдачи ролей.**\n"
            f"Модератор: {moderator.mention}"
        )

        success = await _archive_channel(channel, interaction.guild, interaction)
        if success:
            await interaction.followup.send(f"Ветка закрыта и перемещена в архив: {channel.mention}", ephemeral=True)
            self.stop()


class ProofButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        bot.add_view(ProofActionsView())

    @discord.ui.button(label="Отправить пруф", style=discord.ButtonStyle.blurple, custom_id="proof_button")
    async def send_proof(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(CATEGORY_ID)

        if not category:
            await interaction.followup.send("Категория не найдена.", ephemeral=True)
            return

        # === Проверка на существующую ветку ===
        for channel in category.channels:
            if (
                    interaction.user.name.lower() in channel.name.lower()
                    or (channel.topic and str(interaction.user.id) in channel.topic)
            ):
                await interaction.followup.send(
                    f"У тебя уже есть активная ветка!\n➡️ {channel.mention}",
                    ephemeral=True
                )
                return

        # === Создаём ветку ===
        thread = await category.create_text_channel(
            name=f"пруф-{interaction.user.name}",
            topic=f"Проверка пруфа пользователя {interaction.user.id}",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.get_role(OWN_ROLE_ID): discord.PermissionOverwrite(view_channel=True),
                guild.get_role(OG_ROLE_ID): discord.PermissionOverwrite(view_channel=True),
                interaction.user: discord.PermissionOverwrite(view_channel=True)
            }
        )

        # === EMBED С ПРИМЕРОМ И УСЛОВИЯМИ ===
        proof_file = None
        file_attachment_name = "proof_example.png"
        try:
            proof_file = discord.File(LOCAL_PROOF_IMAGE_PATH, filename=file_attachment_name)
        except FileNotFoundError:
            await interaction.followup.send(
                f"Ошибка: Файл примера пруфа не найден по пути `{LOCAL_PROOF_IMAGE_PATH}`. Ветка создана, но без изображения.",
                ephemeral=True
            )
        except Exception as e:
            print(f"Ошибка при загрузке локального файла: {e}")

        embed = discord.Embed(
            title="Пример выполненных условий",
            description="Вот пример оформленного пруфа для получения доступа:",
            color=discord.Color.green()
        )

        embed.add_field(
            name="Условия выдачи:",
            value=(
                "• Лайк\n"
                "• Комментарий\n"
                "• Подписка на канал [**nonomimik**](https://www.youtube.com/@nonomimik)"
            ),
            inline=False
        )

        if proof_file:
            embed.set_image(url=f"attachment://{file_attachment_name}")

        own_role = guild.get_role(OWN_ROLE_ID)

        # === ОТПРАВКА СООБЩЕНИЯ ТОЛЬКО С УПОМИНАНИЕМ OWN ===
        await thread.send(
            content=f"{own_role.mention}\n"
                    f"Пользователь {interaction.user.mention} создал ветку для пруфа.\n\n"
                    f"**Ожидаем пруф...**",
            embed=embed,
            file=proof_file if proof_file else discord.utils.MISSING,
            view=ProofActionsView()
        )

        await interaction.followup.send(
            f"Ветка для пруфа создана: {thread.mention}",
            ephemeral=True
        )


@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")

    bot.add_view(ProofButton())
    bot.add_view(ProofActionsView())

    # === 1. ГЛАВНОЕ СООБЩЕНИЕ С КНОПКОЙ (PROOFS) ===
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        is_welcome_sent = False
        async for message in channel.history(limit=20):
            if message.author == bot.user and message.embeds:
                embed = message.embeds[0]
                if embed.title == "Привет! Я Miami Helper":
                    is_welcome_sent = True
                    break

        if not is_welcome_sent:
            embed = discord.Embed(
                title="Привет! Я Miami Helper",
                description=(
                    "Нажми на кнопку ниже, чтобы отправить пруф выполнения действий.\n\n"
                    "После этого будет создана отдельная ветка для проверки!"
                ),
                color=discord.Color.teal()
            )
            embed.set_image(url=MAIN_EMBED_IMAGE_URL)
            embed.set_footer(text="В случае ошибок и т.д. пишите в ДС - @britishpoundexchange")

            view = ProofButton()
            await channel.send(embed=embed, view=view)
            print("Отправлено новое сообщение с кнопкой.")

    # === 2. СООБЩЕНИЕ О РЕДУКСЕ ===
    redux_channel = bot.get_channel(REDUX_CHANNEL_ID)
    if redux_channel:
        unique_check_title = "ДРОП | MIAMI REDUX!"
        redux_message_sent = False

        async for message in redux_channel.history(limit=5):
            if message.author == bot.user and message.embeds:
                embed = message.embeds[0]
                if unique_check_title in embed.title:
                    redux_message_sent = True
                    print("Сообщение о Redux уже существует.")
                    break

        if not redux_message_sent:
            redux_file = None
            file_attachment_name = "redux_preview.jpg"
            try:
                redux_file = discord.File(REDUX_IMAGE_PATH, filename=file_attachment_name)
            except FileNotFoundError:
                print(f"Ошибка: Файл {REDUX_IMAGE_PATH} не найден. Отправка без фото.")
            except Exception as e:
                print(f"Ошибка при загрузке файла Redux: {e}")

            embed = discord.Embed(
                title=unique_check_title,
                description="""
Привет всем! Мы с гордостью объявляем о выходе нашего редукса!

Этот релиз, созданный для того, чтобы поднять игровой уровень на новый этап, включает в себя:

**Легитный редукс для игры на Majestic RP:** Включает в себя все необходимые текстуры.

**Оптимизация:** Убраны лишние детали и оптимизировано множество локаций.

Не пропустите новый опыт игры!
                """,
                color=discord.Color.gold()
            )

            embed.add_field(
                name="Обзор и демонстрация",
                value="[Смотреть на YouTube](https://youtu.be/wZdhF5oPaXM?si=KdMQD3l2zNJsh_xh)",
                inline=False
            )
            embed.add_field(
                name="Прямая ссылка на установку",
                value="[Скачать с Google Drive](https://drive.google.com/drive/folders/14HrpZ3-7WPBvDOeUNaclN6aIPQXuRLUE?usp=drive_link)",
                inline=False
            )

            if redux_file:
                embed.set_image(url=f"attachment://{file_attachment_name}")

            embed.set_footer(text="Установи и наслаждайся обновленной графикой!")

            try:
                await redux_channel.send(
                    embed=embed,
                    file=redux_file if redux_file else discord.utils.MISSING
                )
                print("Отправлено новое сообщение о Redux.")
            except Exception as e:
                print(f"Ошибка при отправке сообщения в канал Redux: {e}")



bot.run(TOKEN)
