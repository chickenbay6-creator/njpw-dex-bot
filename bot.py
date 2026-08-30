ADMIN_IDS = [
    1022776420012929094,
    1059359281104814171,
]
import discord
from flask import Flask
from discord.ext import commands
from threading import Thread

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

app = Flask('')



@app.route('/')
def home():
  chno = "Bot is running!"
  return chno


def run():
  app.run(host='0.0.0.0', port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# Make sure keep_alive() is called right before your bot runs
keep_alive()

# Replace lines 30-34 with your actual command:
@bot.tree.command(name="create_card", description="Creates a card")
async def create_card(interaction: discord.Interaction):
  # Notice how the check is indented INSIDE the function
  if interaction.user.id not in ADMIN_IDS:
    await interaction.response.send_message(
        "You do not have permission to use this command.", ephemeral=True
    )
    return

@bot.tree.command(name="forcespawn", description="Forces a spawn")
async def forcespawn(interaction: discord.Interaction):
  if interaction.user.id not in ADMIN_IDS:
    await interaction.response.send_message(
        "You do not have permission to use this command.", ephemeral=True
    )
    await interaction.response.send_message("Spawn forced!", ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

bot.run(MTU0MzUxOTgwOTQzMjU5MjQxNQ.G3SfgV.2L7shfmbyRkaXmshI0J62Dp6SrI3GvVyMNPzW8)
 
    
