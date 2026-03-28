import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────────
TOKEN                = os.environ.get("DISCORD_TOKEN")
LOBBY_CHANNEL_ID     = int(os.environ.get("LOBBY_CHANNEL_ID", 0))
LOG_CHANNEL_ID       = int(os.environ.get("LOG_CHANNEL_ID", 0))
PRIVATE_CATEGORY_ID  = int(os.environ.get("PRIVATE_CATEGORY_ID", 0))
MAX_PLAYERS          = 5  # Actuellement à 2 pour tes tests, tu pourras remettre 5
PROMO_CODE           = "SULEYECOM"
DATA_FILE            = "lobbies.json"

PRIX_ORIGINAL_USD  = 149
REMISE_PCT         = 40
PRIX_GROUPE_EUR    = 16.50

COLOR_OPEN   = 0xFFD700
COLOR_FULL   = 0x2ECC71
COLOR_CLOSED = 0x95A5A6
COLOR_PROMO  = 0xFF6B35

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Lock anti race condition
lobby_creation_lock = asyncio.Lock()

# ─── DATA ──────────────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"lobbies": {}, "lobby_counter": 0}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─── EMBEDS ────────────────────────────────────────────────────────────────────
def build_embed(lobby_id: int, members: list, status: str = "open") -> discord.Embed:
    count     = len(members)
    full      = count >= MAX_PLAYERS
    remaining = MAX_PLAYERS - count

    if full:
        embed = discord.Embed(
            description=(
                f"## ✅ Groupe #{lobby_id} — Complet\n"
                f"Les {MAX_PLAYERS} membres ont leur salon privé. Un nouveau groupe est ouvert ci-dessous 👇"
            ),
            color=0xF7B267
        )
        embed.add_field(
            name="Membres",
            value=" ".join([f"<@{m}>" for m in members]),
            inline=False
        )
        embed.set_footer(text=f"Groupe #{lobby_id}  ·  Brandsearch Agency")
        return embed

    PRIX_SOLO_EUR  = round(PRIX_ORIGINAL_USD * (1 - REMISE_PCT / 100) * 0.93, 2)
    economie_annee = round((PRIX_SOLO_EUR - PRIX_GROUPE_EUR) * 12, 2)
    membres_str    = " ".join([f"<@{m}>" for m in members]) if members else "*Aucun membre — sois le premier !*"

    embed = discord.Embed(
        description=(
            f"## 💸 {PRIX_GROUPE_EUR}€ / mois · Brandsearch Agency\n"
            f"Groupe de {MAX_PLAYERS} · Code **`{PROMO_CODE}`** · **-{REMISE_PCT}%**\n\n"
            f"Solo avec code : ~~{PRIX_SOLO_EUR}€~~ → **{PRIX_GROUPE_EUR}€** · soit **{economie_annee}€ économisés/an**"
        ),
        color=0xFF6B35
    )
    embed.add_field(
        name=f"👥 {count}/{MAX_PLAYERS} membres · {remaining} place{'s' if remaining > 1 else ''} restante{'s' if remaining > 1 else ''}",
        value=membres_str,
        inline=False
    )
    embed.add_field(
        name="⚡ Comment ça marche",
        value=(
            f"**1.** Rejoins le groupe\n"
            f"**2.** À {MAX_PLAYERS}/{MAX_PLAYERS} → salon privé créé automatiquement 🔒\n"
            f"**3.** Vous organisez le paiement entre vous\n"
            f"**4.** Code **`{PROMO_CODE}`** au moment de souscrire"
        ),
        inline=False
    )
    embed.set_footer(text=f"Groupe #{lobby_id}  ·  Brandsearch Agency  ·  {PROMO_CODE}")
    return embed


class LobbyView(discord.ui.View):
    def __init__(self, lobby_id: int):
        super().__init__(timeout=None)
        self.lobby_id = lobby_id

    @discord.ui.button(label="✅  Rejoindre le groupe", style=discord.ButtonStyle.success, custom_id="join_lobby")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_join(interaction, self.lobby_id)

    @discord.ui.button(label="❌  Quitter", style=discord.ButtonStyle.danger, custom_id="leave_lobby")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_leave(interaction, self.lobby_id)


