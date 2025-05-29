import os
import psutil
import discord
import discord.utils

def get_performance_metrics(bot: discord.Bot) -> tuple[float, float, float, float, list[str]]:
    total = round(psutil.virtual_memory().total / (1024 ** 3), 4)
    usage = round(psutil.Process(os.getpid()).memory_info().rss / (1024 ** 3), 4)
    usage_percent = round((usage / total) * 100, 1)
    cpu = psutil.cpu_percent(1)
    connected_guilds = [guild.name for guild in bot.guilds if discord.utils.get(bot.voice_clients, guild=guild)]

    return total, usage, usage_percent, cpu, connected_guilds
