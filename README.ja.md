# RoleWeaver

**言語:** [English](README.md) | [中文](README.zh-CN.md) | 日本語

RoleWeaver は、ベース LLM、任意の LoRA adapter、任意の role skill を組み合わせ、永続的なセッション記憶、ChatGPT 風ローカル Web UI、LoRA 学習補助ツールを備えたローカル・ロールチャット実行環境です。

## 最新アップデート

2026-04-27:

- Windows ランチャーは `127.0.0.1:8000` で既に RoleWeaver が動いている場合、その既存サーバーを開きます。8000 が別プロセスで使われている場合は `8001-8020` の空きポートを自動選択します。
- ローカル Training パネルが Excel、CSV、標準 JSONL データセットに対応しました。
- `resources/qwen35_lora_training/role_sft_template.xlsx` を追加しました。列は `user` と `assistant` の 2 列です。
- 編集可能なチャット表示名を追加しました。内部 `session_id` は UI から隠し、従来通り memory フォルダの対応に使います。
- 履歴チャットの復元、名前変更、削除、セッション別 Settings snapshot に対応しました。

完全な更新告知は [CHANGELOG.md](CHANGELOG.md) を参照してください。

## 機能概要

- ローカルのベースモデルパスからロールチャットを実行します。
- `lora_path` が指定されている場合は LoRA を読み込み、空欄の場合はベースモデルのみで動きます。
- ロール挙動は `SKILL.md` または短い inline skill で指定できます。
- `4bit`、`8bit`、`bf16`、`fp16`、非量子化ロードに対応します。
- 記憶は `memory/` に保存され、ベースモデル、LoRA、skill、セッションごとに分離されます。
- FastAPI API、ブラウザ UI、CLI、bot 連携の土台を提供します。

## クイックスタート

設定テンプレートをコピーします。

```powershell
copy roleweaver.config.example.csv roleweaver.config.csv
```

Excel、Web Settings パネル、またはテキストエディタで以下を入力します。

- `base_model_path`
- `lora_path` 任意。空欄ならベースモデルのみ
- `skill_file` 任意
- `skill_text` 任意の短い inline skill
- `quantization_mode` 既定は `4bit`
- `ui_language`: `zh`、`ja`、`en`

Windows ランチャー:

```powershell
start_roleweaver.bat
```

CLI:

```powershell
python local_chat.py --config roleweaver.config.csv
```

## Windows ランチャーと Web UI

プロジェクトルートで `start_roleweaver.bat` をダブルクリックします。

ランチャーは以下を行います。

- `roleweaver.config.csv` がなければ example から作成します。
- 有効な Python 環境に `fastapi` と `uvicorn` がない場合はインストールを提案します。
- `127.0.0.1:8000` で既に RoleWeaver が動作していれば、そのページを開きます。
- そうでない場合は 8000、または 8001 から 8020 の空きポートで起動します。
- ローカル Web UI をブラウザで開きます。

Web UI は以下に対応します。

- 中国語、日本語、英語の UI 表示。
- ベースモデル、LoRA、skill ファイル、inline skill、量子化方式、UI 言語の設定。
- 履歴チャットの復元。
- 表示名の編集。memory フォルダ名は変更しません。
- 確認後の履歴削除。
- Exit またはページクローズ時の記憶整理。
- Excel、CSV、JSONL を使ったローカル LoRA 学習。

## HTTP API

API を手動起動します。

```powershell
python API.py --config roleweaver.config.csv --host 127.0.0.1 --port 8000
```

### `GET /`

`web/index.html` のローカル Web UI を返します。

### `GET /health`

実行状態と現在のモデル設定を返します。

任意 query:

- `session_id`: 指定した場合、そのセッションに保存された settings snapshot で状態を確認します。

主なレスポンス項目:

- `status`
- `role_name`
- `base_model_path`
- `lora_path`
- `lora_enabled`
- `skill_file`
- `skill_text_present`
- `quantization_mode`
- `memory_root`
- `memory_scope_path`

### `POST /chat`

1 回分の assistant 応答を生成します。

リクエスト:

```json
{
  "user_text": "こんにちは",
  "session_id": "web",
  "max_new_tokens": 160
}
```

レスポンス:

```json
{
  "text": "...",
  "session_id": "web"
}
```

### `GET /chat`

`POST /chat` の query 版です。

例:

```text
/chat?user_text=こんにちは&session_id=api&max_new_tokens=120
```

### `POST /consolidate/{session_id}`

指定セッションの記憶整理を実行します。pending turns から有用な情報を episodic memory、graph facts、profile facts に反映します。

レスポンス:

```json
{
  "result": {}
}
```

### `GET /config`

現在の編集可能な設定を返します。

レスポンス項目:

- `config_file`
- `base_model_path`
- `lora_path`
- `skill_file`
- `skill_text`
- `quantization_mode`
- `ui_language`

### `POST /config`

`roleweaver.config.csv` を更新し、プロセス内 service cache をクリアします。次のチャットから新しい設定でモデルを読み込みます。

リクエスト:

```json
{
  "base_model_path": "C:\\models\\base",
  "lora_path": "C:\\models\\adapter",
  "skill_file": "C:\\roles\\SKILL.md",
  "skill_text": "",
  "quantization_mode": "4bit",
  "ui_language": "ja"
}
```

