<details open>
<summary>En</summary>
<br>
# ⬡ Game Support Tracker

> Monitors the Archipelago community APWorlds list and notifies of newly added games, status changes, and removals.

---

##  Download

- **Installer** : Download `GameSupportTrackerSetup.exe` from the [Releases](https://github.com/EnzoBagnis/GameSupportTracker/releases/latest) page and follow the installation wizard


---

##  First Launch

1. **Launch** `GameSupportTracker.exe`
2. Click on **⟳ Check for updates**
3. The app fetches the data and saves it to cache — this is your starting reference
4. The "Latest Changes" panel shows a very large number of changes → **this is normal**, it just retrieved all the information so it treats everything as new changes!

From the **second check** onwards, you will only see what has changed since the last check.

---

##  Interface

| Area | Description |
|---|---|
| **Left panel** | History of detected changes (additions , removals , statutses ) |
| **Tabs** | Switch between *Playable Worlds* and *Core Verified* |
| **Search** | Filter games by name, status, or notes |
| **Status filter** | Show only Stable, Unstable, In Review… |
| **PopTracker filter** | Show only games with/without a PopTracker pack |
| **Owned filter** | Show only games you own on Steam |
| **APWorld/Client column** | Direct links to APWorlds or custom clients |
| **Detail panel** | Click a game to see its notes, clickable links, and latest GitHub release |

---

##  Statuses

| Status | Meaning |
|---|---|
| 🟢 **Stable** | Functional and tested, recommended for multiworlds |
| 🟠 **Unstable** | Playable but may contain bugs |
| 🔵 **In Review** | Pull Request open on the official repo |
| 🔴 **Broken on Main** | No longer works with Archipelago 0.6.2+ |
| 🟣 **APWorld Only** | Available only as a custom `.apworld` |
| 🟩 **Merged** | Merged, will be included in the next official release |

---

##  Settings

Click the ⚙ icon to open the settings window. You can configure:

###  GitHub (releases)
- **Enable GitHub releases check** : on each check, the app queries the GitHub API to retrieve the latest release for each game that has a GitHub link in its notes.
- **GitHub Token** : required to exceed the 60 requests/hour limit of the public API.
Create a token with **ONLY** the `public_repo` at [github.com/settings/tokens](https://github.com/settings/tokens/new?description=GameSupportTracker&scopes=public_repo), adding more permissions could cause security risks.

###  Steam
- **Steam API Key** : obtenable at [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey).
- **Steam ID(s)** : one Steam ID per line (personal account or family members). Find your Steam ID at [steamidfinder.com](https://www.steamidfinder.com/)..
- Click ** Refresh Steam** to load your library. An **Owned** column will then appear in the table.

###  Language
- Choose between **English** and **French** then click **Apply**. A restart of the app is required for the change to take effect.

---

##  FAQ

**Why 0 changes on the first launch?**
> The first check creates the reference. Changes appear from the second check onwards.

**Where is the cache saved?**
> Automatically saved to `%APPDATA%\GameSupportTracker\archipelago_cache.json` (ex: `C:\Users\Enzo\AppData\Roaming\GameSupportTracker\`). Do not delete it, or you will lose the comparison baseline.

**Do I need to install Python or anything else?**
No. The `.exe` is standalone, everything is included.

**The left panel has disappeared, how do I get it back?**
> ~~Click the ▶ Changes button in the filter bar to show it again.~~
Feature currently non-functional, redesign in progress...

---

##  Data Source

Data comes from the [Archipelago community Google Sheet](https://docs.google.com/spreadsheets/d/1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw) maintained by the community.

---

##  Changelog

### Since v1.1

### Additions
- **License** : License: Added MIT license to the project
### Changes
- Improved game comparison script. Can now **detect** some **acronyms**.
e.g. Totally Accurate Battle Simulator = TABS
- **Project name** changed
now: Game Support Tracker
previously: Archipelago Game Tracker

---

## Planned Features

- Done | Add the ability to cancel an update in progress
- Make the 'latest changes' arrow useful (current utility is very trivial)
- Add a change history for the last 10 updates
- Done | Move the settings button to the right of the title instead of next to the update button
- Done | Add Yes/No values to the lang files
- Done | In the settings page, add automatic line wrapping when text overflows the window
- Done | In the settings page, make the Steam IDs input box display fully
- Done | For the settings page, define a maximum default height
- Done | For the settings page, allow resizing
- Done | Add the option to enter game owned manually
- Dectect game from other platform (Itch.io, epic)
</details>

<details>
<summary>Fr</summary>
<br>
# ⬡ Game Support Tracker

> Surveille la liste communautaire des APWorlds Archipelago et notifie des nouveaux jeux ajoutés, des changements de statut et des retraits.

---

##  Téléchargement

- **Installeur** : Télécharge `GameSupportTrackerSetup.exe` depuis la page [Releases](https://github.com/EnzoBagnis/GameSupportTracker/releases/latest) et suis l'assistant d'installation.


---

##  Premier lancement

1. **Lance** `GameSupportTracker.exe`
2. Clique sur **⟳ Vérifier les mises à jour**
3. L'application récupère les données et les enregistre en cache — c'est ta référence de départ
4. Le panneau "Derniers changements" affiche une très grande quantité de changement → **c'est normal**, il viens de récupérer toute les informations donc, il les considèrent comme changements !

À partir du **deuxième check**, tu verras uniquement ce qui a changé depuis la dernière vérification.

---

##  Interface

| Zone | Description |
|---|---|
| **Panneau gauche** | Historique des changements détectés (ajouts , retraits , statuts ) |
| **Onglets** | Basculer entre *Playable Worlds* et *Core Verified* |
| **Recherche** | Filtrer les jeux par nom, statut ou notes |
| **Filtre statut** | Afficher uniquement Stable, Unstable, In Review… |
| **Filtre PopTracker** | Afficher uniquement les jeux avec/sans pack PopTracker |
| **Filtre Owned** | Afficher uniquement les jeux possédés sur Steam |
| **Colonne APWorld/Client** | Liens directs vers les APWorlds ou clients custom |
| **Panneau de détail** | Cliquer sur un jeu pour voir ses notes, ses liens cliquables et sa dernière release GitHub |

---

##  Statuts

| Statut | Signification |
|---|---|
| 🟢 **Stable** | Fonctionnel et testé, recommandé pour les multis |
| 🟠 **Unstable** | Jouable mais peut contenir des bugs |
| 🔵 **In Review** | Pull Request ouverte sur le repo officiel |
| 🔴 **Broken on Main** | Ne fonctionne pas/plus avec Archipelago 0.6.2+ |
| 🟣 **APWorld Only** | Disponible uniquement en `.apworld` custom |
| 🟩 **Merged** | Mergé, sera dans la prochaine release officielle |

---

##  Paramètres

Clique sur l'icône ⚙ pour ouvrir la fenêtre de paramètres. Tu peux y configurer :

###  GitHub (releases)
- **Activer la vérification des releases GitHub** : lors de chaque check, l'app interroge l'API GitHub pour récupérer la dernière release de chaque jeu ayant un lien GitHub dans ses notes.
- **Token GitHub** : nécessaire pour dépasser la limite de 60 requêtes/heure de l'API publique. 
Crée un token avec SEULEMENT le scope `public_repo` sur [github.com/settings/tokens](https://github.com/settings/tokens/new?description=GameSupportTracker&scopes=public_repo), mettre plus de paramètre pourrais causer des risques.

###  Steam
- **Clé API Steam** : obtenable sur [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey).
- **Steam ID(s)** : un identifiant Steam par ligne (compte personnel ou membres d'une famille). Trouve ton Steam ID sur [steamidfinder.com](https://www.steamidfinder.com/).
- Clique sur ** Refresh Steam** pour charger ta bibliothèque. Une colonne **Owned** apparaît alors dans le tableau.

###  Langue
- Choisis entre **English** et **Français** puis clique sur **Appliquer**. Un redémarrage de l'app est nécessaire pour que le changement prenne effet.

---

##  FAQ

**Pourquoi 0 changement au premier lancement ?**
> Le premier check crée la référence. Les changements apparaissent à partir du second.

**Où est sauvegardé le cache ?**
> Sauvegardé automatiquement dans `%APPDATA%\GameSupportTracker\archipelago_cache.json` (ex: `C:\Users\Enzo\AppData\Roaming\GameSupportTracker\`). Ne pas le supprime, sinon tu perds la comparaison.

**Besoin d'installer Python ou quoi que ce soit ?**
> Non. Le `.exe` est autonome, tout est inclus.

**Le panneau gauche a disparu, comment le retrouver ?**
> ~~Clique sur le bouton **▶ Changes** dans la barre de filtre pour le réafficher.~~
Fonctionnalité actuellement inutile, reconception en cours...

---

##  Source des données

Les données proviennent du [Google Sheets communautaire Archipelago](https://docs.google.com/spreadsheets/d/1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw) maintenu par la communauté.

---

##  Changelog

### Depuis la v1.1

### Ajouts
- **License** : Ajout de la license MIT au projet
### Modifications
- Amélioration du script de comparaison de jeu. Peut désormais **détecter** une partie des **acronymes**.
ex Totally Accurate Battle Simulator = TABS
- Changement du **nom du projet**
maintenant : Game Support Tracker
précedement : Archipelago Game Tracker

---

## Ce qui est prévu pour la suite

- Fait | Ajout de la possibilité d'annuler une update en cours de route
- Rendre la flèche de 'latest changes' utile (utilité actuelle très triviale)
- Ajout d'un historique des changements pour les 10 dernières updates
- Fait | Positionner le bouton paramètre à droite du titre et non collé au bouton update
- Fait | Rajouter les Yes, No du tableau dans les lang files
- Fait | Dans la page paramètre, faire des retours à la ligne automatiques lorsque le texte dépasse de la fenêtre
- Fait | Dans la page paramètre, faire en sorte que la case contenant les Steam IDs s'affiche en entier
- Fait | Pour la page paramètre, définir une hauteur maximale (par défaut)
- Fait | Pour la page paramètre, permettre de la resize
- Fait | Ajouter la possibilité de rentré manuellement les jeux possédés
- Détection des jeux sur les autres platforms (Itch.io, epic)

</details>
