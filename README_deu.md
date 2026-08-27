<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-DETECTION-HEF banner" width="100%">
</p>

# 🎯 HYDRA-UMC-DETECTION-HEF

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | <a href="README_ita.md">🇮🇹 Italiano</a> | 🇩🇪 <b>Deutsch</b> | <a href="README_zho.md">🇨🇳 简体中文</a> | <a href="README_jpn.md">🇯🇵 日本語</a></p>

### 📦 Hardwarebeschleunigte Industrielle Modellbibliothek (Hailo-8 / Hailo-10)

<p align="left">
  <img src="https://img.shields.io/badge/Lizenz-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Format-HEF-FF6F00.svg" alt="HEF">
  <img src="https://img.shields.io/badge/Modelle-YOLOv8%20%2F%20YOLOv10-00A4EF.svg" alt="YOLO">
  <img src="https://img.shields.io/badge/Stufe-Skelett-lightgrey.svg" alt="Skelettstufe">
</p>

---

## 1. 🛠️ TECHNISCHER ÜBERBLICK

**HYDRA-UMC-DETECTION-HEF** soll eine kuratierte Bibliothek und Toolchain für leistungsstarke neuronale Netzwerkmodelle werden, kompiliert in das **Hailo Executable Format (HEF)**, abgestimmt auf industrielle Mikrofabrik-Umgebungen: Elektronikmontage, SMD-Bestückung und Werkzeugkopf-Validierung.

Dies ist eines der 4 Kind-Projekte von **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)**, dem Integrations-Elternteil der Familie: Dieses Projekt besitzt nur Modellkompilierung und -versionierung - die ausgelieferte, laufende Kopie eines `.hef`-Modells wird vom Elternteil geladen und ausgeführt, dem das Hailo-8-Gerätehandle gehört, nicht von diesem Projekt.

### Kernpunkte

* 🛠️ **Industrielle Erkennung (geplant):** Modelle für PCB-Komponenten, Lötstellen und mechanische Defekte.
* 📐 **Passermarken-Ausrichtung (geplant):** hochpräzise Anker für die Pick-and-Place-Synchronisation.
* ⚡ **Quantisierte Leistung (geplant):** INT8/INT4-Varianten für die Hailo-8/Hailo-10-NPUs für Inferenz unter 10ms.
* 🤖 **Posenschätzung (geplant):** Keypoint-Erkennung für die Nachverfolgung von Roboterarm-Gelenken.
* 🧩 **Warum als eigenes Projekt:** Kompilieren und Versionieren von Modellen ist ein Daten-/ML-Workflow, völlig anders als der Laufzeitprozess, der sie bedient - die Toolchain hier zu halten bedeutet, dass eine fehlgeschlagene Kompilierung nie den laufenden Wahrnehmungsknoten gefährdet, und Modelle können offline iteriert und validiert werden, bevor sie [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) erreichen.

**Ehrlichkeitscheck - was heute wirklich läuft:** Dieses Repository befindet sich in der Skelettphase. Der reale Einstiegspunkt (`src/hydra_umc_detection_hef/main.py`) gibt den Projektnamen, seine installierte Version und eine einzeilige Rollenbeschreibung aus und beendet sich mit Code 0. Nichts vom ONNX-Export, der Quantisierung über den Hailo Dataflow Compiler, der HAR/HEF-Paketierung oder der oben beschriebenen Modellregister-/Versionierungslogik existiert bereits im Code. Siehe [`CHANGELOG.md`](CHANGELOG.md) für genau das, was bisher geliefert wurde, und "Aktueller Status & Nächste Schritte" unten für das, was noch offen ist.

---

## 2. 🔄 GEPLANTER MODELLKOMPILIERUNGS-ABLAUF

Das Diagramm unten ist die Ziel-Toolchain, auf die dieses Skelett hinarbeitet, keine heute lauffähige Pipeline.

```mermaid
flowchart LR
    TRAIN["Training (PyTorch/YOLO)"] --> ONNX["Export nach ONNX"]
    ONNX --> DFC["Hailo Dataflow Compiler"]
    DFC --> HAR["Quantisierung (HAR)"]
    HAR --> HEF["HEF-Binärdatei"]
    HEF --> NODE["HYDRA-UMC-VISION-NODE"]
```

---

## 3. 🧠 ERWEITERTE TECHNISCHE INFORMATIONEN

### Warum es hier kein `hardware/`/`firmware/` gibt und `os/`/`models/` im Elternteil bleiben

