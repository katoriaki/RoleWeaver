# RoleWeaver

**言語:** [English](README.md) | [中文](README.zh-CN.md) | 日本語

RoleWeaver は、ベース LLM、任意の LoRA adapter、任意の role skill を組み合わせ、永続的なセッション記憶、ChatGPT 風ローカル Web UI、LoRA 学習補助ツールを備えたローカル・ロールチャット実行環境です。

## 最新アップデート

2026-04-29:

- Vue ベースの一体型コンソールを追加し、チャット、設定、記憶、学習、LINE/TTS/公開 URL、評価、フローを明確なページに分けました。
- Planning ページを追加しました。端末時刻、場所、キャラクターの週間予定、現在の生活状態、参考資料、簡易 Web 検索を表示します。
- memory + reflection + planning 層を追加しました。role mode では現在時刻・場所・予定 context を渡しますが、persona kernel や公式設定を上書きしません。
- Persona Anchor Replay を追加しました。`SKILL.md` の近くにある短い人格アンカーを読み込み、長対話での persona drift を抑えるための校正 context として使います。
- 単一 GPU 常駐向けのバックグラウンド・スケジューラを追加しました。planning 更新、記憶 snapshot、非アクティブモデル解放などの軽量処理はアイドル時間に実行でき、LLM を使う処理は明示的に許可するまで無効です。
- 制御されたツール層を追加しました。`/tools`、`/tools/run`、`/tools/actions` から時刻、planning、記憶、バックグラウンド、LINE/Tunnel、学習状態などのホワイトリスト済みツールを呼び出し、ログに残せます。
- Shiro Bridge を追加しました。独立した `shiro/` プロジェクトから cognitive context を任意で読み込み、会話後に stimulus を書き戻し、Web コンソールに「白」状態ページを表示できます。
- Shiro M6.3 の第一版として、PDF 読み取りと Web 検索のツール意図を追加し、RoleWeaver ツール層に `document.pdf_read` を追加しました。
- モデル-LoRA-Skill ごとの memory scope に `planning/weekly_schedule.json` を保存し、週ごとに自動生成できます。
- LINE Bot 設定、起動/停止、Cloudflare 一時公開 URL の API を追加しました。
- 秦谷美鈴の `persona_kernel.json` を現行 schema に合わせて再生成しました。

完全な更新告知は [CHANGELOG.md](CHANGELOG.md) を参照してください。

## 機能概要

- ローカルのベースモデルパスからロールチャットを実行します。
- `lora_path` が指定されている場合は LoRA を読み込み、空欄の場合はベースモデルのみで動きます。
- ロール挙動は `SKILL.md` または短い inline skill で指定できます。
- `4bit`、`8bit`、`bf16`、`fp16`、非量子化ロードに対応します。
- 記憶は `memory/` に保存され、ベースモデル、LoRA、skill、セッションごとに分離されます。
- FastAPI API、ブラウザ UI、CLI、bot 連携の土台を提供します。
- 明文化された設計契約に従います。キャラクターの自律性は、ペルソナ一貫性、長期記憶、タスク完了、プラットフォーム形式適応より優先されます。詳しくは [docs/DESIGN_PRINCIPLES.md](docs/DESIGN_PRINCIPLES.md) を参照してください。
- `SKILL.md` の近くに `persona_kernel.json` がある場合は自動的に読み込みます。通常ユーザーが指定するパスは引き続き `SKILL.md` だけです。
- `SKILL.md` の近くに `anchors/anchors.jsonl` がある場合は人格アンカーも自動的に読み込みます。詳しくは [Persona Anchors Design](docs/ANCHORS.zh-CN.md) を参照してください。
- キャラクター自律性、メディア適応、記憶境界の退行を確認する初期 persona regression harness を含みます。

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
- `local_location` 任意。Planning が想定する場所。例: `Tokyo, Japan`
- `ui_language`: `zh`、`ja`、`en`
- `background_jobs_enabled`: 軽量バックグラウンド処理を有効化
- `background_llm_enabled`: バックグラウンドでローカルモデルを使うか。単一 GPU では既定の `false` 推奨

Windows ランチャー:

```powershell
setup_runtime.bat
```

以後、`start_roleweaver.bat` と `line/start_line_bot.bat` は `runtime\Scripts\python.exe` を優先して使います。

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
- Planning 状態と週間ロール予定の確認・再生成。
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

### `GET /planning/{session_id}`

指定セッションの planning 状態を返します。Planning はモデル-LoRA-Skill の memory scope ごとに分離され、別キャラクターの予定とは混ざりません。

主なレスポンス項目:

- `device_context`: 端末の現在時刻、日付、UTC offset、タイムゾーン、場所。
- `schedule`: `planning/weekly_schedule.json` に保存される週間ロール予定。
- `current_context`: role mode の prompt に渡される制限付き planning context。
- `current_anchor`: `SKILL.md` の近くに `anchors/anchors.jsonl` がある場合に選ばれる人格アンカー。
- `current_anchor_context`: 新しい記憶ではないことを明示した制限付き anchor context。
- `sources`: 予定設計に使った参考資料。

### `POST /planning/{session_id}/regenerate`

現在の memory scope の週間予定を再生成します。セッションディレクトリの対応は変更しません。

### `GET /planning/search`

Web コンソール用の簡易検索です。日程、祝日、学校生活などの参考資料探しに使います。

例:

```text
/planning/search?q=Japan high school daily schedule club activities&limit=5
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
- `local_location`
- `background_jobs_enabled`
- `background_llm_enabled`
- `background_idle_seconds`
- `background_window_start`
- `background_window_end`
- `background_max_minutes`
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
  "local_location": "Tokyo, Japan",
  "background_jobs_enabled": true,
  "background_llm_enabled": false,
  "background_idle_seconds": 600,
  "background_window_start": "02:00",
  "background_window_end": "05:30",
  "background_max_minutes": 20,
  "ui_language": "ja"
}
```

すべての項目は任意です。省略した項目は現在値を維持します。

### `GET /background/status`

単一 GPU 常駐向けバックグラウンド・スケジューラの状態を返します。`idle_seconds`、`eligible_non_llm`、`eligible_llm`、`active_job`、`recent_jobs` を確認できます。

### `POST /background/pause`

バックグラウンド処理を一時停止します。

### `POST /background/resume`

バックグラウンド処理を再開します。

### `POST /background/run-once`

バックグラウンド処理を1回だけ手動実行します。`force=true` は idle/time-window 制限だけを無視し、`background_llm_enabled=false` は無視しません。

```json
{
  "job_type": "planning_regenerate",
  "session_id": "web",
  "force": true
}
```

対応 job: `planning_regenerate`、`memory_os_snapshot`、`memory_consolidation`、`release_inactive_models`。

### `GET /tools`

現在登録されているホワイトリスト済みツールを返します。

### `POST /tools/run`

ツールを1回実行し、`data/tool_actions/actions.jsonl` に記録します。

```json
{
  "tool_name": "memory.search",
  "session_id": "web",
  "actor": "user",
  "arguments": {
    "query": "カレー",
    "top_k": 5
  }
}
```

### `GET /tools/actions`

最近のツール呼び出しを返します。設計は [docs/TOOL_LAYER.zh-CN.md](docs/TOOL_LAYER.zh-CN.md) を参照してください。

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
