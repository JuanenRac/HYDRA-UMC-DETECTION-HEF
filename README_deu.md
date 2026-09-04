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
  <img src="https://img.shields.io/badge/Stufe-Funktional%20v0-green.svg" alt="Funktional v0">
</p>

---

## 1. 🛠️ TECHNISCHER ÜBERBLICK

**HYDRA-UMC-DETECTION-HEF** soll eine kuratierte Bibliothek und Toolchain für leistungsstarke neuronale Netzwerkmodelle werden, kompiliert in das **Hailo Executable Format (HEF)**, abgestimmt auf industrielle Mikrofabrik-Umgebungen: Elektronikmontage, SMD-Bestückung und Werkzeugkopf-Validierung.

Dies ist eines der 4 Kind-Projekte von **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)**, dem Integrations-Elternteil der Familie: Dieses Projekt besitzt nur Modellkompilierung und -versionierung - die ausgelieferte, laufende Kopie eines `.hef`-Modells wird vom Elternteil geladen und ausgeführt, dem das Hailo-8-Gerätehandle gehört, nicht von diesem Projekt.

### Kernpunkte

* ✅ **Echtes v0 - Modellregister:** `registry.py` parst und schema-validiert ein JSON-Register kompilierter Modelle, erkennt doppelte Name+Version-Einträge, findet die neueste Version für einen Namen/Task, und prüft lokale `.hef`-Dateien per sha256-Checksumme gegen das Register. Über `registry validate`/`registry latest` unten verfügbar - kein Hailo-SDK oder Hardware nötig, um es auszuführen oder zu testen.
* 🔒 **Echtes v0 - Sicheres-Laden-Gate:** `safe_load()` in `compatibility.py` prüft die echte Hailo-Architektur-Kompatibilität (`hailo8`/`hailo15h`/usw. - jeder Registereintrag deklariert jetzt seinen Ziel-Chip) vor der Checksummen-Prüfung und meldet ein Modell nur dann als bereit zum Deployment, wenn beide echten Prüfungen bestehen. Über `registry load` unten verfügbar.
* 🌐 **Echtes v0 - JSON/HTTP-API:** der `serve`-Unterbefehl von `api.py` führt genau dieselben Register-/Sicheres-Laden-Prüfungen als langlebigen lokalen Dienst aus (Standard `127.0.0.1:8093`) über `GET /registry`, `GET /registry/latest`, `GET /registry/load` und `GET /stats` - Register und Modellverzeichnis werden nur einmal beim Start konfiguriert, nicht pro Anfrage. Siehe [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md) für echte, erfasste Beispiele jedes Endpunkts.
* 🛠️ **Industrielle Erkennung (geplant):** Modelle für PCB-Komponenten, Lötstellen und mechanische Defekte.
* 📐 **Passermarken-Ausrichtung (geplant):** hochpräzise Anker für die Pick-and-Place-Synchronisation.
* ⚡ **Quantisierte Leistung (geplant):** INT8/INT4-Varianten für die Hailo-8/Hailo-10-NPUs für Inferenz unter 10ms. *(zukünftige Arbeit - benötigt die echte Hailo-8/Hailo-10-NPU und den Dataflow Compiler, die diese Umgebung nicht hat.)*
* 🤖 **Posenschätzung (geplant):** Keypoint-Erkennung für die Nachverfolgung von Roboterarm-Gelenken. *(zukünftige Arbeit, gleicher Grund.)*
* 🧩 **Warum als eigenes Projekt:** Kompilieren und Versionieren von Modellen ist ein Daten-/ML-Workflow, völlig anders als der Laufzeitprozess, der sie bedient - die Toolchain hier zu halten bedeutet, dass eine fehlgeschlagene Kompilierung nie den laufenden Wahrnehmungsknoten gefährdet, und Modelle können offline iteriert und validiert werden, bevor sie [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) erreichen.

