<p align="center">
  <img src="images/HYDRA_UMC_BANNER.svg" alt="HYDRA-UMC-DETECTION-HEF banner" width="100%">
</p>

# 🎯 HYDRA-UMC-DETECTION-HEF

<p align="center"><a href="README.md">🇺🇸 English</a> | <a href="README_spa.md">🇪🇸 Español</a> | <a href="README_fra.md">🇫🇷 Français</a> | <a href="README_ita.md">🇮🇹 Italiano</a> | <a href="README_deu.md">🇩🇪 Deutsch</a> | <a href="README_zho.md">🇨🇳 简体中文</a> | 🇯🇵 <b>日本語</b></p>

### 📦 ハードウェアアクセラレーション産業用モデルライブラリ（Hailo-8 / Hailo-10）

<p align="left">
  <img src="https://img.shields.io/badge/Licencia-GPL%203.0-blue.svg" alt="GPL 3.0">
  <img src="https://img.shields.io/badge/Format-HEF-FF6F00.svg" alt="HEF">
  <img src="https://img.shields.io/badge/Models-YOLOv8%20%2F%20YOLOv10-00A4EF.svg" alt="YOLO">
  <img src="https://img.shields.io/badge/Stage-Functional%20v0-green.svg" alt="Functional v0">
</p>

---

## 1. 🛠️ 技術概要

**HYDRA-UMC-DETECTION-HEF** は、**Hailo Executable Format（HEF）** に
コンパイルされた高性能ニューラルネットワークモデルの厳選されたライブラリ
とツールチェーンとなることを目指しており、産業用マイクロファクトリー
環境（電子部品組立、SMD 実装、工具ヘッド検証）向けに調整されています。

