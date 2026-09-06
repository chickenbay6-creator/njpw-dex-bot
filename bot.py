import os
import discord
from flask import Flask
from discord.ext import commands, tasks
from threading import Thread

ADMIN_IDS = [
    1022776420012929094,
    1059359281104814171,
]

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

@tasks.loop(hours=1)
async def hourly_spawn():
    channel_id = 123456789012345678
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send("A wild dex card has spawned! Use your commands to catch it.")

@bot.tree.command(name="create_card", description="Creates a card")
async def create_card(interaction: discord.Interaction):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
        return
    await interaction.response.send_message("Card created!", ephemeral=True)

@bot.tree.command(name="forcespawn", description="Forces a spawn")
async def forcespawn(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id not in ADMIN_IDS:
        await interaction.followup.send("You do not have permission to use this command.")
        return
    await interaction.followup.send("Spawn forced!")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")
    if not hourly_spawn.is_running():
        hourly_spawn.start()

bot.run("MTU0MzUxOTgwOTQzMjU5MjQxNQ.G8L54G.voOa0fdHz4uXQnmbqTjLPxaKJLILz-dygQ2V-M")
