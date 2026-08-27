<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-DETECTION-HEF banner" width="100%">
</p>

# 🎯 HYDRA-UMC-DETECTION-HEF

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | 🇮🇹 <b>Italiano</b> | <a href="README_deu.md">🇩🇪 Deutsch</a> | <a href="README_zho.md">🇨🇳 简体中文</a> | <a href="README_jpn.md">🇯🇵 日本語</a></p>

### 📦 Libreria Industriale di Modelli Accelerati via Hardware (Hailo-8 / Hailo-10)

<p align="left">
  <img src="https://img.shields.io/badge/Licenza-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Formato-HEF-FF6F00.svg" alt="HEF">
  <img src="https://img.shields.io/badge/Modelli-YOLOv8%20%2F%20YOLOv10-00A4EF.svg" alt="YOLO">
  <img src="https://img.shields.io/badge/Fase-Scheletro-lightgrey.svg" alt="Fase scheletro">
</p>

---

## 1. 🛠️ PANORAMICA TECNICA

**HYDRA-UMC-DETECTION-HEF** è pensato per essere una libreria e toolchain curata di modelli di rete neurale ad alte prestazioni compilati nel **Hailo Executable Format (HEF)**, ottimizzati per ambienti di micro-fabbrica industriale: assemblaggio elettronico, posizionamento SMD e validazione di teste utensile.

Questo è uno dei 4 figli di **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)**, il genitore di integrazione della famiglia: questo progetto possiede solo la compilazione e il versionamento dei modelli - la copia servita in esecuzione di un modello `.hef` viene caricata ed eseguita dal genitore, proprietario dell'handle del dispositivo Hailo-8, non da questo progetto.

### Punti Chiave

* 🛠️ **Rilevamento Industriale (previsto):** modelli mirati a componenti PCB, saldature e difetti meccanici.
* 📐 **Allineamento Fiduciali (previsto):** riferimenti ad alta precisione per la sincronizzazione Pick-and-Place.
* ⚡ **Prestazioni Quantizzate (previsto):** varianti INT8/INT4 mirate alle NPU Hailo-8/Hailo-10 per inferenza sub-10ms.
* 🤖 **Stima della Posa (previsto):** rilevamento di keypoint per il tracciamento delle articolazioni del braccio robotico.
* 🧩 **Perché esiste come progetto separato:** compilare e versionare modelli è un flusso di lavoro dati/ML, completamente diverso dal processo di esecuzione che li serve - mantenere la toolchain qui significa che una compilazione errata non mette mai a rischio il nodo di percezione in esecuzione, e i modelli possono essere iterati e validati offline prima di raggiungere [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

**Verifica di onestà - cosa funziona davvero oggi:** questo repository è in fase scheletro. L'entry point reale (`src/hydra_umc_detection_hef/main.py`) stampa il nome del progetto, la sua versione installata e una descrizione di ruolo di una riga, quindi esce con codice 0. Nulla dell'esportazione ONNX, della quantizzazione tramite Hailo Dataflow Compiler, del pacchettizzazione HAR/HEF o del registro/versionamento modelli descritto sopra esiste ancora nel codice. Vedi [`CHANGELOG.md`](CHANGELOG.md) per ciò che è stato consegnato esattamente finora, e "Stato Attuale e Prossimi Passi" più sotto per ciò che resta aperto.

---

## 2. 🔄 FLUSSO DI COMPILAZIONE MODELLI PREVISTO

Il diagramma sotto è la toolchain obiettivo verso cui viene costruito questo scheletro, non una pipeline funzionante oggi.

```mermaid
flowchart LR
    TRAIN["Addestramento (PyTorch/YOLO)"] --> ONNX["Esporta in ONNX"]
    ONNX --> DFC["Hailo Dataflow Compiler"]
    DFC --> HAR["Quantizzazione (HAR)"]
    HAR --> HEF["Binario HEF"]
    HEF --> NODE["HYDRA-UMC-VISION-NODE"]
```

---

## 3. 🧠 INFORMAZIONI TECNICHE AVANZATE

### Perché non ci sono `hardware/`/`firmware/` qui, e perché `os/`/`models/` restano nel genitore

Questo progetto distribuisce file di modello e gli strumenti che li compilano, non un dispositivo fisico - quindi, come il resto della famiglia Vision AI Node, non porta cartelle `hardware/`/`firmware/`. Non porta nemmeno `os/` o `models/`, anche se i `.hef` vengono letteralmente *prodotti* qui: la copia *servita in esecuzione* caricata sulla NPU Hailo-8 a runtime vive solo nel genitore di integrazione, [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE), perché è il processo proprietario dell'handle del dispositivo Hailo-8. Il proprio `build/` di questo progetto è dove è previsto che atterri l'output compilato della toolchain prima di essere pubblicato lì.

### Il flusso di compilazione è la decisione di design, prima del codice

Il diagramma sopra fissa già la forma prevista della pipeline: l'addestramento PyTorch/YOLO avviene altrove (fuori dall'ambito di questo repository), i modelli vengono esportati in ONNX, passano per il Hailo Dataflow Compiler per la quantizzazione INT8/INT4 (producendo un `.har`), e infine impacchettati come binario `.hef` consumato da [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE). Decidere e documentare questa forma ora, prima di scrivere il codice della toolchain, evita che l'implementazione finale debba improvvisare più avanti la storia del registro/versionamento dei modelli.

