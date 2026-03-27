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
MAX_PLAYERS          = 5          # ✅ CORRIGÉ : remis à 5
PROMO_CODE           = "SULEYECOM"
DATA_FILE            = "lobbies.json"

# Prix réels
PRIX_ORIGINAL_USD  = 149    # Agency sans code
REMISE_PCT         = 40     # -40% avec SULEYECOM
PRIX_GROUPE_EUR    = 16.50  # par personne après remise + division par 5

# ─── COULEURS EMBED ────────────────────────────────────────────────────────────
COLOR_OPEN   = 0xFFD700
COLOR_FULL   = 0x2ECC71
COLOR_CLOSED = 0x95A5A6
COLOR_PROMO  = 0xFF6B35

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
    count     = len(members)
    full      = count >= MAX_PLAYERS
    remaining = MAX_PLAYERS - count

    # ── Lobby COMPLET ──
    if full:
        embed = discord.Embed(
            title="✅  Groupe #" + str(lobby_id) + " — COMPLET",
            description=(
                "Ce groupe est **complet** ! Les 5 membres sont dans leur salon privé.\n"
                "Un nouveau groupe a été ouvert ci-dessous 👇"
            ),
            color=COLOR_FULL
        )
        embed.add_field(
            name="Membres du groupe",
            value=" ".join([f"<@{m}>" for m in members]),
            inline=False
        )
        embed.set_footer(text=f"Groupe #{lobby_id} • Brandsearch Agency")
        return embed

    # ── Lobby OUVERT ──
    # ✅ CORRIGÉ : calcul propre et cohérent, tout en euros
    # 149$ / 5 personnes = 29.8$/personne
    # 29.8$ * 0.60 (après -40%) ≈ 17.88$ → mais on affiche le vrai prix négocié : 16.50€
    # Économie annuelle : un abo solo Agency coûterait ~149$ soit ~138€/mois
    # Avec groupe : 16.50€/mois → économie = (138 - 16.50) * 12 = ~1458€/an
    # On garde simple : on compare vs prix solo avec code uniquement = 149*0.6 = 89.4$ ≈ 83€/mois
    PRIX_SOLO_AVEC_CODE_EUR = round(PRIX_ORIGINAL_USD * (1 - REMISE_PCT / 100) * 0.93, 2)  # ~83€ (1$≈0.93€)
    economie_mois           = round(PRIX_SOLO_AVEC_CODE_EUR - PRIX_GROUPE_EUR, 2)
    economie_annee          = round(economie_mois * 12, 2)

    filled = "🟡" * count
    empty  = "⬛" * remaining

    embed = discord.Embed(
        title=f"💰 Groupe #{lobby_id} — {count}/{MAX_PLAYERS} membres",
        description=(
            "### Brandsearch Agency pour **16,50€/mois** 🔥\n"
            f"Divisez le prix par 5 et profitez de **-{REMISE_PCT}%** avec le code **`{PROMO_CODE}`**.\n\n"
            f"⏳ *Il reste **{remaining} place{'s' if remaining > 1 else ''}** dans ce groupe.*"
        ),
        color=COLOR_OPEN
    )

    embed.add_field(
        name="💵 Économie réalisée",
        value=(
            f"• Prix Agency **solo** (avec code) : ~{PRIX_SOLO_AVEC_CODE_EUR}€/mois\n"
            f"• Prix Agency **en groupe** : **{PRIX_GROUPE_EUR}€/mois** ✅\n"
            f"🎯 Tu économises **~{economie_mois}€/mois** soit **~{economie_annee}€/an** !"
        ),
        inline=False
    )

    membres_str = " ".join([f"<@{m}>" for m in members]) if members else "*Aucun membre — sois le premier !*"
    embed.add_field(
        name=f"👥 Membres ({count}/{MAX_PLAYERS})",
        value=f"{filled}{empty}  {membres_str}",
        inline=False
    )

    embed.add_field(
        name="🚀 Brandsearch Agency inclut",
        value=(
            "• **Brand Library** — Unlimited stores (spy Shopify, trafic, demande)\n"
            "• **Spectre** — 100 marques trackées en simultané\n"
            "• **Discovery** — Unlimited (ads qui vendent, triggers émotionnels IA)\n"
            "• **Swipe Files** — Chrome ext, Instagram auto-sync\n"
            "• **Remplace Foreplay & Atria** — 150$/mois économisés en plus ✅"
        ),
        inline=False
    )

    embed.add_field(
        name="📋 Comment ça marche ?",
        value=(
            "1️⃣ Clique sur **Rejoindre** pour bloquer ta place\n"
            "2️⃣ À **5/5**, un salon secret se crée automatiquement 🔒\n"
            "3️⃣ Vous organisez le paiement à l'intérieur\n"
            f"4️⃣ Code **`{PROMO_CODE}`** → **-{REMISE_PCT}%** au moment de souscrire"
        ),
        inline=False
    )

    embed.set_footer(text=f"Groupe #{lobby_id} • Brandsearch Agency • Code : {PROMO_CODE}")
    return embed