# ─── LOGIQUE PRINCIPALE ────────────────────────────────────────────────────────
async def handle_join(interaction: discord.Interaction, lobby_id: int):
    data = load_data()
    key  = str(lobby_id)

    if key not in data["lobbies"]:
        return await interaction.response.send_message("❌ Ce groupe n'existe plus.", ephemeral=True)

    lobby   = data["lobbies"][key]
    user_id = str(interaction.user.id)

    if lobby["status"] == "full":
        return await interaction.response.send_message("⛔ Ce groupe est déjà complet !", ephemeral=True)

    if user_id in lobby["members"]:
        return await interaction.response.send_message("⚠️ Tu es déjà dans ce groupe.", ephemeral=True)

    for lid, lob in data["lobbies"].items():
        if user_id in lob["members"] and lob["status"] == "open":
            return await interaction.response.send_message(f"⚠️ Tu es déjà dans le Groupe #{lid}. Quitte-le d'abord.", ephemeral=True)

    # Ajout du membre
    lobby["members"].append(user_id)
    lobby["join_times"][user_id] = datetime.utcnow().isoformat()
    places_restantes = MAX_PLAYERS - len(lobby["members"])

    # ─── SI LE GROUPE EST PLEIN ───
    if len(lobby["members"]) >= MAX_PLAYERS:
        lobby["status"] = "full"
        save_data(data)
        await interaction.response.defer()

        # 1. Mise à jour du message public (désactive les boutons)
        try:
            channel = bot.get_channel(LOBBY_CHANNEL_ID)
            msg     = await channel.fetch_message(int(lobby["message_id"]))
            view    = LobbyView(lobby_id)
            view.children[0].disabled = True
            view.children[1].disabled = True
            await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=view)
        except Exception as e:
            print(f"Erreur public : {e}")

        # 2. OUVERTURE DU NOUVEAU GROUPE IMMÉDIATE
        try:
            async with lobby_creation_lock:
                fresh = load_data()
                if sum(1 for v in fresh["lobbies"].values() if v["status"] == "open") == 0:
                    await create_new_lobby(interaction.guild)
        except Exception as e:
            print(f"Erreur nouveau lobby : {e}")

        # 3. CRÉATION DU SALON PRIVÉ
        private_chan = None
        try:
            guild = interaction.guild
            category = guild.get_channel(PRIVATE_CATEGORY_ID) if PRIVATE_CATEGORY_ID else None
            
            membres_obj = []
            for uid in lobby["members"]:
                m = guild.get_member(int(uid)) or await guild.fetch_member(int(uid))
                if m: membres_obj.append(m)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            }
            for m in membres_obj:
                overwrites[m] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            for role in guild.roles:
                if role.permissions.administrator or role.permissions.manage_guild:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            private_chan = await guild.create_text_channel(
                name=f"groupe-{lobby_id}-brandsearch",
                overwrites=overwrites,
                category=category,
                topic=f"Groupe #{lobby_id} Brandsearch — salon privé"
            )

            mentions = " ".join([m.mention for m in membres_obj])
            PRIX_SOLO_CODE = round(PRIX_ORIGINAL_USD * (1 - REMISE_PCT / 100) * 0.93, 2)
            economie_annee = round((PRIX_SOLO_CODE - PRIX_GROUPE_EUR) * 12, 2)

            welcome_embed = discord.Embed(
                title=f"🔒 Groupe #{lobby_id} — Salon privé Brandsearch",
                description=(
                    f"Bienvenue {mentions} !\n\n"
                    f"Vous êtes les **{MAX_PLAYERS} membres** de ce groupe. Ce salon est **totalement invisible** "
                    "pour les autres.\n\n"
                    "**Coordonnez-vous ici librement** pour organiser le paiement groupé."
                ),
                color=0x2ECC71
            )
            welcome_embed.add_field(
                name="💰 Récapitulatif",
                value=(
                    f"• Plan : **Brandsearch Agency** (149$/mois)\n"
                    f"• Code : **`{PROMO_CODE}`** → **-{REMISE_PCT}%**\n"
                    f"• Prix par personne : **{PRIX_GROUPE_EUR}€/mois** 🎯\n"
                    f"• Économie vs solo (avec code) : ~**{economie_annee}€/an**"
                ),
                inline=False
            )
            welcome_embed.add_field(
                name="📋 Étapes",
                value=(
                    "1️⃣ Désignez un **référent** qui souscrit l'abonnement\n"
                    "2️⃣ Le référent partage son **RIB** ici\n"
                    f"3️⃣ Les autres font un virement de **{PRIX_GROUPE_EUR}€** au référent\n"
                    f"4️⃣ Le référent souscrit avec le code **`{PROMO_CODE}`**\n"
                    "5️⃣ Il ajoute vos **emails** dans l'espace Agency\n"
                    "6️⃣ Chacun a ses propres accès — aucune donnée partagée 🔐"
                ),
                inline=False
            )
            welcome_embed.add_field(
                name="🆘 En cas de problème",
                value="Un souci ou une question ? N'hésitez pas à mentionner <@706208703761874965> ou <@923601439815778315> pour qu'on vienne vous aider.",
                inline=False
            )
            welcome_embed.set_footer(text=f"Groupe #{lobby_id} • Brandsearch Agency • Salon modéré")

            data2 = load_data()
            data2["lobbies"][key]["private_channel_id"] = str(private_chan.id)
            save_data(data2)

            for m in membres_obj:
                try:
                    await m.send(
                        f"🎉 **Votre groupe Brandsearch #{lobby_id} est complet !**\n"
                        f"Un salon privé a été créé : **<#{private_chan.id}>**"
                    )
                except discord.Forbidden:
                    pass

        except Exception as e:
            print(f"Erreur salon privé : {e}")

        # 4. ENVOI DES LOGS
        try:
            await send_log(interaction.guild, lobby_id, interaction.user, "full", private_chan)
        except Exception as e:
            print(f"Erreur log complet : {e}")

    # ─── SI LE GROUPE N'EST PAS ENCORE PLEIN ───
    else:
        save_data(data)
        await interaction.response.defer()

        try:
            channel = bot.get_channel(LOBBY_CHANNEL_ID)
            msg     = await channel.fetch_message(int(lobby["message_id"]))
            await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=LobbyView(lobby_id))
        except Exception as e:
            print(f"Erreur edit message: {e}")

        try:
            await interaction.user.send(
                f"✅ **Tu as rejoint le Groupe #{lobby_id} !**\n\n"
                f"Il reste **{places_restantes} place{'s' if places_restantes > 1 else ''}**.\n"
                f"Dès que vous êtes {MAX_PLAYERS}, un salon privé est créé automatiquement."
            )
        except discord.Forbidden:
            pass

        await send_log(interaction.guild, lobby_id, interaction.user, "join", None)


