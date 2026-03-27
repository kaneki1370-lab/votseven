import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TOKEN        = os.environ.get("DISCORD_TOKEN")
LOBBY_CHANNEL_ID = int(os.environ.get("LOBBY_CHANNEL_ID", 0))   # salon brandsearch-groupe
LOG_CHANNEL_ID   = int(os.environ.get("LOG_CHANNEL_ID", 0))     # salon privé logs (visible que par toi)
MAX_PLAYERS  = 5
PROMO_CODE   = "SULEYECOM"
DATA_FILE    = "lobbies.json"

# ─── COULEURS EMBED ────────────────────────────────────────────────────────────
COLOR_OPEN   = 0xFFD700   # or — lobby ouvert
COLOR_FULL   = 0x2ECC71   # vert — lobby complet
COLOR_CLOSED = 0x95A5A6   # gris — fermé

# ─── INTENTS ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ─── PERSISTANCE JSON ──────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"lobbies": {}, "lobby_counter": 0}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def build_embed(lobby_id: int, members: list, status: str = "open") -> discord.Embed:
    count = len(members)
    full  = count >= MAX_PLAYERS

    if full:
        color = COLOR_FULL
        title = f"✅  Lobby #{lobby_id} — COMPLET"
        desc  = "Ce groupe est complet ! Un nouveau lobby vient d'être créé ci-dessous."
    else:
        color = COLOR_OPEN
        title = f"🔍  Lobby #{lobby_id} — {count}/{MAX_PLAYERS} places"
        desc  = (
            f"**Divisez le coût à {MAX_PLAYERS} et accédez à Brandsearch.**\n"
            f"Utilisez le code **`{PROMO_CODE}`** pour **-40%** sur votre abonnement.\n\n"
            f"{' '.join([f'<@{m}>' for m in members]) if members else '*Aucun membre pour instant*'}\n"
        )

    embed = discord.Embed(title=title, description=desc, color=color)

    # Barre de progression visuelle
    filled  = "🟡" * count
    empty   = "⬛" * (MAX_PLAYERS - count)
    embed.add_field(
        name="Places",
        value=f"{filled}{empty}  **{count}/{MAX_PLAYERS}**",
        inline=False
    )

    if not full:
        embed.add_field(
            name="📋 Instructions",
            value=(
                "1️⃣ Clique **Rejoindre** pour réserver ta place\n"
                "2️⃣ Attends que le lobby soit **5/5**\n"
                "3️⃣ Ajoutez-vous en amis Discord\n"
                "4️⃣ Créez un groupe privé entre vous\n"
                "5️⃣ Gérez paiements & accès **uniquement dans ce groupe**"
            ),
            inline=False
        )
        embed.add_field(
            name="⚠️ Règle stricte",
            value="🔒 Aucun code, mot de passe ou info privée dans ce fil public.\n🚫 Violation = bannissement immédiat.",
            inline=False
        )

    embed.set_footer(text=f"Lobby #{lobby_id} • Brandsearch Group Buy")
    return embed

# ─── VUE BOUTON ────────────────────────────────────────────────────────────────
class LobbyView(discord.ui.View):
    def __init__(self, lobby_id: int):
        super().__init__(timeout=None)  # persistant (survive aux redémarrages)
        self.lobby_id = lobby_id

    @discord.ui.button(label="✅  Rejoindre", style=discord.ButtonStyle.success,
                       custom_id="join_lobby")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_join(interaction, self.lobby_id)

    @discord.ui.button(label="❌  Quitter", style=discord.ButtonStyle.danger,
                       custom_id="leave_lobby")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_leave(interaction, self.lobby_id)


