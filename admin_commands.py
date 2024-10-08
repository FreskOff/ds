import discord
from discord.ext import commands
from discord.utils import get
from dotenv import load_dotenv
import os
import json
import time
import asyncio
import re
import random
from collections import defaultdict

# Загрузка токена из файла .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Настройка ID ролей
ROLES = {
    'moderator_role': 1292360394626564128,  # ID роли модератора
    'mute_role': 1292360480350015498        # ID роли мута
}

# Инициализация бота
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Хранение истории мутов, варнов и банов
punishment_data = defaultdict(list)
# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Логи действий в отдельный канал
async def log_action(ctx, action, member, reason=None):
    log_channel = discord.utils.get(ctx.guild.text_channels, name="admin-logs")
    if not log_channel:
        return
    log_message = f"{ctx.author} выполнил команду {action} на {member.name}"
    if reason:
        log_message += f" с причиной: {reason}"
    await log_channel.send(log_message)
# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Предупреждение пользователя через ЛС
async def warn_user(ctx, member, warning_message):
    try:
        await member.send(f"Вам выдано предупреждение: {warning_message}")
    except discord.Forbidden:
        await ctx.send(f"Не удалось отправить предупреждение {member.name}, у него закрыты ЛС.")
# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Проверка наличия роли модератора
def has_moderator_role(ctx):
    moderator_role = discord.utils.get(ctx.guild.roles, id=ROLES['moderator_role'])
    return moderator_role in ctx.author.roles
# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Функция для преобразования строки времени в секунды
def parse_time(time_str):
    time_units = {'m': 60, 'h': 3600, 'd': 86400}  # минуты, часы, дни
    match = re.match(r"(\d+)([mhd])", time_str)
    
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        return amount * time_units[unit]
    else:
        raise ValueError("Неверный формат времени. Используйте m (минуты), h (часы), или d (дни).")
# НОВОЕ 
# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Функция для логирования изменений сообщений
@bot.event
async def on_message_edit(before, after):
    log_channel = discord.utils.get(before.guild.text_channels, name="logs")
    if log_channel is None:
        return
    
    if before.content != after.content:  # Проверяем, изменилось ли сообщение
        embed = discord.Embed(title="Сообщение изменено", color=discord.Color.orange())
        embed.add_field(name="Автор", value=before.author.mention, inline=False)
        embed.add_field(name="До изменения", value=before.content or "Пусто", inline=False)
        embed.add_field(name="После изменения", value=after.content or "Пусто", inline=False)
        embed.add_field(name="Канал", value=before.channel.mention, inline=False)
        await log_channel.send(embed=embed)

# Функция для логирования удалённых сообщений
@bot.event
async def on_message_delete(message):
    log_channel = discord.utils.get(message.guild.text_channels, name="logs")
    if log_channel is None:
        return
    
    embed = discord.Embed(title="Сообщение удалено", color=discord.Color.red())
    embed.add_field(name="Автор", value=message.author.mention, inline=False)
    embed.add_field(name="Содержание", value=message.content or "Пусто", inline=False)
    embed.add_field(name="Канал", value=message.channel.mention, inline=False)
    await log_channel.send(embed=embed)
# -----------------------------------------------------------------------------------------------------------------------------------------------------
@bot.command(name='участники')
async def member_count(ctx):
    await ctx.send(f"На сервере {ctx.guild.member_count} участников.")
# -----------------------------------------------------------------------------------------------------------------------------------------------------
@bot.command(name='случайный')
async def random_member(ctx):
    random_user = random.choice(ctx.guild.members)
    await ctx.send(f"Случайный участник: {random_user.mention}")
# -----------------------------------------------------------------------------------------------------------------------------------------------------
#МУТ РАЗМУТ