Dieses Projekt liefert Modelldateien und die Werkzeuge, die sie kompilieren, kein physisches Gerät - daher trägt es, wie der Rest der Vision-AI-Node-Familie, keinen `hardware/`/`firmware/`-Ordner. Es trägt auch kein `os/` oder `models/`, obwohl `.hef`-Dateien hier buchstäblich *erzeugt* werden: Die *ausgelieferte, laufende* Kopie, die zur Laufzeit auf die Hailo-8-NPU geladen wird, lebt nur im Integrations-Elternteil, [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE), da dieser der Prozess ist, dem das Hailo-8-Gerätehandle gehört. Das eigene `build/` dieses Projekts ist der Ort, an dem kompilierte Toolchain-Ausgaben landen sollen, bevor sie dort veröffentlicht werden.

### Der Kompilierungsablauf ist die Designentscheidung, vor dem Code

Das obige Diagramm legt die geplante Pipeline-Form bereits fest: PyTorch/YOLO-Training findet anderswo statt (außerhalb des Umfangs dieses Repositorys), Modelle werden nach ONNX exportiert, durchlaufen den Hailo Dataflow Compiler für INT8/INT4-Quantisierung (was ein `.har` erzeugt) und werden schließlich als `.hef`-Binärdatei paketiert, die [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) konsumiert. Diese Form jetzt zu entscheiden und zu dokumentieren, bevor der Toolchain-Code geschrieben wird, erspart der endgültigen Implementierung, die Modellregister-/Versionierungsgeschichte später improvisieren zu müssen.

### In diesem Skelett bereits getroffene Designentscheidungen

* **Die Version wird aus den Metadaten des installierten Pakets gelesen, nicht fest codiert** - `main.py` ruft `importlib.metadata.version("hydra-umc-detection-hef")` statt einer zweiten `__version__`-Zeichenkette auf, sodass `bump_version.py` nur eine Stelle zu bearbeiten hat.
* **Der "Kilometerzähler"-Bump berührt automatisch nur `PATCH`/`MINOR`** - `bump_version.py` überträgt `PATCH` auf `MINOR` über 9 hinaus und `MINOR` auf `MAJOR` über 9 hinaus, erhöht aber nie `MAJOR` selbst; dieselbe Konvention wie `HYDRA-UMC-EDITOR-URDF/bump_version.py` und `HYDRA-UMC-SUITE/bump_version.py`.

---

## 📂 VERZEICHNISSTRUKTUR

```text
HYDRA-UMC-DETECTION-HEF/
├── src/                 # Quellcode (Paket hydra_umc_detection_hef)
├── docs/                # Dokumentation und Validierungsberichte
├── build/               # Build-Ausgabe (lokales .venv + künftige HEF-Toolchain-Ausgabe)
├── images/              # Medien und Diagramme
├── scripts/             # Hilfsskripte
├── pyproject.toml       # Paketmetadaten, Abhängigkeiten, Kilometerzähler-Version
├── bump_version.py      # Kilometerzähler-artiger Versions-Bump (build.sh/.bat)
├── build.sh / build.bat # venv + editierbare Installation + Compile-Check
├── run.sh / run.bat     # Führt den Einstiegspunkt aus dem lokalen venv aus
└── CHANGELOG.md         # Versions-für-Versions-Historie (Kilometerzähler-Schema, ohne Daten)
```

Kein `hardware/`-, `firmware/`-, `os/`- oder `models/`-Ordner - siehe "Erweiterte technische Informationen" oben für das Warum. `os/` und `models/` leben nur im Integrations-Elternteil, [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE); das eigene `build/` dieses Projekts ist, wo die Ausgabe seiner HEF-Toolchain landet, bevor sie dort veröffentlicht wird.

---

## 🏗️ BUILD UND AUSFÜHRUNG

### Voraussetzungen

* **Python 3.10 oder neuer** im `PATH` (die Skripte probieren `python3`, dann `python`).
* Kein ONNX- oder Hailo-Dataflow-Compiler-Werkzeug ist bisher erforderlich - **null Drittanbieter-Laufzeitabhängigkeiten** in dieser Phase (`dependencies = []` in `pyproject.toml`).
* Einige Dutzend MB Festplattenplatz für eine lokale virtuelle Umgebung unter `.venv/`.

### Schritt für Schritt

```bash
# Linux / macOS
./build.sh
```

1. **Kilometerzähler-Versions-Bump** - führt `bump_version.py` aus, das `PATCH` in `pyproject.toml` bei jedem Build erhöht.
2. **Virtuelle Umgebung** - erstellt `.venv/`, falls nicht vorhanden; verwendet es sonst weiter.
3. **Editierbare Installation** - `pip install -e .`, sodass Änderungen unter `src/` sofort wirken, und registriert den Konsolen-Einstiegspunkt `hydra-umc-detection-hef`.
4. **Compile-Check** - `python -m compileall -q src` kompiliert jede Datei unter `src/` zu Bytecode.

