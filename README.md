# ⬡ Archipelago Game Tracker

> Surveille la liste communautaire des APWorlds Archipelago et te notifie des nouveaux jeux ajoutés, des changements de statut et des retraits.

---

## ⬇️ Téléchargement

- **Installeur** : télécharge `ArchipelagoTrackerSetup.exe` depuis la page [Releases](https://github.com/EnzoBagnis/ArchipelagoGameTracker/releases/latest) et suis l'assistant d'installation.


---

## 🚀 Premier lancement

1. **Lance** `ArchipelagoTracker.exe`
2. Clique sur **⟳ Vérifier les mises à jour**
3. L'application récupère les données et les enregistre en cache — c'est ta référence de départ
4. Le panneau "Derniers changements" affiche `0 changement` → **c'est normal**, il n'y a rien à comparer encore !

À partir du **deuxième check**, tu verras uniquement ce qui a changé depuis la dernière vérification.

---

## 🖥️ Interface

| Zone | Description |
|---|---|
| **Panneau gauche** | Historique des changements détectés (ajouts ✅, retraits ❌, statuts 🔄) |
| **Onglets** | Basculer entre *Playable Worlds* et *Core Verified* |
| **Recherche** | Filtrer les jeux par nom, statut ou notes |
| **Filtre statut** | Afficher uniquement Stable, Unstable, In Review… |
| **Filtre PopTracker** | Afficher uniquement les jeux avec/sans pack PopTracker |
| **Filtre Owned** | Afficher uniquement les jeux possédés sur Steam |
| **Colonne APWorld/Client** | Liens directs vers les APWorlds ou clients custom |
| **Panneau de détail** | Cliquer sur un jeu pour voir ses notes, ses liens cliquables et sa dernière release GitHub |

---

## 🎨 Statuts

| Statut | Signification |
|---|---|
| 🟢 **Stable** | Fonctionnel et testé, recommandé pour les multis |
| 🟠 **Unstable** | Jouable mais peut contenir des bugs |
| 🔵 **In Review** | Pull Request ouverte sur le repo officiel |
| 🔴 **Broken on Main** | Ne fonctionne plus avec Archipelago 0.6.2+ |
| 🟣 **APWorld Only** | Disponible uniquement en `.apworld` custom |
| 🟩 **Merged** | Mergé, sera dans la prochaine release officielle |

---

## ⚙️ Paramètres

Clique sur l'icône ⚙ pour ouvrir la fenêtre de paramètres. Tu peux y configurer :

### 🐙 GitHub (releases)
- **Activer la vérification des releases GitHub** : lors de chaque check, l'app interroge l'API GitHub pour récupérer la dernière release de chaque jeu ayant un lien GitHub dans ses notes.
- **Token GitHub** : nécessaire pour dépasser la limite de 60 requêtes/heure de l'API publique. Crée un token avec le scope `public_repo` sur [github.com/settings/tokens](https://github.com/settings/tokens/new?description=ArchipelagoTracker&scopes=public_repo).

### 🎮 Steam
- **Clé API Steam** : obtiens-la sur [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey).
- **Steam ID(s)** : un identifiant Steam par ligne (compte personnel ou membres d'une famille). Trouve ton Steam ID sur [steamidfinder.com](https://www.steamidfinder.com/).
- Clique sur **🎮 Refresh Steam** pour charger ta bibliothèque. Une colonne **Owned** apparaît alors dans le tableau.

### 🌐 Langue
- Choisis entre **English** et **Français** puis clique sur **Appliquer**. Un redémarrage de l'app est nécessaire pour que le changement prenne effet.

---

## ❓ FAQ

**Pourquoi 0 changement au premier lancement ?**
> Le premier check crée la référence. Les changements apparaissent à partir du second.

**Où est sauvegardé le cache ?**
> Sauvegardé automatiquement dans `%APPDATA%\ArchipelagoTracker\archipelago_cache.json` (ex: `C:\Users\Enzo\AppData\Roaming\ArchipelagoTracker\`). Ne le supprime pas, sinon tu perds la comparaison.

**Besoin d'installer Python ou quoi que ce soit ?**
> Non. Le `.exe` est autonome, tout est inclus.

**Le panneau gauche a disparu, comment le retrouver ?**
> Clique sur le bouton **▶ Changes** dans la barre de filtre pour le réafficher.

---

## 📊 Source des données

Les données proviennent du [Google Sheets communautaire Archipelago](https://docs.google.com/spreadsheets/d/1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw) maintenu par la communauté.

---

## 🗒️ Changelog

### Depuis la v1.0.2

- **Architecture** : le code a été découpé en plusieurs modules (`cache.py`, `config.py`, `data.py`, `ui/changes.py`, `ui/detail.py`, `ui/settings.py`, `ui/table.py`) pour une meilleure maintenabilité
- **Internationalisation** : support multilingue ajouté (Français 🇫🇷 / English 🇬🇧) via des fichiers YAML dans `lang/`
- **Colonne APWorld/Client** : nouvelle colonne dans le tableau avec liens directs vers les APWorlds ou clients custom des jeux
- **Intégration Steam** : détection de la bibliothèque Steam via API — colonne *Owned* et filtre associé
- **Vérification des releases GitHub** : optionnelle (configurable), affiche la dernière release de chaque jeu dans le panneau de détail
- **Fenêtre Paramètres** : nouvelle fenêtre de configuration (token GitHub, clé Steam, Steam ID(s), langue)
- **Panneau gauche rétractable** : le panneau "Derniers changements" peut être masqué/affiché via un bouton dédié
- **Redimensionnement** : la fenêtre principale est redimensionnable, le panneau gauche peut être resizé
- **Logo** : icône `logo.ico` ajoutée à l'application et à l'exécutable
- **Script de build** : `build.py` pour compiler l'exe en un clic (PyInstaller) avec choix du fichier source
- **Installeur Inno Setup** : `installer.iss` pour générer un installeur Windows (`ArchipelagoTrackerSetup.exe`), proposé automatiquement après le build

---

## Ce qui est prévu pour la suite

- Ajout de la possibilité d'annuler une update en cours de route
- Rendre la flèche de 'latest changes' utile (utilité actuelle très triviale)
- Ajout d'un historique des changements pour les 10 dernières updates
- Positionner le bouton paramètre à droite du titre et non collé au bouton update
- Rajouter les Yes, No du tableau dans les lang files
- Dans la page paramètre, faire des retours à la ligne automatiques lorsque le texte dépasse de la fenêtre
- Dans la page paramètre, faire en sorte que la case contenant les Steam IDs s'affiche en entier
- Pour la page paramètre, définir une hauteur maximale (par défaut)
- Pour la page paramètre, permettre de la resize
