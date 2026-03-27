# 🤖 Guide d'installation — Brandsearch Lobby Bot

---

## ÉTAPE 1 — Créer le bot sur Discord

1. Va sur https://discord.com/developers/applications
2. Clique **"New Application"** → nomme-le `Brandsearch Bot`
3. Dans le menu gauche → **"Bot"**
4. Clique **"Reset Token"** → copie le token (garde-le secret !)
5. Active ces 3 options dans "Privileged Gateway Intents" :
   - ✅ PRESENCE INTENT
   - ✅ SERVER MEMBERS INTENT
   - ✅ MESSAGE CONTENT INTENT
6. Clique **"Save Changes"**

---

## ÉTAPE 2 — Inviter le bot sur ton serveur

1. Dans le menu gauche → **"OAuth2"** → **"URL Generator"**
2. Coche **"bot"** et **"applications.commands"**
3. Dans les permissions bot, coche :
   - ✅ Read Messages/View Channels
   - ✅ Send Messages
   - ✅ Manage Messages
   - ✅ Embed Links
   - ✅ Read Message History
4. Copie l'URL générée en bas → ouvre-la dans ton navigateur
5. Sélectionne ton serveur → **"Authoriser"**

---

## ÉTAPE 3 — Préparer les salons Discord

Sur ton serveur, crée :

**Salon public :**
- `🔍・brandsearch-groupe` (dans la catégorie FREEMIUM - BRANDSEARCH)
  - Permissions : les membres peuvent lire mais PAS écrire (le bot gère tout)

**Salon privé logs (visible uniquement par toi) :**
- `📋・logs-brandsearch` (dans une catégorie staff/privée)
  - Permissions : visible uniquement par toi et le bot

**Récupère les IDs des salons :**
1. Dans Discord → Paramètres → Avancés → Active le **Mode développeur**
2. Fais clic droit sur chaque salon → **"Copier l'identifiant"**

---

## ÉTAPE 4 — Héberger sur Railway (gratuit)

1. Va sur https://railway.app
2. Crée un compte (avec GitHub, c'est plus simple)
3. Clique **"New Project"** → **"Deploy from GitHub repo"**
4. Crée un repo GitHub avec les fichiers du bot (bot.py, requirements.txt, Procfile)
5. Connecte Railway à ce repo

**Ajoute les variables d'environnement dans Railway :**
- Clique sur ton projet → **"Variables"**
- Ajoute ces 3 variables :

```
DISCORD_TOKEN     = [le token copié à l'étape 1]
LOBBY_CHANNEL_ID  = [l'ID du salon brandsearch-groupe]
LOG_CHANNEL_ID    = [l'ID du salon logs-brandsearch]
```

6. Railway démarre le bot automatiquement ✅

---

## ÉTAPE 5 — Premier démarrage

Le bot va automatiquement :
- ✅ Se connecter à Discord
- ✅ Créer un premier lobby dans ton salon
- ✅ Synchroniser les commandes slash

**Commandes disponibles (admin uniquement) :**

| Commande | Description |
|----------|-------------|
| `/nouveau-lobby` | Crée un nouveau lobby manuellement |
| `/lobbies-actifs` | Voir tous les lobbies et leurs membres |
| `/reset-lobbies` | Tout effacer et recommencer à zéro |

---

## FONCTIONNEMENT

```
[Membre clique "Rejoindre"]
        ↓
Bot vérifie : pas déjà dans un lobby ? lobby pas full ?
        ↓
Ajoute le membre + met à jour le compteur 1/5 → 2/5...
        ↓
Si 5/5 → Lobby marqué COMPLET + bouton désactivé
        ↓
Nouveau lobby créé automatiquement
        ↓
Log envoyé dans ton salon privé
```

---

## EN CAS DE PROBLÈME

**Le bot ne répond pas :**
→ Vérifie que le TOKEN est correct dans Railway

**Les boutons ne fonctionnent plus après redémarrage :**
→ Normal, le bot les réenregistre automatiquement au démarrage

**Le bot ne peut pas supprimer les messages :**
→ Vérifie que la permission "Manage Messages" est activée

---

## SÉCURITÉ

- Ne partage JAMAIS ton `DISCORD_TOKEN`
- Le fichier `lobbies.json` contient les IDs des membres — garde-le en sécurité
- Les membres ne peuvent pas écrire dans le salon (messages supprimés automatiquement)