**Ehrlichkeitscheck - was heute wirklich läuft:** die reale, hardwareunabhängige Hälfte der Aufgabe dieses Projekts - das Modellregister (`registry.py`) und das echte Sicheres-Laden-Gate (`compatibility.py`), verfügbar über `registry validate`/`registry latest`/`registry load` und, als langlebige JSON/HTTP-API, über `serve` (`api.py`) - ist implementiert und getestet (48 Tests). Der ONNX-Export, die Quantisierung über den Hailo Dataflow Compiler und die HAR/HEF-Paketierung, die die von diesem Register beschriebenen Modelle tatsächlich erzeugen würden, bleiben zukünftige Arbeit: sie benötigen echte Hailo-Hardware, die diese Umgebung nicht hat. Siehe [`CHANGELOG.md`](CHANGELOG.md) für genau das, was bisher geliefert wurde, und "Aktueller Status & Nächste Schritte" unten für das, was noch offen ist.

---

## 2. 🔄 GEPLANTER MODELLKOMPILIERUNGS-ABLAUF

Das Diagramm unten ist die Ziel-*Kompilierungs*-Toolchain, auf die dieses Projekt hinarbeitet - immer noch nicht implementiert, da jeder Schritt echte Hailo-Hardware benötigt. Das Modell*register* (Versionierung + Integritätsprüfung der `.hef`-Dateien, die diese Pipeline eines Tages erzeugt) ist heute real; siehe "Kernpunkte" oben und die Designentscheidungen unten.

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

### Bereits getroffene Designentscheidungen

* **Die Version wird aus den Metadaten des installierten Pakets gelesen, nicht fest codiert** - `main.py` ruft `importlib.metadata.version("hydra-umc-detection-hef")` statt einer zweiten `__version__`-Zeichenkette auf, sodass `bump_version.py` nur eine Stelle zu bearbeiten hat.
* **Der "Kilometerzähler"-Bump berührt automatisch nur `PATCH`/`MINOR`** - `bump_version.py` überträgt `PATCH` auf `MINOR` über 9 hinaus und `MINOR` auf `MAJOR` über 9 hinaus, erhöht aber nie `MAJOR` selbst; dieselbe Konvention wie `HYDRA-UMC-EDITOR-URDF/bump_version.py` und `HYDRA-UMC-SUITE/bump_version.py`.
* **Eine fehlende lokale `.hef`-Datei ist kein Checksummen-Fehler** - `verify_checksum()` gibt `None` (nicht `False`) zurück, wenn die vom Register beschriebene Datei nicht unter `--models-dir` vorhanden ist, und `registry validate` meldet dies als "skipped", nicht als Fehler. Das Register soll Modelle beschreiben können, die in einem separaten Object-Store liegen, nicht notwendigerweise in diesem Repo eingecheckt - nur eine tatsächlich abweichende Checksumme für eine vorhandene Datei zeigt ein beschädigtes Register an.
* **Warum `safe_load()` die Architektur vor der Checksumme prüft, nicht umgekehrt.** Architektur-Kompatibilität ist reine Metadaten (keine I/O); die Checksummen-Prüfung muss eine echte Datei lesen. Zuerst das billige, fundamentale Gate zu prüfen bedeutet, dass ein für den falschen Hailo-Chip kompiliertes Modell abgelehnt wird, bevor überhaupt das Dateisystem berührt wird, und der Ablehnungsgrund nennt die tatsächlich fehlgeschlagene fundamentale Prüfung statt eines irreführenden "Datei fehlt" für ein Modell, das ohnehin nie auf dieser Hardware gelaufen wäre.
* **Warum Architektur-Kompatibilität eine exakte Übereinstimmung ist, keine Kompatibilitätsmatrix.** Der Hailo Dataflow Compiler brennt den Ziel-Chip zur Kompilierzeit in eine `.hef` ein - zu behaupten, dass z.B. ein Hailo-15H eine Hailo-8-`.hef` ausführen könnte, würde eine echte architekturübergreifende Validierung auf echter Hardware erfordern, die diese Umgebung nicht hat. Exakte Übereinstimmung ist die einzige Kompatibilitätsaussage, die allein aus den Register-Metadaten ehrlich nachweisbar ist.

---

## 📂 VERZEICHNISSTRUKTUR

