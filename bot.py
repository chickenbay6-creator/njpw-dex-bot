import os
import json
import random
import sqlite3
from datetime import datetime, timezone
from threading import Thread

import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask


# ============================================================
# NJPW DEX BOT
# ============================================================

OWNER_ID = 1022776420012929094
CO_OWNER_ID = 1059359281104814171
ADMIN_IDS = {OWNER_ID, CO_OWNER_ID}

TOKEN = os.getenv(MTU0MzUxOTgwOTQzMjU5MjQxNQ.Gpy71y.ORralCAwuMqiCqpKdZzd46PdKOoluPe-y7jroI)
SPAWN_CHANNEL_ID = int(os.getenv("SPAWN_CHANNEL_ID", "0"))

DATABASE = "njpw_dex.db"

RARITY_BONUS = {
    "Common": 0,
    "Uncommon": 2,
    "Rare": 5,
    "Super Rare": 8,
    "Epic": 12,
    "Legend": 16,
}


# ============================================================
# DATABASE
# ============================================================

db = sqlite3.connect(
    DATABASE,
    check_same_thread=False
)

db.row_factory = sqlite3.Row

db.execute("PRAGMA journal_mode=WAL")

db.execute("""
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    rarity TEXT NOT NULL DEFAULT 'Common',
    faction TEXT NOT NULL DEFAULT 'NJPW',
    fighting_spirit INTEGER NOT NULL DEFAULT 50,
    technique INTEGER NOT NULL DEFAULT 50,
    stamina INTEGER NOT NULL DEFAULT 50,
    image_url TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    date_claimed TEXT NOT NULL
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS spawns (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    claimed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
""")

db.commit()


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(text):
    return " ".join(
        text.lower()
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )


def is_admin(user_id):
    return user_id in ADMIN_IDS


def get_card(card_id):
    return db.execute(
        "SELECT * FROM cards WHERE id = ? AND active = 1",
        (card_id,)
    ).fetchone()


def get_all_cards():
    return db.execute(
        "SELECT * FROM cards WHERE active = 1 ORDER BY id"
    ).fetchall()


def get_aliases(card):
    try:
        return [
            normalize(x)
            for x in json.loads(card["aliases"])
        ]
    except Exception:
        return []


def owns_card(user_id, card_id):
    result = db.execute(
        """
        SELECT id
        FROM inventory
        WHERE user_id = ?
        AND card_id = ?
        LIMIT 1
        """,
        (user_id, card_id)
    ).fetchone()

    return result is not None


def give_card_to_user(user_id, card_id):
    db.execute(
        """
        INSERT INTO inventory
        (user_id, card_id, date_claimed)
        VALUES (?, ?, ?)
        """,
        (user_id, card_id, now())
    )
    db.commit()


def take_card_from_user(user_id, card_id):
    result = db.execute(
        """
        SELECT id
        FROM inventory
        WHERE user_id = ?
        AND card_id = ?
        LIMIT 1
        """,
        (user_id, card_id)
    ).fetchone()

    if not result:
        return False

    db.execute(
        "DELETE FROM inventory WHERE id = ?",
        (result["id"],)
    )

    db.commit()
    return True


def card_power(card):
    average = (
        card["fighting_spirit"]
        + card["technique"]
        + card["stamina"]
    ) / 3

    return average + RARITY_BONUS.get(
        card["rarity"],
        0
    )


# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ============================================================
# RENDER WEB SERVER
# ============================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "NJPW DEX BOT IS ONLINE", 200


@app.route("/health")
def health():
    return "OK", 200