`set -euo pipefail` stoppt das Skript beim ersten fehlschlagenden Schritt; `== Build OK ==` wird nur ausgegeben, wenn alle 4 Schritte erfolgreich waren.

```bash
./run.sh
```

Sucht den Interpreter innerhalb von `.venv` und führt `python -m hydra_umc_detection_hef.main` aus, das Name + Version + Rolle ausgibt.

```bat
:: Windows - gleiche Schritte, Batch-Syntax
build.bat
run.bat
```

### Fehlerbehebung

* **`python`/`python3` nicht gefunden** - Python 3.10+ installieren und sicherstellen, dass es im `PATH` liegt.
* **`compileall` schlägt fehl** - ein echter Syntaxfehler wurde unter `src/` eingeführt; der Build stoppt absichtlich, ohne die Installation anzufassen.
* **"No `.venv` found" von `run.sh`/`run.bat`** - `build.sh`/`build.bat` vorher mindestens einmal ausführen.
* **Veraltete editierbare Installation** - `.venv/` löschen und neu bauen; selten nötig.

---

## 🚀 Aktueller Status & Nächste Schritte

**Was heute funktioniert:** ein echtes, installierbares Python-Paket mit verifiziertem Einstiegspunkt (siehe [`CHANGELOG.md`](CHANGELOG.md) für die erfasste Build-/Run-Ausgabe) und ein in den Build integrierter Kilometerzähler-Versions-Bump.

**Was noch offen ist, ohne bestimmte Reihenfolge und ohne verbindlichen Zeitplan:**

* Der echte ONNX-Export aus trainierten PyTorch/YOLO-Modellen.
* Die Integration des Hailo Dataflow Compiler für INT8/INT4-Quantisierung.
* HAR/HEF-Paketierung und ein versioniertes Modellregister.
* Veröffentlichung kompilierter `.hef`-Ausgaben im `models/`-Ordner von [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

---

## 🔗 Verwandte Projekte

Dieses Projekt ist Teil eines größeren Robotik-Ökosystems desselben Autors (JuanenRac / Electro Hobby 3D), das Firmware, Steuerungssoftware, KI-Knoten und Flottenwerkzeuge umfasst. Gut zu wissen, denn eine Anfrage könnte sich eigentlich auf eines dieser Projekte statt auf dieses Repository beziehen.

### Familie

**Elternteil:** **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — der Integrations-Elternteil, der diese HEF-Modelle auf seine Hailo-8-NPU lädt.

**Geschwister:**
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — erfasst und verarbeitet die vom Elternteil konsumierten Kameraströme vor.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — wandelt die Wahrnehmung des Elternteils (mit hier kompilierten Modellen) in Eindringlingserkennung und E-STOP-Auslösung um.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — wandelt die Wahrnehmung des Elternteils in kinematische Posenkorrekturen um.

### Direkte Beziehung (außerhalb der Familie)

- **[URTC](https://github.com/JuanenRac/URTC)** — die visuelle Erkennung von URTCs eigenen Werkzeugköpfen stützt sich auf hier kompilierte Modelle.

### Restliches Ökosystem

**HYDRA-UMC-Plattform** — die Multi-Roboter-Mikrofabrikzelle
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — das CM5 + STM32H745-Motherboard, das bis zu 8 Roboterarme orchestriert.
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — das Express/WebSocket-Backend, mit dem jeder Steuerungsclient spricht.
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — webbasiertes Steuerungs-Dashboard, Multi-Roboter-3D-Visualisierung.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — Android-Steuerungs-App über Wi-Fi/Bluetooth.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — iOS/iPadOS-Steuerungs-App, gebaut in Flutter.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — Desktop-Schwarm-Kommandozentrale (Python/PySide6).
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — Desktop-URDF-Modelleditor für den Roboterkatalog.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — native Touch-UI für den eingebauten DSI-Touchscreen.

**URTC-Plattform** — der Werkzeugkopf-Controller, den jeder HYDRA-UMC-Roboterarm trägt
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — Desktop-Tool für CAN-OTA + SWD/JTAG-Flashing.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — Desktop-Tool für Live-CAN-Bus-Diagnose.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — browserbasierte Alternative über die Web-Serial-API.

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

## 👤 AUTOR
**JuanenRac** (Electro Hobby 3D)
📧 electrohobby3d@gmail.com

## 📜 LIZENZ
GPL-3.0 - Siehe LICENSE-Datei für Details.