```text
HYDRA-UMC-DETECTION-HEF/
├── src/                 # Quellcode (Paket hydra_umc_detection_hef)
│   └── hydra_umc_detection_hef/
│       ├── registry.py       # Modellregister: Schema-Validierung, Versionierung, sha256-Prüfsummen
│       ├── compatibility.py  # Echtes Sicheres-Laden-Gate: Architektur-Kompatibilität + Checksumme
│       ├── api.py            # Einfache JSON/HTTP-Oberfläche (stdlib http.server) über das Modellregister
│       └── main.py           # CLI-Einstiegspunkt (nackter Aufruf + `registry` + `serve`)
├── tests/               # Echte pytest-Suite (registry, compatibility, api, CLI)
├── docs/
│   └── CLI_REFERENCE.md # Vollständige CLI- + JSON/HTTP-API-Referenz, jedes Beispiel aus einem echten Lauf erfasst
├── build/               # Build-Ausgabe (lokales .venv + künftige HEF-Toolchain-Ausgabe)
├── images/              # Medien und Diagramme
├── systemd/
│   └── hydra-umc-detection-hef.service # systemd-Unit der lokalen CM5-Modellregister-API
├── tools/
│   ├── build_test.py    # Nicht-versionierender Build-Check
│   └── ci_validate.py   # Manifest/CHANGELOG/Docs-Validierung, von CI genutzt
├── pyproject.toml       # Paketmetadaten, Abhängigkeiten, Kilometerzähler-Version
├── bump_version.py      # Native Kilometerzähler-artige Versions-Bump (build.sh/.bat)
├── bump_manifest_version.py # Synchronisiert die Version von hydra-umc.project.json mit der nativen (--sync)
├── build.sh / build.bat # venv + editierbare Installation + Compile-Check + Tests
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
3. **Editierbare Installation** - `pip install -e ".[dev]"`, sodass Änderungen unter `src/` sofort wirken, installiert `pytest`, und registriert den Konsolen-Einstiegspunkt `hydra-umc-detection-hef`.
4. **Compile-Check** - `python -m compileall -q src` kompiliert jede Datei unter `src/` zu Bytecode.
5. **Echte Test-Suite** - `python -m pytest tests/ -q` (48 Tests, die das Register, das Sicheres-Laden-Gate und die CLI abdecken).

`set -euo pipefail` stoppt das Skript beim ersten fehlschlagenden Schritt; der Build meldet Erfolg nur, wenn alle 5 Schritte erfolgreich waren.

```bash
./run.sh
```

Sucht den Interpreter innerhalb von `.venv` und führt `python -m hydra_umc_detection_hef.main` aus, wobei alle Argumente weitergereicht werden - der nackte Aufruf gibt Name + Version + Rolle aus.

Echtes Beispiel - ein Register validieren und die neueste Version eines Modells nachschlagen:

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

Jeder Registereintrag deklariert auch seine Ziel-`hailo_arch` (z.B. `hailo8`). Der echte `registry load`-Unterbefehl kombiniert die obige Checksummen-Prüfung mit einer echten Architektur-Kompatibilitätsprüfung und meldet ein Modell nur dann als bereit, wenn beide bestehen:

```bash
./run.sh registry load --registry registry.json --models-dir models/ --name pcb-defect --target-arch hailo8
# READY: pcb-defect 0.2.0 (hailo8) verified and ready

