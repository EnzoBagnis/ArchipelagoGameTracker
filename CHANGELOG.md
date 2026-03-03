# Changelog — Archipelago Game Tracker

Toutes les modifications notables de ce projet sont documentées ici.

---

## [Unreleased] — en développement

### 🆕 Ajouts
- **Architecture modulaire** : le code principal a été découpé en plusieurs modules dédiés :
  - `cache.py` — gestion du cache et des paramètres
  - `config.py` — constantes globales (couleurs, URLs, statuts…)
  - `data.py` — récupération et parsing des données (Google Sheets, GitHub, PopTracker, Steam)
  - `ui/changes.py` — panneau "Derniers changements"
  - `ui/detail.py` — panneau de détail d'un jeu
  - `ui/settings.py` — fenêtre de paramètres
  - `ui/table.py` — tableau principal et barre de filtres
- **Internationalisation (i18n)** : support multilingue via des fichiers YAML (`lang/en.yaml`, `lang/fr.yaml`) et un module `lang/l18n.py`
  - Langues disponibles : 🇫🇷 Français, 🇬🇧 English
  - Changement de langue depuis les paramètres (redémarrage requis)
- **Colonne APWorld/Client** : nouvelle colonne dans le tableau affichant les liens directs vers les APWorlds ou clients custom d'un jeu
- **Intégration Steam** :
  - Connexion via clé API Steam et Steam ID(s) configurables dans les paramètres
  - Nouvelle colonne *Owned* dans le tableau indiquant les jeux possédés sur Steam
  - Filtre *Owned* pour n'afficher que les jeux possédés (ou non)
  - Support multi-comptes (famille Steam)
- **Vérification des releases GitHub** :
  - Option activable dans les paramètres
  - Récupère la dernière release GitHub de chaque jeu ayant un lien GitHub dans ses notes
  - Affiché dans le panneau de détail avec lien cliquable
  - Support du token GitHub pour dépasser la limite de 60 req/h
- **Fenêtre Paramètres** (⚙) :
  - Token GitHub + activation de la vérification des releases
  - Clé API Steam + Steam ID(s) + bouton de rafraîchissement
  - Sélection de la langue de l'interface
- **Panneau gauche rétractable** : le panneau "Derniers changements" peut être masqué/affiché via le bouton **▶ Changes** dans la barre de filtre
- **Logo** : icône `logo.ico` ajoutée à la fenêtre et à l'exécutable compilé
- **Script de build `build.py`** :
  - Compilation en `.exe` via PyInstaller en un clic
  - Sélection interactive du fichier source
  - Nettoyage automatique des anciens artefacts de build et des caches `__pycache__`
  - Inclus les dossiers `lang/`, `ui/` et `logo.ico` dans l'exécutable
- **Installeur Windows `installer.iss`** (Inno Setup) :
  - Génère `ArchipelagoTrackerSetup.exe` dans `dist/`
  - Proposé automatiquement à la fin du build (`build.py`)
  - Installation sans droits administrateur (dossier utilisateur)
  - Raccourci bureau optionnel, désinstallation propre

### 🔄 Modifications
- Interface principale remaniée : panneau gauche redimensionnable, mise en page générale améliorée
- Fenêtre principale redimensionnable (taille minimale : 1050×600)
- Le panneau de détail affiche maintenant séparément les liens APWorld/Client et les liens des notes
- `README.md` enrichi avec la documentation des paramètres, de l'installeur et du changelog

### 🐛 Corrections
- Correction du scroll dans le panneau des changements
- Correction de la normalisation des noms pour la détection PopTracker et Steam
- Correction du build pour inclure correctement les ressources de langue

---

## [1.0.2]

### 🆕 Ajouts
- Intégration PopTracker : détection automatique des packs PopTracker disponibles depuis le wiki Archipelago
- Nouveaux filtres dans la barre d'outils (statut, PopTracker)
- Panneau de détail d'un jeu avec liens cliquables dans les notes

---

## [1.0.1]

### 🔄 Modifications
- Correction de la gestion du chemin du cache
- Mise à jour de la documentation

---

## [1.0.0]

- Version initiale du projet