すべての項目は任意です。省略した項目は現在値を維持します。

### `GET /sessions`

`memory/` から検出された永続セッション一覧を返します。

各項目:

- `session_id`: 内部 ID。ディレクトリと API 呼び出しに使います。
- `display_name`: ユーザー向け表示名。
- `created_ts`
- `updated_ts`
- `session_path`
- `memory_scope_path`
- `settings_snapshot`
- `warnings`: モデル、LoRA、skill パス欠落など。

### `POST /sessions`

現在のベースモデル/LoRA/skill の memory scope に新規セッションを作成します。フォルダは timestamp ベースで、表示名は別に保存されます。

### `GET /sessions/{session_id}`

1 つのセッションを読み込みます。transcript と settings snapshot を含みます。

`GET /sessions` の項目に加えて:

- `messages`
- `config`

### `PATCH /sessions/{session_id}`

ユーザー向け表示名だけを変更します。セッションフォルダ名や内部 `session_id` は変更しません。

リクエスト:

```json
{
  "display_name": "ロールテスト"
}
```

### `DELETE /sessions/{session_id}`

`memory/` 内の該当ローカルセッションフォルダを削除します。Web UI はこの API を呼ぶ前に確認を出します。

### `POST /training/start`

ローカル LoRA 学習をバックグラウンドプロセスとして開始します。Web API 経由では同時に 1 つの学習ジョブのみ実行できます。

リクエスト:

```json
{
  "model_path": "C:\\models\\base",
  "data_file": "C:\\datasets\\role_sft.xlsx",
  "output_dir": ".\\outputs\\your-role-lora",
  "epochs": 3,
  "learning_rate": 0.0001,
  "per_device_train_batch_size": 2,
  "gradient_accumulation_steps": 8,
  "save_steps": 50,
  "save_total_limit": 2,
  "logging_steps": 10,
  "lora_r": 16,
  "lora_alpha": 32,
  "lora_dropout": 0.05,
  "online": false
}
```

対応する `data_file`:

- `.xlsx`、`.xlsm`、`.xltx`: 1 枚目のシート。1 行目は `user | assistant`、2 行目以降がデータ。
- `.csv`: 1 行目は `user,assistant`。
- `.jsonl`: 標準 messages JSONL。

Excel と CSV は学習前に `training_runs/<run_id>/converted_dataset.jsonl` に変換されます。

### `GET /training/status`

現在または直近の学習ジョブ状態を返します。

レスポンス項目:

- `active`
- `run_id`
- `status`: `idle`、`running`、`completed`、`failed`
- `returncode`
- `started_ts`
- `command`
- `log_path`
- `log_tail`
- `message`

### `POST /training/stop`

現在の学習サブプロセスの終了を要求します。

### `GET /training/template`

`resources/qwen35_lora_training/role_sft_template.xlsx` をダウンロードします。

## 学習データ

最も簡単な入力は Excel テンプレートです。

[resources/qwen35_lora_training/role_sft_template.xlsx](resources/qwen35_lora_training/role_sft_template.xlsx)

表形式:

```text
user       | assistant
こんにちは | こんにちは...
```

手動変換:

```powershell
python resources\qwen35_lora_training\convert_excel_to_jsonl.py `
  --input "C:\datasets\role_sft.xlsx" `
  --output "C:\datasets\role_sft.jsonl"
```

手動学習:

```powershell
python resources\qwen35_lora_training\train_qwen35_lora_offline.py `
  --model-path "C:\models\base-model" `
  --data-file "C:\datasets\role_sft.jsonl" `
  --output-dir ".\outputs\your-role-lora"
```

Qwen 系 thinking model 向けに、trainer は SFT テキスト生成時に thinking タグを無効化します。

## 記憶システム

RoleWeaver の記憶は以下のように保存されます。

```text
memory/
  base__lora__skill__hash/
    session-id/
      short_term/
        session_meta.json
        settings_snapshot.json
        transcript.jsonl
        memory_state_v1.json
      long_term/
        memories_v2.json
        memories_v2.faiss
      graph/
        knowledge_graph_v1.json
        user_profile_v1.json
```

記憶は以下で構成されます。

- 直近対話状態: すぐの文脈を保ちます。
- episodic memory: 選別された長期イベントや好みを保存します。
- graph memory: 構造化された事実を保存します。
- profile projection: コンパクトなユーザー文脈を生成します。

embedding 依存関係や embedding model が利用できない場合、検索は lexical search にフォールバックし、チャットサービスは停止しません。

## Bot 連携

### LINE

LINE アプリは `line/` にあります。

```powershell
uvicorn line.app:app --host 0.0.0.0 --port 8000
```

エンドポイント:

- `GET /health`
- `POST /callback`

### QQ Voice Bot

QQ 音声返信連携は `QQbot/` にあります。QQ bot event、リモート RoleWeaver text API への SSH、ローカル GPT-SoVITS 合成を組み合わせます。

```powershell
python -m QQbot.main --config QQbot\qq_voice_bot.config.csv
```

最小リモート text API:

- `GET /health`
- `POST /chat`

## 注意

- `roleweaver.config.csv` は git ignore され、ローカルモデルパスをコミットしません。
- `memory/`、`training_runs/`、生成出力は git ignore されています。
- このプロジェクトは現時点で実用的なローカルフレームワークですが、完全な packaged desktop app ではありません。