### Decisioni di design già prese in questo scheletro

* **La versione viene letta dai metadati del pacchetto installato, non è hardcoded** - `main.py` chiama `importlib.metadata.version("hydra-umc-detection-hef")` invece di una seconda stringa `__version__`, così `bump_version.py` ha un solo posto da modificare.
* **L'incremento "contachilometri" tocca automaticamente solo `PATCH`/`MINOR`** - `bump_version.py` riporta `PATCH` a `MINOR` oltre il 9 e da `MINOR` a `MAJOR` oltre il 9, ma non incrementa mai `MAJOR` da solo; stessa convenzione di `HYDRA-UMC-EDITOR-URDF/bump_version.py` e `HYDRA-UMC-SUITE/bump_version.py`.

---

## 📂 STRUTTURA DELLE DIRECTORY

```text
HYDRA-UMC-DETECTION-HEF/
├── src/                 # Codice sorgente (pacchetto hydra_umc_detection_hef)
├── docs/                # Documentazione e report di validazione
├── build/               # Output di build (.venv locale + futuro output toolchain HEF)
├── images/              # Media e diagrammi
├── scripts/             # Script di utilità
├── pyproject.toml       # Metadati pacchetto, dipendenze, versione contachilometri
├── bump_version.py      # Incremento versione tipo contachilometri (build.sh/.bat)
├── build.sh / build.bat # venv + installazione editabile + compile-check
├── run.sh / run.bat     # Esegue l'entry point dal venv locale
└── CHANGELOG.md         # Storico versione per versione (schema contachilometri, senza date)
```

Nessuna cartella `hardware/`, `firmware/`, `os/` o `models/` - vedi "Informazioni Tecniche Avanzate" sopra per il perché. `os/` e `models/` vivono solo nel genitore di integrazione, [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE); il proprio `build/` di questo progetto è dove atterra l'output della sua toolchain HEF prima di essere pubblicato lì.

---

## 🏗️ BUILD ED ESECUZIONE

### Prerequisiti

* **Python 3.10 o superiore** nel `PATH` (gli script provano `python3` poi ripiegano su `python`).
* Non serve ancora ONNX né il Hailo Dataflow Compiler - **zero dipendenze di terze parti a runtime** in questa fase (`dependencies = []` in `pyproject.toml`).
* Poche decine di MB di spazio su disco per un ambiente virtuale locale sotto `.venv/`.

### Passo dopo passo

```bash
# Linux / macOS
./build.sh
```

1. **Incremento versione contachilometri** - esegue `bump_version.py`, incrementando `PATCH` in `pyproject.toml` a ogni build.
2. **Ambiente virtuale** - crea `.venv/` se manca; lo riutilizza altrimenti.
3. **Installazione editabile** - `pip install -e .` così le modifiche sotto `src/` hanno effetto immediato, e registra l'entry point da console `hydra-umc-detection-hef`.
4. **Compile-check** - `python -m compileall -q src` compila in bytecode ogni file sotto `src/`.

