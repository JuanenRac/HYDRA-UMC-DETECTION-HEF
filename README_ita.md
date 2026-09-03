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
  <img src="https://img.shields.io/badge/Fase-Funzionale%20v0-green.svg" alt="Funzionale v0">
</p>

---

## 1. 🛠️ PANORAMICA TECNICA

**HYDRA-UMC-DETECTION-HEF** è pensato per essere una libreria e toolchain curata di modelli di rete neurale ad alte prestazioni compilati nel **Hailo Executable Format (HEF)**, ottimizzati per ambienti di micro-fabbrica industriale: assemblaggio elettronico, posizionamento SMD e validazione di teste utensile.

Questo è uno dei 4 figli di **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)**, il genitore di integrazione della famiglia: questo progetto possiede solo la compilazione e il versionamento dei modelli - la copia servita in esecuzione di un modello `.hef` viene caricata ed eseguita dal genitore, proprietario dell'handle del dispositivo Hailo-8, non da questo progetto.

### Punti Chiave

* ✅ **Reale v0 - registro modelli:** `registry.py` analizza e valida per schema un registro JSON di modelli compilati, rileva voci duplicate nome+versione, trova l'ultima versione per un nome/task, e verifica i file `.hef` locali tramite checksum sha256 rispetto al registro. Esposto tramite `registry validate`/`registry latest` più sotto - non serve SDK Hailo né hardware per eseguirlo o testarlo.
* 🔒 **Reale v0 - verifica di caricamento sicuro:** `safe_load()` di `compatibility.py` verifica la compatibilità reale dell'architettura Hailo (`hailo8`/`hailo15h`/ecc. - ogni voce del registro ora dichiara il proprio chip target) prima di verificare il checksum, e non riporta mai un modello pronto per il deploy a meno che entrambi i controlli reali non passino. Esposto tramite `registry load` più sotto.
* 🌐 **Reale v0 - API JSON/HTTP:** il sottocomando `serve` di `api.py` esegue esattamente gli stessi controlli di registro/caricamento sicuro come servizio locale di lunga durata (default `127.0.0.1:8093`) tramite `GET /registry`, `GET /registry/latest`, `GET /registry/load` e `GET /stats` - registro e cartella dei modelli si configurano una sola volta all'avvio, non per ogni richiesta. Vedi [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md) per esempi reali catturati di ogni endpoint.
* 🛠️ **Rilevamento Industriale (previsto):** modelli mirati a componenti PCB, saldature e difetti meccanici.
* 📐 **Allineamento Fiduciali (previsto):** riferimenti ad alta precisione per la sincronizzazione Pick-and-Place.
* ⚡ **Prestazioni Quantizzate (previsto):** varianti INT8/INT4 mirate alle NPU Hailo-8/Hailo-10 per inferenza sub-10ms. *(lavoro futuro - richiede la vera NPU Hailo-8/Hailo-10 e il Dataflow Compiler che questo ambiente non ha.)*
* 🤖 **Stima della Posa (previsto):** rilevamento di keypoint per il tracciamento delle articolazioni del braccio robotico. *(lavoro futuro, stesso motivo.)*
* 🧩 **Perché esiste come progetto separato:** compilare e versionare modelli è un flusso di lavoro dati/ML, completamente diverso dal processo di esecuzione che li serve - mantenere la toolchain qui significa che una compilazione errata non mette mai a rischio il nodo di percezione in esecuzione, e i modelli possono essere iterati e validati offline prima di raggiungere [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

**Verifica di onestà - cosa funziona davvero oggi:** la metà reale e indipendente dall'hardware del lavoro di questo progetto - il registro di modelli (`registry.py`) e la reale verifica di caricamento sicuro (`compatibility.py`), esposti tramite `registry validate`/`registry latest`/`registry load` e, come API JSON/HTTP di lunga durata, tramite `serve` (`api.py`) - è implementata e testata (48 test). L'esportazione ONNX, la quantizzazione tramite Hailo Dataflow Compiler e il pacchettizzazione HAR/HEF che produrrebbero davvero i modelli descritti da questo registro restano lavoro futuro: richiedono vero hardware Hailo che questo ambiente non ha. Vedi [`CHANGELOG.md`](CHANGELOG.md) per ciò che è stato consegnato esattamente finora, e "Stato Attuale e Prossimi Passi" più sotto per ciò che resta aperto.

---

## 2. 🔄 FLUSSO DI COMPILAZIONE MODELLI PREVISTO

Il diagramma sotto è la toolchain di *compilazione* obiettivo verso cui viene costruito questo progetto - ancora non implementata, perché ogni passo richiede vero hardware Hailo. Il *registro* di modelli (versionamento + verifica di integrità dei `.hef` che questa pipeline produrrà un giorno) è reale oggi; vedi "Punti Chiave" sopra e le decisioni di design più sotto.

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

### Decisioni di design già prese

* **La versione viene letta dai metadati del pacchetto installato, non è hardcoded** - `main.py` chiama `importlib.metadata.version("hydra-umc-detection-hef")` invece di una seconda stringa `__version__`, così `bump_version.py` ha un solo posto da modificare.
* **L'incremento "contachilometri" tocca automaticamente solo `PATCH`/`MINOR`** - `bump_version.py` riporta `PATCH` a `MINOR` oltre il 9 e da `MINOR` a `MAJOR` oltre il 9, ma non incrementa mai `MAJOR` da solo; stessa convenzione di `HYDRA-UMC-EDITOR-URDF/bump_version.py` e `HYDRA-UMC-SUITE/bump_version.py`.
* **Un file `.hef` locale mancante non è un fallimento di checksum** - `verify_checksum()` restituisce `None` (non `False`) quando il file descritto dal registro non è presente sotto `--models-dir`, e `registry validate` lo segnala come "skipped", non come errore. Il registro è pensato per descrivere modelli che possono vivere in un object store separato, non necessariamente incluso in questo repo - solo un checksum realmente discordante per un file effettivamente presente indica un registro corrotto.
* **Perché `safe_load()` controlla l'architettura prima del checksum, non il contrario.** La compatibilità dell'architettura è pura metadata (nessun I/O); la verifica del checksum deve leggere un file reale. Controllare prima la verifica economica e fondamentale significa che un modello compilato per il chip Hailo sbagliato viene rifiutato prima ancora di toccare il filesystem, e il motivo del rifiuto nomina il controllo fondamentale che è realmente fallito invece di un fuorviante "file mancante" per un modello che comunque non sarebbe mai girato su questo hardware.
* **Perché la compatibilità dell'architettura è corrispondenza esatta, non una matrice di compatibilità.** Il Hailo Dataflow Compiler incide il chip target in un `.hef` al momento della compilazione - affermare ad esempio che un Hailo-15H può eseguire un `.hef` Hailo-8 richiederebbe una validazione incrociata tra architetture su hardware reale che questo ambiente non ha. La corrispondenza esatta è l'unica affermazione di compatibilità onestamente verificabile solo dalla metadata del registro.

---

## 📂 STRUTTURA DELLE DIRECTORY

```text
HYDRA-UMC-DETECTION-HEF/
├── src/                 # Codice sorgente (pacchetto hydra_umc_detection_hef)
│   └── hydra_umc_detection_hef/
│       ├── registry.py       # Registro modelli: validazione per schema, versionamento, checksum sha256
│       ├── compatibility.py  # Vera verifica di caricamento sicuro: compatibilità + checksum
│       ├── api.py            # Superficie JSON/HTTP semplice (http.server di stdlib) sul registro modelli
│       └── main.py           # Entry point CLI (invocazione nuda + `registry` + `serve`)
├── tests/               # Suite pytest reale (registry, compatibility, api, CLI)
├── docs/
│   └── CLI_REFERENCE.md # Riferimento completo CLI + API JSON/HTTP, ogni esempio catturato da un'esecuzione reale
├── build/               # Output di build (.venv locale + futuro output toolchain HEF)
├── images/              # Media e diagrammi
├── systemd/
│   └── hydra-umc-detection-hef.service # Unità systemd della API locale di registro modelli sulla CM5
├── tools/
│   ├── build_test.py    # Controllo build senza versionamento
│   └── ci_validate.py   # Validazione manifest/CHANGELOG/docs usata dalla CI
├── pyproject.toml       # Metadati pacchetto, dipendenze, versione contachilometri
├── bump_version.py      # Incremento versione nativa tipo contachilometri (build.sh/.bat)
├── bump_manifest_version.py # Sincronizza la versione di hydra-umc.project.json con quella nativa (--sync)
├── build.sh / build.bat # venv + installazione editabile + compile-check + test
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
3. **Installazione editabile** - `pip install -e ".[dev]"` così le modifiche sotto `src/` hanno effetto immediato, installa `pytest`, e registra l'entry point da console `hydra-umc-detection-hef`.
4. **Compile-check** - `python -m compileall -q src` compila in bytecode ogni file sotto `src/`.
5. **Suite di test reale** - `python -m pytest tests/ -q` (48 test che coprono il registro, la verifica di caricamento sicuro e il CLI).

`set -euo pipefail` ferma lo script al primo passo che fallisce; il build segnala successo solo se tutti e 5 i passi hanno successo.

```bash
./run.sh
```

Individua l'interprete dentro `.venv` ed esegue `python -m hydra_umc_detection_hef.main`, inoltrando qualsiasi argomento - l'invocazione nuda stampa nome + versione + ruolo.

Esempio reale - validare un registro e cercare l'ultima versione di un modello:

```bash
./run.sh registry validate --registry registry.json --models-dir models/
# 2 entries in registry.json
#   pcb-defect 0.1.0: pcb-defect-0.1.0.hef not present locally, skipped
#   pcb-defect 0.2.0: checksum OK
# registry OK

./run.sh registry latest --registry registry.json --name pcb-defect
# pcb-defect 0.2.0  task=detection  input_shape=(640, 640, 3)
# classes: solder_bridge, missing_component
# hef_path: pcb-defect-0.2.0.hef
# sha256: 1c8a52bb4a34927d55efc913b23f06bd08ff5eeee0aca2ccd8d2c0fd34c81497
```

Ogni voce del registro dichiara anche il proprio `hailo_arch` target (es. `hailo8`). Il vero sottocomando `registry load` combina la verifica del checksum di cui sopra con una vera verifica di compatibilità dell'architettura, e riporta un modello pronto solo se entrambe passano:

```bash
./run.sh registry load --registry registry.json --models-dir models/ --name pcb-defect --target-arch hailo8
# READY: pcb-defect 0.2.0 (hailo8) verified and ready

./run.sh registry load --registry registry.json --models-dir models/ --name pcb-defect --target-arch hailo15h
# REJECTED_ARCH_MISMATCH: model compiled for 'hailo8', this deployment targets 'hailo15h'
```

Gli stessi controlli di registro/caricamento sicuro sono raggiungibili anche come API JSON/HTTP di lunga durata tramite `./run.sh serve --registry registry.json --models-dir models/` (default `127.0.0.1:8093`). Vedi [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md) per il riferimento completo di comandi ed endpoint, con ogni esempio catturato da un'esecuzione reale.

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

**Cosa funziona oggi:** il registro di modelli - validazione per schema (inclusi metadati di architettura Hailo richiesti e validati), rilevamento versioni duplicate, ricerca dell'ultima versione, e verifica di integrità tramite sha256 (`registry.py`) - più una vera verifica combinata di caricamento sicuro che controlla compatibilità dell'architettura e integrità del checksum insieme e non riporta mai un modello pronto a meno che entrambi non passino (`compatibility.py`), gli stessi controlli esposti anche come vera API JSON/HTTP di lunga durata (`api.py`, sottocomando `serve`) accanto alla CLI a esecuzione singola, 48 test in totale, più un vero pacchetto Python installabile con un entry point verificato e un incremento di versione contachilometri integrato nel build. Vedi [`CHANGELOG.md`](CHANGELOG.md) per l'output di build/run catturato.

**Cosa resta aperto, senza ordine particolare, senza calendario impegnato, e bloccato da vero hardware Hailo:**

* La vera esportazione ONNX da modelli PyTorch/YOLO addestrati.
* L'integrazione con il Hailo Dataflow Compiler per la quantizzazione INT8/INT4.
* Il pacchettizzazione HAR/HEF che popolerebbe davvero un file di registro che il `registry.py` di questo progetto sa già leggere e validare.
* Pubblicare l'output `.hef` compilato nella cartella `models/` di [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

---

## 🔗 Progetti Correlati

Questo progetto fa parte dell'ecosistema robotico HYDRA-UMC dello stesso autore (JuanenRac / Electro Hobby 3D). Vale la pena conoscerlo, poiché una richiesta potrebbe in realtà riguardare uno di questi invece di questo repository.

**Progetto Padre**
- **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — hub di integrazione per la pipeline di visione Hailo-8, con un vero controllo di prontezza hardware per fase; il genitore di cui questo repository è una fase o un consumatore specifico, all'interno della propria pipeline di percezione.

**Progetti Fratelli** — le altre fasi/consumatori della pipeline di percezione Hailo-8 propria di HYDRA-UMC-VISION-NODE
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — generatore reale di pipeline GStreamer + config MediaMTX, con una vera barriera di integrazione HailoRT.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — vero controllo di violazione zona e richiesta E-STOP, con imposizione della freschezza di calibrazione.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — vera legge di correzione Position-Based Visual Servoing, con cancello di sicurezza sullo stato di zona a monte.

**Direttamente Correlati**
- **[URTC](https://github.com/JuanenRac/URTC)** — firmware per la scheda fisica dell'Universal Robot Tool Controller, oltre 25 profili utensile su bus CAN; il riconoscimento visivo delle proprie teste utensile di URTC si basa sui modelli compilati qui.

**Fa Anche Parte dell'Ecosistema**

*Hardware e Piattaforma di Base*
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — la scheda madre fisica del braccio robotico: host CM5 + coprocessore STM32H745 dual-core, che coordina fino a 8 bracci utensile via CAN-OTA/SPI-OTA.
- **[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS)** — livello prodotto riproducibile su Raspberry Pi OS per il CM5: agente in sola lettura, config/profili validati, provisioning WiFi al primo contatto.
- **[HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)** — il contratto JSON-Schema condiviso e la barriera di sicurezza contro cui ogni bridge valida i propri comandi.

*Backend Centrale e Client*
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — il vero backend headless (REST/WebSocket) con cui parla davvero ogni client di controllo.
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — dashboard di controllo web con visualizzazione 3D multi-robot in tempo reale.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — centro di comando sciame desktop (PySide6) per più server contemporaneamente, pacchettizzato come eseguibile standalone.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — app di controllo nativa per Android con login biometrico e un companion Wear OS abbinato.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — app di controllo per iOS/iPadOS (Flutter) con sincronizzazione WebSocket in tempo reale.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — interfaccia touch nativa per il touchscreen DSI da 7" a bordo, incorporata direttamente nel CM5.
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — creatore/editor grafico desktop di URDF che invia i modelli finiti al catalogo di STUDIO.
- **[HYDRA-UMC-BRIDGE-AMR](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-AMR)** — barriera di coordinamento per flotte AGV/AMR tramite un publisher MQTT VDA 5050 reale.
- **[HYDRA-UMC-BRIDGE-CNC](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-CNC)** — coordinatore ad alto livello per celle CNC con accesso reale a stato/byte di controllo GRBL.
- **[HYDRA-UMC-BRIDGE-DROIDS](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-DROIDS)** — barriera di coordinamento per droidi con zampe/umanoidi, con un vero mittente di comandi per Boston Dynamics Spot.
- **[HYDRA-UMC-BRIDGE-LASER](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-LASER)** — coordinatore di sicurezza per celle laser che legge 3 salvaguardie GPIO reali di chiave/involucro/interblocco.
- **[HYDRA-UMC-BRIDGE-OPENPNP](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-OPENPNP)** — coordinatore ad alto livello sicuro per il flusso schede del pick-and-place OpenPnP.
- **[HYDRA-UMC-BRIDGE-PRINTER3D](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-PRINTER3D)** — barriera di coordinamento sicura per stampanti 3D Moonraker/Klipper, con comandi di lavoro reali e controllati.
- **[HYDRA-UMC-BRIDGE-ROS2](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-ROS2)** — coordinatore di sicurezza con un vero trasporto ROS 2 rclpy, importato in modo lazy.
- **[HYDRA-UMC-BRIDGE-UAV](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-UAV)** — barriera di coordinamento per UAV dotati di fotocamera, con un vero mittente di comandi MAVLink.

*Piattaforma Strumenti URTC*
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — strumento desktop con GUI per il flashing delle schede URTC, CAN-OTA più SWD/JTAG a chip intero.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — strumento desktop di diagnostica CAN-bus dal vivo per schede URTC, un pannello per profilo utensile.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — alternativa basata su browser a URTC-TESTER tramite la Web Serial API, senza installazione locale.

*Nodo IA Cognitivo (Hailo-10)*
- **[HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)** — hub di integrazione per la pipeline cognitiva Hailo-10 (orchestrazione LLM/VLA/voce).
- **[HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)** — vera codifica/decodifica di token d'azione e generazione di traiettoria per un modello Vision-Language-Action.
- **[HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)** — vero front-end vocale (VAD + parser di intenti) con un relay verso Watch limitato e soggetto a conferma.
- **[HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)** — vera scomposizione dei task basata su regole e recupero semantico degli errori sui codici errore MCU.
- **[HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)** — vera ricerca documentale TF-IDF (solo libreria standard) sui documenti Markdown di questo ecosistema.

*Orchestrazione e Sciame*
- **[HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)** — hub di integrazione con un vero contratto di health-report gRPC/Protobuf e una macchina a stati di missione.
- **[HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)** — vera coda di lavori basata su priorità con deduplicazione, su una vera API HTTP.
- **[HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)** — vero watchdog di salute della flotta basato su gRPC, con retry/backoff e rilevamento di discrepanza d'identità.
- **[HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)** — vero pianificatore di percorsi 3D basato su RRT, con vera validazione delle collisioni ostacolo/spazio di lavoro.
- **[HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)** — vera sincronizzazione di stato CRDT LWW-Element-Map, con property test per la convergenza multi-cella.

*Gemello Digitale e Simulazione*
- **[HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)** — hub di integrazione per il motore di gemello digitale, con un vero contratto di sincronizzazione per compatibilità di versione.
- **[HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)** — vero interblocco di sicurezza hardware-in-the-loop che instrada i comandi tra simulazione e hardware reale.
- **[HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)** — vera cinematica diretta e validazione dei limiti articolari su un vero sottoinsieme URDF.
- **[HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)** — vero generatore procedurale di scene 2D con esportazione di annotazioni YOLO/COCO.

*Dati e Analisi*
- **[HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)** — vero archivio di serie temporali basato su sqlite3, con una vera API HTTP di ingestione/query.
- **[HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)** — vero rilevatore di anomalie FFT + baseline statistica, con monitoraggio della deriva.
- **[HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)** — vero calcolo OEE/disponibilità sullo storico di DATALAKE, con esportazione CSV riproducibile.
- **[HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)** — vera pipeline di ingestione CAN/WebSocket verso DATALAKE, con deduplicazione per sequenza.

*Gateway Industriale*
- **[HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)** — hub di integrazione che inoltra ai protocolli industriali, con un vero livello di allowlist dei comandi/backpressure.
- **[HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)** — vero spazio di indirizzi OPC-UA, verificato con una vera sessione client del protocollo binario.
- **[HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)** — vero broker MQTT con autenticazione opzionale per client e ACL sui topic.
- **[HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)** — veri endpoint XML `/probe` e `/current` di MTConnect, con output in modalità degradata.

*Strumenti Complementari e Operazioni dell'Ecosistema*
- **[HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)** — pannelli Smart Summaries e Anomaly Highlighting su DATALAKE/ANOMALY-DETECTOR, con un fallback statistico onesto.
- **[HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)** — CLI di flotta con un vero e stabile contratto di exit-code, un client live reale della stessa API di HYDRA-UMC-SERVER.
- **[HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)** — app companion WearOS con avvisi aptici reali e un relay vocale verso il telefono abbinato.
- **[URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)** — firmware per un rack di montaggio schede con decodifica reale dell'ID utensile e logica di preriscaldamento Smart Idle.
- **[URTC-VISION-TOOL](https://github.com/JuanenRac/URTC-VISION-TOOL)** — firmware più un vero companion di visione Python per una testa utensile di ispezione termica/RGB.
- **[HYDRA-UMC-UPDATER](https://github.com/JuanenRac/HYDRA-UMC-UPDATER)** — strumento amministrativo desktop che scopre, clona e aggiorna ogni repository di questo ecosistema.

---

## 📚 Documentazione e Comunità

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — stack tecnologico e linee guida di codifica per una pull request.
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** — gli standard di comportamento attesi in questa comunità.
- **[SECURITY.md](SECURITY.md)** — come segnalare una vulnerabilità, e le reali aree di attenzione sulla sicurezza di questo progetto.
- **[SUPPORT.md](SUPPORT.md)** — dove porre domande e segnalare bug.
- **[LICENSE.md](LICENSE.md)** — la licenza propria di questo progetto.

## 👤 AUTORE
**JuanenRac** (Electro Hobby 3D)
📧 electrohobby3d@gmail.com
📺 [youtube.com/@electrohobby3d](https://youtube.com/@electrohobby3d)

## 📜 LICENZA
GPL-3.0 - Vedi il file LICENSE per i dettagli.