async def handle_leave(interaction: discord.Interaction, lobby_id: int):
    data = load_data()
    key  = str(lobby_id)

    if key not in data["lobbies"]:
        return await interaction.response.send_message("❌ Ce groupe n'existe plus.", ephemeral=True)

    lobby   = data["lobbies"][key]
    user_id = str(interaction.user.id)

    if user_id not in lobby["members"]:
        return await interaction.response.send_message("⚠️ Tu n'es pas dans ce groupe.", ephemeral=True)

    if lobby["status"] == "full":
        return await interaction.response.send_message("⛔ Le groupe est complet, tu ne peux plus quitter. Gère ça dans votre salon privé.", ephemeral=True)

    lobby["members"].remove(user_id)
    lobby["join_times"].pop(user_id, None)
    save_data(data)

    await interaction.response.defer()
    channel = bot.get_channel(LOBBY_CHANNEL_ID)
    msg     = await channel.fetch_message(int(lobby["message_id"]))
    await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=LobbyView(lobby_id))
    await send_log(interaction.guild, lobby_id, interaction.user, "leave", None)


async def send_log(guild: discord.Guild, lobby_id: int, user, action: str, private_chan=None):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel: return

    icons   = {"join": "➕", "leave": "➖", "full": "✅", "create": "🆕", "close": "🗑️"}
    colors  = {"join": 0x3498DB, "leave": 0xE74C3C, "full": 0x2ECC71, "create": 0x9B59B6, "close": 0x95A5A6}
    actions = {
        "join"  : f"a rejoint le Groupe #{lobby_id}",
        "leave" : f"a quitté le Groupe #{lobby_id}",
        "full"  : f"a complété le Groupe #{lobby_id} — salon privé créé",
        "create": f"— Groupe #{lobby_id} créé automatiquement",
        "close" : f"— Groupe #{lobby_id} fermé et salon supprimé",
    }

    is_system = action == "create"
    embed = discord.Embed(
        title=f"{icons.get(action, '📋')} {'Système' if is_system else user.display_name} {actions[action]}",
        color=colors.get(action, 0x95A5A6),
        timestamp=datetime.utcnow()
    )
    if not is_system:
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="Groupe", value=f"#{lobby_id}", inline=True)
    
    if private_chan:
        embed.add_field(name="🔒 Salon privé", value=private_chan.mention, inline=False)

    await log_channel.send(embed=embed)


