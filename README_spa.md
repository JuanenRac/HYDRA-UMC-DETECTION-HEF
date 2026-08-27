<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-DETECTION-HEF banner" width="100%">
</p>

# 🎯 HYDRA-UMC-DETECTION-HEF

<p align="center"><a href="README.md">🇺🇸 English</a> | 🇪🇸 <b>Español</b> | <a href="README_fra.md">🇫🇷 Français</a> | <a href="README_ita.md">🇮🇹 Italiano</a> | <a href="README_deu.md">🇩🇪 Deutsch</a> | <a href="README_zho.md">🇨🇳 简体中文</a> | <a href="README_jpn.md">🇯🇵 日本語</a></p>

### 📦 Librería Industrial de Modelos Acelerados por Hardware (Hailo-8 / Hailo-10)

<p align="left">
  <img src="https://img.shields.io/badge/Licencia-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Formato-HEF-FF6F00.svg" alt="HEF">
  <img src="https://img.shields.io/badge/Modelos-YOLOv8%20%2F%20YOLOv10-00A4EF.svg" alt="YOLO">
  <img src="https://img.shields.io/badge/Etapa-Esqueleto-lightgrey.svg" alt="Etapa esqueleto">
</p>

---

## 1. 🛠️ VISIÓN GENERAL TÉCNICA

**HYDRA-UMC-DETECTION-HEF** está pensado para ser una librería y toolchain curada de modelos de red neuronal de alto rendimiento compilados al **Hailo Executable Format (HEF)**, ajustados para entornos de micro-fábrica industrial: ensamblaje de electrónica, colocación SMD y validación de cabezales de herramienta.

Este es uno de los 4 hijos de **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)**, el padre de integración de la familia: este proyecto solo posee la compilación y versionado de modelos - la copia servida en ejecución de un modelo `.hef` la carga y ejecuta el padre, que posee el handle del dispositivo Hailo-8, no este proyecto.

### Puntos Clave

