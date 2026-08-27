<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-DETECTION-HEF banner" width="100%">
</p>

# 🎯 HYDRA-UMC-DETECTION-HEF

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | 🇫🇷 <b>Français</b> | <a href="README_ita.md">🇮🇹 Italiano</a> | <a href="README_deu.md">🇩🇪 Deutsch</a> | <a href="README_zho.md">🇨🇳 简体中文</a> | <a href="README_jpn.md">🇯🇵 日本語</a></p>

### 📦 Bibliothèque Industrielle de Modèles Accélérés par Matériel (Hailo-8 / Hailo-10)

<p align="left">
  <img src="https://img.shields.io/badge/Licence-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Format-HEF-FF6F00.svg" alt="HEF">
  <img src="https://img.shields.io/badge/Mod%C3%A8les-YOLOv8%20%2F%20YOLOv10-00A4EF.svg" alt="YOLO">
  <img src="https://img.shields.io/badge/%C3%89tape-Squelette-lightgrey.svg" alt="Étape squelette">
</p>

---

## 1. 🛠️ VUE D'ENSEMBLE TECHNIQUE

**HYDRA-UMC-DETECTION-HEF** est destiné à être une bibliothèque et une chaîne d'outils organisées de modèles de réseaux de neurones haute performance compilés au format **Hailo Executable Format (HEF)**, ajustés pour les environnements de micro-usine industrielle : assemblage électronique, placement SMD et validation de têtes d'outil.

C'est l'un des 4 enfants de **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)**, le parent d'intégration de la famille : ce projet ne possède que la compilation et le versionnement des modèles - la copie servie en exécution d'un modèle `.hef` est chargée et exécutée par le parent, propriétaire du handle du périphérique Hailo-8, pas par ce projet.

### Points Clés