これは、ファミリーの統合親プロジェクトである
**[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** の 4 つの子プロジェクトの 1 つです：本プロジェクトはモデルのコンパイルとバージョン管理のみを担当します——実際に配信され実行される `.hef` モデルのコピーは、Hailo-8 デバイスハンドルを保持する親プロジェクトによってロードおよび実行され、本プロジェクト自体は行いません。

### 要点

* ✅ **実装済み v0 —— モデルレジストリ：** `registry.py` はコンパイル済みモデルの JSON レジストリを解析・スキーマ検証し、重複した名前+バージョンのエントリを検出し、名前/タスクに対する最新バージョンを検索し、ローカルの `.hef` ファイルをレジストリと照合して sha256 チェックサムを検証します。下記の `registry validate`/`registry latest` から利用可能で、実行にもテストにも Hailo SDK やハードウェアは不要です。
* 🛠️ **産業用検知（計画中）：** PCB 部品、はんだ接合部、機械的欠陥を対象としたモデル。
* 📐 **フィデューシャルアライメント（計画中）：** ピック＆プレース同期のための高精度アンカー。
* ⚡ **量子化パフォーマンス（計画中）：** Hailo-8/Hailo-10 NPU を対象としたサブ 10ms 推論のための INT8/INT4 バリアント。*（将来の作業——この環境にはまだない実際の Hailo-8/Hailo-10 NPU と Dataflow Compiler が必要です。）*
* 🤖 **姿勢推定（計画中）：** ロボットアームの関節追跡のためのキーポイント検出。*（同じ理由で将来の作業です。）*
* 🧩 **独立したプロジェクトとして存在する理由：** モデルのコンパイルとバージョン管理はデータ/ML ワークフローであり、それらを提供するランタイムプロセスとは完全に異なります——ツールチェーンをここに保つことで、不良なコンパイルが実行中の知覚ノードを危険にさらすことは決してなく、モデルは [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) に到達する前にオフラインで反復・検証できます。

**正直な現状確認 —— 今日実際に動くもの：** 本プロジェクトの仕事のうち、実際にハードウェアに依存しない半分——モデルレジストリ（`registry.py`、`registry validate`/`registry latest`）——は実装され、テストされています（21 個のテスト）。このレジストリが記述するモデルを実際に*生成*する ONNX エクスポート、Hailo Dataflow Compiler による量子化、HAR/HEF パッケージングは、依然として将来の作業です：いずれもこの環境にはない実際の Hailo ハードウェアを必要とします。
実際に出荷済みの内容は [`CHANGELOG.md`](CHANGELOG.md) を、まだ残っている
作業は下記の「現在の状況と次のステップ」セクションを参照してください。

---

## 2. 🔄 目標モデルコンパイルフロー

下図は、本プロジェクトが構築を目指している目標*コンパイル*ツールチェーンです——各ステップが実際の Hailo ハードウェアを必要とするため、依然として未実装です。モデル*レジストリ*（このパイプラインが将来生成する `.hef` のバージョン管理と整合性検証）は今日すでに実際に動作します。上記の「要点」と下記の設計上の決定を参照してください。

```mermaid
flowchart LR
    TRAIN["Training (PyTorch/YOLO)"] --> ONNX["Export to ONNX"]
    ONNX --> DFC["Hailo Dataflow Compiler"]
    DFC --> HAR["Quantization (HAR)"]
    HAR --> HEF["HEF Binary"]
    HEF --> NODE["HYDRA-UMC-VISION-NODE"]
```

---

## 3. 🧠 高度な技術情報

### なぜここに `hardware/`/`firmware/` がなく、なぜ `os/`/`models/` は依然として親プロジェクトに存在するのか

本プロジェクトはモデルファイルとそれをコンパイルするツールを提供する
ものであり、物理デバイスではありません——そのため、Vision AI Node
ファミリーの他のプロジェクトと同様に、`hardware/`/`firmware/` フォルダを
携えていません。`.hef` ファイルが文字通りここで*生成される*にもかかわ
らず、`os/` や `models/` も携えていません：ランタイム時に Hailo-8 NPU に
ロードされる*配信され実行される*コピーは、Hailo-8 デバイスハンドルを
保持するプロセスである統合親プロジェクト [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) にのみ存在するためです。本プロジェクト自身の `build/` は、コンパイルされたツールチェーンの出力がそこに公開される前に到達する場所です。

### コンパイルフローはコードに先立つ設計上の決定である

上図は、意図されたパイプラインの形をすでに確定しています：PyTorch/YOLO
のトレーニングは他の場所で行われ（本リポジトリの範囲外）、モデルは
ONNX にエクスポートされ、Hailo Dataflow Compiler を通じて INT8/INT4
量子化が行われ（`.har` を生成）、最終的に [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) が消費する `.hef` バイナリとしてパッケージ化されます。ツールチェーンのコードを書く前に、今のうちにこの形を決定し文書化しておくことで、最終的な実装が後でモデルレジストリ/バージョン管理の方法を即興で考案する必要がなくなります。

### 既に行われた設計上の決定

* **バージョンはハードコードではなく、インストール済みパッケージのメタデータから読み取られます** —— `main.py` は 2 つ目の `__version__` 文字列の代わりに `importlib.metadata.version("hydra-umc-detection-hef")` を呼び出すため、`bump_version.py` が編集すべき箇所は常に 1 か所です。
* **オドメーター式のインクリメントは自動的に `PATCH`/`MINOR` にのみ触れます** —— `bump_version.py` は `PATCH` が 9 を超えると `MINOR` に、`MINOR` が 9 を超えると `MAJOR` に繰り上がりますが、`MAJOR` 自体を自動で増加させることは決してありません。`HYDRA-UMC-EDITOR-URDF/bump_version.py` および `HYDRA-UMC-SUITE/bump_version.py` と同じ慣例です。
* **ローカルの `.hef` ファイルが存在しないことはチェックサムの失敗にはなりません** —— レジストリが記述するファイルが `--models-dir` の下に存在しない場合、`verify_checksum()` はエラーではなく `None`（`False` ではない）を返し、`registry validate` はこれを "skipped" として報告します。レジストリは、このリポジトリに必ずしもチェックインされていない別のオブジェクトストアに存在しうるモデルを記述することを想定しています——実際に存在するファイルのチェックサムが本当に一致しない場合のみ、レジストリが壊れていることを示します。

---

## 📂 リポジトリ構成

```text
HYDRA-UMC-DETECTION-HEF/
├── src/                 # ソースコード（hydra_umc_detection_hef パッケージ）
│   └── hydra_umc_detection_hef/
│       ├── registry.py  # モデルレジストリ：スキーマ検証、バージョン管理、sha256 チェックサム
│       └── main.py      # CLI エントリポイント（素の呼び出し + `registry`）
├── tests/               # 実際の pytest スイート（registry、CLI）
├── docs/                # ドキュメントと検証レポート
├── build/               # ビルド出力（ローカルの .venv + 将来の HEF ツールチェーン出力）
├── images/              # メディアと図表
├── scripts/             # ユーティリティスクリプト
├── pyproject.toml       # パッケージメタデータ、依存関係、オドメーターバージョン
├── bump_version.py      # オドメーター式バージョンインクリメント（build.sh/.bat が実行）
├── build.sh / build.bat # venv + editable インストール + コンパイルチェック + テスト
├── run.sh / run.bat     # ローカル venv からエントリポイントを実行
└── CHANGELOG.md         # バージョンごとの履歴（オドメーター方式、日付なし）
```

`hardware/`、`firmware/`、`os/`、`models/` フォルダは存在しません——理由は
上記「高度な技術情報」を参照してください。`os/` と `models/` は統合親
プロジェクトである [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) にのみ存在します。本プロジェクト自身の `build/` は、その HEF ツールチェーン出力がそこに公開される前に到達する場所です。

---

## 🏗️ ビルドと実行

### 前提条件

* `PATH` 上に **Python 3.10 以降**があること（スクリプトは先に `python3` を試し、次に `python` にフォールバックします）。
* ONNX/Hailo Dataflow Compiler ツールは現時点では不要です——この段階では**サードパーティのランタイム依存関係が一切ありません**（`pyproject.toml` の `dependencies = []`）。
* ローカル仮想環境（`.venv/` 下）には数十 MB のディスク容量が必要です。

### ステップバイステップ

```bash
# Linux / macOS
./build.sh
```

1. **オドメーター式バージョンインクリメント** — `bump_version.py` を実行し、ビルドのたびに `pyproject.toml` 内の `PATCH` を増加させます（上記の規則に従って `MINOR`/`MAJOR` に繰り上がります）。
2. **仮想環境** — `.venv/` が存在しない場合は作成し、存在する場合は再利用します。
3. **Editable インストール** — `pip install -e ".[dev]"` により `src/` 下の変更が即座に反映され、`pytest` がインストールされ、`hydra-umc-detection-hef` コンソールエントリポイントが登録されます。
4. **コンパイルチェック** — `python -m compileall -q src` が `src/` 下の各ファイルをバイトコンパイルし、エコシステム全体にわたる構文エラーを検出します。
5. **実際のテストスイート** — `python -m pytest tests/ -q`（レジストリと CLI をカバーする 21 個のテスト）。

`set -euo pipefail` は最初に失敗したステップでスクリプトを停止させます。
5 つのステップすべてが成功した場合にのみビルドは成功を報告します。

```bash
./run.sh
```

`.venv` 内のインタープリタを特定し（POSIX と Windows 両方の `.venv`
ディレクトリ構造を処理）、`python -m hydra_umc_detection_hef.main` を
実行してすべての引数を転送します——素の呼び出しは名前・バージョン・役割
を表示します。

実際の例 —— レジストリを検証し、モデルの最新バージョンを検索する：

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

```bat
:: Windows - 手順は同じ、バッチ構文
build.bat
run.bat
```

### トラブルシューティング

* **`python`/`python3` が見つからない** —— Python 3.10+ をインストールし `PATH` に含まれていることを確認してください。
* **`compileall` が失敗する** —— `src/` 下に実際の構文エラーが導入されたことを意味します。ビルドは意図的にインストールに触れることなく停止します。
* **`run.sh`/`run.bat` が「`.venv` が見つかりません」と表示する** —— 先に少なくとも 1 回 `build.sh`/`build.bat` を実行してください。
* **editable インストールが古いままになる** —— `.venv/` を削除して再構築してください。これが必要になることはまれです。

---

## 🚀 現在の状況と次のステップ

**今日実現していること：** モデルレジストリ——スキーマ検証、重複バージョンの検出、最新バージョンの検索、sha256 による整合性検証（`registry.py`、21 個のテスト）——に加え、検証済みのエントリポイントを持つ実際のインストール
可能な Python パッケージ、そしてビルドに組み込まれた
オドメーター式バージョンインクリメント。実際に取得されたビルド/実行出力については
[`CHANGELOG.md`](CHANGELOG.md) を参照してください。

**まだ残っている作業（順不同、確定した期限なし、実際の Hailo ハードウェアに阻まれている）：**

* 訓練済みの PyTorch/YOLO モデルからの実際の ONNX エクスポートステップ。
* INT8/INT4 量子化のための Hailo Dataflow Compiler 統合。
* HAR/HEF パッケージング——これが実現すれば、本プロジェクトの `registry.py` が既に読み取り・検証できるレジストリファイルを実際に埋めることになります。
* コンパイルされた `.hef` 出力を [HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE) の `models/` フォルダへ公開すること。

---

## 🔗 関連プロジェクト

本プロジェクトは、同一著者（JuanenRac / Electro Hobby 3D）による、
ファームウェア、制御ソフトウェア、AI ノード、フリート管理ツールにまたがる、
より大きなロボティクスエコシステムの一部です。ご要望が実際にはこれらの
プロジェクトのいずれかに関するものであり、本リポジトリのものではない
可能性もあるため、知っておく価値があります。

### プロジェクトファミリー

**親プロジェクト：** **[HYDRA-UMC-VISION-NODE](https://github.com/JuanenRac/HYDRA-UMC-VISION-NODE)** —— これらの HEF モデルをその Hailo-8 NPU にロードする統合親プロジェクト。

**兄弟プロジェクト：**
- **[HYDRA-UMC-VISION-STREAMER](https://github.com/JuanenRac/HYDRA-UMC-VISION-STREAMER)** — 親プロジェクトが消費するカメラフィードをキャプチャし前処理します。
- **[HYDRA-UMC-SAFETY-ZONES](https://github.com/JuanenRac/HYDRA-UMC-SAFETY-ZONES)** — 本プロジェクトでコンパイルされたモデルを使用し、親プロジェクトの知覚結果を侵入検知と E-STOP トリガーに変換します。
- **[HYDRA-UMC-VISUAL-SERVOING-API](https://github.com/JuanenRac/HYDRA-UMC-VISUAL-SERVOING-API)** — 親プロジェクトの知覚結果を運動学的な姿勢補正に変換します。

### 直接関連（ファミリー外）

- **[URTC](https://github.com/JuanenRac/URTC)** — URTC 自身の工具ヘッドの視覚認識は、本プロジェクトでコンパイルされたモデルに依存しています。

### エコシステムのその他のプロジェクト

**HYDRA-UMC プラットフォーム** — マルチロボット・マイクロファクトリーセル
- **[HYDRA-UMC](https://github.com/JuanenRac/HYDRA-UMC)** — 最大 8 台のロボットアームを統括する CM5 + STM32H745 マザーボード。
- **[HYDRA-UMC-SERVER](https://github.com/JuanenRac/HYDRA-UMC-SERVER)** — すべての制御クライアントが接続する Express/WebSocket バックエンド。
- **[HYDRA-UMC-STUDIO](https://github.com/JuanenRac/HYDRA-UMC-STUDIO)** — Web ベースの制御ダッシュボード、マルチロボット 3D 可視化。
- **[HYDRA-UMC-ANDROID-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-ANDROID-CONTROL)** — Wi-Fi/Bluetooth 経由の Android 制御アプリ。
- **[HYDRA-UMC-IOS-CONTROL](https://github.com/JuanenRac/HYDRA-UMC-IOS-CONTROL)** — Flutter で構築された iOS/iPadOS 制御アプリ。
- **[HYDRA-UMC-SUITE](https://github.com/JuanenRac/HYDRA-UMC-SUITE)** — デスクトップ版群制御コマンドセンター（Python/PySide6）。
- **[HYDRA-UMC-EDITOR-URDF](https://github.com/JuanenRac/HYDRA-UMC-EDITOR-URDF)** — ロボットカタログ向けのデスクトップ版 URDF モデルエディター。
- **[HYDRA-UMC-DSI](https://github.com/JuanenRac/HYDRA-UMC-DSI)** — 機載 DSI タッチスクリーン用のネイティブタッチ UI。

**URTC プラットフォーム** — すべての HYDRA-UMC ロボットアームが搭載するツールヘッドコントローラー
- **[URTC-FLASHER](https://github.com/JuanenRac/URTC-FLASHER)** — デスクトップ版 CAN-OTA + SWD/JTAG フラッシュツール。
- **[URTC-TESTER](https://github.com/JuanenRac/URTC-TESTER)** — デスクトップ版ライブ CAN バス診断ツール。
- **[URTC-WEB-STUDIO](https://github.com/JuanenRac/URTC-WEB-STUDIO)** — Web Serial API によるブラウザベースの代替版。

**🧠 認知 AI ノード（Hailo-10）**
- [HYDRA-UMC-COGNITIVE-NODE](https://github.com/JuanenRac/HYDRA-UMC-COGNITIVE-NODE)
- [HYDRA-UMC-VLA-ENGINE](https://github.com/JuanenRac/HYDRA-UMC-VLA-ENGINE)
- [HYDRA-UMC-VOICE-UI](https://github.com/JuanenRac/HYDRA-UMC-VOICE-UI)
- [HYDRA-UMC-SEMANTIC-PLANNER](https://github.com/JuanenRac/HYDRA-UMC-SEMANTIC-PLANNER)
- [HYDRA-UMC-DOCS-QA](https://github.com/JuanenRac/HYDRA-UMC-DOCS-QA)

**🐝 オーケストレーションと群制御**
- [HYDRA-UMC-ORCHESTRATOR](https://github.com/JuanenRac/HYDRA-UMC-ORCHESTRATOR)
- [HYDRA-UMC-SWARM-SYNC](https://github.com/JuanenRac/HYDRA-UMC-SWARM-SYNC)
- [HYDRA-UMC-PATH-PLANNER-3D](https://github.com/JuanenRac/HYDRA-UMC-PATH-PLANNER-3D)
- [HYDRA-UMC-JOB-DISPATCHER](https://github.com/JuanenRac/HYDRA-UMC-JOB-DISPATCHER)
- [HYDRA-UMC-NODE-HEALING](https://github.com/JuanenRac/HYDRA-UMC-NODE-HEALING)

**🎮 デジタルツインとシミュレーション**
- [HYDRA-UMC-TWIN](https://github.com/JuanenRac/HYDRA-UMC-TWIN)
- [HYDRA-UMC-PHYSICS-REPLICA](https://github.com/JuanenRac/HYDRA-UMC-PHYSICS-REPLICA)
- [HYDRA-UMC-HIL-BRIDGE](https://github.com/JuanenRac/HYDRA-UMC-HIL-BRIDGE)
- [HYDRA-UMC-SYNTHETIC-DATA-GEN](https://github.com/JuanenRac/HYDRA-UMC-SYNTHETIC-DATA-GEN)

**📊 データと分析**
- [HYDRA-UMC-DATALAKE](https://github.com/JuanenRac/HYDRA-UMC-DATALAKE)
- [HYDRA-UMC-TELEMETRY-COLLECTOR](https://github.com/JuanenRac/HYDRA-UMC-TELEMETRY-COLLECTOR)
- [HYDRA-UMC-ANOMALY-DETECTOR](https://github.com/JuanenRac/HYDRA-UMC-ANOMALY-DETECTOR)
- [HYDRA-UMC-PRODUCTION-REPORTS](https://github.com/JuanenRac/HYDRA-UMC-PRODUCTION-REPORTS)

**🏭 産業用ゲートウェイ**
- [HYDRA-UMC-GATEWAY-INDUSTRIAL](https://github.com/JuanenRac/HYDRA-UMC-GATEWAY-INDUSTRIAL)
- [HYDRA-UMC-OPCUA-SERVER](https://github.com/JuanenRac/HYDRA-UMC-OPCUA-SERVER)
- [HYDRA-UMC-MQTT-BROKER](https://github.com/JuanenRac/HYDRA-UMC-MQTT-BROKER)
- [HYDRA-UMC-MTCONNECT-ADAPTER](https://github.com/JuanenRac/HYDRA-UMC-MTCONNECT-ADAPTER)

**🛠️ 補完ツール**
- [URTC-SMART-RACK](https://github.com/JuanenRac/URTC-SMART-RACK)
- [URTC-VISION-TOOL](https://github.com/JuanenRac/URTC-VISION-TOOL)
- [HYDRA-UMC-WATCH](https://github.com/JuanenRac/HYDRA-UMC-WATCH)
- [HYDRA-UMC-TOOL-CLI](https://github.com/JuanenRac/HYDRA-UMC-TOOL-CLI)
- [HYDRA-UMC-DASHBOARD-AI](https://github.com/JuanenRac/HYDRA-UMC-DASHBOARD-AI)

---

## 👤 作者
**JuanenRac**（Electro Hobby 3D）
📧 electrohobby3d@gmail.com

## 📜 ライセンス
GPL-3.0 —— 詳細は LICENSE を参照してください。
