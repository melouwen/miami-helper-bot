import discord
from discord.ext import commands
import os
import asyncio
from aiohttp import web  # <--- ДОБАВЛЕНО

# ==== НАСТРОЙКИ ====\
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
REDUX_CHANNEL_ID = 1378147425881479240
REDUX_IMAGE_PATH = "0.jpg"
# ===================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- ДОБАВЛЕННЫЙ WEB-СЕРВЕР ---
async def web_server():
    """Создает минимальный веб-сервер для прохождения проверки хостинга."""
    # Получаем порт из переменной окружения (например, Heroku/Render)
    port = int(os.environ.get("PORT", 8080))

    # Очень простой обработчик: всегда возвращает 200 OK
    async def handler(request):
        return web.Response(text="Miami Helper Bot is running! (WebSocket OK)")

    app = web.Application()
    app.router.add_get('/', handler)

    # Запускаем веб-сервер на 0.0.0.0 (все интерфейсы)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)

    await site.start()
    print(f"Web server started on port {port}. This is required for hosting provider health check.")
    # Сервер будет слушать, пока задача не будет отменена
    await asyncio.Event().wait()

# -------------------------------

# Класс View для кнопок "Дать доступ" / "Закрыть ветку"
class ProofActionsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Сделаем View постоянным

    # Кнопка "Выдать доступ"
    @discord.ui.button(label="Выдать доступ", style=discord.ButtonStyle.green, custom_id="persistent_proof_access")
    async def give_access(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Проверяем, есть ли у пользователя роль OG/OWN (модератор)
        if interaction.user.get_role(OWN_ROLE_ID) is None and interaction.user.get_role(OG_ROLE_ID) is None:
            return await interaction.response.send_message("У вас нет прав для выдачи доступа.", ephemeral=True)

        # ID владельца ветки (пользователь, который подал пруф)
        # Ветка создается как канал с именем типа 'proof-user-id'
        try:
            user_id = int(interaction.channel.name.split('-')[-1])
            member = interaction.guild.get_member(user_id)
        except Exception:
            return await interaction.response.send_message("Не удалось определить владельца ветки.", ephemeral=True)

        if member:
            access_role = interaction.guild.get_role(ACCESS_ROLE_ID)
            if access_role and access_role not in member.roles:
                await member.add_roles(access_role, reason="Доступ выдан по пруфу.")
                await interaction.channel.send(f"{interaction.user.mention} выдал доступ ({access_role.mention}) пользователю {member.mention}.")
            elif access_role in member.roles:
                await interaction.channel.send(f"{member.mention} уже имеет роль доступа. Ветка закрывается.")
            else:
                return await interaction.response.send_message("Ошибка: Не удалось найти роль доступа.", ephemeral=True)
        else:
            await interaction.channel.send("Ошибка: Не удалось найти пользователя в этом Discord.")

        # Архивируем и перемещаем ветку
        await self.archive_thread(interaction)

    # Кнопка "Закрыть ветку"
    @discord.ui.button(label="Закрыть ветку", style=discord.ButtonStyle.red, custom_id="persistent_proof_close")
    async def close_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Проверяем, есть ли у пользователя роль OG/OWN (модератор)
        if interaction.user.get_role(OWN_ROLE_ID) is None and interaction.user.get_role(OG_ROLE_ID) is None:
            return await interaction.response.send_message("У вас нет прав для закрытия ветки.", ephemeral=True)

        await interaction.channel.send(f"Ветка закрыта модератором {interaction.user.mention}.")
        # Архивируем и перемещаем ветку
        await self.archive_thread(interaction)

    async def archive_thread(self, interaction: discord.Interaction):
        archive_category = interaction.guild.get_channel(CATEGORY_ARCHIVE_ID)
        restricted_role = interaction.guild.get_role(RESTRICTED_ROLE_ID)

        if archive_category and restricted_role:
            # Сначала перемещаем
            await interaction.channel.edit(category=archive_category)
            # Убираем права на просмотр у всех, кроме определенных ролей
            await interaction.channel.set_permissions(
                interaction.guild.default_role,
                read_messages=False
            )
            # Добавляем права для модераторов/админов
            await interaction.channel.set_permissions(
                interaction.guild.get_role(OWN_ROLE_ID),
                read_messages=True,
                send_messages=False # Только для просмотра архива
            )
            await interaction.channel.set_permissions(
                interaction.guild.get_role(OG_ROLE_ID),
                read_messages=True,
                send_messages=False
            )
            await interaction.channel.set_permissions(
                restricted_role,
                read_messages=False
            )
            # Архивируем (устанавливаем статус archive)
            if interaction.channel.type == discord.ChannelType.text:
                await interaction.response.edit_message(view=None) # Удаляем кнопки
                await interaction.channel.send("Ветка перемещена в архив и закрыта для новых сообщений.")
        else:
            await interaction.channel.send("Ошибка при архивации: Не найдена категория архива или роль ограничений.")

# Класс View для кнопки "Подать пруф"
class ProofButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Сделаем View постоянным

    @discord.ui.button(label="Подать пруф", style=discord.ButtonStyle.blurple, custom_id="persistent_proof_request")
    async def request_proof(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = guild.get_channel(CATEGORY_ID)

        if not category:
            return await interaction.response.send_message("Ошибка: Категория для создания веток не найдена.", ephemeral=True)

        # Проверяем, есть ли уже открытая ветка для этого пользователя
        existing_thread_name = f"proof-{interaction.user.id}"
        for channel in category.channels:
            if channel.name == existing_thread_name:
                return await interaction.response.send_message(f"У вас уже есть открытая ветка для пруфа: {channel.mention}", ephemeral=True)


        # Создаем новую приватную текстовую ветку
        # Настраиваем права доступа: видит только автор и модераторы
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_role(OWN_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.get_role(OG_ROLE_ID): discord.PermissionOverwrite(read_messages=True, send_messages=True),
            bot.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        new_thread = await guild.create_text_channel(
            name=existing_thread_name,
            category=category,
            overwrites=overwrites
        )

        # Отправляем первое сообщение в ветку с инструкцией
        try:
            proof_file = discord.File(LOCAL_PROOF_IMAGE_PATH, filename="dadsad.png")
            file_attachment_name = "dadsad.png"
        except FileNotFoundError:
            proof_file = None
            file_attachment_name = "(Изображение не найдено)"

        embed = discord.Embed(
            title="✅ Подтверждение доступа к Miami Redux",
            description=f"""
Привет, {interaction.user.mention}!
Эта ветка создана специально для тебя.

Для получения доступа к Miami Redux необходимо предоставить **скриншот**, где видно, что ты:
1. **Лайкнул** это видео: `[Ссылка на видео]`
2. **Написал комментарий** под этим видео.
3. **Подписан** на канал: **@nonomimik** (на скрине должно быть видно твой профиль с активной подпиской).

Загрузи скриншот ниже! 

**Пример скриншота:**
""",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Модераторы проверят твой пруф и выдадут доступ.")

        if proof_file:
            embed.set_image(url=f"attachment://{file_attachment_name}")

        await new_thread.send(
            content=f"{interaction.user.mention}, ожидаем ваш пруф.",
            embed=embed,
            file=proof_file if proof_file else discord.utils.MISSING,
            view=ProofActionsView() # Добавляем кнопки модераторов
        )

        await interaction.response.send_message(f"Ваша личная ветка для пруфа создана: {new_thread.mention}", ephemeral=True)


# Регистрация постоянных View при запуске бота
@bot.event
async def on_ready():
    print(f'{bot.user.name} успешно подключился к Discord!')

    # Регистрация всех постоянных (persistent) View
    bot.add_view(ProofButtonView())
    bot.add_view(ProofActionsView())

    # Единоразовая отправка сообщения с кнопкой "Подать пруф" (если канала нет, бот пропустит)
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if channel and channel.last_message_id is None: # Проверяем, что канал пуст, чтобы не спамить
            await channel.send("Нажмите кнопку, чтобы подать пруф для получения доступа:", view=ProofButtonView())
    except Exception as e:
        print(f"Ошибка при отправке начального сообщения: {e}")

    # Запускаем отправку Redux сообщения
    bot.loop.create_task(send_redux_announcement())


# Функция для отправки анонса Redux
async def send_redux_announcement():
    await bot.wait_until_ready()
    redux_channel = bot.get_channel(REDUX_CHANNEL_ID)

    if redux_channel:
        try:
            redux_file = None
            file_attachment_name = ""
            try:
                redux_file = discord.File(REDUX_IMAGE_PATH, filename=REDUX_IMAGE_PATH)
                file_attachment_name = REDUX_IMAGE_PATH
            except FileNotFoundError:
                print(f"Файл {REDUX_IMAGE_PATH} не найден. Отправка без изображения.")

            embed = discord.Embed(
                title="✨ MIAMI REDUX - ВЫШЕЛ! ✨",
                description="""
С гордостью объявляем о выходе нашего редукса!

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

            # Находим последнее сообщение бота в канале
            last_message = None
            async for message in redux_channel.history(limit=5):
                if message.author == bot.user:
                    last_message = message
                    break

            # Если сообщение уже есть, редактируем его. Иначе — отправляем новое.
            if last_message:
                await last_message.edit(embed=embed, attachments=[redux_file] if redux_file else [])
            else:
                await redux_channel.send(
                    embed=embed,
                    file=redux_file if redux_file else discord.utils.MISSING,
                    content="@everyone" # Можно добавить пинг, если нужно
                )
            print("Объявление о Redux отправлено/обновлено.")

        except Exception as e:
            print(f"Ошибка при отправке Redux объявления: {e}")


# ГЛАВНЫЙ БЛОК ЗАПУСКА
if __name__ == "__main__":
    if TOKEN:
        # Получаем цикл событий
        loop = asyncio.get_event_loop()

        # Запускаем задачи бота и веб-сервера параллельно
        # bot.start() используется вместо bot.run() для асинхронного запуска в цикле
        tasks = [
            loop.create_task(web_server()), # Задача для веб-сервера
            loop.create_task(bot.start(TOKEN)) # Задача для Discord-бота
        ]

        # Ожидаем завершения обеих задач. Бот должен работать бесконечно.
        try:
            loop.run_until_complete(asyncio.gather(*tasks))
        except KeyboardInterrupt:
            # Обработка остановки
            print("Бот и веб-сервер остановлены пользователем.")
        finally:
            loop.run_until_complete(bot.close())
            loop.close()
    else:
        print("Ошибка: Токен Discord не найден в переменной окружения DISCORD_TOKEN.")