* 🛠️ **Détection industrielle (prévu) :** modèles ciblant les composants PCB, les soudures et les défauts mécaniques.
* 📐 **Alignement de fiduciaux (prévu) :** repères de haute précision pour la synchronisation Pick-and-Place.
* ⚡ **Performance quantifiée (prévu) :** variantes INT8/INT4 ciblant les NPU Hailo-8/Hailo-10 pour une inférence sub-10ms.
* 🤖 **Estimation de pose (prévu) :** détection de points clés pour le suivi des articulations du bras robotique.
* 🧩 **Pourquoi c'est un projet séparé :** compiler et versionner des modèles est un flux de travail data/ML, entièrement différent du processus d'exécution qui les sert - garder la chaîne d'outils ici signifie qu'une mauvaise compilation ne met jamais en danger le nœud de perception en cours d'exécution, et les modèles peuvent être itérés et validés hors ligne avant d'atteindre [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

**Vérification d'honnêteté - ce qui fonctionne réellement aujourd'hui :** ce dépôt est à l'étape squelette. Le point d'entrée réel (`src/hydra_umc_detection_hef/main.py`) affiche le nom du projet, sa version installée et une description de rôle en une ligne, puis se termine avec le code 0. Rien de l'export ONNX, de la quantification via le Hailo Dataflow Compiler, de l'empaquetage HAR/HEF ou du registre/versionnement de modèles décrit ci-dessus n'existe encore dans le code. Voir [`CHANGELOG.md`](CHANGELOG.md) pour ce qui a été livré exactement jusqu'à présent, et « État Actuel et Prochaines Étapes » ci-dessous pour ce qui reste ouvert.

---

## 2. 🔄 FLUX DE COMPILATION DE MODÈLES PRÉVU

Le diagramme ci-dessous est la chaîne d'outils cible vers laquelle ce squelette est construit, pas un pipeline fonctionnel aujourd'hui.

```mermaid
flowchart LR
    TRAIN["Entraînement (PyTorch/YOLO)"] --> ONNX["Export vers ONNX"]
    ONNX --> DFC["Hailo Dataflow Compiler"]
    DFC --> HAR["Quantification (HAR)"]
    HAR --> HEF["Binaire HEF"]
    HEF --> NODE["HYDRA-UMC-VISION-NODE"]
```

---

## 3. 🧠 INFORMATIONS TECHNIQUES AVANCÉES

### Pourquoi il n'y a pas de `hardware/`/`firmware/` ici, et pourquoi `os/`/`models/` restent dans le parent

Ce projet livre des fichiers de modèles et l'outillage qui les compile, pas un périphérique physique - donc, comme le reste de la famille Vision AI Node, il ne porte pas de dossier `hardware/`/`firmware/`. Il ne porte pas non plus `os/` ni `models/`, même si les `.hef` sont littéralement *produits* ici : la copie *servie en exécution* chargée sur le NPU Hailo-8 à l'exécution ne vit que dans le parent d'intégration, [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE), car c'est le processus propriétaire du handle du périphérique Hailo-8. Le `build/` propre de ce projet est l'endroit où la sortie compilée de la chaîne d'outils est censée atterrir avant d'être publiée là-bas.

### Le flux de compilation est la décision de conception, avant le code

Le diagramme ci-dessus fixe déjà la forme prévue du pipeline : l'entraînement PyTorch/YOLO se passe ailleurs (hors périmètre de ce dépôt), les modèles sont exportés vers ONNX, passent par le Hailo Dataflow Compiler pour une quantification INT8/INT4 (produisant un `.har`), et sont enfin empaquetés en un binaire `.hef` consommé par [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE). Décider et documenter cette forme maintenant, avant d'écrire le code de la chaîne d'outils, évite à l'implémentation finale d'avoir à improviser plus tard l'histoire du registre/versionnement des modèles.

### Décisions de conception déjà prises dans ce squelette

* **La version est lue depuis les métadonnées du paquet installé, pas codée en dur** - `main.py` appelle `importlib.metadata.version("hydra-umc-detection-hef")` plutôt qu'une seconde chaîne `__version__`, donc `bump_version.py` n'a qu'un seul endroit à modifier.
* **L'incrément « compteur kilométrique » ne touche automatiquement que `PATCH`/`MINOR`** - `bump_version.py` reporte `PATCH` vers `MINOR` au-delà de 9 et `MINOR` vers `MAJOR` au-delà de 9, mais n'incrémente jamais `MAJOR` lui-même ; même convention que `HYDRA-UMC-EDITOR-URDF/bump_version.py` et `HYDRA-UMC-SUITE/bump_version.py`.

---

## 📂 STRUCTURE DES RÉPERTOIRES

```text
HYDRA-UMC-DETECTION-HEF/
├── src/                 # Code source (paquet hydra_umc_detection_hef)
├── docs/                # Documentation et rapports de validation
├── build/               # Sortie de build (.venv local + future sortie de la chaîne HEF)
├── images/              # Médias et diagrammes
├── scripts/             # Scripts utilitaires
├── pyproject.toml       # Métadonnées du paquet, dépendances, version compteur kilométrique
├── bump_version.py      # Incrément de version type compteur kilométrique (build.sh/.bat)
├── build.sh / build.bat # venv + installation éditable + compile-check
├── run.sh / run.bat     # Exécute le point d'entrée depuis le venv local
└── CHANGELOG.md         # Historique version par version (schéma compteur kilométrique, sans dates)
```

Aucun dossier `hardware/`, `firmware/`, `os/` ni `models/` - voir « Informations Techniques Avancées » ci-dessus pour le pourquoi. `os/` et `models/` ne vivent que dans le parent d'intégration, [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) ; le `build/` propre de ce projet est où atterrit la sortie de sa chaîne d'outils HEF avant d'être publiée là-bas.

---

## 🏗️ BUILD ET EXÉCUTION

### Prérequis

* **Python 3.10 ou plus récent** sur le `PATH` (les scripts essaient `python3` puis se replient sur `python`).
* Aucun outillage ONNX/Hailo Dataflow Compiler n'est requis pour l'instant - **zéro dépendance tierce à l'exécution** à ce stade (`dependencies = []` dans `pyproject.toml`).
* Quelques dizaines de Mo d'espace disque pour un environnement virtuel local sous `.venv/`.

### Étape par étape

```bash
# Linux / macOS
./build.sh
```

1. **Incrément de version compteur kilométrique** - exécute `bump_version.py`, incrémentant `PATCH` dans `pyproject.toml` à chaque build.
2. **Environnement virtuel** - crée `.venv/` s'il manque ; le réutilise sinon.
3. **Installation éditable** - `pip install -e .` pour que les modifications sous `src/` prennent effet immédiatement, et enregistre le point d'entrée console `hydra-umc-detection-hef`.
4. **Compile-check** - `python -m compileall -q src` compile en bytecode chaque fichier sous `src/`.

`set -euo pipefail` arrête le script à la première étape en échec ; `== Build OK ==` ne s'affiche que si les 4 étapes réussissent.

```bash
./run.sh
```

Localise l'interpréteur dans `.venv` et exécute `python -m hydra_umc_detection_hef.main`, affichant nom + version + rôle.

```bat
:: Windows - mêmes étapes, syntaxe batch
build.bat
run.bat
```

### Dépannage

* **`python`/`python3` introuvable** - installez Python 3.10+ et assurez-vous qu'il est sur le `PATH`.
* **`compileall` échoue** - une vraie erreur de syntaxe a été introduite sous `src/` ; le build s'arrête sans toucher à l'installation, volontairement.
* **« No `.venv` found » depuis `run.sh`/`run.bat`** - exécutez `build.sh`/`build.bat` au moins une fois avant.
* **Installation éditable obsolète** - supprimez `.venv/` et reconstruisez ; rarement nécessaire.

---

## 🚀 État Actuel et Prochaines Étapes

**Ce qui fonctionne aujourd'hui :** un vrai paquet Python installable avec un point d'entrée vérifié (voir [`CHANGELOG.md`](CHANGELOG.md) pour la sortie de build/run capturée) et un incrément de version compteur kilométrique intégré au build.

**Ce qui reste ouvert, sans ordre particulier et sans calendrier engagé :**

* L'export ONNX réel depuis des modèles PyTorch/YOLO entraînés.
* L'intégration du Hailo Dataflow Compiler pour la quantification INT8/INT4.
* L'empaquetage HAR/HEF et un registre de modèles versionné.
* La publication de la sortie `.hef` compilée dans le dossier `models/` de [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

---

## 🔗 Projets Liés

Ce projet fait partie d'un écosystème robotique plus large du même auteur (JuanenRac / Electro Hobby 3D), couvrant firmware, logiciel de contrôle, nœuds d'IA et outillage de flotte. Bon à savoir, car une demande pourrait en réalité concerner l'un de ces projets plutôt que ce dépôt.

### Famille

**Parent :** **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — le parent d'intégration qui charge ces modèles HEF sur son NPU Hailo-8.

**Frères et sœurs :**
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — capture et pré-traite les flux caméra consommés par le parent.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — transforme la perception du parent (avec des modèles compilés ici) en détection d'intrusion et déclenchement d'E-STOP.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — transforme la perception du parent en corrections cinématiques de pose.

### Relation Directe (hors de la famille)

- **[URTC](https://github.com/JuanenRac/URTC)** — la reconnaissance visuelle des propres têtes d'outil d'URTC repose sur des modèles compilés ici.

### Reste de l'Écosystème

**Plateforme HYDRA-UMC** — la cellule de micro-usine multi-robot
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — la carte mère CM5 + STM32H745 orchestrant jusqu'à 8 bras robotiques.
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — le backend Express/WebSocket auquel parle chaque client de contrôle.
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — tableau de bord de contrôle web, visualisation 3D multi-robot.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — application de contrôle Android via Wi-Fi/Bluetooth.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — application de contrôle iOS/iPadOS construite en Flutter.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — centre de commande d'essaim de bureau (Python/PySide6).
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — éditeur de modèles URDF de bureau pour le catalogue de robots.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — interface tactile native pour l'écran DSI embarqué.

**Plateforme URTC** — le contrôleur de tête d'outil que porte chaque bras HYDRA-UMC
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — outil de bureau de flashage CAN-OTA + SWD/JTAG.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — outil de bureau de diagnostic CAN en direct.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — alternative basée navigateur via l'API Web Serial.

**🧠 Cognitive AI Node (Hailo-10)**
- [HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)
- [HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)
- [HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)
- [HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)
- [HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)

**🐝 Orchestration & Swarm**
- [HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)
- [HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)
- [HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)
- [HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)
- [HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)

**🎮 Digital Twin & Simulation**
- [HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)
- [HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)
- [HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)
- [HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)

**📊 Data & Analytics**
- [HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)
- [HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)
- [HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)
- [HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)

**🏭 Industrial Gateway**
- [HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)
- [HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)
- [HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)
- [HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)

**🛠️ Complementary Tools**
- [URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)
- [URTC-VISION-TOOL](https://github.com/JuanenRac/URTC-VISION-TOOL)
- [HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)
- [HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)
- [HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)

---

## 👤 AUTEUR
**JuanenRac** (Electro Hobby 3D)
📧 electrohobby3d@gmail.com

## 📜 LICENCE
GPL-3.0 - Voir le fichier LICENSE pour les détails.

## Projets associés

> Canonical public ecosystem relationship map.

**Direct integrations:**
[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS) · [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) · [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) · [URTC](https://github.com/JuanenRac/URTC) · [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) · [HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER) · [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)

**Platform and contracts:**
[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS) · [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)

**Rest of the ecosystem:**
All remaining public repositories are grouped by the seven ecosystem layers in the [JuanenRac ecosystem dashboard](https://juanenrac.github.io/JuanenRac/).