async def handle_join(interaction: discord.Interaction, lobby_id: int):
    data = load_data()
    key  = str(lobby_id)

    if key not in data["lobbies"]:
        await interaction.response.send_message("❌ Ce lobby n'existe plus.", ephemeral=True)
        return

    lobby   = data["lobbies"][key]
    user_id = str(interaction.user.id)

    if lobby["status"] == "full":
        await interaction.response.send_message("⛔ Ce lobby est déjà complet !", ephemeral=True)
        return

    if user_id in lobby["members"]:
        await interaction.response.send_message("⚠️ Tu es déjà dans ce lobby.", ephemeral=True)
        return

    # Vérifie si l'user est dans un autre lobby actif
    for lid, lob in data["lobbies"].items():
        if user_id in lob["members"] and lob["status"] == "open":
            await interaction.response.send_message(
                f"⚠️ Tu es déjà dans le Lobby #{lid}. Quitte-le avant d'en rejoindre un autre.",
                ephemeral=True
            )
            return

    lobby["members"].append(user_id)
    lobby["join_times"][user_id] = datetime.utcnow().isoformat()

    # Lobby complet ?
    if len(lobby["members"]) >= MAX_PLAYERS:
        lobby["status"] = "full"
        save_data(data)
        await interaction.response.defer()
        # Mise à jour embed
        channel = bot.get_channel(LOBBY_CHANNEL_ID)
        msg     = await channel.fetch_message(int(lobby["message_id"]))
        view    = LobbyView(lobby_id)
        view.children[0].disabled = True  # désactive bouton rejoindre
        await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=view)
        # Log
        await send_log(interaction.guild, lobby_id, interaction.user, "full")
        # Crée nouveau lobby automatiquement
        await create_new_lobby(interaction.guild, data)
    else:
        save_data(data)
        await interaction.response.defer()
        channel = bot.get_channel(LOBBY_CHANNEL_ID)
        msg     = await channel.fetch_message(int(lobby["message_id"]))
        await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=LobbyView(lobby_id))
        await send_log(interaction.guild, lobby_id, interaction.user, "join")


async def handle_leave(interaction: discord.Interaction, lobby_id: int):
    data = load_data()
    key  = str(lobby_id)

    if key not in data["lobbies"]:
        await interaction.response.send_message("❌ Ce lobby n'existe plus.", ephemeral=True)
        return

    lobby   = data["lobbies"][key]
    user_id = str(interaction.user.id)

    if user_id not in lobby["members"]:
        await interaction.response.send_message("⚠️ Tu n'es pas dans ce lobby.", ephemeral=True)
        return

    if lobby["status"] == "full":
        await interaction.response.send_message(
            "⛔ Le lobby est complet, tu ne peux plus quitter. Gère ça dans ton groupe privé.",
            ephemeral=True
        )
        return

    lobby["members"].remove(user_id)
    lobby["join_times"].pop(user_id, None)
    save_data(data)

    await interaction.response.defer()
    channel = bot.get_channel(LOBBY_CHANNEL_ID)
    msg     = await channel.fetch_message(int(lobby["message_id"]))
    await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=LobbyView(lobby_id))
    await send_log(interaction.guild, lobby_id, interaction.user, "leave")