* 🛠️ **Detección Industrial (previsto):** modelos orientados a componentes de PCB, soldaduras y defectos mecánicos.
* 📐 **Alineación de Fiduciales (previsto):** anclas de alta precisión para sincronización Pick-and-Place.
* ⚡ **Rendimiento Cuantizado (previsto):** variantes INT8/INT4 orientadas a las NPU Hailo-8/Hailo-10 para inferencia sub-10ms.
* 🤖 **Estimación de Pose (previsto):** detección de puntos clave para seguimiento de articulaciones del brazo robótico.
* 🧩 **Por qué existe como proyecto separado:** compilar y versionar modelos es un flujo de trabajo de datos/ML, completamente distinto del proceso en tiempo de ejecución que los sirve - mantener el toolchain aquí significa que una compilación fallida nunca pone en riesgo el nodo de percepción en ejecución, y los modelos se pueden iterar y validar offline antes de llegar a [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

**Comprobación de honestidad - qué funciona hoy de verdad:** este repositorio está en etapa de esqueleto. El entry point real (`src/hydra_umc_detection_hef/main.py`) imprime el nombre del proyecto, su versión instalada y una descripción de rol de una línea, y sale con código 0. Nada de la exportación ONNX, la cuantización con el Hailo Dataflow Compiler, el empaquetado HAR/HEF ni el registro/versionado de modelos descrito arriba existe todavía en código. Ver [`CHANGELOG.md`](CHANGELOG.md) para lo entregado exactamente hasta ahora, y "Estado Actual y Próximos Pasos" más abajo para lo que sigue abierto.

---

## 2. 🔄 FLUJO DE COMPILACIÓN DE MODELOS PREVISTO

El diagrama de abajo es el toolchain objetivo hacia el que se construye este esqueleto, no un pipeline que funcione hoy.

```mermaid
flowchart LR
    TRAIN["Entrenamiento (PyTorch/YOLO)"] --> ONNX["Exportar a ONNX"]
    ONNX --> DFC["Hailo Dataflow Compiler"]
    DFC --> HAR["Cuantización (HAR)"]
    HAR --> HEF["Binario HEF"]
    HEF --> NODE["HYDRA-UMC-VISION-NODE"]
```

---

## 3. 🧠 INFORMACIÓN TÉCNICA AVANZADA

### Por qué no hay `hardware/`/`firmware/` aquí, y por qué `os/`/`models/` siguen viviendo en el padre

Este proyecto distribuye archivos de modelo y las herramientas que los compilan, no un dispositivo físico - así que, como el resto de la familia Vision AI Node, no lleva carpeta `hardware/`/`firmware/`. Tampoco lleva `os/` ni `models/`, aunque los `.hef` se *producen* literalmente aquí: la copia *servida en ejecución* cargada en la NPU Hailo-8 en tiempo de ejecución vive solo en el padre de integración, [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE), porque es el proceso dueño del handle del dispositivo Hailo-8. El propio `build/` de este proyecto es donde está pensado que aterrice la salida compilada del toolchain antes de publicarse allí.

### El flujo de compilación es la decisión de diseño, antes que el código

El diagrama de arriba ya fija la forma prevista del pipeline: el entrenamiento PyTorch/YOLO ocurre en otro lugar (fuera del alcance de este repositorio), los modelos se exportan a ONNX, pasan por el Hailo Dataflow Compiler para cuantización INT8/INT4 (produciendo un `.har`), y finalmente se empaquetan como un binario `.hef` que consume [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE). Decidir y documentar esta forma ahora, antes de escribir el código del toolchain, evita que la implementación final tenga que improvisar más adelante la historia del registro/versionado de modelos.

### Decisiones de diseño ya tomadas en este esqueleto

* **La versión se lee de los metadatos del paquete instalado, no está fija en el código** - `main.py` llama a `importlib.metadata.version("hydra-umc-detection-hef")` en vez de una segunda cadena `__version__`, así `bump_version.py` solo tiene un lugar que editar.
* **El bump cuentakilómetros solo toca `PATCH`/`MINOR` automáticamente** - `bump_version.py` acarrea `PATCH` a `MINOR` al pasar de 9 y `MINOR` a `MAJOR` al pasar de 9, pero nunca incrementa `MAJOR` por sí mismo; misma convención que `HYDRA-UMC-EDITOR-URDF/bump_version.py` y `HYDRA-UMC-SUITE/bump_version.py`.

---

## 📂 ESTRUCTURA DE DIRECTORIOS

```text
HYDRA-UMC-DETECTION-HEF/
├── src/                 # Código fuente (paquete hydra_umc_detection_hef)
├── docs/                # Documentación e informes de validación
├── build/               # Salida de build (.venv local + futura salida del toolchain HEF)
├── images/              # Medios y diagramas
├── scripts/             # Scripts de utilidad
├── pyproject.toml       # Metadatos del paquete, dependencias, versión cuentakilómetros
├── bump_version.py      # Bump de versión tipo cuentakilómetros (build.sh/.bat)
├── build.sh / build.bat # venv + instalación editable + compile-check
├── run.sh / run.bat     # Ejecuta el entry point desde el venv local
└── CHANGELOG.md         # Historial versión a versión (esquema cuentakilómetros, sin fechas)
```

Sin carpeta `hardware/`, `firmware/`, `os/` ni `models/` - ver "Información Técnica Avanzada" arriba para el porqué. `os/` y `models/` viven solo en el padre de integración, [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE); el propio `build/` de este proyecto es donde aterriza la salida de su toolchain HEF hasta que se publica allí.

---

## 🏗️ BUILD Y RUN

### Requisitos previos

* **Python 3.10 o superior** en el `PATH` (los scripts prueban `python3` y luego `python`).
* No hace falta todavía ONNX ni el Hailo Dataflow Compiler - **cero dependencias de terceros en tiempo de ejecución** en esta etapa (`dependencies = []` en `pyproject.toml`).
* Unas pocas decenas de MB de espacio en disco para un entorno virtual local en `.venv/`.

### Paso a paso

```bash
# Linux / macOS
./build.sh
```

1. **Bump de versión cuentakilómetros** - ejecuta `bump_version.py`, incrementando `PATCH` en `pyproject.toml` en cada build.
2. **Entorno virtual** - crea `.venv/` si falta; lo reutiliza si ya existe.
3. **Instalación editable** - `pip install -e .` para que los cambios en `src/` tengan efecto inmediato, y registra el entry point de consola `hydra-umc-detection-hef`.
4. **Compile-check** - `python -m compileall -q src` compila a bytecode cada archivo bajo `src/`.

`set -euo pipefail` detiene el script en el primer paso que falle; `== Build OK ==` se imprime solo si los 4 pasos tienen éxito.

```bash
./run.sh
```

Localiza el intérprete dentro de `.venv` y ejecuta `python -m hydra_umc_detection_hef.main`, imprimiendo nombre + versión + rol.

```bat
:: Windows - mismos pasos, sintaxis batch
build.bat
run.bat
```

### Solución de problemas

* **No se encuentra `python`/`python3`** - instala Python 3.10+ y asegúrate de que está en el `PATH`.
* **`compileall` falla** - se introdujo un error de sintaxis real bajo `src/`; el build se detiene sin tocar la instalación, a propósito.
* **"No `.venv` found" en `run.sh`/`run.bat`** - ejecuta `build.sh`/`build.bat` al menos una vez antes.
* **Instalación editable desactualizada** - borra `.venv/` y reconstruye; rara vez hace falta.

---

## 🚀 Estado Actual y Próximos Pasos

**Qué funciona hoy:** un paquete Python real e instalable con un entry point verificado (ver [`CHANGELOG.md`](CHANGELOG.md) para la salida de build/run capturada) y un bump de versión cuentakilómetros integrado en el build.

**Qué sigue abierto, sin orden particular y sin calendario comprometido:**

* La exportación ONNX real desde modelos PyTorch/YOLO entrenados.
* Integración con el Hailo Dataflow Compiler para cuantización INT8/INT4.
* Empaquetado HAR/HEF y un registro de modelos versionado.
* Publicar la salida `.hef` compilada en la carpeta `models/` de [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE).

---

## 🔗 Proyectos Relacionados

Este proyecto forma parte de un ecosistema de robótica más amplio del mismo autor (JuanenRac / Electro Hobby 3D), que abarca firmware, software de control, nodos de IA y herramientas de flota. Vale la pena conocerlo, ya que una petición podría en realidad ser sobre uno de estos proyectos en vez de sobre este repositorio.

### Familia

**Padre:** **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** — el padre de integración que carga estos modelos HEF en su NPU Hailo-8.

**Hermanos:**
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — captura y pre-procesa los flujos de cámara que consume el padre.
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — convierte la percepción del padre (usando modelos compilados aquí) en detección de intrusión y disparo de E-STOP.
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — convierte la percepción del padre en correcciones cinemáticas de pose.

### Relación Directa (fuera de la familia)

- **[URTC](https://github.com/JuanenRac/URTC)** — el reconocimiento visual de las propias herramientas de URTC depende de modelos compilados aquí.

### Resto del Ecosistema

**Plataforma HYDRA-UMC** — la célula de micro-fábrica multi-robot
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — la placa base CM5 + STM32H745 que orquesta hasta 8 brazos robóticos.
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — el backend Express/WebSocket con el que habla cada cliente de control.
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — panel de control web, visualización 3D multi-robot.
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — app de control Android por Wi-Fi/Bluetooth.
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — app de control iOS/iPadOS construida en Flutter.
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — centro de mando de enjambre de escritorio (Python/PySide6).
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — editor de modelos URDF de escritorio para el catálogo de robots.
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — interfaz táctil nativa para la pantalla DSI integrada.

**Plataforma URTC** — el controlador de cabezal de herramienta que lleva cada brazo HYDRA-UMC
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — herramienta de escritorio de flasheo CAN-OTA + SWD/JTAG.
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — herramienta de escritorio de diagnóstico CAN en vivo.
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — alternativa basada en navegador vía Web Serial API.

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

## 📜 LICENCIA
GPL-3.0 - Ver archivo LICENSE para más detalles.