./run.sh registry load --registry registry.json --models-dir models/ --name pcb-defect --target-arch hailo15h
# REJECTED_ARCH_MISMATCH: model compiled for 'hailo8', this deployment targets 'hailo15h'
```

Dieselben Register-/Sicheres-Laden-Prüfungen sind auch als langlebige JSON/HTTP-API über `./run.sh serve --registry registry.json --models-dir models/` erreichbar (Standard `127.0.0.1:8093`). Siehe [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md) für die vollständige Befehls- und Endpunkt-Referenz, mit jedem Beispiel aus einem echten Lauf erfasst.

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

**Was heute funktioniert:** das Modellregister - Schema-Validierung (einschließlich erforderlicher, validierter Hailo-Architektur-Metadaten), Erkennung doppelter Versionen, Suche nach der neuesten Version, und sha256-Integritätsprüfung (`registry.py`) - plus ein echtes, kombiniertes Sicheres-Laden-Gate, das Architektur-Kompatibilität und Checksummen-Integrität zusammen prüft und ein Modell nur dann als bereit meldet, wenn beide bestehen (`compatibility.py`), dieselben Prüfungen zusätzlich als echte, langlebige JSON/HTTP-API (`api.py`, `serve`-Unterbefehl) neben der Einmal-CLI, 48 Tests insgesamt, plus ein echtes, installierbares Python-Paket mit verifiziertem Einstiegspunkt und ein in den Build integrierter Kilometerzähler-Versions-Bump. Siehe [`CHANGELOG.md`](CHANGELOG.md) für die erfasste Build-/Run-Ausgabe.

**Was noch offen ist, ohne bestimmte Reihenfolge, ohne verbindlichen Zeitplan, und blockiert durch echte Hailo-Hardware:**

* Der echte ONNX-Export aus trainierten PyTorch/YOLO-Modellen.
* Die Integration des Hailo Dataflow Compiler für INT8/INT4-Quantisierung.
* Die HAR/HEF-Paketierung, die eine Registerdatei, die das `registry.py` dieses Projekts bereits lesen und validieren kann, tatsächlich befüllen würde.
* Veröffentlichung kompilierter `.hef`-Ausgaben im `models/`-Ordner von [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

---

## 🔗 Verwandte Projekte

Dieses Projekt ist Teil des HYDRA-UMC-Robotik-Ökosystems desselben Autors (JuanenRac / Electro Hobby 3D). Gut zu wissen, da eine Anfrage eigentlich eines dieser Projekte betreffen könnte statt dieses Repositorys.

**Übergeordnetes Projekt**
- **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — Integrationsknoten für die Hailo-8-Vision-Pipeline, mit einer echten stufenweisen Hardware-Bereitschaftsprüfung; das übergeordnete Projekt, dessen spezifische Stufe bzw. Verbraucher dieses Repository innerhalb seiner eigenen Wahrnehmungs-Pipeline ist.

**Geschwisterprojekte** — die übrigen Stufen/Verbraucher der eigenen Hailo-8-Wahrnehmungs-Pipeline von HYDRA-UMC-VISION-NODE
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — echter GStreamer-Pipeline- + MediaMTX-Konfigurationsgenerator mit einer echten HailoRT-Integrationsschranke.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — echte Zonenverletzungsprüfung und E-STOP-Anforderung, mit erzwungener Kalibrierungsaktualität.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — echtes Position-Based-Visual-Servoing-Korrekturgesetz, sicherheitsgesteuert nach vorgelagertem Zonenstatus.

**Direkt verwandt**
- **[URTC](https://github.com/JuanenRac/URTC)** — Firmware für die physische Universal-Robot-Tool-Controller-Platine, 25+ Werkzeugprofile über CAN-Bus; die visuelle Erkennung der eigenen Werkzeugköpfe von URTC beruht auf den hier kompilierten Modellen.

**Ebenfalls Teil des Ökosystems**

*Kern-Hardware & Plattform*
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — das physische Motherboard des Roboterarms: CM5-Host + Dual-Core-STM32H745, koordiniert bis zu 8 Werkzeugarme über CAN-OTA/SPI-OTA.
- **[HYDRA-UMC-OS](https://github.com/JuanenRac/HYDRA-UMC-OS)** — reproduzierbare Raspberry-Pi-OS-Produktschicht für den CM5: schreibgeschützter Agent, validierte Konfiguration/Profile, WiFi-Ersteinrichtung.
- **[HYDRA-UMC-SDK](https://github.com/JuanenRac/HYDRA-UMC-SDK)** — der gemeinsame JSON-Schema-Vertrag und die Sicherheitsschranke, gegen die jede Bridge ihre Befehle validiert.

*Kern-Backend & Clients*
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — das reale Headless-Backend (REST/WebSocket), mit dem jeder Steuerungsclient tatsächlich spricht.
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — Web-Steuerungs-Dashboard mit Echtzeit-3D-Visualisierung mehrerer Roboter.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — Desktop-Schwarmleitstand (PySide6) für mehrere Server gleichzeitig, verpackt als eigenständige ausführbare Datei.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — native Android-Steuerungs-App mit biometrischem Login und einer gekoppelten Wear-OS-Begleit-App.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — iOS/iPadOS-Steuerungs-App (Flutter) mit Echtzeit-WebSocket-Synchronisierung.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — native Touch-UI für das eingebaute 7"-DSI-Touchscreen, direkt auf dem CM5 eingebettet.
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — grafischer Desktop-URDF-Ersteller/-Editor, der fertige Modelle in STUDIOs eigenen Katalog überträgt.
- **[HYDRA-UMC-BRIDGE-AMR](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-AMR)** — Koordinationsschranke für AGV-/AMR-Flotten über einen echten VDA-5050-MQTT-Publisher.
- **[HYDRA-UMC-BRIDGE-CNC](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-CNC)** — High-Level-Koordinator für CNC-Zellen mit echtem GRBL-Status-/Steuerbyte-Zugriff.
- **[HYDRA-UMC-BRIDGE-DROIDS](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-DROIDS)** — Koordinationsschranke für laufende/humanoide Droiden, mit einem echten Boston-Dynamics-Spot-Befehlssender.
- **[HYDRA-UMC-BRIDGE-LASER](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-LASER)** — Sicherheitskoordinator für Laserzellen, liest 3 echte Schlüssel-/Gehäuse-/Verriegelungs-GPIO-Sicherungen.
- **[HYDRA-UMC-BRIDGE-OPENPNP](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-OPENPNP)** — sicherer High-Level-Koordinator für den Leiterplattenfluss von OpenPnP Pick-and-Place.
- **[HYDRA-UMC-BRIDGE-PRINTER3D](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-PRINTER3D)** — sichere Koordinationsschranke für Moonraker/Klipper-3D-Drucker, mit echten gesicherten Job-Befehlen.
- **[HYDRA-UMC-BRIDGE-ROS2](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-ROS2)** — Sicherheitskoordinator mit einem echten, träge importierten rclpy-ROS-2-Transport.
- **[HYDRA-UMC-BRIDGE-UAV](https://github.com/JuanenRac/HYDRA-UMC-BRIDGE-UAV)** — Koordinationsschranke für kameraausgestattete UAVs, mit einem echten MAVLink-Befehlssender.

*URTC-Werkzeugplattform*
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — Desktop-GUI-Flash-Tool für URTC-Platinen, CAN-OTA plus Full-Chip-SWD/JTAG.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — Desktop-Live-CAN-Bus-Diagnosetool für URTC-Platinen, ein Panel pro Werkzeugprofil.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — browserbasierte Alternative zu URTC-TESTER über die Web-Serial-API, ohne lokale Installation.

*Kognitiver KI-Knoten (Hailo-10)*
- **[HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)** — Integrationsknoten für die Hailo-10-Cognitive-Pipeline (LLM-/VLA-/Sprach-Orchestrierung).
- **[HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)** — echte Aktions-Token-Kodierung/-Dekodierung und Trajektoriengenerierung für ein Vision-Language-Action-Modell.
- **[HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)** — echtes Sprach-Frontend (VAD + Intent-Parser) mit einem begrenzten, bestätigungsgesicherten Watch-Relay.
- **[HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)** — echte regelbasierte Aufgabenzerlegung und semantische Fehlerbehebung über MCU-Fehlercodes.
- **[HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)** — echte, nur auf der Standardbibliothek basierende TF-IDF-Dokumentensuche über die eigenen Markdown-Dokumente dieses Ökosystems.

*Orchestrierung & Schwarm*
- **[HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)** — Integrationsknoten mit einem echten gRPC/Protobuf-Health-Report-Vertrag und einer Missions-Zustandsmaschine.
- **[HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)** — echte prioritätsbasierte Job-Queue mit Deduplizierung, über eine echte HTTP-API.
- **[HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)** — echter gRPC-basierter Flotten-Health-Watchdog mit Retry/Backoff und Identitäts-Mismatch-Erkennung.
- **[HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)** — echter RRT-basierter 3D-Pfadplaner mit echter Hindernis-/Arbeitsraum-Kollisionsvalidierung.
- **[HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)** — echte CRDT-LWW-Element-Map-Zustandssynchronisation, eigenschaftsgetestet auf Multi-Zellen-Konvergenz.

*Digitaler Zwilling & Simulation*
- **[HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)** — Integrationsknoten für die Digital-Twin-Engine, mit einem echten Versionskompatibilitäts-Sync-Vertrag.
- **[HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)** — echte Hardware-in-the-Loop-Sicherheitsverriegelung, die Befehle zwischen Simulation und echter Hardware routet.
- **[HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)** — echte Vorwärtskinematik und Gelenkgrenzenvalidierung über eine echte URDF-Teilmenge.
- **[HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)** — echter prozeduraler 2D-Szenengenerator mit YOLO/COCO-Annotationsexport.

*Daten & Analytik*
- **[HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)** — echter sqlite3-gestützter Zeitreihenspeicher mit einer echten Ingest-/Abfrage-HTTP-API.
- **[HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)** — echter FFT- + statistischer Basislinien-Anomaliedetektor mit Drift-Überwachung.
- **[HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)** — echte OEE-/Verfügbarkeitsberechnung über den DATALAKE-Verlauf, mit reproduzierbarem CSV-Export.
- **[HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)** — echte CAN/WebSocket-Ingestion-Pipeline in DATALAKE, mit Sequenz-Deduplizierung.

*Industrie-Gateway*
- **[HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)** — Integrationsknoten, der zu Industrieprotokollen weiterleitet, mit einer echten Befehls-Allowlist-/Backpressure-Schicht.
- **[HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)** — echter OPC-UA-Adressraum, verifiziert mit einer echten Binärprotokoll-Client-Session.
- **[HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)** — echter MQTT-Broker mit optionaler Pro-Client-Authentifizierung und Topic-ACLs.
- **[HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)** — echte MTConnect-`/probe`- und `/current`-XML-Endpunkte mit Degraded-Mode-Ausgabe.

*Ergänzende Tools & Ökosystembetrieb*
- **[HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)** — Smart-Summaries- und Anomaly-Highlighting-Panels über DATALAKE/ANOMALY-DETECTOR, mit einem ehrlichen statistischen Fallback.
- **[HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)** — Flotten-CLI mit einem echten, stabilen Exit-Code-Vertrag, ein echter Live-Client der eigenen API von HYDRA-UMC-SERVER.
- **[HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)** — WearOS-Begleit-App mit echten haptischen Alarmen und einem Sprach-Relay zum gekoppelten Telefon.
- **[URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)** — Firmware für ein Platinenmontagegestell mit echter Werkzeug-ID-Dekodierung und Smart-Idle-Vorheizlogik.
- **[URTC-VISION-TOOL](https://github.com/JuanenRac/URTC-VISION-TOOL)** — Firmware plus ein echter Python-Vision-Begleiter für einen Thermal-/RGB-Inspektionswerkzeugkopf.
- **[HYDRA-UMC-UPDATER](https://github.com/JuanenRac/HYDRA-UMC-UPDATER)** — administratives Desktop-Tool, das jedes Repository in diesem Ökosystem entdeckt, klont und aktualisiert.
- **[HYDRA-UMC-OS-REBUILDER](https://github.com/JuanenRac/HYDRA-UMC-OS-REBUILDER)** — Windows/Linux-Desktop-Tool, das ein flashbereites CM5-Image baut, vorgeladen mit den aktuellsten Versionen des Ökosystems, mit Ersteinrichtungs-Konfiguration für WLAN/Benutzer/SSH im Stil von Raspberry Pi Imager.

---

## 📚 Dokumentation & Community

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — Technologie-Stack und Coding-Richtlinien für einen Pull Request.
- **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** — die in dieser Community erwarteten Verhaltensstandards.
- **[SECURITY.md](SECURITY.md)** — wie man eine Schwachstelle meldet, und die echten Sicherheitsschwerpunkte dieses Projekts.
- **[SUPPORT.md](SUPPORT.md)** — wo man Fragen stellt und Fehler meldet.
- **[LICENSE.md](LICENSE.md)** — die eigene Lizenz dieses Projekts.

## 👤 AUTOR
**JuanenRac** (Electro Hobby 3D)
📧 electrohobby3d@gmail.com
📺 [youtube.com/@electrohobby3d](https://youtube.com/@electrohobby3d)

## 📜 LIZENZ
GPL-3.0 - Siehe LICENSE-Datei für Details.