# ─── VUE BOUTON ────────────────────────────────────────────────────────────────
class LobbyView(discord.ui.View):
    def __init__(self, lobby_id: int):
        super().__init__(timeout=None)
        self.lobby_id = lobby_id

    @discord.ui.button(label="✅  Rejoindre le groupe", style=discord.ButtonStyle.success,
                       custom_id="join_lobby")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_join(interaction, self.lobby_id)

    @discord.ui.button(label="❌  Quitter", style=discord.ButtonStyle.danger,
                       custom_id="leave_lobby")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_leave(interaction, self.lobby_id)


# ─── LOGIQUE JOIN ──────────────────────────────────────────────────────────────
async def handle_join(interaction: discord.Interaction, lobby_id: int):
    data = load_data()
    key  = str(lobby_id)

    if key not in data["lobbies"]:
        await interaction.response.send_message("❌ Ce groupe n'existe plus.", ephemeral=True)
        return

    lobby   = data["lobbies"][key]
    user_id = str(interaction.user.id)

    if lobby["status"] == "full":
        await interaction.response.send_message(
            "⛔ Ce groupe est déjà complet ! Regarde s'il y a un groupe ouvert plus bas.",
            ephemeral=True
        )
        return

    if user_id in lobby["members"]:
        await interaction.response.send_message(
            "⚠️ Tu es déjà dans ce groupe. Attends que les 5 places soient prises !",
            ephemeral=True
        )
        return

    # Vérifie si l'user est dans un autre lobby actif
    for lid, lob in data["lobbies"].items():
        if user_id in lob["members"] and lob["status"] == "open":
            await interaction.response.send_message(
                f"⚠️ Tu es déjà dans le Groupe #{lid}. Quitte-le d'abord avant d'en rejoindre un autre.",
                ephemeral=True
            )
            return

    lobby["members"].append(user_id)
    lobby["join_times"][user_id] = datetime.utcnow().isoformat()

    places_restantes = MAX_PLAYERS - len(lobby["members"])

    # ── Lobby complet ? ────────────────────────────────────────────────────────
    if len(lobby["members"]) >= MAX_PLAYERS:
        lobby["status"] = "full"
        save_data(data)

        await interaction.response.defer()

        channel = bot.get_channel(LOBBY_CHANNEL_ID)
        msg     = await channel.fetch_message(int(lobby["message_id"]))
        view    = LobbyView(lobby_id)
        view.children[0].disabled = True
        view.children[1].disabled = True
        await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=view)

        # ── Création du salon privé ────────────────────────────────────────────
        guild        = interaction.guild
        private_chan = None

        try:
            membres_obj = []
            for uid in lobby["members"]:
                m = guild.get_member(int(uid))
                if m is None:
                    try:
                        m = await guild.fetch_member(int(uid))
                    except Exception:
                        pass
                if m:
                    membres_obj.append(m)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me:           discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            }
            for m in membres_obj:
                overwrites[m] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            for role in guild.roles:
                if role.permissions.administrator or role.permissions.manage_guild:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            category = None
            if PRIVATE_CATEGORY_ID:
                category = guild.get_channel(PRIVATE_CATEGORY_ID)

            private_chan = await guild.create_text_channel(
                name=f"groupe-{lobby_id}-brandsearch",
                overwrites=overwrites,
                category=category,
                topic=f"Groupe #{lobby_id} Brandsearch Agency — salon privé des 5 membres"
            )

            mentions = " ".join([m.mention for m in membres_obj])

            PRIX_SOLO_AVEC_CODE_EUR = round(PRIX_ORIGINAL_USD * (1 - REMISE_PCT / 100) * 0.93, 2)
            economie_annee          = round((PRIX_SOLO_AVEC_CODE_EUR - PRIX_GROUPE_EUR) * 12, 2)

            welcome_embed = discord.Embed(
                title=f"🔒 Groupe #{lobby_id} — Salon privé Brandsearch",
                description=(
                    f"Bienvenue {mentions} !\n\n"
                    "Vous êtes les **5 membres** de ce groupe. Ce salon est **totalement invisible** "
                    "pour les autres membres du serveur.\n\n"
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
                    "2️⃣ Le référent partage son **RIB** ici pour se faire rembourser\n"
                    "3️⃣ Les 4 autres font un virement de **16,50€** au référent\n"
                    f"4️⃣ Le référent souscrit avec le code **`{PROMO_CODE}`** sur Brandsearch\n"
                    "5️⃣ Il ajoute vos **emails** dans l'espace Agency pour vous donner accès\n"
                    "6️⃣ Chacun a ses propres accès — aucune donnée partagée 🔐\n\n"
                    "⚠️ Les admins peuvent voir ce salon — restez corrects 👀"
                ),
                inline=False
            )
            welcome_embed.set_footer(text=f"Groupe #{lobby_id} • Brandsearch Agency • Salon modéré")

            await private_chan.send(content=mentions, embed=welcome_embed)

            # ✅ CORRIGÉ : sauvegarde du channel_id proprement sans re-charger
            data["lobbies"][key]["private_channel_id"] = str(private_chan.id)
            save_data(data)

        except discord.Forbidden:
            print(f"❌ Permissions insuffisantes pour créer le salon privé du groupe #{lobby_id}")
        except Exception as e:
            print(f"❌ Erreur création salon privé groupe #{lobby_id} : {e}")

        await send_log(interaction.guild, lobby_id, interaction.user, "full", private_chan)

        # ✅ CORRIGÉ : on recharge les données APRÈS la sauvegarde pour éviter la race condition
        await create_new_lobby(interaction.guild)

    else:
        save_data(data)
        await interaction.response.defer()

        channel = bot.get_channel(LOBBY_CHANNEL_ID)
        msg     = await channel.fetch_message(int(lobby["message_id"]))
        await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=LobbyView(lobby_id))

        try:
            await interaction.user.send(
                f"✅ **Tu as rejoint le Groupe #{lobby_id} !**\n\n"
                f"Il reste **{places_restantes} place{'s' if places_restantes > 1 else ''}** avant que le groupe soit complet.\n"
                f"Dès que vous êtes {MAX_PLAYERS}, un **salon privé** est créé automatiquement pour vous coordonner. 🔒\n\n"
                f"**Rappel :** Code **`{PROMO_CODE}`** = **-{REMISE_PCT}%** sur Brandsearch Agency → **{PRIX_GROUPE_EUR}€/mois** 💰"
            )
        except discord.Forbidden:
            pass

        await send_log(interaction.guild, lobby_id, interaction.user, "join")