async def create_new_lobby(guild: discord.Guild):
    data = load_data()
    data["lobby_counter"] += 1
    lobby_id = data["lobby_counter"]
    key      = str(lobby_id)

    channel = bot.get_channel(LOBBY_CHANNEL_ID)
    embed   = build_embed(lobby_id, [])
    view    = LobbyView(lobby_id)
    msg     = await channel.send(embed=embed, view=view)

    data["lobbies"][key] = {
        "message_id"        : str(msg.id),
        "members"           : [],
        "join_times"        : {},
        "status"            : "open",
        "created_at"        : datetime.utcnow().isoformat(),
        "private_channel_id": None
    }
    save_data(data)

    class FakeUser:
        display_name   = "Système"
        display_avatar = guild.me.display_avatar
        mention        = bot.user.mention
        id             = bot.user.id

    await send_log(guild, lobby_id, FakeUser(), "create", None)
    return lobby_id


# ─── COMMANDES SLASH ───────────────────────────────────────────────────────────
@bot.tree.command(name="nouveau-groupe", description="[Admin] Crée un nouveau groupe Brandsearch")
@app_commands.checks.has_permissions(manage_channels=True)
async def new_lobby(interaction: discord.Interaction):
    async with lobby_creation_lock:
        lobby_id = await create_new_lobby(interaction.guild)
    await interaction.response.send_message(f"Groupe #{lobby_id} créé dans <#{LOBBY_CHANNEL_ID}>", ephemeral=True)

@bot.tree.command(name="groupes-actifs", description="[Admin] Voir tous les groupes actifs")
@app_commands.checks.has_permissions(manage_channels=True)
async def list_lobbies(interaction: discord.Interaction):
    data = load_data()
    open_lobbies = [(k, v) for k, v in data["lobbies"].items() if v["status"] == "open"]
    if not open_lobbies:
        return await interaction.response.send_message("Aucun groupe actif.", ephemeral=True)
    
    embed = discord.Embed(title="Groupes Brandsearch actifs", color=COLOR_OPEN)
    for lid, lob in open_lobbies:
        membres_str = ", ".join([f"<@{m}>" for m in lob["members"]]) or "*vide*"
        embed.add_field(name=f"Groupe #{lid} — {len(lob['members'])}/{MAX_PLAYERS}", value=membres_str, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset-groupes", description="[Admin] Supprime tous les groupes et repart à zéro")
@app_commands.checks.has_permissions(administrator=True)
async def reset_lobbies(interaction: discord.Interaction):
    data = {"lobbies": {}, "lobby_counter": 0}
    save_data(data)
    await interaction.response.send_message("🔄 Tous les groupes ont été réinitialisés.", ephemeral=True)

@bot.tree.command(name="kick-membre", description="[Admin] Retire un membre d'un groupe")
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(lobby_id="ID du groupe", membre="Membre à retirer")
async def kick_membre(interaction: discord.Interaction, lobby_id: int, membre: discord.Member):
    data  = load_data()
    key   = str(lobby_id)
    lobby = data["lobbies"].get(key)
    
    if not lobby:
        return await interaction.response.send_message("Groupe introuvable.", ephemeral=True)
    if str(membre.id) not in lobby["members"]:
        return await interaction.response.send_message(f"{membre.mention} n'est pas dans ce groupe.", ephemeral=True)
        
    lobby["members"].remove(str(membre.id))
    lobby["join_times"].pop(str(membre.id), None)
    if lobby["status"] == "full":
        lobby["status"] = "open"
    save_data(data)
    
    channel = bot.get_channel(LOBBY_CHANNEL_ID)
    msg     = await channel.fetch_message(int(lobby["message_id"]))
    await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=LobbyView(lobby_id))
    await interaction.response.send_message(f"{membre.mention} retiré du Groupe #{lobby_id}.", ephemeral=True)
    await send_log(interaction.guild, lobby_id, membre, "leave", None)


