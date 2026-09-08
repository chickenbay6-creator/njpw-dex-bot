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
intents.message_content = True
intents.members = True

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
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if any(name in channel.name for name in ["spawn", "main", "general", "test"]):
                await channel.send("A wild NJPW dex card has spawned! Use your commands to catch it.")
                break

@bot.tree.command(name="create_card", description="Creates a card")
async def create_card(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id not in ADMIN_IDS:
        await interaction.followup.send("You do not have permission to use this command.", ephemeral=True)
        return
    await interaction.followup.send("Card successfully created!", ephemeral=True)

@bot.tree.command(name="force_spawn", description="Forces a spawn")
async def force_spawn(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id not in ADMIN_IDS:
        await interaction.followup.send("You do not have permission to use this command.", ephemeral=True)
        return
    await interaction.channel.send("A wild NJPW dex card has been force-spawned! Catch me!")
    await interaction.followup.send("Spawn forced successfully!", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.content.strip().lower() == "spawn":
        await message.channel.send("A wild NJPW dex card has spawned! Catch me!")
    await bot.process_commands(message)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} and commands synced!")
    if not hourly_spawn.is_running():
        hourly_spawn.start()

bot.run(os.getenv("DISCORD_TOKEN"))
