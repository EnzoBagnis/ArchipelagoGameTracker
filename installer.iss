; ============================================================================
; Inno Setup Script pour Archipelago Game Tracker
; ============================================================================
; Prérequis : Installer Inno Setup depuis https://jrsoftware.org/isinfo.php
;
; Pour compiler l'installeur :
;   1. Ouvrir ce fichier dans Inno Setup Compiler
;   2. Cliquer sur "Compile" (Ctrl+F9)
;   OU en ligne de commande :
;      "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; ============================================================================

#define MyAppName "Archipelago Game Tracker"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "EnzoB"
#define MyAppExeName "main.exe"
#define MyAppURL "https://github.com/EnzoB/ArchipelagoGameTracker"

[Setup]
; Identifiant unique de l'application (ne pas changer après la première publication)
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Pas de page de sélection de dossier programme si inutile
AllowNoIcons=yes
; Dossier de sortie de l'installeur
OutputDir=dist
OutputBaseFilename=ArchipelagoTrackerSetup
; Icône de l'installeur
SetupIconFile=logo.ico
; Compression maximale
Compression=lzma2/ultra64
SolidCompression=yes
; Style moderne
WizardStyle=modern
; Privilèges : installation possible sans admin (dans AppData)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Infos de désinstallation
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
; Version minimale de Windows
MinVersion=10.0

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; L'exécutable principal
Source: "dist\main.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion

; Icône (décommenter si logo.ico existe)
; Source: "logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Désinstaller {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer {#MyAppName}"; Flags: nowait postinstall skipifsilent