def web_server():
    port = int(
        os.getenv("PORT", "10000")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


def start_web_server():
    Thread(
        target=web_server,
        daemon=True
    ).start()


# ============================================================
# SPAWN EMBED
# ============================================================

def spawn_embed(card):

    embed = discord.Embed(
        title="A WILD NJPW CARD HAS SPAWNED!",
        description=(
            "A mysterious NJPW wrestler has appeared!\n\n"
            "Click **CATCH** and enter the wrestler's name."
        ),
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Rarity",
        value=card["rarity"],
        inline=True
    )

    embed.add_field(
        name="Faction",
        value=card["faction"],
        inline=True
    )

    if card["image_url"]:
        embed.set_image(
            url=card["image_url"]
        )

    embed.set_footer(
        text="NJPW DEX • First correct answer wins"
    )

    return embed


# ============================================================
# CLAIM MODAL
# ============================================================

class CatchModal(
    discord.ui.Modal,
    title="Who is this wrestler?"
):

    def __init__(self, message_id):
        super().__init__()

        self.message_id = message_id

        self.answer = discord.ui.TextInput(
            label="Wrestler Name",
            placeholder="Example: Shingo Takagi",
            required=True,
            max_length=100
        )

        self.add_item(self.answer)


    async def on_submit(self, interaction):

        spawn = db.execute(
            """
            SELECT
                s.message_id,
                s.channel_id,
                s.card_id,
                s.claimed,
                c.*
            FROM spawns s
            JOIN cards c
            ON c.id = s.card_id
            WHERE s.message_id = ?
            """,
            (self.message_id,)
        ).fetchone()

        if not spawn:

            await interaction.response.send_message(
                "This spawn no longer exists.",
                ephemeral=True
            )

            return


        if spawn["claimed"]:

            await interaction.response.send_message(
                "Someone already caught this card.",
                ephemeral=True
            )

            return


        answer = normalize(
            self.answer.value
        )

        accepted = {
            normalize(spawn["name"])
        }

        accepted.update(
            get_aliases(spawn)
        )


        if answer not in accepted:

            await interaction.response.send_message(
                "Incorrect! Try again.",
                ephemeral=True
            )

            return


        # Atomic claim lock
        db.execute(
            """
            UPDATE spawns
            SET claimed = 1
            WHERE message_id = ?
            AND claimed = 0
            """,
            (self.message_id,)
        )

        changed = db.execute(
            "SELECT changes()"
        ).fetchone()[0]

        db.commit()


        if changed != 1:

            await interaction.response.send_message(
                "Someone else caught it first!",
                ephemeral=True
            )

            return


        give_card_to_user(
            interaction.user.id,
            spawn["card_id"]
        )


        try:

            message = await interaction.channel.fetch_message(
                self.message_id
            )

            embed = discord.Embed(
                title="CARD CLAIMED!",
                description=(
                    f"{interaction.user.mention} caught "
                    f"**{spawn['name']}**!"
                ),
                color=discord.Color.green()
            )

            embed.add_field(
                name="Rarity",
                value=spawn["rarity"],
                inline=True
            )

            embed.add_field(
                name="Faction",
                value=spawn["faction"],
                inline=True
            )

            if spawn["image_url"]:
                embed.set_image(
                    url=spawn["image_url"]
                )

            view = discord.ui.View()

            view.add_item(
                discord.ui.Button(
                    label="CLAIMED",
                    style=discord.ButtonStyle.secondary,
                    disabled=True
                )
            )

            await message.edit(
                embed=embed,
                view=view
            )

        except Exception as error:

            print(
                f"Could not update spawn message: {error}"
            )


        await interaction.response.send_message(
            f"Correct! {interaction.user.mention} caught "
            f"**{spawn['name']}**!"
        )


# ============================================================
# CATCH BUTTON
# ============================================================

class CatchView(discord.ui.View):

    def __init__(self, message_id):
        super().__init__(timeout=None)

        self.message_id = message_id


    @discord.ui.button(
        label="CATCH",
        style=discord.ButtonStyle.primary
    )
    async def catch(
        self,
        interaction,
        button
    ):

        await interaction.response.send_modal(
            CatchModal(
                self.message_id
            )
        )


# ============================================================
# SPAWN FUNCTION
# ============================================================

async def spawn_card(channel):

    cards = get_all_cards()

    if not cards:

        await channel.send(
            "There are no cards yet. "
            "An admin needs to use `/create_card` first."
        )

        return None


    card = random.choice(cards)


    message = await channel.send(
        embed=spawn_embed(card)
    )


    db.execute(
        """
        INSERT INTO spawns
        (
            message_id,
            channel_id,
            card_id,
            claimed,
            created_at
        )
        VALUES (?, ?, ?, 0, ?)
        """,
        (
            message.id,
            channel.id,
            card["id"],
            now()
        )
    )

    db.commit()


    await message.edit(
        view=CatchView(
            message.id
        )
    )


    return message


# ============================================================
# FIND SPAWN CHANNEL
# ============================================================

def find_spawn_channel():

    if SPAWN_CHANNEL_ID:

        channel = bot.get_channel(
            SPAWN_CHANNEL_ID
        )

        if isinstance(
            channel,
            discord.TextChannel
        ):
            return channel


    preferred = [
        "spawn",
        "dex",
        "general",
        "main",
        "test"
    ]


    for guild in bot.guilds:

        for channel in guild.text_channels:

            if any(
                name in channel.name.lower()
                for name in preferred
            ):
                return channel


    for guild in bot.guilds:

        if guild.text_channels:
            return guild.text_channels[0]


    return None


# ============================================================
# HOURLY SPAWN
# ============================================================

@tasks.loop(hours=1)
async def hourly_spawn():

    channel = find_spawn_channel()

    if channel:

        try:

            await spawn_card(channel)

        except Exception as error:

            print(
                f"Hourly spawn error: {error}"
            )


@hourly_spawn.before_loop
async def before_hourly_spawn():

    await bot.wait_until_ready()


# ============================================================
# CREATE CARD
# ============================================================

@bot.tree.command(
    name="create_card",
    description="Create an NJPW DEX card"
)
@app_commands.describe(
    name="Wrestler name",
    aliases="Aliases separated by commas",
    rarity="Common, Uncommon, Rare, Super Rare, Epic, Legend",
    faction="Faction or stable",
    fighting_spirit="Fighting Spirit 1-100",
    technique="Technique 1-100",
    stamina="Stamina 1-100",
    image_url="Direct image URL"
)
async def create_card(
    interaction,
    name: str,
    aliases: str = "",
    rarity: str = "Common",
    faction: str = "NJPW",
    fighting_spirit: int = 50,
    technique: int = 50,
    stamina: int = 50,
    image_url: str = ""
):

    if not is_admin(
        interaction.user.id
    ):

        await interaction.response.send_message(
            "Owner/co-owner only.",
            ephemeral=True
        )

        return


    rarity = rarity.strip().title()


    if rarity not in RARITY_BONUS:

        await interaction.response.send_message(
            "Invalid rarity. Use Common, Uncommon, Rare, "
            "Super Rare, Epic, or Legend.",
            ephemeral=True
        )

        return


    if any(
        stat < 1 or stat > 100
        for stat in [
            fighting_spirit,
            technique,
            stamina
        ]
    ):

        await interaction.response.send_message(
            "Stats must be between 1 and 100.",
            ephemeral=True
        )

        return


    alias_list = [
        x.strip()
        for x in aliases.split(",")
        if x.strip()
    ]


    cursor = db.execute(
        """
        INSERT INTO cards
        (
            name,
            aliases,
            rarity,
            faction,
            fighting_spirit,
            technique,
            stamina,
            image_url,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name.strip(),
            json.dumps(alias_list),
            rarity,
            faction.strip(),
            fighting_spirit,
            technique,
            stamina,
            image_url.strip(),
            now()
        )
    )

    db.commit()


    await interaction.response.send_message(
        f"Card successfully created!\n\n"
        f"**ID:** #{cursor.lastrowid}\n"
        f"**Name:** {name}\n"
        f"**Rarity:** {rarity}\n"
        f"**Faction:** {faction}\n"
        f"**Fighting Spirit:** {fighting_spirit}\n"
        f"**Technique:** {technique}\n"
        f"**Stamina:** {stamina}",
        ephemeral=True
    )


# ============================================================
# EDIT CARD
# ============================================================

@bot.tree.command(
    name="edit_card",
    description="Edit an NJPW DEX card"
)
@app_commands.describe(
    card_id="Card ID",
    name="New wrestler name",
    aliases="New aliases separated by commas",
    rarity="New rarity",
    faction="New faction",
    fighting_spirit="New Fighting Spirit",
    technique="New Technique",
    stamina="New Stamina",
    image_url="New image URL"
)
async def edit_card(
    interaction,
    card_id: int,
    name: str = None,
    aliases: str = None,
    rarity: str = None,
    faction: str = None,
    fighting_spirit: int = None,
    technique: int = None,
    stamina: int = None,
    image_url: str = None
):

    if not is_admin(
        interaction.user.id
    ):

        await interaction.response.send_message(
            "Owner/co-owner only.",
            ephemeral=True
        )

        return


    card = get_card(card_id)


    if not card:

        await interaction.response.send_message(
            "Card not found.",
            ephemeral=True
        )

        return


    updates = []
    values = []


    if name is not None:

        updates.append("name = ?")
        values.append(name.strip())


    if aliases is not None:

        updates.append("aliases = ?")

        values.append(
            json.dumps([
                x.strip()
                for x in aliases.split(",")
                if x.strip()
            ])
        )


    if rarity is not None:

        rarity = rarity.strip().title()

        if rarity not in RARITY_BONUS:

            await interaction.response.send_message(
                "Invalid rarity.",
                ephemeral=True
            )

            return

        updates.append("rarity = ?")
        values.append(rarity)


    if faction is not None:

        updates.append("faction = ?")
        values.append(faction.strip())


    for field, value in [
        ("fighting_spirit", fighting_spirit),
        ("technique", technique),
        ("stamina", stamina)
    ]:

        if value is not None:

            if value < 1 or value > 100:

                await interaction.response.send_message(
                    "Stats must be between 1 and 100.",
                    ephemeral=True
                )

                return

            updates.append(
                f"{field} = ?"
            )

            values.append(value)


    if image_url is not None:

        updates.append("image_url = ?")
        values.append(image_url.strip())


    if not updates:

        await interaction.response.send_message(
            "Nothing to edit.",
            ephemeral=True
        )

        return


    values.append(card_id)


    db.execute(
        f"""
        UPDATE cards
        SET {", ".join(updates)}
        WHERE id = ?
        """,
        values
    )

    db.commit()


    await interaction.response.send_message(
        f"Card **#{card_id}** updated.",
        ephemeral=True
    )


# ============================================================
# DELETE CARD
# ============================================================

@bot.tree.command(
    name="delete_card",
    description="Remove a card from the spawn pool"
)
@app_commands.describe(
    card_id="Card ID"
)
async def delete_card(
    interaction,
    card_id: int
):

    if not is_admin(
        interaction.user.id
    ):

        await interaction.response.send_message(
            "Owner/co-owner only.",
            ephemeral=True
        )

        return


    card = get_card(card_id)


    if not card:

        await interaction.response.send_message(
            "Card not found.",
            ephemeral=True
        )

        return


    db.execute(
        """
        UPDATE cards
        SET active = 0
        WHERE id = ?
        """,
        (card_id,)
    )

    db.commit()


    await interaction.response.send_message(
        f"**{card['name']}** removed from the spawn pool.",
        ephemeral=True
    )


# ============================================================
# FORCE SPAWN
# ============================================================

@bot.tree.command(
    name="force_spawn",
    description="Force spawn an NJPW card"
)
async def force_spawn(interaction):

    if not is_admin(
        interaction.user.id
    ):

        await interaction.response.send_message(
            "Owner/co-owner only.",
            ephemeral=True
        )

        return


    if not isinstance(
        interaction.channel,
        discord.TextChannel
    ):

        await interaction.response.send_message(
            "Use this command in a normal text channel.",
            ephemeral=True
        )

        return


    await interaction.response.defer(
        ephemeral=True
    )


    message = await spawn_card(
        interaction.channel
    )


    if message:

        await interaction.followup.send(
            "Force spawn successful!",
            ephemeral=True
        )


# ============================================================
# ADMIN GIVE CARD
# ============================================================

@bot.tree.command(
    name="give_card_admin",
    description="Give any card to a player"
)
@app_commands.describe(
    user="Player receiving the card",
    card_id="Card ID"
)
async def give_card_admin(
    interaction,
    user: discord.Member,
    card_id: int
):

    if not is_admin(
        interaction.user.id
    ):

        await interaction.response.send_message(
            "Owner/co-owner only.",
            ephemeral=True
        )

        return


    card = get_card(card_id)


    if not card:

        await interaction.response.send_message(
            "Card not found.",
            ephemeral=True
        )

        return


    give_card_to_user(
        user.id,
        card_id
    )


    await interaction.response.send_message(
        f"Gave **{card['name']}** "
        f"(#{card_id}) to {user.mention}.",
        ephemeral=True
    )


# ============================================================
# CARD LIST
# ============================================================

@bot.tree.command(
    name="card_list",
    description="List all NJPW cards"
)
async def card_list(interaction):

    if not is_admin(
        interaction.user.id
    ):

        await interaction.response.send_message(
            "Owner/co-owner only.",
            ephemeral=True
        )

        return


    cards = get_all_cards()


    if not cards:

        await interaction.response.send_message(
            "No cards exist yet.",
            ephemeral=True
        )

        return


    lines = []

    for card in cards:

        lines.append(
            f"**#{card['id']}** — "
            f"{card['name']} — "
            f"{card['rarity']} — "
            f"{card['faction']}"
        )


    await interaction.response.send_message(
        "\n".join(lines)[:4000],
        ephemeral=True
    )


# ============================================================
# DEX
# ============================================================

@bot.tree.command(
    name="dex",
    description="View your NJPW DEX"
)
@app_commands.describe(
    user="Optional player"
)
async def dex(
    interaction,
    user: discord.Member = None
):

    target = user or interaction.user


    cards = db.execute(
        """
        SELECT c.*
        FROM inventory i
        JOIN cards c
        ON c.id = i.card_id
        WHERE i.user_id = ?
        AND c.active = 1
        ORDER BY c.rarity, c.name
        """,
        (target.id,)
    ).fetchall()


    total = len(
        get_all_cards()
    )


    embed = discord.Embed(
        title=f"{target.display_name}'s NJPW DEX",
        color=discord.Color.blue()
    )


    embed.add_field(
        name="Cards Caught",
        value=str(len(cards)),
        inline=True
    )


    embed.add_field(
        name="Collection",
        value=f"{len(cards)}/{total}",
        inline=True
    )


    if cards:

        groups = {}

        for card in cards:

            groups.setdefault(
                card["rarity"],
                []
            ).append(
                f"#{card['id']} {card['name']}"
            )


        embed.description = "\n\n".join(
            f"**{rarity}**\n"
            + ", ".join(names)
            for rarity, names in groups.items()
        )[:4000]

    else:

        embed.description = (
            "You don't have any cards yet."
        )


    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# SHOW CARD
# ============================================================

@bot.tree.command(
    name="card_show",
    description="Show a card you own"
)
@app_commands.describe(
    card_id="Card ID"
)
async def card_show(
    interaction,
    card_id: int
):

    if not owns_card(
        interaction.user.id,
        card_id
    ):

        await interaction.response.send_message(
            "You don't own this card.",
            ephemeral=True
        )

        return


    card = get_card(card_id)


    if not card:

        await interaction.response.send_message(
            "Card not found.",
            ephemeral=True
        )

        return


    embed = discord.Embed(
        title=f"{card['name']} • #{card['id']}",
        description=(
            f"**{card['rarity']}** • "
            f"{card['faction']}"
        ),
        color=discord.Color.blue()
    )


    embed.add_field(
        name="Fighting Spirit",
        value=str(
            card["fighting_spirit"]
        ),
        inline=True
    )


    embed.add_field(
        name="Technique",
        value=str(
            card["technique"]
        ),
        inline=True
    )


    embed.add_field(
        name="Stamina",
        value=str(
            card["stamina"]
        ),
        inline=True
    )


    embed.add_field(
        name="Card Power",
        value=f"{card_power(card):.1f}",
        inline=False
    )


    if card["image_url"]:

        embed.set_image(
            url=card["image_url"]
        )


    embed.set_footer(
        text=f"Owner: {interaction.user.display_name}"
    )


    await interaction.response.send_message(
        embed=embed
    )


# ============================================================
# GIVE CARD
# ============================================================

@bot.tree.command(
    name="give_card",
    description="Give one of your cards to another player"
)
@app_commands.describe(
    user="Player receiving the card",
    card_id="Card ID"
)
async def give_card(
    interaction,
    user: discord.Member,
    card_id: int
):

    if user.id == interaction.user.id:

        await interaction.response.send_message(
            "You can't give a card to yourself.",
            ephemeral=True
        )

        return


    if not owns_card(
        interaction.user.id,
        card_id
    ):

        await interaction.response.send_message(
            "You don't own this card.",
            ephemeral=True
        )

        return


    card = get_card(card_id)


    take_card_from_user(
        interaction.user.id,
        card_id
    )

    give_card_to_user(
        user.id,
        card_id
    )


    await interaction.response.send_message(
        f"{interaction.user.mention} gave "
        f"**{card['name']}** to "
        f"{user.mention}."
    )


# ============================================================
# BATTLE
# ============================================================

@bot.tree.command(
    name="battle",
    description="Battle another player for their card"
)
@app_commands.describe(
    opponent="Player you want to battle",
    your_card_id="Your wagered card ID",
    opponent_card_id="Opponent's wagered card ID"
)
async def battle(
    interaction,
    opponent: discord.Member,
    your_card_id: int,
    opponent_card_id: int
):

    if opponent.bot:

        await interaction.response.send_message(
            "You can't battle a bot.",
            ephemeral=True
        )

        return


    if opponent.id == interaction.user.id:

        await interaction.response.send_message(
            "You can't battle yourself.",
            ephemeral=True
        )

        return


    if not owns_card(
        interaction.user.id,
        your_card_id
    ):

        await interaction.response.send_message(
            "You don't own your wagered card.",
            ephemeral=True
        )

        return


    if not owns_card(
        opponent.id,
        opponent_card_id
    ):

        await interaction.response.send_message(
            "Your opponent doesn't own that card.",
            ephemeral=True
        )

        return


    card_a = get_card(
        your_card_id
    )

    card_b = get_card(
        opponent_card_id
    )


    roll_a = random.randint(
        1,
        20
    )

    roll_b = random.randint(
        1,
        20
    )


    score_a = (
        card_power(card_a)
        + roll_a
    )

    score_b = (
        card_power(card_b)
        + roll_b
    )


    if score_a == score_b:

        await interaction.response.send_message(
            f"**DRAW!**\n\n"
            f"{card_a['name']}: {score_a:.1f}\n"
            f"{card_b['name']}: {score_b:.1f}\n\n"
            "No cards changed hands."
        )

        return


    if score_a > score_b:

        winner = interaction.user
        loser = opponent
        losing_card_id = opponent_card_id

    else:

        winner = opponent
        loser = interaction.user
        losing_card_id = your_card_id


    losing_card = get_card(
        losing_card_id
    )


    take_card_from_user(
        loser.id,
        losing_card_id
    )

    give_card_to_user(
        winner.id,
        losing_card_id
    )


    await interaction.response.send_message(
        f"**NJPW DEX BATTLE**\n\n"
        f"**{interaction.user.display_name}** — "
        f"{card_a['name']} — "
        f"{card_power(card_a):.1f} + {roll_a} = "
        f"**{score_a:.1f}**\n\n"
        f"**{opponent.display_name}** — "
        f"{card_b['name']} — "
        f"{card_power(card_b):.1f} + {roll_b} = "
        f"**{score_b:.1f}**\n\n"
        f"🏆 **{winner.display_name} WINS!**\n\n"
        f"**{losing_card['name']}** "
        f"has been transferred to {winner.mention}."
    )


# ============================================================
# MANUAL SPAWN COMMAND
# ============================================================

@bot.tree.command(
    name="spawn",
    description="Spawn a random NJPW card"
)
async def spawn_command(interaction):

    if not isinstance(
        interaction.channel,
        discord.TextChannel
    ):

        await interaction.response.send_message(
            "Use this in a text channel.",
            ephemeral=True
        )

        return


    await interaction.response.defer(
        ephemeral=True
    )


    message = await spawn_card(
        interaction.channel
    )


    if message:

        await interaction.followup.send(
            "Card spawned!",
            ephemeral=True
        )


# ============================================================
# TEXT COMMAND
# ============================================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return


    if (
        message.content
        .strip()
        .lower()
        == "spawn"
    ):

        if isinstance(
            message.channel,
            discord.TextChannel
        ):

            await spawn_card(
                message.channel
            )


    await bot.process_commands(
        message
    )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print("=" * 50)

    print(
        f"BOT ONLINE: {bot.user}"
    )

    print(
        f"BOT ID: {bot.user.id}"
    )

    print(
        f"SERVERS: {len(bot.guilds)}"
    )

    print(
        f"OWNER ID: {OWNER_ID}"
    )

    print(
        f"CO-OWNER ID: {CO_OWNER_ID}"
    )

    print("=" * 50)


    try:

        synced = await bot.tree.sync()

        print(
            f"SYNCED {len(synced)} SLASH COMMANDS"
        )

    except Exception as error:

        print(
            f"COMMAND SYNC ERROR: {error}"
        )


    if not hourly_spawn.is_running():

        hourly_spawn.start()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    start_web_server()


    if not TOKEN:

        raise RuntimeError(
            "DISCORD_TOKEN is missing. "
            "Add your Discord bot token to "
            "Render Environment Variables."
        )


    bot.run(TOKEN)