@bot.command(name='мут', aliases=['мьют', 'замутить', 'mute', 'muteuser']) 
async def mute(ctx, member: discord.Member = None, time: str = None, *, reason=None):
    if not has_moderator_role(ctx):
        await ctx.send("У вас нет прав для выполнения этой команды.")
        return
    
    if member is None or time is None or reason is None:
        await ctx.send("Неправильное использование команды. Пример: !мут @пользователь (время, например 10m) причина")
        return

    try:
        duration_in_seconds = parse_time(time)
    except ValueError as e:
        await ctx.send(str(e))
        return

    mute_role = discord.utils.get(ctx.guild.roles, id=ROLES['mute_role'])
    if mute_role is None:
        await ctx.send("Роль мута не найдена.")
        return
    
    await member.add_roles(mute_role, reason=reason)
    await ctx.send(f"{member.mention} был замьючен на {time} по причине: {reason}")
    
    # Логируем действие
    await log_action(ctx, 'мут', member, reason)
    
    # Записываем в историю
    if member.id not in punishment_data:
        punishment_data[member.id] = []
    punishment_data[member.id].append(f"Мут на {time} по причине: {reason}")
    
    # Снятие мута через заданное время
    await unmute_member_after(ctx, member, duration_in_seconds)

# Функция для автоматического снятия мута
async def unmute_member_after(ctx, member, duration):
    await asyncio.sleep(duration)
    mute_role = discord.utils.get(ctx.guild.roles, id=ROLES['mute_role'])
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await ctx.send(f'{member.mention} был размьючен автоматически.')  


# Команда !размут
@bot.command(name='размут', aliases=['размьют', 'unmute', 'unmuteuser', 'снятьмут'])
async def unmute(ctx, member: discord.Member = None):
    if not has_moderator_role(ctx):
        await ctx.send("У вас нет прав для выполнения этой команды.")
        return
    
    if member is None:
        await ctx.send("Неправильное использование команды. Пример: !размут @пользователь")
        return

    mute_role = discord.utils.get(ctx.guild.roles, id=ROLES['mute_role'])
    if mute_role is None:
        await ctx.send("Роль мута не найдена.")
        return

    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await ctx.send(f'{member.mention} был размьючен.')
        
        # Логируем действие
        await log_action(ctx, 'размут', member, 'Команда размут')
    else:
        await ctx.send(f'{member.mention} не был в муте.')
# -----------------------------------------------------------------------------------------------------------------------------------------------------
#КОМАНДА БАН


@bot.command(name='бан', aliases=['ban', 'banuser'])
async def ban(ctx, member: discord.Member = None, *, reason=None):
    if not has_moderator_role(ctx):
        await ctx.send("У вас нет прав для выполнения этой команды.")
        return
    
    if member is None or reason is None:
        await ctx.send("Неправильное использование команды. Пример: !бан @пользователь причина")
        return

    await member.ban(reason=reason)
    await ctx.send(f'{member.mention} был забанен по причине: {reason}')

    # Логируем действие
    await log_action(ctx, 'бан', member, reason)

# !разбан
@bot.command(name='разбан', aliases=['разбанить', 'unban'])
async def unban(ctx, user_id: int = None, *, reason=None):
    if not has_moderator_role(ctx):
        await ctx.send("У вас нет прав для выполнения этой команды.")
        return
    
    if user_id is None:
        await ctx.send("Неправильное использование команды. Пример: !разбан <ID пользователя> причина")
        return

    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        await ctx.send(f'{user.mention} был разбанен. Причина: {reason}' if reason else f'{user.mention} был разбанен.')

        # Логируем действие
        await log_action(ctx, 'разбан', user, reason if reason else 'Команда размут')
    except discord.NotFound:
        await ctx.send("Пользователь не найден в бане.")
    except discord.Forbidden:
        await ctx.send("У меня нет прав для разбанивания этого пользователя.")
    except Exception as e:
        await ctx.send(f"Произошла ошибка: {str(e)}")


# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Команда !варн
@bot.command(name='варн')
async def warn(ctx, member: discord.Member, *, reason=None):
    if not has_moderator_role(ctx):
        await ctx.send("У вас нет прав для выполнения этой команды.")
        return
    
    if not member or not reason:
        await ctx.send("Неправильное использование команды. Пример: !варн @пользователь причина")
        return
    
    await warn_user(ctx, member, reason)
    await ctx.send(f"{member.mention} получил предупреждение: {reason}")
    
    # Логируем действие
    await log_action(ctx, 'варн', member, reason)
    
    # Записываем в историю
    punishment_data[member.id].append(f"Варн по причине: {reason}")

# Команда !анварн
@bot.command(name='анварн', aliases=['unwarn', 'снятьварн'])
async def unwarn(ctx, member: discord.Member, *, reason=None):
    if not has_moderator_role(ctx):
        await ctx.send("У вас нет прав для выполнения этой команды.")
        return
    
    if not member:
        await ctx.send("Неправильное использование команды. Пример: !анварн @пользователь")
        return
    
    if member.id not in punishment_data or not punishment_data[member.id]:
        await ctx.send(f"{member.mention} не имеет предупреждений.")
        return

    # Удаляем последнее предупреждение
    last_warn = punishment_data[member.id].pop()
    
    await ctx.send(f"{member.mention} был очищен от предупреждения: {last_warn}")
    
    # Логируем действие
    await log_action(ctx, 'анварн', member, reason)

# -----------------------------------------------------------------------------------------------------------------------------------------------------

# Команда !история для просмотра истории наказаний
@bot.command(name='история')
async def history(ctx, member: discord.Member):
    if not has_moderator_role(ctx):
        await ctx.send("У вас нет прав для выполнения этой команды.")
        return
    
    history = punishment_data.get(member.id, [])
    if not history:
        await ctx.send(f"У {member.mention} нет истории наказаний.")
    else:
        await ctx.send(f"История наказаний {member.mention}:\n" + "\n".join(history))

# Команда !очистка для очистки сообщений
@bot.command(name='очистка')
async def clear(ctx, amount: int):
    if has_moderator_role(ctx):
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"Очищено {len(deleted)} сообщений.", delete_after=5)
    else:
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")      

# -----------------------------------------------------------------------------------------------------------------------------------------------------   
#НАЧАЛО ОБНОВЫ
# -----------------------------------------------------------------------------------------------------------------------------------------------------