class ConfirmFermetureView(discord.ui.View):
    def __init__(self, lobby_id: int, raison: str):
        super().__init__(timeout=30)
        self.lobby_id = lobby_id
        self.raison   = raison
        self.done     = False

    @discord.ui.button(label="Confirmer la suppression", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.done = True
        self.stop()
        data  = load_data()
        key   = str(self.lobby_id)
        lobby = data["lobbies"].get(key)
        
        if not lobby:
            return await interaction.response.send_message("Groupe introuvable.", ephemeral=True)
            
        private_chan_id = lobby.get("private_channel_id")
        if private_chan_id:
            private_chan = interaction.guild.get_channel(int(private_chan_id))
            if private_chan:
                try:
                    closing = discord.Embed(title="Ce salon va être supprimé", description=f"Raison : {self.raison}\n\nSuppression dans 5 secondes.", color=0x95A5A6)
                    await private_chan.send(embed=closing)
                    await asyncio.sleep(5)
                    await private_chan.delete(reason=f"Groupe #{self.lobby_id} fermé — {self.raison}")
                except (discord.Forbidden, discord.NotFound):
                    pass
                    
        data["lobbies"][key]["status"]             = "closed"
        data["lobbies"][key]["closed_at"]          = datetime.utcnow().isoformat()
        data["lobbies"][key]["closed_by"]          = str(interaction.user.id)
        data["lobbies"][key]["close_reason"]       = self.raison
        data["lobbies"][key]["private_channel_id"] = None
        save_data(data)
        
        await send_log(interaction.guild, self.lobby_id, interaction.user, "close", None)
        await interaction.response.send_message(f"✅ Groupe #{self.lobby_id} fermé. Raison : {self.raison}", ephemeral=True)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.done = True
        self.stop()
        await interaction.response.send_message("Annulé.", ephemeral=True)


@bot.tree.command(name="fermer-groupe", description="[Admin] Clôture un groupe et supprime son salon privé")
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(lobby_id="Numéro du groupe", raison="Raison de fermeture")
async def fermer_groupe(interaction: discord.Interaction, lobby_id: int, raison: str = "Achat terminé"):
    data  = load_data()
    key   = str(lobby_id)
    lobby = data["lobbies"].get(key)
    
    if not lobby:
        return await interaction.response.send_message(f"Groupe #{lobby_id} introuvable.", ephemeral=True)
    if lobby["status"] == "closed":
        return await interaction.response.send_message(f"Groupe #{lobby_id} déjà fermé.", ephemeral=True)
        
    membres_str = " ".join([f"<@{m}>" for m in lobby["members"]]) or "*aucun*"
    chan_id     = lobby.get("private_channel_id")
    chan_info   = f"<#{chan_id}>" if chan_id else "*pas de salon privé*"
    
    embed = discord.Embed(
        title=f"Confirmer la fermeture du Groupe #{lobby_id}",
        description=f"Membres : {membres_str}\nSalon privé : {chan_info}\nRaison : {raison}\n\nLe salon privé sera supprimé après 5 secondes.",
        color=0xE74C3C
    )
    await interaction.response.send_message(embed=embed, view=ConfirmFermetureView(lobby_id, raison), ephemeral=True)


@bot.event
async def on_ready():
    print(f"✅ Bot connecté : {bot.user} ({bot.user.id})")
    data = load_data()
    for lid, lob in data["lobbies"].items():
        if lob["status"] == "open":
            bot.add_view(LobbyView(int(lid)))
            
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} commande(s) slash synchronisée(s)")
    except Exception as e:
        print(f"Erreur sync : {e}")
        
    open_count = sum(1 for v in data["lobbies"].values() if v["status"] == "open")
    if open_count == 0 and LOBBY_CHANNEL_ID:
        guild = bot.guilds[0] if bot.guilds else None
        if guild:
            async with lobby_creation_lock:
                await create_new_lobby(guild)
            print("✅ Groupe initial créé au démarrage")


@bot.event
async def on_message(message: discord.Message):
    if message.channel.id == LOBBY_CHANNEL_ID and not message.author.bot:
        await message.delete()
        try:
            await message.author.send(
                "⚠️ Le salon Brandsearch Groupe ne permet pas les messages.\n"
                "Utilise les boutons Rejoindre / Quitter directement sur l'embed."
            )
        except discord.Forbidden:
            pass
    await bot.process_commands(message)

# ─── LANCEMENT ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN manquant !")
        exit(1)
    bot.run(TOKEN)