# ─── LOGIQUE LEAVE ─────────────────────────────────────────────────────────────
async def handle_leave(interaction: discord.Interaction, lobby_id: int):
    data = load_data()
    key  = str(lobby_id)

    if key not in data["lobbies"]:
        await interaction.response.send_message("❌ Ce groupe n'existe plus.", ephemeral=True)
        return

    lobby   = data["lobbies"][key]
    user_id = str(interaction.user.id)

    if user_id not in lobby["members"]:
        await interaction.response.send_message("⚠️ Tu n'es pas dans ce groupe.", ephemeral=True)
        return

    if lobby["status"] == "full":
        await interaction.response.send_message(
            "⛔ Le groupe est complet, tu ne peux plus quitter. Gère ça dans votre salon privé.",
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
    await send_log(interaction.guild, lobby_id, interaction.user, "leave", None)


# ─── LOG ───────────────────────────────────────────────────────────────────────
async def send_log(guild: discord.Guild, lobby_id: int, user, action: str, private_chan=None):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return

    icons   = {"join": "➕", "leave": "➖", "full": "✅", "create": "🆕", "close": "🗑️", "archive": "📦"}
    colors  = {"join": 0x3498DB, "leave": 0xE74C3C, "full": 0x2ECC71, "create": 0x9B59B6, "close": 0x95A5A6, "archive": 0xF39C12}
    actions = {
        "join"   : f"a rejoint le Groupe #{lobby_id}",
        "leave"  : f"a quitté le Groupe #{lobby_id}",
        "full"   : f"a complété le Groupe #{lobby_id} (5/5) — salon privé créé + nouveau groupe ouvert",
        "create" : f"— Groupe #{lobby_id} créé automatiquement",
        "close"  : f"— Groupe #{lobby_id} fermé et salon supprimé",
        "archive": f"— Groupe #{lobby_id} archivé (salon supprimé, données conservées)",
    }

    is_system = action in ("create",)
    embed = discord.Embed(
        title=f"{icons.get(action,'📋')} {'Système' if is_system else user.display_name} {actions[action]}",
        color=colors.get(action, 0x95A5A6),
        timestamp=datetime.utcnow()
    )
    if not is_system:
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=True)
    embed.add_field(name="Groupe", value=f"#{lobby_id}", inline=True)
    embed.add_field(name="Heure (UTC)", value=datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S"), inline=True)
    if private_chan:
        embed.add_field(name="🔒 Salon privé créé", value=private_chan.mention, inline=False)

    await log_channel.send(embed=embed)


# ─── CRÉATION D'UN GROUPE ──────────────────────────────────────────────────────
async def create_new_lobby(guild: discord.Guild, data: dict = None):
    # ✅ CORRIGÉ : on recharge TOUJOURS depuis le disque pour avoir les données fraîches
    data = load_data()

    data["lobby_counter"] += 1
    lobby_id = data["lobby_counter"]
    key      = str(lobby_id)

    channel = bot.get_channel(LOBBY_CHANNEL_ID)
    embed   = build_embed(lobby_id, [])
    view    = LobbyView(lobby_id)
    msg     = await channel.send(embed=embed, view=view)

    data["lobbies"][key] = {
        "message_id"       : str(msg.id),
        "members"          : [],
        "join_times"       : {},
        "status"           : "open",
        "created_at"       : datetime.utcnow().isoformat(),
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
    lobby_id = await create_new_lobby(interaction.guild)
    await interaction.response.send_message(
        f"✅ Groupe #{lobby_id} créé dans <#{LOBBY_CHANNEL_ID}>", ephemeral=True
    )

@bot.tree.command(name="groupes-actifs", description="[Admin] Voir tous les groupes actifs")
@app_commands.checks.has_permissions(manage_channels=True)
async def list_lobbies(interaction: discord.Interaction):
    data = load_data()
    open_lobbies = [(k, v) for k, v in data["lobbies"].items() if v["status"] == "open"]

    if not open_lobbies:
        await interaction.response.send_message("Aucun groupe actif.", ephemeral=True)
        return

    embed = discord.Embed(title="🔍 Groupes Brandsearch actifs", color=COLOR_OPEN)
    for lid, lob in open_lobbies:
        membres_str = ", ".join([f"<@{m}>" for m in lob["members"]]) or "*vide*"
        embed.add_field(
            name=f"Groupe #{lid} — {len(lob['members'])}/{MAX_PLAYERS}",
            value=membres_str,
            inline=False
        )
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
    data = load_data()
    key  = str(lobby_id)

    if key not in data["lobbies"]:
        await interaction.response.send_message("❌ Groupe introuvable.", ephemeral=True)
        return

    lobby   = data["lobbies"][key]
    user_id = str(membre.id)

    if user_id not in lobby["members"]:
        await interaction.response.send_message(f"⚠️ {membre.mention} n'est pas dans ce groupe.", ephemeral=True)
        return

    lobby["members"].remove(user_id)
    lobby["join_times"].pop(user_id, None)

    if lobby["status"] == "full":
        lobby["status"] = "open"

    save_data(data)

    channel = bot.get_channel(LOBBY_CHANNEL_ID)
    msg     = await channel.fetch_message(int(lobby["message_id"]))
    await msg.edit(embed=build_embed(lobby_id, lobby["members"]), view=LobbyView(lobby_id))

    await interaction.response.send_message(
        f"✅ {membre.mention} a été retiré du Groupe #{lobby_id}.", ephemeral=True
    )
    await send_log(interaction.guild, lobby_id, membre, "leave", None)


# ─── VUE DE CONFIRMATION FERMETURE ────────────────────────────────────────────
class ConfirmFermetureView(discord.ui.View):
    def __init__(self, lobby_id: int, raison: str):
        super().__init__(timeout=30)
        self.lobby_id = lobby_id
        self.raison   = raison
        self.done     = False

    @discord.ui.button(label="✅ Confirmer la suppression", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.done = True
        self.stop()

        data  = load_data()
        key   = str(self.lobby_id)
        lobby = data["lobbies"].get(key)

        if not lobby:
            await interaction.response.send_message("❌ Groupe introuvable dans les données.", ephemeral=True)
            return

        private_chan_id = lobby.get("private_channel_id")

        if private_chan_id:
            private_chan = interaction.guild.get_channel(int(private_chan_id))
            if private_chan:
                try:
                    closing_embed = discord.Embed(
                        title="🔒 Ce salon va être supprimé",
                        description=(
                            f"**Raison :** {self.raison}\n\n"
                            "Ce salon privé a été clôturé par un administrateur.\n"
                            "Toutes les données qu'il contient vont disparaître.\n\n"
                            "Merci d'avoir utilisé le groupe Brandsearch ! 🙌"
                        ),
                        color=0x95A5A6
                    )
                    closing_embed.set_footer(text="Suppression dans 5 secondes…")
                    await private_chan.send(embed=closing_embed)
                    await asyncio.sleep(5)
                    await private_chan.delete(reason=f"Groupe #{self.lobby_id} fermé par admin — {self.raison}")
                except discord.Forbidden:
                    await interaction.followup.send(
                        "⚠️ Je n'ai pas la permission de supprimer ce salon. Vérifie mes permissions `Manage Channels`.",
                        ephemeral=True
                    )
                    return
                except discord.NotFound:
                    pass
            else:
                await interaction.followup.send(
                    f"⚠️ Salon privé introuvable (ID `{private_chan_id}`). Déjà supprimé manuellement ?\n"
                    "Les données du groupe ont quand même été archivées.",
                    ephemeral=True
                )
        else:
            await interaction.followup.send(
                f"ℹ️ Aucun salon privé enregistré pour le Groupe #{self.lobby_id}.",
                ephemeral=True
            )

        data["lobbies"][key]["status"]             = "closed"
        data["lobbies"][key]["closed_at"]          = datetime.utcnow().isoformat()
        data["lobbies"][key]["closed_by"]          = str(interaction.user.id)
        data["lobbies"][key]["close_reason"]       = self.raison
        data["lobbies"][key]["private_channel_id"] = None
        save_data(data)

        await send_log(interaction.guild, self.lobby_id, interaction.user, "close", None)

        await interaction.response.send_message(
            f"✅ **Groupe #{self.lobby_id} fermé.**\n"
            f"Salon privé supprimé • Données archivées • Raison : *{self.raison}*",
            ephemeral=True
        )

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.done = True
        self.stop()
        await interaction.response.send_message("Annulé. Aucune modification effectuée.", ephemeral=True)

    async def on_timeout(self):
        pass


@bot.tree.command(name="fermer-groupe", description="[Admin] Clôture un groupe et supprime son salon privé")
@app_commands.checks.has_permissions(manage_channels=True)
@app_commands.describe(
    lobby_id="Numéro du groupe à fermer",
    raison="Raison de la fermeture (ex: achat terminé, membre inactif…)"
)
async def fermer_groupe(interaction: discord.Interaction, lobby_id: int, raison: str = "Achat terminé"):
    data  = load_data()
    key   = str(lobby_id)
    lobby = data["lobbies"].get(key)

    if not lobby:
        await interaction.response.send_message(f"❌ Groupe #{lobby_id} introuvable.", ephemeral=True)
        return

    if lobby["status"] == "closed":
        await interaction.response.send_message(f"⚠️ Le Groupe #{lobby_id} est déjà fermé.", ephemeral=True)
        return

    membres_str     = " ".join([f"<@{m}>" for m in lobby["members"]]) or "*aucun*"
    private_chan_id = lobby.get("private_channel_id")
    chan_info       = f"<#{private_chan_id}>" if private_chan_id else "*pas de salon privé*"

    confirm_embed = discord.Embed(
        title=f"⚠️ Confirmer la fermeture du Groupe #{lobby_id}",
        description=(
            f"**Statut actuel :** `{lobby['status']}`\n"
            f"**Membres :** {membres_str}\n"
            f"**Salon privé :** {chan_info}\n"
            f"**Raison saisie :** {raison}\n\n"
            "Le salon privé recevra un **message d'avertissement** puis sera **supprimé après 5 secondes**.\n"
            "Les données du groupe seront **archivées** dans le fichier JSON (non effacées)."
        ),
        color=0xE74C3C
    )

    view = ConfirmFermetureView(lobby_id, raison)
    await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)


# ─── EVENTS ────────────────────────────────────────────────────────────────────
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
        print(f"❌ Erreur sync : {e}")

    open_count = sum(1 for v in data["lobbies"].values() if v["status"] == "open")
    if open_count == 0 and LOBBY_CHANNEL_ID:
        guild = bot.guilds[0] if bot.guilds else None
        if guild:
            await create_new_lobby(guild)
            print("✅ Groupe initial créé")


@bot.event
async def on_message(message: discord.Message):
    if message.channel.id == LOBBY_CHANNEL_ID and not message.author.bot:
        await message.delete()
        try:
            await message.author.send(
                "⚠️ Le salon **Brandsearch Groupe** ne permet pas les messages.\n"
                "Utilise les boutons **Rejoindre / Quitter** directement sur l'embed."
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