`set -euo pipefail` ferma lo script al primo passo che fallisce; `== Build OK ==` viene stampato solo se tutti e 4 i passi hanno successo.

```bash
./run.sh
```

Individua l'interprete dentro `.venv` ed esegue `python -m hydra_umc_detection_hef.main`, stampando nome + versione + ruolo.

```bat
:: Windows - stessi passi, sintassi batch
build.bat
run.bat
```

### Risoluzione dei problemi

* **`python`/`python3` non trovato** - installa Python 3.10+ e assicurati che sia nel `PATH`.
* **`compileall` fallisce** - è stato introdotto un vero errore di sintassi sotto `src/`; il build si ferma senza toccare l'installazione, di proposito.
* **"No `.venv` found" da `run.sh`/`run.bat`** - esegui `build.sh`/`build.bat` almeno una volta prima.
* **Installazione editabile obsoleta** - elimina `.venv/` e ricostruisci; raramente necessario.

---

## 🚀 Stato Attuale e Prossimi Passi

**Cosa funziona oggi:** un vero pacchetto Python installabile con un entry point verificato (vedi [`CHANGELOG.md`](CHANGELOG.md) per l'output di build/run catturato) e un incremento di versione contachilometri integrato nel build.

**Cosa resta aperto, senza ordine particolare e senza calendario impegnato:**

* La vera esportazione ONNX da modelli PyTorch/YOLO addestrati.
* L'integrazione con il Hailo Dataflow Compiler per la quantizzazione INT8/INT4.
* Il pacchettizzazione HAR/HEF e un registro di modelli versionato.
* Pubblicare l'output `.hef` compilato nella cartella `models/` di [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

---

## 🔗 Progetti Correlati

Questo progetto fa parte di un ecosistema robotico più ampio dello stesso autore (JuanenRac / Electro Hobby 3D), che copre firmware, software di controllo, nodi IA e strumenti per flotte. Utile saperlo, perché una richiesta potrebbe in realtà riguardare uno di questi progetti anziché questo repository.

### Famiglia

**Genitore:** **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — il genitore di integrazione che carica questi modelli HEF sulla sua NPU Hailo-8.

**Fratelli:**
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — cattura e pre-elabora i flussi camera consumati dal genitore.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — trasforma la percezione del genitore (usando modelli compilati qui) in rilevamento intrusioni e attivazione E-STOP.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — trasforma la percezione del genitore in correzioni cinematiche di posa.

### Relazione Diretta (fuori dalla famiglia)

- **[URTC](https://github.com/JuanenRac/URTC)** — il riconoscimento visivo delle proprie teste utensile di URTC dipende da modelli compilati qui.

### Resto dell'Ecosistema

**Piattaforma HYDRA-UMC** — la cella di micro-fabbrica multi-robot
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — la scheda madre CM5 + STM32H745 che orchestra fino a 8 bracci robotici.
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — il backend Express/WebSocket con cui parla ogni client di controllo.
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — dashboard di controllo web, visualizzazione 3D multi-robot.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — app di controllo Android via Wi-Fi/Bluetooth.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — app di controllo iOS/iPadOS costruita in Flutter.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — centro di comando sciame desktop (Python/PySide6).
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — editor desktop di modelli URDF per il catalogo robot.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — interfaccia touch nativa per lo schermo DSI a bordo.

**Piattaforma URTC** — il controller della testa utensile che ogni braccio HYDRA-UMC porta con sé
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — strumento desktop di flashing CAN-OTA + SWD/JTAG.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — strumento desktop di diagnostica CAN live.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — alternativa basata su browser via Web Serial API.

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

## 👤 AUTORE
**JuanenRac** (Electro Hobby 3D)
📧 electrohobby3d@gmail.com

## 📜 LICENZA
GPL-3.0 - Vedi il file LICENSE per i dettagli.

## Progetti correlati

> Canonical public ecosystem relationship map.

**Direct integrations:**
[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS) · [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK) · [HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER) · [URTC](https://github.com/JuanenRac/URTC) · [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) · [HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER) · [HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)

**Platform and contracts:**
[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS) · [HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)

**Rest of the ecosystem:**
All remaining public repositories are grouped by the seven ecosystem layers in the [JuanenRac ecosystem dashboard](https://juanenrac.github.io/JuanenRac/).