# Загрузка данных об уровнях из файла
def load_levels():
    try:
        with open('levels.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Сохранение данных об уровнях в файл
def save_levels(levels):
    with open('levels.json', 'w') as f:
        json.dump(levels, f)

levels = load_levels()

# Список ID текстовых каналов, где можно получать опыт
allowed_text_channels = [1286723629517766810, ]

# Список ID голосовых каналов, где можно получать опыт
allowed_voice_channels = [1286723629517766811, ]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id not in allowed_text_channels:
        return

    user_id = str(message.author.id)
    if user_id not in levels:
        levels[user_id] = {'xp': 0, 'level': 1}

    levels[user_id]['xp'] += 2  # Количество XP за сообщение

    # Проверка на повышение уровня
    xp = levels[user_id]['xp']
    level = levels[user_id]['level']
    if xp >= level * 100:
        levels[user_id]['level'] += 1
        await message.channel.send(f'Поздравляю, {message.author.mention}, вы достигли уровня {levels[user_id]["level"]}!')

    save_levels(levels)
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id in allowed_voice_channels:
        if len(after.channel.members) >= 2 and after.self_mute == False and after.self_deaf == False:
            user_id = str(member.id)
            if user_id not in levels:
                levels[user_id] = {'xp': 0, 'level': 1}

            levels[user_id]['xp'] += 5  # Количество XP за нахождение в голосовом канале

            # Проверка на повышение уровня
            xp = levels[user_id]['xp']
            level = levels[user_id]['level']
            if xp >= level * 100:
                levels[user_id]['level'] += 1
                await member.guild.system_channel.send(f'Поздравляю, {member.mention}, вы достигли уровня {levels[user_id]["level"]}!')

            save_levels(levels)

@bot.command()
async def level(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    user_id = str(member.id)
    if user_id in levels:
        await ctx.send(f'{member.mention} на уровне {levels[user_id]["level"]} с {levels[user_id]["xp"]} XP.')
    else:
        await ctx.send(f'{member.mention} еще не имеет уровня.')

@bot.command()
async def топ(ctx):
    sorted_levels = sorted(levels.items(), key=lambda x: x[1]['xp'], reverse=True)
    top_users = sorted_levels[:10]
    leaderboard = '\n'.join([f'{ctx.guild.get_member(int(user_id)).mention}: {data["level"]} уровень, {data["xp"]} XP' for user_id, data in top_users])
    await ctx.send(f'Топ пользователей:\n{leaderboard}')

@bot.command()
async def я(ctx):
    user_id = str(ctx.author.id)
    if user_id in levels:
        await ctx.send(f'{ctx.author.mention}, вы на уровне {levels[user_id]["level"]} с {levels[user_id]["xp"]} XP.')
    else:
        await ctx.send(f'{ctx.author.mention}, у вас еще нет уровня.')


@bot.command()
async def сброслвл(ctx, member: discord.Member = None):
    if not has_moderator_role(ctx):
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")
        return

    if member is None:
        member = ctx.author

    user_id = str(member.id)
    if user_id in levels:
        del levels[user_id]
        save_levels(levels)
        await ctx.send(f'{member.mention}, ваш уровень и опыт сброшены.')
    else:
        await ctx.send(f'{member.mention} еще не имеет уровня.')

@bot.command()
async def set_xp_text(ctx, xp: int):
    if not has_moderator_role(ctx):
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")
        return

    global text_xp
    text_xp = xp
    await ctx.send(f'XP за текстовое сообщение установлен на {text_xp}.')

@bot.command()
async def set_xp_voice(ctx, xp: int):
    if not has_moderator_role(ctx):
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")
        return

    global voice_xp
    voice_xp = xp
    await ctx.send(f'XP за голосовое присутствие установлен на {voice_xp}.')

 # -----------------------------------------------------------------------------------------------------------------------------------------------------
 #КОНЕЦ ОБНОВЫ
# -----------------------------------------------------------------------------------------------------------------------------------------------------

# Команда !помощь для обычных пользователей
@bot.command(name='помощь')
async def help_command(ctx):
    help_text = """
    **Команды для пользователей:**
    `!помощь` - Вывод всех доступных команд
    `!история @пользователь` - Просмотр истории наказаний пользователя
    `!участники` - Количество участников на сервере
    `!случайный` - Выбор случайного участника на сервере
    """
    await ctx.send(help_text)
# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Команда !админпомощь для администраторов
@bot.command(name='админпомощь')
async def admin_help_command(ctx):
    if has_moderator_role(ctx):
        help_text = """
        **Административные команды:**
        `!мут @пользователь (время) причина` - Замьютить пользователя
        `!бан @пользователь причина` - Забанить пользователя
        `!варн @пользователь причина` - Выдать предупреждение
        `!история @пользователь` - Просмотреть историю наказаний пользователя
        `!очистка (количество)` - Очистить сообщения в канале
        `!участники` - Количество участников на сервере
        `!случайный` - Выбор случайного участника на сервере
        """
        await ctx.send(help_text)
    else:
        await ctx.send("У вас нет прав для просмотра админских команд.")
# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Новая команда !админы для просмотра списка всех администраторов
@bot.command(name='админы')
async def list_admins(ctx):
    admins = [member.mention for member in ctx.guild.members if ROLES['moderator_role'] in [role.id for role in member.roles]]
    await ctx.send(f"Администраторы сервера: {', '.join(admins)}")
# -----------------------------------------------------------------------------------------------------------------------------------------------------
# Запуск бота
bot.run(TOKEN)