# ─── LOG ───────────────────────────────────────────────────────────────────────
async def send_log(guild: discord.Guild, lobby_id: int, user: discord.Member, action: str):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return

    icons   = {"join": "➕", "leave": "➖", "full": "✅", "create": "🆕"}
    colors  = {"join": 0x3498DB, "leave": 0xE74C3C, "full": 0x2ECC71, "create": 0x9B59B6}
    actions = {
        "join"  : f"a rejoint le Lobby #{lobby_id}",
        "leave" : f"a quitté le Lobby #{lobby_id}",
        "full"  : f"a complété le Lobby #{lobby_id} (5/5) — nouveau lobby créé",
        "create": f"— Lobby #{lobby_id} créé automatiquement",
    }

    embed = discord.Embed(
        title=f"{icons.get(action,'📋')} {user.display_name if action != 'create' else 'Système'} {actions[action]}",
        color=colors.get(action, 0x95A5A6),
        timestamp=datetime.utcnow()
    )
    if action != "create":
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="Lobby", value=f"#{lobby_id}", inline=True)
    embed.add_field(name="Heure (UTC)", value=datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S"), inline=True)

    await log_channel.send(embed=embed)


# ─── CRÉATION D'UN LOBBY ───────────────────────────────────────────────────────
async def create_new_lobby(guild: discord.Guild, data: dict = None):
    if data is None:
        data = load_data()

    data["lobby_counter"] += 1
    lobby_id = data["lobby_counter"]
    key      = str(lobby_id)

    channel  = bot.get_channel(LOBBY_CHANNEL_ID)
    embed    = build_embed(lobby_id, [])
    view     = LobbyView(lobby_id)
    msg      = await channel.send(embed=embed, view=view)

    data["lobbies"][key] = {
        "message_id": str(msg.id),
        "members"   : [],
        "join_times": {},
        "status"    : "open",
        "created_at": datetime.utcnow().isoformat()
    }
    save_data(data)

    # Log création
    class FakeUser:
        display_name = "Système"
        display_avatar = guild.me.display_avatar
        mention = bot.user.mention
        id = bot.user.id
    await send_log(guild, lobby_id, FakeUser(), "create")
    return lobby_id


# ─── COMMANDES SLASH (admin) ───────────────────────────────────────────────────
@bot.tree.command(name="nouveau-lobby", description="[Admin] Crée un nouveau lobby Brandsearch")
@app_commands.checks.has_permissions(manage_channels=True)
async def new_lobby(interaction: discord.Interaction):
    lobby_id = await create_new_lobby(interaction.guild)
    await interaction.response.send_message(
        f"✅ Lobby #{lobby_id} créé dans <#{LOBBY_CHANNEL_ID}>", ephemeral=True
    )

@bot.tree.command(name="lobbies-actifs", description="[Admin] Voir tous les lobbies actifs")
@app_commands.checks.has_permissions(manage_channels=True)
async def list_lobbies(interaction: discord.Interaction):
    data = load_data()
    open_lobbies = [(k, v) for k, v in data["lobbies"].items() if v["status"] == "open"]

    if not open_lobbies:
        await interaction.response.send_message("Aucun lobby actif.", ephemeral=True)
        return

    embed = discord.Embed(title="🔍 Lobbies Brandsearch actifs", color=COLOR_OPEN)
    for lid, lob in open_lobbies:
        members_str = ", ".join([f"<@{m}>" for m in lob["members"]]) or "*vide*"
        embed.add_field(
            name=f"Lobby #{lid} — {len(lob['members'])}/{MAX_PLAYERS}",
            value=members_str,
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset-lobbies", description="[Admin] Supprime tous les lobbies et repart à zéro")
@app_commands.checks.has_permissions(administrator=True)
async def reset_lobbies(interaction: discord.Interaction):
    data = {"lobbies": {}, "lobby_counter": 0}
    save_data(data)
    await interaction.response.send_message("🔄 Tous les lobbies ont été réinitialisés.", ephemeral=True)


# ─── EVENTS ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅ Bot connecté : {bot.user} ({bot.user.id})")
    # Réenregistre les vues persistantes
    data = load_data()
    for lid, lob in data["lobbies"].items():
        if lob["status"] == "open":
            bot.add_view(LobbyView(int(lid)))
    # Sync commandes slash
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} commande(s) slash synchronisée(s)")
    except Exception as e:
        print(f"❌ Erreur sync : {e}")

    # Crée un lobby de démarrage s'il n'y en a aucun d'ouvert
    open_count = sum(1 for v in data["lobbies"].values() if v["status"] == "open")
    if open_count == 0 and LOBBY_CHANNEL_ID:
        guild = bot.guilds[0] if bot.guilds else None
        if guild:
            await create_new_lobby(guild, data)
            print("✅ Lobby initial créé")


@bot.event
async def on_message(message: discord.Message):
    # Supprime les messages dans le salon lobby (garde le canal propre)
    if message.channel.id == LOBBY_CHANNEL_ID and not message.author.bot:
        await message.delete()
        try:
            await message.author.send(
                "⚠️ Le salon **Brandsearch Groupe** ne permet pas les messages.\n"
                "Utilise les boutons pour rejoindre/quitter un lobby."
            )
        except discord.Forbidden:
            pass
    await bot.process_commands(message)


# ─── LANCEMENT ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN manquant dans les variables d'environnement !")
        exit(1)
    bot.run(TOKEN)
