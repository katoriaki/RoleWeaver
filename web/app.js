const { createApp, nextTick } = Vue;

const I18N = {
  zh: {
    appSubtitle: "本地角色智能体控制台",
    overview: "总览",
    chat: "聊天",
    runtime: "角色运行时",
    memory: "记忆 OS",
    training: "训练",
    line: "LINE / TTS / 公网",
    planning: "日程规划",
    evaluation: "评测",
    docs: "流程",
    online: "在线",
    offline: "离线",
    refresh: "刷新",
    save: "保存",
    start: "启动",
    stop: "停止",
    send: "发送",
    delete: "删除",
    close: "关闭",
    copy: "复制",
    copied: "已复制",
    requestFailed: "请求失败",
    saved: "已保存",
    loading: "读取中",
    overviewTitle: "一站式入口",
    overviewBody: "从这里完成模型配置、会话、记忆、训练、LINE、TTS 和临时公网地址。每个模型/LoRA/Skill 组合会进入各自的记忆空间。",
    health: "运行状态",
    role: "角色",
    model: "模型",
    lora: "LoRA",
    skill: "Skill",
    quantization: "量化",
    memoryScope: "记忆空间",
    flowTitle: "运行流程",
    flowInput: "用户输入",
    flowInputDesc: "Web / LINE / 图片 / 语音请求",
    flowSurface: "表层适配",
    flowSurfaceDesc: "只改变媒介格式，不改变人格",
    flowRuntime: "角色运行时",
    flowRuntimeDesc: "底模 + 可选 LoRA + SKILL.md",
    flowMemory: "记忆 OS",
    flowMemoryDesc: "按模型、LoRA、Skill 和会话隔离",
    flowOutput: "回复输出",
    flowOutputDesc: "文本、LINE、TTS 或看图回复",
    memoryFlowTitle: "记忆分层流程",
    shortTerm: "短时",
    midTerm: "中期",
    longTerm: "长期",
    graph: "图谱",
    reflection: "反思",
    contradiction: "矛盾链",
    chatTitle: "角色聊天",
    chatBody: "这里保留最常用的聊天入口，支持恢复历史、改名、删除、发图和手动整理记忆。",
    chatName: "会话名称",
    maxTokens: "最大生成 token",
    newChat: "新会话",
    history: "历史会话",
    noHistory: "暂无历史会话",
    promptPlaceholder: "给角色发送消息，Enter 发送，Shift+Enter 换行",
    attachImage: "附图",
    imageSelected: "已选择图片",
    consolidate: "整理记忆",
    thinking: "正在思考...",
    runtimeTitle: "角色运行时设置",
    runtimeBody: "先决定模型身份，再进入会话。这个组合会决定记忆空间：底模、LoRA、Skill 变了，记忆也应该隔离。",
    baseModelPath: "底模路径",
    loraPath: "LoRA adapter 路径",
    loraNote: "留空就不加载 LoRA，直接用底模启动。",
    skillFile: "SKILL.md 路径",
    inlineSkill: "内联 Skill",
    inlineSkillPlaceholder: "少量补充设定、边界、语气。复杂角色建议使用 SKILL.md。",
    deviceMap: "设备放置",
    modelLoader: "模型加载器",
    contextWindow: "上下文窗口 token",
    uiLanguage: "界面语言",
    memoryTitle: "记忆 OS",
    memoryBody: "查看和编辑当前会话的长期记忆、证据、矛盾链、生命周期。非 active 记忆不会进入实时召回。",
    statusFilter: "状态筛选",
    all: "全部",
    loadMemories: "读取记忆",
    memoryOs: "Memory OS 摘要",
    noMemories: "暂无记忆",
    reason: "原因",
    evidence: "证据",
    links: "链接",
    lifecycle: "生命周期",
    markActive: "设为 active",
    markStale: "设为 stale",
    markContradicted: "设为 contradicted",
    archive: "归档",
    trainingTitle: "LoRA 训练",
    trainingBody: "用户只需要准备 Excel/CSV/JSONL。Excel 模板第一行是 user 和 assistant，第二行开始自动转标准 messages JSONL。",
    downloadTemplate: "下载 Excel 模板",
    trainModelPath: "原始模型路径",
    trainDataFile: "训练文件",
    trainOutputDir: "输出目录",
    epochs: "轮数",
    learningRate: "学习率",
    batchSize: "批大小",
    gradAccum: "梯度累积",
    allowOnline: "允许联网下载 Hugging Face 资源",
    startTraining: "开始训练",
    stopTraining: "停止训练",
    trainingStatus: "训练状态",
    lineTitle: "LINE / TTS / 临时公网地址",
    lineBody: "LINE 控制台需要 HTTPS Webhook。你可以在这里启动本地 LINE bot，再生成临时 Cloudflare 地址，把中间显示的 Webhook URL 填回 LINE 控制台。",
    lineRuntime: "LINE bot 运行",
    lineHost: "监听地址",
    linePort: "端口",
    startLine: "启动 LINE bot",
    stopLine: "停止 LINE bot",
    tunnelTitle: "临时公网地址",
    tunnelTarget: "转发目标",
    generateTunnel: "生成临时 HTTPS 地址",
    stopTunnel: "停止临时地址",
    webhookUrl: "填入 LINE 控制台的 Webhook URL",
    tunnelHint: "这是临时地址。关闭 cloudflared 或重启后地址会变，需要重新复制到 LINE 控制台。",
    envFile: "LINE .env",
    envText: "环境变量",
    policyFile: "表层策略 JSON",
    policyText: "LINE/TTS/图片/起床策略",
    saveLineSettings: "保存 LINE/TTS 设置",
    ttsCommand: "TTS 启动命令",
    ttsCommandText: "双击 G\\start_roleweaver_tts_api.bat，或在终端运行该脚本。",
    evaluationTitle: "Persona 评测",
    evaluationBody: "低成本检查回复是否保持身份、自主性和媒介适配。更完整的长对话评测仍放在 eval/persona_regression 脚本中运行。",
    userProbe: "用户输入",
    assistantProbe: "模型回复",
    category: "评测类别",
    surface: "媒介",
    score: "评分",
    runScore: "运行规则评分",
    regressionCommands: "回归测试命令",
    docsTitle: "流程设计",
    docsBody: "RoleWeaver 的每条流程都先确定角色组合，再进入对应记忆空间。LINE、TTS、图片只是媒介适配层，不能覆盖角色人格。",
    planningTitle: "角色日程与 Planning",
    planningBody: "每个模型/LoRA/Skill 组合都有自己的周计划。系统读取设备时间、时区和本地地点，把角色当天的生活状态注入回复，但不写入长期记忆。",
    deviceTime: "设备时间",
    localLocation: "本地地点",
    regenerateSchedule: "重新生成本周日程",
    currentPlanningContext: "当前 planning context",
    currentAnchor: "当前人格锚点",
    anchorContext: "人格锚点 context",
    weeklySchedule: "本周日程",
    referenceSources: "参考来源",
    webSearch: "网络查找",
    searchPlaceholder: "搜索参考资料，例如：日本 高校 部活动 日程",
    runSearch: "搜索",
    searchResults: "搜索结果",
  },
  ja: {
    appSubtitle: "ローカル役割エージェント制御コンソール",
    overview: "概要",
    chat: "チャット",
    runtime: "役割ランタイム",
    memory: "記憶 OS",
    training: "訓練",
    line: "LINE / TTS / 公開URL",
    planning: "予定",
    evaluation: "評価",
    docs: "フロー",
    online: "オンライン",
    offline: "オフライン",
    refresh: "更新",
    save: "保存",
    start: "開始",
    stop: "停止",
    send: "送信",
    delete: "削除",
    close: "閉じる",
    copy: "コピー",
    copied: "コピーしました",
    requestFailed: "リクエスト失敗",
    saved: "保存しました",
    loading: "読み込み中",
    overviewTitle: "一体型入口",
    overviewBody: "モデル設定、会話、記憶、訓練、LINE、TTS、一時公開URLを同じ画面で管理します。モデル/LoRA/Skill の組み合わせごとに記憶空間を分けます。",
    health: "状態",
    role: "役割",
    model: "モデル",
    lora: "LoRA",
    skill: "Skill",
    quantization: "量子化",
    memoryScope: "記憶空間",
    flowTitle: "実行フロー",
    flowInput: "ユーザー入力",
    flowInputDesc: "Web / LINE / 画像 / 音声要求",
    flowSurface: "表層適応",
    flowSurfaceDesc: "媒体だけを変え、人格は変えない",
    flowRuntime: "役割ランタイム",
    flowRuntimeDesc: "ベースモデル + 任意 LoRA + SKILL.md",
    flowMemory: "記憶 OS",
    flowMemoryDesc: "モデル、LoRA、Skill、会話ごとに分離",
    flowOutput: "出力",
    flowOutputDesc: "テキスト、LINE、TTS、画像応答",
    memoryFlowTitle: "記憶レイヤー",
    shortTerm: "短期",
    midTerm: "中期",
    longTerm: "長期",
    graph: "グラフ",
    reflection: "反省",
    contradiction: "矛盾リンク",
    chatTitle: "役割チャット",
    chatBody: "履歴復元、名前変更、削除、画像送信、記憶整理に対応した通常チャット入口です。",
    chatName: "会話名",
    maxTokens: "最大生成 token",
    newChat: "新規会話",
    history: "履歴",
    noHistory: "履歴はありません",
    promptPlaceholder: "メッセージを入力。Enter 送信、Shift+Enter 改行",
    attachImage: "画像",
    imageSelected: "画像を選択しました",
    consolidate: "記憶整理",
    thinking: "考えています...",
    runtimeTitle: "役割ランタイム設定",
    runtimeBody: "まずモデルの組み合わせを決めます。この組み合わせが記憶空間を決めます。",
    baseModelPath: "ベースモデルパス",
    loraPath: "LoRA adapter パス",
    loraNote: "空欄なら LoRA を読み込まず、ベースモデルだけで起動します。",
    skillFile: "SKILL.md パス",
    inlineSkill: "インライン Skill",
    inlineSkillPlaceholder: "短い補足設定、境界、口調。複雑な役割は SKILL.md 推奨。",
    deviceMap: "デバイス配置",
    modelLoader: "モデルローダー",
    contextWindow: "コンテキスト token",
    uiLanguage: "表示言語",
    memoryTitle: "記憶 OS",
    memoryBody: "現在の会話の長期記憶、証拠、矛盾リンク、ライフサイクルを確認します。",
    statusFilter: "状態フィルター",
    all: "すべて",
    loadMemories: "記憶を読む",
    memoryOs: "Memory OS 概要",
    noMemories: "記憶はありません",
    reason: "理由",
    evidence: "証拠",
    links: "リンク",
    lifecycle: "ライフサイクル",
    markActive: "active にする",
    markStale: "stale にする",
    markContradicted: "contradicted にする",
    archive: "アーカイブ",
    trainingTitle: "LoRA 訓練",
    trainingBody: "Excel/CSV/JSONL を指定できます。Excel は user と assistant の2列テンプレートから自動変換します。",
    downloadTemplate: "Excel テンプレート",
    trainModelPath: "元モデルパス",
    trainDataFile: "訓練ファイル",
    trainOutputDir: "出力先",
    epochs: "エポック",
    learningRate: "学習率",
    batchSize: "バッチ",
    gradAccum: "勾配累積",
    allowOnline: "Hugging Face への接続を許可",
    startTraining: "訓練開始",
    stopTraining: "訓練停止",
    trainingStatus: "訓練状態",
    lineTitle: "LINE / TTS / 一時公開URL",
    lineBody: "LINE コンソールには HTTPS Webhook が必要です。ここで LINE bot を起動し、一時 Cloudflare URL を作り、中央の Webhook URL を LINE に貼り付けます。",
    lineRuntime: "LINE bot 実行",
    lineHost: "ホスト",
    linePort: "ポート",
    startLine: "LINE bot 起動",
    stopLine: "LINE bot 停止",
    tunnelTitle: "一時公開URL",
    tunnelTarget: "転送先",
    generateTunnel: "一時 HTTPS URL を生成",
    stopTunnel: "一時URLを停止",
    webhookUrl: "LINE に設定する Webhook URL",
    tunnelHint: "これは一時URLです。再起動すると変わるので LINE コンソールで再設定してください。",
    envFile: "LINE .env",
    envText: "環境変数",
    policyFile: "表層ポリシー JSON",
    policyText: "LINE/TTS/画像/起床ポリシー",
    saveLineSettings: "LINE/TTS 設定を保存",
    ttsCommand: "TTS 起動コマンド",
    ttsCommandText: "G\\start_roleweaver_tts_api.bat をダブルクリック、または端末で実行します。",
    evaluationTitle: "Persona 評価",
    evaluationBody: "返答が身份、自律性、媒体適応を保っているかを低コストに確認します。",
    userProbe: "ユーザー入力",
    assistantProbe: "モデル返答",
    category: "カテゴリ",
    surface: "媒体",
    score: "スコア",
    runScore: "ルール評価",
    regressionCommands: "回帰テストコマンド",
    docsTitle: "フロー設計",
    docsBody: "RoleWeaver はまず役割組み合わせを決め、それに対応する記憶空間へ入ります。LINE/TTS/画像は媒体層であり、人格を上書きできません。",
    planningTitle: "役割スケジュールと Planning",
    planningBody: "モデル/LoRA/Skill の組み合わせごとに週予定を持ちます。端末時刻、タイムゾーン、ローカル場所を読み、今日の生活状態を返答へ注入しますが、長期記憶には書きません。",
    deviceTime: "端末時刻",
    localLocation: "ローカル場所",
    regenerateSchedule: "今週の予定を再生成",
    currentPlanningContext: "現在の planning context",
    currentAnchor: "現在の人格アンカー",
    anchorContext: "人格アンカー context",
    weeklySchedule: "週間予定",
    referenceSources: "参考ソース",
    webSearch: "Web 検索",
    searchPlaceholder: "例：日本 高校 部活動 日程",
    runSearch: "検索",
    searchResults: "検索結果",
  },
  en: {
    appSubtitle: "Local role-agent control console",
    overview: "Overview",
    chat: "Chat",
    runtime: "Runtime",
    memory: "Memory OS",
    training: "Training",
    line: "LINE / TTS / Public URL",
    planning: "Planning",
    evaluation: "Evaluation",
    docs: "Flows",
    online: "online",
    offline: "offline",
    refresh: "Refresh",
    save: "Save",
    start: "Start",
    stop: "Stop",
    send: "Send",
    delete: "Delete",
    close: "Close",
    copy: "Copy",
    copied: "Copied",
    requestFailed: "Request failed",
    saved: "Saved",
    loading: "Loading",
    overviewTitle: "One-stop entry",
    overviewBody: "Configure models, chat, memory, training, LINE, TTS, and temporary public URLs in one local console. Each base model, LoRA, and Skill combination gets its own memory scope.",
    health: "Runtime health",
    role: "Role",
    model: "Model",
    lora: "LoRA",
    skill: "Skill",
    quantization: "Quantization",
    memoryScope: "Memory scope",
    flowTitle: "Runtime flow",
    flowInput: "User input",
    flowInputDesc: "Web / LINE / image / voice request",
    flowSurface: "Surface adapter",
    flowSurfaceDesc: "Changes media format, not personality",
    flowRuntime: "Role runtime",
    flowRuntimeDesc: "Base model + optional LoRA + SKILL.md",
    flowMemory: "Memory OS",
    flowMemoryDesc: "Isolated by model, LoRA, Skill, and session",
    flowOutput: "Output",
    flowOutputDesc: "Text, LINE, TTS, or image-aware reply",
    memoryFlowTitle: "Memory layers",
    shortTerm: "Short-term",
    midTerm: "Mid-term",
    longTerm: "Long-term",
    graph: "Graph",
    reflection: "Reflection",
    contradiction: "Contradictions",
    chatTitle: "Role chat",
    chatBody: "The main chat entry, with history restore, renaming, deletion, image input, and manual memory consolidation.",
    chatName: "Chat name",
    maxTokens: "Max new tokens",
    newChat: "New chat",
    history: "History",
    noHistory: "No history yet",
    promptPlaceholder: "Send a message. Enter sends, Shift+Enter starts a new line.",
    attachImage: "Image",
    imageSelected: "Image selected",
    consolidate: "Consolidate memory",
    thinking: "Thinking...",
    runtimeTitle: "Role runtime settings",
    runtimeBody: "Choose the role runtime first. This combination determines the memory scope: base model, LoRA, and Skill changes should isolate memory.",
    baseModelPath: "Base model path",
    loraPath: "LoRA adapter path",
    loraNote: "Leave blank to load the base model without LoRA.",
    skillFile: "SKILL.md path",
    inlineSkill: "Inline Skill",
    inlineSkillPlaceholder: "Short extra role notes, boundaries, or style. Use SKILL.md for complex roles.",
    deviceMap: "Device placement",
    modelLoader: "Model loader",
    contextWindow: "Context window tokens",
    uiLanguage: "UI language",
    memoryTitle: "Memory OS",
    memoryBody: "View and edit long-term memories, evidence, contradiction links, and lifecycle notes for the current session.",
    statusFilter: "Status filter",
    all: "All",
    loadMemories: "Load memories",
    memoryOs: "Memory OS summary",
    noMemories: "No memories yet",
    reason: "Reason",
    evidence: "Evidence",
    links: "Links",
    lifecycle: "Lifecycle",
    markActive: "Mark active",
    markStale: "Mark stale",
    markContradicted: "Mark contradicted",
    archive: "Archive",
    trainingTitle: "LoRA training",
    trainingBody: "Use Excel, CSV, or JSONL. Excel templates use user and assistant columns and are converted automatically.",
    downloadTemplate: "Download Excel template",
    trainModelPath: "Base model path",
    trainDataFile: "Training file",
    trainOutputDir: "Output directory",
    epochs: "Epochs",
    learningRate: "Learning rate",
    batchSize: "Batch size",
    gradAccum: "Grad accum",
    allowOnline: "Allow Hugging Face/network access",
    startTraining: "Start training",
    stopTraining: "Stop training",
    trainingStatus: "Training status",
    lineTitle: "LINE / TTS / Temporary public URL",
    lineBody: "LINE requires an HTTPS webhook. Start the local LINE bot, generate a temporary Cloudflare URL, then paste the Webhook URL shown in the middle into the LINE console.",
    lineRuntime: "LINE bot runtime",
    lineHost: "Host",
    linePort: "Port",
    startLine: "Start LINE bot",
    stopLine: "Stop LINE bot",
    tunnelTitle: "Temporary public URL",
    tunnelTarget: "Forward target",
    generateTunnel: "Generate temporary HTTPS URL",
    stopTunnel: "Stop temporary URL",
    webhookUrl: "Webhook URL for LINE console",
    tunnelHint: "This URL is temporary. If cloudflared restarts, copy the new URL back into the LINE console.",
    envFile: "LINE .env",
    envText: "Environment variables",
    policyFile: "Surface policy JSON",
    policyText: "LINE/TTS/image/wake-up policy",
    saveLineSettings: "Save LINE/TTS settings",
    ttsCommand: "TTS start command",
    ttsCommandText: "Double-click G\\start_roleweaver_tts_api.bat, or run it from a terminal.",
    evaluationTitle: "Persona evaluation",
    evaluationBody: "Low-cost checks for identity, autonomy, and surface adaptation. Full long-dialogue regression remains under eval/persona_regression.",
    userProbe: "User input",
    assistantProbe: "Assistant reply",
    category: "Category",
    surface: "Surface",
    score: "Score",
    runScore: "Run rule score",
    regressionCommands: "Regression commands",
    docsTitle: "Flow design",
    docsBody: "Every RoleWeaver flow chooses a role runtime first, then enters the matching memory scope. LINE, TTS, and image input are surface adapters, not personality overrides.",
    planningTitle: "Role Schedule and Planning",
    planningBody: "Each model/LoRA/Skill combination owns a weekly plan. The system reads device time, timezone, and local place, then injects today's role state into replies without writing it into long-term memory.",
    deviceTime: "Device time",
    localLocation: "Local place",
    regenerateSchedule: "Regenerate this week",
    currentPlanningContext: "Current planning context",
    currentAnchor: "Current persona anchor",
    anchorContext: "Persona anchor context",
    weeklySchedule: "Weekly schedule",
    referenceSources: "Reference sources",
    webSearch: "Web lookup",
    searchPlaceholder: "Search reference material, e.g. Japanese high school club timetable",
    runSearch: "Search",
    searchResults: "Search results",
  },
};

Object.assign(I18N.zh, {
  background: "后台任务",
  backgroundTitle: "后台任务调度",
  backgroundBody: "把反思、整理、planning 和 persona 检查放到空闲时间运行。单卡常驻时，默认不让后台任务调用大模型，避免抢占实时聊天。",
  backgroundEnabled: "启用后台轻任务",
  backgroundLlmEnabled: "允许后台调用大模型",
  preloadModelOnStartup: "启动时直接加载模型",
  backgroundIdleSeconds: "空闲多少秒后可运行",
  backgroundWindowStart: "后台窗口开始",
  backgroundWindowEnd: "后台窗口结束",
  backgroundMaxMinutes: "单任务最长分钟",
  backgroundStatus: "调度状态",
  backgroundPaused: "已暂停",
  backgroundActive: "运行中",
  backgroundIdle: "空闲秒数",
  backgroundEligibility: "可运行性",
  backgroundJobType: "任务类型",
  backgroundForce: "忽略空闲/时间窗手动执行",
  runBackgroundJob: "运行后台任务",
  pauseBackground: "暂停后台",
  resumeBackground: "恢复后台",
  recentBackgroundJobs: "最近任务",
  singleGpuHint: "建议：单卡常驻时只在夜间窗口允许 LLM 后台任务；日常保持关闭，只跑 planning、释放模型等轻任务。",
});

Object.assign(I18N.ja, {
  background: "バックグラウンド",
  backgroundTitle: "バックグラウンド・スケジューラ",
  backgroundBody: "reflection、整理、planning、persona 検査をアイドル時間に回します。単一 GPU 常駐では、リアルタイム応答を守るため、LLM を使うバックグラウンド処理は既定で無効です。",
  backgroundEnabled: "軽量バックグラウンド処理を有効化",
  backgroundLlmEnabled: "バックグラウンドで LLM を使う",
  preloadModelOnStartup: "起動時にモデルを直接ロード",
  backgroundIdleSeconds: "実行前のアイドル秒数",
  backgroundWindowStart: "実行ウィンドウ開始",
  backgroundWindowEnd: "実行ウィンドウ終了",
  backgroundMaxMinutes: "1タスク最大分数",
  backgroundStatus: "状態",
  backgroundPaused: "一時停止中",
  backgroundActive: "実行中",
  backgroundIdle: "アイドル秒数",
  backgroundEligibility: "実行可否",
  backgroundJobType: "タスク種別",
  backgroundForce: "アイドル/時間帯を無視して手動実行",
  runBackgroundJob: "バックグラウンド実行",
  pauseBackground: "一時停止",
  resumeBackground: "再開",
  recentBackgroundJobs: "最近のタスク",
  singleGpuHint: "推奨: 単一 GPU 常駐では LLM バックグラウンド処理は夜間だけ許可し、通常は planning やモデル解放など軽量処理だけにします。",
});

Object.assign(I18N.en, {
  background: "Background",
  backgroundTitle: "Background Scheduler",
  backgroundBody: "Runs reflection, consolidation, planning, and persona checks during idle windows. On a single always-on GPU, LLM background work stays disabled by default so realtime chat stays responsive.",
  backgroundEnabled: "Enable light background jobs",
  backgroundLlmEnabled: "Allow background LLM jobs",
  preloadModelOnStartup: "Load model on startup",
  backgroundIdleSeconds: "Idle seconds before jobs",
  backgroundWindowStart: "Window start",
  backgroundWindowEnd: "Window end",
  backgroundMaxMinutes: "Max minutes per job",
  autonomousLearningEnabled: "Autonomous idle learning",
  autonomousLearningSubjects: "Autonomous subjects",
  autonomousLearningInterval: "Autonomous interval seconds",
  autonomousLearningUseModel: "Use model for idle study",
  autonomousLearningMaxTokens: "Idle study max tokens",
  backgroundStatus: "Scheduler status",
  backgroundPaused: "Paused",
  backgroundActive: "Active",
  backgroundIdle: "Idle seconds",
  backgroundEligibility: "Eligibility",
  backgroundJobType: "Job type",
  backgroundForce: "Force manual run outside idle/window",
  runBackgroundJob: "Run background job",
  pauseBackground: "Pause background",
  resumeBackground: "Resume background",
  recentBackgroundJobs: "Recent jobs",
  singleGpuHint: "Recommendation: on one always-on GPU, only allow LLM background work during night windows. Keep daily operation to planning, release, and other light jobs.",
});

Object.assign(I18N.zh, {
  autonomousLearningEnabled: "启用空闲自主学习",
  autonomousLearningSubjects: "自主学习主题",
  autonomousLearningInterval: "自主学习间隔秒数",
  autonomousLearningUseModel: "空闲学习调用模型",
  autonomousLearningMaxTokens: "空闲学习最大 token",
});

Object.assign(I18N.ja, {
  autonomousLearningEnabled: "アイドル時の自律学習",
  autonomousLearningSubjects: "自律学習テーマ",
  autonomousLearningInterval: "自律学習の間隔秒数",
  autonomousLearningUseModel: "アイドル学習でモデルを使う",
  autonomousLearningMaxTokens: "アイドル学習最大 token",
});

Object.assign(I18N.zh, {
  tools: "工具",
  toolsTitle: "工具层",
  toolsBody: "这里是 RoleWeaver 的受控工具总线。工具先走白名单和日志，后续可以逐步交给角色运行时调用。",
  toolName: "工具名称",
  toolArguments: "参数 JSON",
  toolRun: "运行工具",
  toolOutput: "运行结果",
  toolActions: "最近调用",
  toolCategory: "分类",
  toolRequiresSession: "需要会话",
  toolRequiresLlm: "可能调用大模型",
  toolMutates: "会改变状态",
  toolSelect: "选择工具",
});

Object.assign(I18N.ja, {
  tools: "ツール",
  toolsTitle: "ツール層",
  toolsBody: "RoleWeaver の制御されたツールバスです。まずはホワイトリストとログを通し、あとで角色ランタイムから呼べるようにします。",
  toolName: "ツール名",
  toolArguments: "引数 JSON",
  toolRun: "ツール実行",
  toolOutput: "実行結果",
  toolActions: "最近の呼び出し",
  toolCategory: "カテゴリ",
  toolRequiresSession: "会話が必要",
  toolRequiresLlm: "LLM を使う可能性",
  toolMutates: "状態を変更",
  toolSelect: "ツールを選択",
});

Object.assign(I18N.en, {
  tools: "Tools",
  toolsTitle: "Tool Layer",
  toolsBody: "A controlled RoleWeaver tool bus. Tools are whitelisted and logged first, then can be exposed to the role runtime step by step.",
  toolName: "Tool name",
  toolArguments: "Arguments JSON",
  toolRun: "Run tool",
  toolOutput: "Output",
  toolActions: "Recent calls",
  toolCategory: "Category",
  toolRequiresSession: "Needs session",
  toolRequiresLlm: "May call LLM",
  toolMutates: "Mutates state",
  toolSelect: "Select tool",
});

Object.assign(I18N.zh, {
  shiro: "白",
  shiroTitle: "白的认知状态",
  shiroBody: "查看 Shiro 认知层传给 RoleWeaver 的 thought context，以及最近状态转移。Shiro 项目仍保持独立，只通过桥接读取和回写。",
  shiroEnabled: "启用 Shiro 认知桥接",
  shiroRoot: "Shiro 状态目录",
  shiroIdentity: "Shiro 身份名",
  shiroStatus: "Shiro 状态",
  emotionState: "情绪状态",
  live2dSignal: "Live2D外显",
  thoughtContext: "Thought Context",
  recentTransitions: "最近状态转移",
  observeStimulus: "手动写入刺激",
  stimulusText: "刺激文本",
  stimulusSource: "刺激来源",
  toolIntentions: "工具意图",
  inferToolIntentions: "推断工具意图",
  intentionText: "意图输入",
});

Object.assign(I18N.ja, {
  shiro: "白",
  shiroTitle: "白の認知状態",
  shiroBody: "Shiro 認知層から RoleWeaver に渡される thought context と最近の状態遷移を確認します。Shiro は独立プロジェクトのまま、bridge 経由で読み書きします。",
  shiroEnabled: "Shiro 認知 bridge を有効化",
  shiroRoot: "Shiro 状態ディレクトリ",
  shiroIdentity: "Shiro identity",
  shiroStatus: "Shiro 状態",
  emotionState: "感情状態",
  live2dSignal: "Live2D 表現",
  thoughtContext: "Thought Context",
  recentTransitions: "最近の状態遷移",
  observeStimulus: "刺激を手動記録",
  stimulusText: "刺激テキスト",
  stimulusSource: "刺激ソース",
  toolIntentions: "ツール意図",
  inferToolIntentions: "ツール意図を推定",
  intentionText: "意図入力",
});

Object.assign(I18N.en, {
  shiro: "Shiro",
  shiroTitle: "Shiro Cognitive State",
  shiroBody: "Inspect the thought context passed from Shiro to RoleWeaver and recent state transitions. Shiro remains a separate project and is connected only through the bridge.",
  shiroEnabled: "Enable Shiro cognitive bridge",
  shiroRoot: "Shiro state directory",
  shiroIdentity: "Shiro identity",
  shiroStatus: "Shiro status",
  emotionState: "Emotion",
  live2dSignal: "Live2D",
  thoughtContext: "Thought Context",
  recentTransitions: "Recent transitions",
  observeStimulus: "Observe stimulus",
  stimulusText: "Stimulus text",
  stimulusSource: "Stimulus source",
  toolIntentions: "Tool intentions",
  inferToolIntentions: "Infer tool intentions",
  intentionText: "Intention input",
});

Object.assign(I18N.zh, {
  pet: "桌宠",
  petTitle: "Live2D 桌宠",
  petBody: "用 VTube Studio 渲染 Live2D 形象，RoleWeaver 前端负责连接、同步白的情绪状态，并触发表情或动作。",
  petModel: "模型",
  petModelPath: "模型目录",
  petVtsUrl: "VTube Studio API",
  petConnection: "VTube Studio 连接",
  petDisconnected: "未连接",
  petConnected: "已连接",
  petAuthenticated: "已授权",
  petTokenRequired: "需要授权 token",
  petConnect: "连接 VTube Studio",
  petDisconnect: "断开",
  petRequestToken: "请求授权",
  petAuthenticate: "授权连接",
  petRefresh: "刷新模型/热键",
  petSyncEmotion: "同步白的情绪",
  petTriggerExpression: "触发表情",
  petTriggerHotkey: "触发热键",
  petExpression: "表情",
  petHotkey: "热键",
  petCurrentModel: "当前 VTS 模型",
  petAvailableHotkeys: "可用热键",
  petSetupHint: "先打开 VTube Studio，在 Settings > API 中启用 API。把模型目录导入 VTube Studio 后，点击连接；第一次会在 VTube Studio 中弹出授权确认。",
});

Object.assign(I18N.ja, {
  pet: "デスクペット",
  petTitle: "Live2D デスクペット",
  petBody: "VTube Studio で Live2D を描画し、RoleWeaver 側から白の感情状態を同期して表情やモーションを送ります。",
  petModel: "モデル",
  petModelPath: "モデルフォルダ",
  petVtsUrl: "VTube Studio API",
  petConnection: "VTube Studio 接続",
  petDisconnected: "未接続",
  petConnected: "接続済み",
  petAuthenticated: "認証済み",
  petTokenRequired: "認証 token が必要",
  petConnect: "VTube Studio に接続",
  petDisconnect: "切断",
  petRequestToken: "認証を要求",
  petAuthenticate: "認証",
  petRefresh: "モデル/ホットキー更新",
  petSyncEmotion: "白の感情を同期",
  petTriggerExpression: "表情を送る",
  petTriggerHotkey: "ホットキー実行",
  petExpression: "表情",
  petHotkey: "ホットキー",
  petCurrentModel: "現在の VTS モデル",
  petAvailableHotkeys: "利用可能なホットキー",
  petSetupHint: "先に VTube Studio を開き、Settings > API で API を有効にしてください。モデルフォルダを VTube Studio に読み込んでから接続します。初回は VTube Studio 側で許可が必要です。",
});

Object.assign(I18N.en, {
  pet: "Pet",
  petTitle: "Live2D Desktop Pet",
  petBody: "Render the Live2D avatar in VTube Studio while RoleWeaver connects, syncs Shiro's emotion state, and triggers expressions or motions.",
  petModel: "Model",
  petModelPath: "Model folder",
  petVtsUrl: "VTube Studio API",
  petConnection: "VTube Studio connection",
  petDisconnected: "Disconnected",
  petConnected: "Connected",
  petAuthenticated: "Authenticated",
  petTokenRequired: "Token required",
  petConnect: "Connect VTube Studio",
  petDisconnect: "Disconnect",
  petRequestToken: "Request token",
  petAuthenticate: "Authenticate",
  petRefresh: "Refresh model/hotkeys",
  petSyncEmotion: "Sync Shiro emotion",
  petTriggerExpression: "Trigger expression",
  petTriggerHotkey: "Trigger hotkey",
  petExpression: "Expression",
  petHotkey: "Hotkey",
  petCurrentModel: "Current VTS model",
  petAvailableHotkeys: "Available hotkeys",
  petSetupHint: "Open VTube Studio first and enable Settings > API. Import the model folder into VTube Studio, then connect here. The first connection asks for approval inside VTube Studio.",
});

Object.assign(I18N.zh, {
  learning: "自学",
  learningTitle: "Shiro 长时间自学",
  learningBody: "让白以学生身份读取 ChinaTextbook 教材，分阶段学习、做题、回写情绪状态和 adapter 候选样本。",
  learningBootstrap: "唤醒 Shiro / 开启视觉配置",
  learningStatus: "学习状态",
  learningSubject: "科目筛选",
  learningUseModel: "调用本地模型",
  learningRunOnce: "学习一步",
  learningStart: "开始长时间学习",
  learningStop: "停止学习",
  learningMaxSteps: "步数",
  learningInterval: "间隔秒",
  learningRepo: "教材仓库",
  learningAdapter: "Adapter 候选样本",
});

Object.assign(I18N.ja, {
  learning: "自学",
  learningTitle: "Shiro 長時間自学",
  learningBody: "白を学生として ChinaTextbook 教材から段階的に学習させ、テスト、感情状態、adapter 候補を記録します。",
  learningBootstrap: "Shiro 起動 / vision 設定",
  learningStatus: "学習状態",
  learningSubject: "科目フィルタ",
  learningUseModel: "ローカルモデルを使う",
  learningRunOnce: "一歩学習",
  learningStart: "長時間学習開始",
  learningStop: "停止",
  learningMaxSteps: "ステップ数",
  learningInterval: "間隔秒",
  learningRepo: "教材リポジトリ",
  learningAdapter: "Adapter 候補",
});

Object.assign(I18N.en, {
  learning: "Learning",
  learningTitle: "Shiro Long-Term Study",
  learningBody: "Let Shiro study ChinaTextbook as a student, run phase quizzes, update emotion state, and collect adapter candidates.",
  learningBootstrap: "Wake Shiro / enable vision config",
  learningStatus: "Learning status",
  learningSubject: "Subject filter",
  learningUseModel: "Use local model",
  learningRunOnce: "Study one step",
  learningStart: "Start long run",
  learningStop: "Stop learning",
  learningMaxSteps: "Steps",
  learningInterval: "Interval seconds",
  learningRepo: "Textbook repo",
  learningAdapter: "Adapter candidates",
});

Object.assign(I18N.zh, {
  setup: "统一配置",
  setupTitle: "统一配置入口",
  setupBody: "集中配置模型、视觉加载、Shiro、学习运行时、Live2D 桌宠和 LINE/TTS。这里是正式运行前的总控台。",
  setupModelBlock: "模型与角色",
  setupShiroBlock: "Shiro / 学习",
  setupPetBlock: "Live2D / VTube Studio",
  setupLineBlock: "LINE / TTS",
  setupSaveAll: "保存并重置运行时",
  setupOpenLearning: "打开自学页",
  setupOpenPet: "打开桌宠页",
  setupOpenLine: "打开 LINE 页",
});

Object.assign(I18N.ja, {
  setup: "統一設定",
  setupTitle: "統一設定入口",
  setupBody: "モデル、vision loader、Shiro、学習ランタイム、Live2D デスクペット、LINE/TTS をまとめて設定します。",
  setupModelBlock: "モデルと人格",
  setupShiroBlock: "Shiro / 学習",
  setupPetBlock: "Live2D / VTube Studio",
  setupLineBlock: "LINE / TTS",
  setupSaveAll: "保存してランタイム再起動",
  setupOpenLearning: "自学ページへ",
  setupOpenPet: "ペットページへ",
  setupOpenLine: "LINE ページへ",
});

Object.assign(I18N.en, {
  setup: "Setup",
  setupTitle: "Unified Setup",
  setupBody: "Configure model, vision loading, Shiro, learning runtime, Live2D desktop pet, and LINE/TTS from one place.",
  setupModelBlock: "Model and role",
  setupShiroBlock: "Shiro / learning",
  setupPetBlock: "Live2D / VTube Studio",
  setupLineBlock: "LINE / TTS",
  setupSaveAll: "Save and reset runtime",
  setupOpenLearning: "Open learning",
  setupOpenPet: "Open pet",
  setupOpenLine: "Open LINE",
});

createApp({
  data() {
    return {
      lang: localStorage.getItem("roleweaver.console.lang") || "zh",
      activeView: "overview",
      health: null,
      config: {},
      sessions: [],
      sessionId: localStorage.getItem("roleweaver.sessionId") || "web",
      chatName: "",
      maxTokens: 160,
      messages: JSON.parse(localStorage.getItem("roleweaver.messages") || "[]"),
      prompt: "",
      image: null,
      memories: [],
      memoryFilter: "",
      memoryOs: null,
      planning: null,
      planningQuery: "Japan high school daily schedule club activities idol training",
      planningSearch: null,
      background: {},
      backgroundRunForm: {
        job_type: "planning_regenerate",
        force: true,
      },
      tools: [],
      toolActions: [],
      toolRunForm: {
        tool_name: "runtime.time_now",
        arguments: "{}",
        actor: "user",
      },
      toolOutput: null,
      shiro: {},
      shiroObserveForm: {
        text: "",
        source: "manual",
      },
      shiroIntentForm: {
        text: "",
      },
      shiroIntentions: [],
      petModel: null,
      vts: {
        url: "ws://127.0.0.1:8001",
        connected: false,
        authenticated: false,
        token: localStorage.getItem("roleweaver.vts.token") || "",
        currentModel: null,
        hotkeys: [],
        expressionFile: "",
        hotkeyId: "",
        lastAction: "",
        error: "",
      },
      learning: {},
      learningForm: {
        session_id: "shiro-study",
        subject: "",
        use_model: false,
        max_new_tokens: 384,
        max_steps: 3,
        interval_seconds: 3,
      },
      training: {},
      lineSettings: { env_text: "", surface_policy_text: "" },
      lineRuntime: {},
      lineRuntimeForm: { host: "0.0.0.0", port: 8010 },
      tunnel: {},
      tunnelTarget: "http://127.0.0.1:8010",
      personaProbe: {
        user_text: "",
        assistant_text: "",
        category: "identity",
        surface: "web",
      },
      personaScore: null,
      trainingForm: {
        model_path: "",
        data_file: "",
        output_dir: "outputs/your-role-lora",
        epochs: 3,
        learning_rate: 0.0001,
        per_device_train_batch_size: 2,
        gradient_accumulation_steps: 8,
        online: false,
      },
      toastText: "",
      busy: false,
    };
  },
  computed: {
    tr() { return I18N[this.lang] || I18N.zh; },
    navItems() {
      return [
        ["overview", "overview", "⌂"],
        ["setup", "setup", "S"],
        ["chat", "chat", "✉"],
        ["runtime", "runtime", "⚙"],
        ["memory", "memory", "◎"],
        ["planning", "planning", "◷"],
        ["background", "background", "⏱"],
        ["tools", "tools", "T"],
        ["shiro", "shiro", "白"],
        ["pet", "pet", "P"],
        ["learning", "learning", "L"],
        ["training", "training", "△"],
        ["line", "line", "◇"],
        ["evaluation", "evaluation", "✓"],
        ["docs", "docs", "↦"],
      ].map(([view, key, icon]) => ({ view, key, icon, label: this.t(key) }));
    },
    title() { return this.t(`${this.activeView}Title`) || this.t(this.activeView); },
    subtitle() { return this.t(`${this.activeView}Body`) || ""; },
    flowNodes() {
      return [
        ["flowInput", "flowInputDesc"],
        ["flowSurface", "flowSurfaceDesc"],
        ["flowRuntime", "flowRuntimeDesc"],
        ["flowMemory", "flowMemoryDesc"],
        ["flowOutput", "flowOutputDesc"],
      ].map(([title, body]) => ({ title: this.t(title), body: this.t(body) }));
    },
    memoryFlowNodes() {
      return ["shortTerm", "midTerm", "longTerm", "graph", "contradiction", "reflection"].map((key) => this.t(key));
    },
    isOnline() { return this.health && this.health.status === "ok"; },
    currentSessionName() {
      const found = this.sessions.find((item) => item.session_id === this.sessionId);
      return found ? found.display_name : this.chatName;
    },
    selectedTool() {
      return this.tools.find((tool) => tool.name === this.toolRunForm.tool_name) || null;
    },
  },
  mounted() {
    document.documentElement.lang = this.lang === "ja" ? "ja" : this.lang === "en" ? "en" : "zh-CN";
    window.addEventListener("pagehide", this.consolidateWithBeacon);
    window.addEventListener("beforeunload", this.consolidateWithBeacon);
    this.loadAll();
  },
  beforeUnmount() {
    window.removeEventListener("pagehide", this.consolidateWithBeacon);
    window.removeEventListener("beforeunload", this.consolidateWithBeacon);
    this.vtsDisconnect();
  },
  methods: {
    t(key) { return (I18N[this.lang] && I18N[this.lang][key]) || I18N.en[key] || key; },
    setLanguage(lang) {
      this.lang = lang;
      document.documentElement.lang = lang === "ja" ? "ja" : lang === "en" ? "en" : "zh-CN";
      localStorage.setItem("roleweaver.console.lang", lang);
    },
    async api(path, options = {}) {
      const res = await fetch(path, options);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(this.parseError(text) || `HTTP ${res.status}`);
      }
      const contentType = res.headers.get("content-type") || "";
      if (contentType.includes("application/json")) return res.json();
      return res.text();
    },
    parseError(text) {
      try {
        const data = JSON.parse(text);
        return data.detail || text;
      } catch {
        return text;
      }
    },
    toast(text) {
      this.toastText = text;
      window.clearTimeout(this.toastTimer);
      this.toastTimer = window.setTimeout(() => { this.toastText = ""; }, 3200);
    },
    async loadAll() {
      await Promise.allSettled([
        this.loadConfig(),
        this.checkHealth(),
        this.listSessions(),
        this.loadPlanning(),
        this.refreshBackground(),
        this.refreshTools(),
        this.refreshShiro(),
        this.refreshPetModel(),
        this.refreshLearning(),
        this.refreshTraining(),
        this.loadLineSettings(),
        this.refreshLineRuntime(),
        this.refreshTunnel(),
      ]);
    },
    async checkHealth() {
      try {
        this.health = await this.api(`/health?session_id=${encodeURIComponent(this.sessionId)}`);
      } catch {
        this.health = { status: "offline" };
      }
    },
    async loadConfig() {
      this.config = await this.api("/config");
      this.trainingForm.model_path = this.config.base_model_path || "";
      if (this.config.ui_language && I18N[this.config.ui_language]) this.setLanguage(this.config.ui_language);
    },
    async saveConfig() {
      try {
        this.config = await this.api("/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.config),
        });
        this.toast(this.t("saved"));
        await this.checkHealth();
        await this.listSessions();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async listSessions() {
      try {
        this.sessions = await this.api("/sessions");
        const found = this.sessions.find((item) => item.session_id === this.sessionId);
        this.chatName = found ? found.display_name : (this.chatName || "");
      } catch {
        this.sessions = [];
      }
    },
    setSessionName(data) {
      this.chatName = data.display_name || data.session_id || "web";
    },
    async createSession() {
      try {
        const data = await this.api("/sessions", { method: "POST" });
        this.sessionId = data.session_id;
        localStorage.setItem("roleweaver.sessionId", this.sessionId);
        this.setSessionName(data);
        this.messages = [];
        this.saveMessages();
        await this.listSessions();
        await this.refreshShiro();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async loadSession(id) {
      try {
        const data = await this.api(`/sessions/${encodeURIComponent(id)}`);
        this.sessionId = data.session_id;
        localStorage.setItem("roleweaver.sessionId", this.sessionId);
        this.setSessionName(data);
        this.messages = data.messages || [];
        this.config = data.config || this.config;
        this.saveMessages();
        await this.checkHealth();
        await this.loadPlanning();
        await this.refreshShiro();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async renameSession() {
      if (!this.chatName.trim()) return;
      try {
        const data = await this.api(`/sessions/${encodeURIComponent(this.sessionId)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ display_name: this.chatName.trim() }),
        });
        this.setSessionName(data);
        await this.listSessions();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async deleteSession(id) {
      if (!window.confirm(this.t("delete"))) return;
      try {
        await this.api(`/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
        if (id === this.sessionId) await this.createSession();
        await this.listSessions();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    saveMessages() {
      localStorage.setItem("roleweaver.messages", JSON.stringify(this.messages.slice(-80)));
    },
    async readImage(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      this.image = { name: file.name, dataUrl };
    },
    clearImage() {
      this.image = null;
      const input = this.$refs.imageInput;
      if (input) input.value = "";
    },
    async sendMessage() {
      const text = this.prompt.trim();
      if (!text || this.busy) return;
      const image = this.image;
      this.prompt = "";
      this.clearImage();
      this.messages.push({ role: "user", content: image ? `${text}\n[${this.t("imageSelected")}: ${image.name}]` : text });
      this.messages.push({ role: "assistant", content: this.t("thinking") });
      this.saveMessages();
      this.busy = true;
      await nextTick();
      const scroller = this.$refs.messages;
      if (scroller) scroller.scrollTop = scroller.scrollHeight;
      try {
        const body = {
          user_text: text,
          session_id: this.sessionId,
          max_new_tokens: Number(this.maxTokens || 160),
        };
        const endpoint = image ? "/chat/image" : "/chat";
        if (image) {
          body.image_base64 = image.dataUrl;
          body.image_name = image.name;
        }
        const data = await this.api(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        this.messages[this.messages.length - 1] = { role: "assistant", content: data.text || "" };
      } catch (err) {
        this.messages[this.messages.length - 1] = { role: "assistant", content: `${this.t("requestFailed")}: ${err.message}` };
      } finally {
        this.busy = false;
        this.saveMessages();
        this.refreshShiro();
      }
    },
    async consolidate() {
      try {
        await this.api(`/consolidate/${encodeURIComponent(this.sessionId)}`, { method: "POST" });
        this.toast(this.t("saved"));
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    consolidateWithBeacon() {
      const sessionId = encodeURIComponent(this.sessionId || "web");
      const url = `/consolidate/${sessionId}`;
      if (navigator.sendBeacon) {
        navigator.sendBeacon(url, new Blob([], { type: "text/plain" }));
      } else {
        fetch(url, { method: "POST", keepalive: true }).catch(() => {});
      }
    },
    async loadMemories() {
      const params = new URLSearchParams({ include_inactive: "true" });
      if (this.memoryFilter) params.set("status", this.memoryFilter);
      try {
        const data = await this.api(`/sessions/${encodeURIComponent(this.sessionId)}/memories?${params.toString()}`);
        this.memories = data.memories || [];
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async refreshMemoryOs() {
      try {
        const data = await this.api(`/sessions/${encodeURIComponent(this.sessionId)}/memory-os`);
        this.memoryOs = data.memory_os || data;
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async updateMemory(memory, status) {
      try {
        await this.api(`/sessions/${encodeURIComponent(this.sessionId)}/memories/${encodeURIComponent(memory.id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        });
        await this.loadMemories();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async deleteMemory(memory) {
      try {
        await this.api(`/sessions/${encodeURIComponent(this.sessionId)}/memories/${encodeURIComponent(memory.id)}`, { method: "DELETE" });
        await this.loadMemories();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async loadPlanning() {
      try {
        this.planning = await this.api(`/planning/${encodeURIComponent(this.sessionId)}`);
      } catch {
        this.planning = null;
      }
    },
    async regeneratePlanning() {
      try {
        this.planning = await this.api(`/planning/${encodeURIComponent(this.sessionId)}/regenerate`, { method: "POST" });
        this.toast(this.t("saved"));
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async runPlanningSearch() {
      try {
        const params = new URLSearchParams({ q: this.planningQuery || "", limit: "5" });
        this.planningSearch = await this.api(`/planning/search?${params.toString()}`);
      } catch (err) {
        this.planningSearch = { error: err.message, results: [] };
      }
    },
    async refreshBackground() {
      try {
        this.background = await this.api("/background/status");
      } catch {
        this.background = {};
      }
    },
    async pauseBackground() {
      try {
        this.background = await this.api("/background/pause", { method: "POST" });
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async resumeBackground() {
      try {
        this.background = await this.api("/background/resume", { method: "POST" });
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async runBackgroundJob() {
      try {
        await this.api("/background/run-once", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            job_type: this.backgroundRunForm.job_type,
            session_id: this.sessionId,
            force: Boolean(this.backgroundRunForm.force),
          }),
        });
        await this.refreshBackground();
        this.toast(this.t("saved"));
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async refreshTools() {
      try {
        const listed = await this.api("/tools");
        this.tools = listed.tools || [];
        if (!this.tools.find((tool) => tool.name === this.toolRunForm.tool_name) && this.tools.length) {
          this.selectTool(this.tools[0].name);
        }
        await this.refreshToolActions();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async refreshToolActions() {
      try {
        const data = await this.api("/tools/actions?limit=30");
        this.toolActions = data.actions || [];
      } catch {
        this.toolActions = [];
      }
    },
    defaultToolArguments(tool) {
      const properties = (tool && tool.parameters && tool.parameters.properties) || {};
      const defaults = {};
      Object.entries(properties).forEach(([key, spec]) => {
        if (key === "query") defaults[key] = "";
        else if (key === "job_type") defaults[key] = "planning_regenerate";
        else if (key === "force") defaults[key] = true;
        else if (spec.type === "integer") defaults[key] = 5;
        else if (spec.type === "number") defaults[key] = 0;
        else if (spec.type === "boolean") defaults[key] = false;
        else if (spec.type === "array") defaults[key] = [];
        else if (spec.type === "object") defaults[key] = {};
        else defaults[key] = "";
      });
      return defaults;
    },
    selectTool(name) {
      this.toolRunForm.tool_name = name;
      const tool = this.tools.find((item) => item.name === name);
      this.toolRunForm.arguments = JSON.stringify(this.defaultToolArguments(tool), null, 2);
    },
    async runTool() {
      try {
        const args = JSON.parse(this.toolRunForm.arguments || "{}");
        this.toolOutput = await this.api("/tools/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tool_name: this.toolRunForm.tool_name,
            session_id: this.sessionId || "web",
            actor: this.toolRunForm.actor || "user",
            arguments: args,
          }),
        });
        await this.refreshToolActions();
      } catch (err) {
        this.toolOutput = { status: "failed", error: err.message };
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async refreshShiro() {
      if (!this.sessionId) return;
      try {
        this.shiro = await this.api(`/sessions/${encodeURIComponent(this.sessionId)}/shiro`);
      } catch (err) {
        this.shiro = { available: false, error: err.message };
      }
    },
    async observeShiroStimulus() {
      try {
        await this.api(`/sessions/${encodeURIComponent(this.sessionId)}/shiro/observe`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: this.shiroObserveForm.text || "",
            source: this.shiroObserveForm.source || "manual",
            metadata: {},
          }),
        });
        this.shiroObserveForm.text = "";
        await this.refreshShiro();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async inferShiroToolIntentions() {
      try {
        const data = await this.api(`/sessions/${encodeURIComponent(this.sessionId)}/shiro/tool-intentions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: this.shiroIntentForm.text || "",
            metadata: {},
          }),
        });
        this.shiroIntentions = data.intentions || [];
      } catch (err) {
        this.shiroIntentions = [{ tool_name: "error", reason: err.message }];
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async refreshPetModel() {
      try {
        this.petModel = await this.api("/pet/model");
        this.vts.url = this.petModel.vts_websocket_url || this.vts.url;
        if (!this.vts.expressionFile && this.petModel.expressions && this.petModel.expressions.length) {
          this.vts.expressionFile = this.petModel.expressions[0].file;
        }
      } catch (err) {
        this.petModel = { error: err.message };
      }
    },
    async vtsConnect() {
      this.vts.error = "";
      if (this._vtsSocket && this._vtsSocket.readyState === WebSocket.OPEN) return;
      await new Promise((resolve, reject) => {
        const socket = new WebSocket(this.vts.url || "ws://127.0.0.1:8001");
        this._vtsSocket = socket;
        this._vtsPending = {};
        socket.onopen = () => {
          this.vts.connected = true;
          this.vts.lastAction = this.t("petConnected");
          resolve();
        };
        socket.onerror = () => {
          this.vts.error = "VTube Studio WebSocket error";
          reject(new Error(this.vts.error));
        };
        socket.onclose = () => {
          this.vts.connected = false;
          this.vts.authenticated = false;
        };
        socket.onmessage = (event) => this.vtsHandleMessage(event);
      });
      if (this.vts.token) {
        try { await this.vtsAuthenticate(); } catch { /* user can authenticate manually */ }
      }
    },
    vtsDisconnect() {
      if (this._vtsSocket) {
        this._vtsSocket.close();
        this._vtsSocket = null;
      }
      this.vts.connected = false;
      this.vts.authenticated = false;
    },
    vtsHandleMessage(event) {
      let message = null;
      try { message = JSON.parse(event.data); } catch { return; }
      const pending = this._vtsPending && this._vtsPending[message.requestID];
      if (!pending) return;
      delete this._vtsPending[message.requestID];
      if (message.messageType === "APIError") {
        const detail = message.data && (message.data.message || message.data.errorID);
        pending.reject(new Error(detail || "VTube Studio API error"));
      } else {
        pending.resolve(message);
      }
    },
    vtsRequest(messageType, data = {}, timeoutMs = 20000) {
      if (!this._vtsSocket || this._vtsSocket.readyState !== WebSocket.OPEN) {
        return Promise.reject(new Error(this.t("petDisconnected")));
      }
      this._vtsSeq = (this._vtsSeq || 0) + 1;
      const requestID = `roleweaver-${Date.now()}-${this._vtsSeq}`;
      const payload = {
        apiName: "VTubeStudioPublicAPI",
        apiVersion: "1.0",
        requestID,
        messageType,
        data,
      };
      return new Promise((resolve, reject) => {
        this._vtsPending = this._vtsPending || {};
        const timer = window.setTimeout(() => {
          if (this._vtsPending && this._vtsPending[requestID]) {
            delete this._vtsPending[requestID];
            reject(new Error("VTube Studio API timeout"));
          }
        }, timeoutMs);
        this._vtsPending[requestID] = {
          resolve: (value) => { window.clearTimeout(timer); resolve(value); },
          reject: (err) => { window.clearTimeout(timer); reject(err); },
        };
        this._vtsSocket.send(JSON.stringify(payload));
      });
    },
    async vtsRequestToken() {
      try {
        await this.vtsConnect();
        const pluginName = (this.petModel && this.petModel.vts_plugin_name) || "RoleWeaver Shiro Pet";
        const pluginDeveloper = (this.petModel && this.petModel.vts_plugin_developer) || "RoleWeaver";
        const response = await this.vtsRequest("AuthenticationTokenRequest", { pluginName, pluginDeveloper }, 60000);
        this.vts.token = response.data.authenticationToken || "";
        localStorage.setItem("roleweaver.vts.token", this.vts.token);
        this.vts.lastAction = this.t("petTokenRequired");
        await this.vtsAuthenticate();
      } catch (err) {
        this.vts.error = err.message;
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async vtsAuthenticate() {
      try {
        await this.vtsConnect();
        if (!this.vts.token) throw new Error(this.t("petTokenRequired"));
        const pluginName = (this.petModel && this.petModel.vts_plugin_name) || "RoleWeaver Shiro Pet";
        const pluginDeveloper = (this.petModel && this.petModel.vts_plugin_developer) || "RoleWeaver";
        const response = await this.vtsRequest("AuthenticationRequest", {
          pluginName,
          pluginDeveloper,
          authenticationToken: this.vts.token,
        });
        this.vts.authenticated = !!(response.data && response.data.authenticated);
        this.vts.lastAction = this.t("petAuthenticated");
        await this.vtsRefresh();
      } catch (err) {
        this.vts.error = err.message;
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
        return false;
      }
    },
    async vtsRefresh() {
      try {
        await this.vtsConnect();
        const model = await this.vtsRequest("CurrentModelRequest");
        this.vts.currentModel = model.data || null;
        const hotkeys = await this.vtsRequest("HotkeysInCurrentModelRequest");
        this.vts.hotkeys = (hotkeys.data && hotkeys.data.availableHotkeys) || [];
        if (!this.vts.hotkeyId && this.vts.hotkeys.length) this.vts.hotkeyId = this.vts.hotkeys[0].hotkeyID;
      } catch (err) {
        this.vts.error = err.message;
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async vtsResetExpressions() {
      const expressions = (this.petModel && this.petModel.expressions) || [];
      await Promise.allSettled(expressions.map((item) => (
        item.file ? this.vtsRequest("ExpressionActivationRequest", { expressionFile: item.file, active: false }) : null
      )));
    },
    async vtsTriggerExpression(file) {
      try {
        await this.vtsConnect();
        const expressionFile = file || this.vts.expressionFile;
        if (!expressionFile) throw new Error("No expression selected");
        await this.vtsResetExpressions();
        await this.vtsRequest("ExpressionActivationRequest", { expressionFile, active: true });
        this.vts.expressionFile = expressionFile;
        this.vts.lastAction = `${this.t("petExpression")}: ${expressionFile}`;
      } catch (err) {
        this.vts.error = err.message;
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async vtsTriggerHotkey(hotkeyId) {
      try {
        await this.vtsConnect();
        const target = hotkeyId || this.vts.hotkeyId;
        if (!target) throw new Error("No hotkey selected");
        await this.vtsRequest("HotkeyTriggerRequest", { hotkeyID: target });
        this.vts.hotkeyId = target;
        this.vts.lastAction = `${this.t("petHotkey")}: ${target}`;
      } catch (err) {
        this.vts.error = err.message;
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    expressionForEmotion(primary) {
      const map = {
        warm: "exp/4.exp3.json",
        playful: "exp/8.exp3.json",
        focused: "exp/7.exp3.json",
        curious: "exp/8.exp3.json",
        guarded: "exp/5.exp3.json",
        hurt: "exp/6.exp3.json",
        tired: "exp/1.exp3.json",
        neutral: "",
      };
      return map[primary || "neutral"] || "";
    },
    async syncPetWithShiro() {
      await this.refreshShiro();
      const emotion = ((this.shiro.state || {}).emotion || {}).primary || "neutral";
      const expressionFile = this.expressionForEmotion(emotion);
      if (expressionFile) {
        await this.vtsTriggerExpression(expressionFile);
      } else {
        await this.vtsResetExpressions();
      }
      this.vts.lastAction = `${this.t("emotionState")}: ${emotion}`;
    },
    async refreshLearning() {
      try {
        const params = new URLSearchParams({
          session_id: this.learningForm.session_id || "shiro-study",
          subject: this.learningForm.subject || "",
        });
        this.learning = await this.api(`/learning/status?${params.toString()}`);
      } catch (err) {
        this.learning = { error: err.message };
      }
    },
    async bootstrapLearningShiro() {
      try {
        const data = await this.api("/learning/bootstrap-shiro", { method: "POST" });
        this.config = data.config || this.config;
        await this.refreshLearning();
        await this.refreshShiro();
        this.toast(this.t("saved"));
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async runLearningOnce() {
      try {
        this.learning = await this.api("/learning/run-once", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.learningForm),
        });
        await this.refreshShiro();
        if (this.vts.connected) await this.syncPetWithShiro();
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async startLearning() {
      try {
        this.learning = await this.api("/learning/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.learningForm),
        });
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async stopLearning() {
      try {
        this.learning = await this.api("/learning/stop", { method: "POST" });
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async startTraining() {
      try {
        this.training = await this.api("/training/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.trainingForm),
        });
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async refreshTraining() {
      try { this.training = await this.api("/training/status"); } catch { this.training = {}; }
    },
    async stopTraining() {
      try { this.training = await this.api("/training/stop", { method: "POST" }); } catch (err) { this.toast(`${this.t("requestFailed")}: ${err.message}`); }
    },
    async loadLineSettings() {
      try { this.lineSettings = await this.api("/integrations/line/settings"); } catch { this.lineSettings = { env_text: "", surface_policy_text: "" }; }
    },
    async saveLineSettings() {
      try {
        this.lineSettings = await this.api("/integrations/line/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            env_text: this.lineSettings.env_text,
            surface_policy_text: this.lineSettings.surface_policy_text,
          }),
        });
        this.toast(this.t("saved"));
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async refreshLineRuntime() {
      try { this.lineRuntime = await this.api("/integrations/line/runtime/status"); } catch { this.lineRuntime = {}; }
    },
    async startLineRuntime() {
      try {
        this.lineRuntime = await this.api("/integrations/line/runtime/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.lineRuntimeForm),
        });
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async stopLineRuntime() {
      try { this.lineRuntime = await this.api("/integrations/line/runtime/stop", { method: "POST" }); } catch (err) { this.toast(`${this.t("requestFailed")}: ${err.message}`); }
    },
    async refreshTunnel() {
      try { this.tunnel = await this.api("/integrations/tunnel/status"); } catch { this.tunnel = {}; }
    },
    async startTunnel() {
      try {
        this.tunnel = await this.api("/integrations/tunnel/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: "cloudflared", target_url: this.tunnelTarget }),
        });
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
    async stopTunnel() {
      try { this.tunnel = await this.api("/integrations/tunnel/stop", { method: "POST" }); } catch (err) { this.toast(`${this.t("requestFailed")}: ${err.message}`); }
    },
    async copyText(text) {
      try {
        await navigator.clipboard.writeText(text || "");
        this.toast(this.t("copied"));
      } catch {
        this.toast(text || "");
      }
    },
    async runPersonaScore() {
      try {
        this.personaScore = await this.api("/persona/score", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.personaProbe),
        });
      } catch (err) {
        this.toast(`${this.t("requestFailed")}: ${err.message}`);
      }
    },
  },
  template: `
    <div class="layout">
      <aside class="sidebar">
        <div class="brand">
          <h1>RoleWeaver</h1>
          <p>{{ t('appSubtitle') }}</p>
        </div>
        <div class="language-row">
          <button :class="{active: lang === 'zh'}" @click="setLanguage('zh')">中文</button>
          <button :class="{active: lang === 'ja'}" @click="setLanguage('ja')">日本語</button>
          <button :class="{active: lang === 'en'}" @click="setLanguage('en')">EN</button>
        </div>
        <nav class="nav">
          <button v-for="item in navItems" :key="item.view" :class="{active: activeView === item.view}" @click="activeView = item.view">
            <span class="nav-icon">{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </button>
        </nav>
        <div class="sidebar-status">
          <span class="status-pill"><span class="status-dot" :class="{online: isOnline}"></span>{{ isOnline ? t('online') : t('offline') }}</span>
          <span>{{ currentSessionName || sessionId }}</span>
        </div>
      </aside>

      <main class="main">
        <header class="topbar">
          <div>
            <p class="eyebrow">RoleWeaver Console</p>
            <h2>{{ title }}</h2>
            <p>{{ subtitle }}</p>
          </div>
          <div class="toolbar">
            <button class="secondary" @click="loadAll">{{ t('refresh') }}</button>
          </div>
        </header>

        <section v-if="activeView === 'overview'" class="grid">
          <div class="grid three">
            <div class="metric"><span>{{ t('health') }}</span><strong>{{ isOnline ? t('online') : t('offline') }}</strong></div>
            <div class="metric"><span>{{ t('role') }}</span><strong>{{ (health && health.role_name) || 'RoleWeaver' }}</strong></div>
            <div class="metric"><span>{{ t('quantization') }}</span><strong>{{ (health && health.quantization_mode) || config.quantization_mode || '-' }}</strong></div>
          </div>
          <div class="card pad">
            <h3>{{ t('flowTitle') }}</h3>
            <div class="flow-row">
              <div class="flow-node" v-for="node in flowNodes" :key="node.title"><strong>{{ node.title }}</strong><span>{{ node.body }}</span></div>
            </div>
          </div>
          <div class="card pad">
            <h3>{{ t('memoryFlowTitle') }}</h3>
            <div class="flow-row">
              <div class="flow-node" v-for="node in memoryFlowNodes" :key="node"><strong>{{ node }}</strong><span>{{ t('memoryScope') }}</span></div>
            </div>
          </div>
          <div class="grid two">
            <div class="card pad"><h3>{{ t('model') }}</h3><p>{{ (health && health.base_model_path) || config.base_model_path || '-' }}</p></div>
            <div class="card pad"><h3>{{ t('memoryScope') }}</h3><p>{{ (health && health.memory_scope_path) || '-' }}</p></div>
          </div>
        </section>

        <section v-if="activeView === 'setup'" class="grid">
          <div class="grid three">
            <div class="metric"><span>{{ t('model') }}</span><strong>{{ config.model_loader_mode || '-' }}</strong></div>
            <div class="metric"><span>{{ t('shiro') }}</span><strong>{{ config.shiro_enabled ? t('online') : t('offline') }}</strong></div>
            <div class="metric"><span>{{ t('pet') }}</span><strong>{{ vts.connected ? t('petConnected') : t('petDisconnected') }}</strong></div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('setupModelBlock') }}</h3>
              <div class="field"><label>{{ t('baseModelPath') }}</label><input v-model="config.base_model_path"></div>
              <div class="field"><label>{{ t('loraPath') }}</label><input v-model="config.lora_path"></div>
              <div class="field"><label>{{ t('skillFile') }}</label><input v-model="config.skill_file"></div>
              <div class="field"><label>{{ t('inlineSkill') }}</label><textarea class="textarea-code" v-model="config.skill_text"></textarea></div>
              <div class="grid two">
                <div class="field"><label>{{ t('modelLoader') }}</label><select v-model="config.model_loader_mode"><option>auto</option><option>text</option><option>vision</option><option>omni</option></select></div>
                <div class="field"><label>{{ t('quantization') }}</label><select v-model="config.quantization_mode"><option>4bit</option><option>8bit</option><option>bf16</option><option>fp16</option><option>none</option></select></div>
                <div class="field"><label>{{ t('deviceMap') }}</label><select v-model="config.device_map_mode"><option>gpu</option><option>auto</option></select></div>
                <div class="field"><label>{{ t('contextWindow') }}</label><input type="number" v-model.number="config.context_window_tokens"></div>
              </div>
            </div>
            <div class="card pad">
              <h3>{{ t('setupShiroBlock') }}</h3>
              <label><input type="checkbox" v-model="config.shiro_enabled"> {{ t('shiroEnabled') }}</label>
              <label><input type="checkbox" v-model="config.preload_model_on_startup"> {{ t('preloadModelOnStartup') }}</label>
              <div class="field"><label>{{ t('shiroRoot') }}</label><input v-model="config.shiro_root"></div>
              <div class="field"><label>{{ t('shiroIdentity') }}</label><input v-model="config.shiro_identity"></div>
              <div class="field"><label>{{ t('learningSubject') }}</label><input v-model="learningForm.subject"></div>
              <div class="toolbar">
                <button class="secondary" @click="bootstrapLearningShiro">{{ t('learningBootstrap') }}</button>
                <button class="secondary" @click="activeView = 'learning'">{{ t('setupOpenLearning') }}</button>
              </div>
            </div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('setupPetBlock') }}</h3>
              <p>{{ petModel && petModel.model_root }}</p>
              <div class="field"><label>{{ t('petVtsUrl') }}</label><input v-model="vts.url"></div>
              <div class="toolbar">
                <button class="secondary" @click="refreshPetModel">{{ t('refresh') }}</button>
                <button class="secondary" @click="vtsConnect">{{ t('petConnect') }}</button>
                <button class="secondary" @click="activeView = 'pet'">{{ t('setupOpenPet') }}</button>
              </div>
            </div>
            <div class="card pad">
              <h3>{{ t('setupLineBlock') }}</h3>
              <p>{{ t('ttsCommandText') }}</p>
              <code>G\\start_roleweaver_tts_api.bat</code>
              <div class="toolbar">
                <button class="secondary" @click="loadLineSettings">{{ t('refresh') }}</button>
                <button class="secondary" @click="activeView = 'line'">{{ t('setupOpenLine') }}</button>
              </div>
            </div>
          </div>
          <div class="toolbar">
            <button class="primary" @click="saveConfig">{{ t('setupSaveAll') }}</button>
          </div>
        </section>

        <section v-if="activeView === 'chat'" class="chat-shell">
          <aside class="card pad">
            <div class="grid">
              <button class="primary" @click="createSession">{{ t('newChat') }}</button>
              <div class="field"><label>{{ t('chatName') }}</label><input v-model="chatName" @blur="renameSession"></div>
              <div class="field"><label>{{ t('maxTokens') }}</label><input type="number" min="16" max="4096" step="16" v-model.number="maxTokens"></div>
              <button class="secondary" @click="consolidate">{{ t('consolidate') }}</button>
              <h3>{{ t('history') }}</h3>
              <div class="session-list" v-if="sessions.length">
                <div class="session-row" v-for="session in sessions" :key="session.session_id">
                  <button class="session-name" :class="{active: session.session_id === sessionId}" @click="loadSession(session.session_id)">{{ session.display_name }}</button>
                  <button class="session-delete" @click="deleteSession(session.session_id)">×</button>
                </div>
              </div>
              <p class="note" v-else>{{ t('noHistory') }}</p>
            </div>
          </aside>
          <section class="card">
            <div class="messages" ref="messages">
              <div class="message" :class="msg.role" v-for="(msg, idx) in messages" :key="idx">
                <div class="avatar">{{ msg.role === 'user' ? 'U' : 'R' }}</div>
                <div class="bubble">{{ msg.content }}</div>
              </div>
            </div>
            <form class="composer" @submit.prevent="sendMessage">
              <input ref="imageInput" type="file" accept="image/png,image/jpeg,image/webp,image/bmp" hidden @change="readImage">
              <button class="secondary" type="button" @click="$refs.imageInput.click()">{{ t('attachImage') }}</button>
              <textarea v-model="prompt" :placeholder="t('promptPlaceholder')" @keydown.enter.exact.prevent="sendMessage"></textarea>
              <button class="primary" type="submit" :disabled="busy">{{ t('send') }}</button>
            </form>
            <div class="image-preview" v-if="image"><img :src="image.dataUrl" alt=""><span>{{ image.name }}</span><button class="subtle" @click="clearImage">{{ t('close') }}</button></div>
          </section>
        </section>

        <section v-if="activeView === 'runtime'" class="card pad">
          <div class="grid two">
            <div class="field"><label>{{ t('baseModelPath') }}</label><input v-model="config.base_model_path"></div>
            <div class="field"><label>{{ t('loraPath') }}</label><input v-model="config.lora_path"><p class="note">{{ t('loraNote') }}</p></div>
            <div class="field"><label>{{ t('skillFile') }}</label><input v-model="config.skill_file"></div>
            <div class="field"><label>{{ t('quantization') }}</label><select v-model="config.quantization_mode"><option>4bit</option><option>8bit</option><option>bf16</option><option>fp16</option><option>none</option></select></div>
            <div class="field"><label>{{ t('deviceMap') }}</label><select v-model="config.device_map_mode"><option value="gpu">GPU only</option><option value="auto">Auto / CPU offload</option></select></div>
            <div class="field"><label>{{ t('modelLoader') }}</label><select v-model="config.model_loader_mode"><option value="auto">Auto</option><option value="text">Text / Causal LM</option><option value="vision">Vision / image-text</option><option value="omni">Omni / audio-image-video</option></select></div>
            <div class="field"><label>{{ t('contextWindow') }}</label><input type="number" min="0" step="1024" v-model.number="config.context_window_tokens"></div>
            <div class="field"><label>{{ t('localLocation') }}</label><input v-model="config.local_location" placeholder="Tokyo, Japan"></div>
            <label><input type="checkbox" v-model="config.background_jobs_enabled"> {{ t('backgroundEnabled') }}</label>
            <label><input type="checkbox" v-model="config.background_llm_enabled"> {{ t('backgroundLlmEnabled') }}</label>
            <label><input type="checkbox" v-model="config.autonomous_learning_enabled"> {{ t('autonomousLearningEnabled') }}</label>
            <label><input type="checkbox" v-model="config.autonomous_learning_use_model"> {{ t('autonomousLearningUseModel') }}</label>
            <label><input type="checkbox" v-model="config.preload_model_on_startup"> {{ t('preloadModelOnStartup') }}</label>
            <div class="field"><label>{{ t('backgroundIdleSeconds') }}</label><input type="number" min="0" step="60" v-model.number="config.background_idle_seconds"></div>
            <div class="field"><label>{{ t('backgroundMaxMinutes') }}</label><input type="number" min="1" step="1" v-model.number="config.background_max_minutes"></div>
            <div class="field"><label>{{ t('backgroundWindowStart') }}</label><input v-model="config.background_window_start" placeholder="02:00"></div>
            <div class="field"><label>{{ t('backgroundWindowEnd') }}</label><input v-model="config.background_window_end" placeholder="05:30"></div>
            <div class="field"><label>{{ t('autonomousLearningSubjects') }}</label><input v-model="config.autonomous_learning_subjects" placeholder="mathematics, computer science"></div>
            <div class="field"><label>{{ t('autonomousLearningInterval') }}</label><input type="number" min="60" step="60" v-model.number="config.autonomous_learning_interval_seconds"></div>
            <div class="field"><label>{{ t('autonomousLearningMaxTokens') }}</label><input type="number" min="64" step="64" v-model.number="config.autonomous_learning_max_new_tokens"></div>
            <label><input type="checkbox" v-model="config.shiro_enabled"> {{ t('shiroEnabled') }}</label>
            <div class="field"><label>{{ t('shiroRoot') }}</label><input v-model="config.shiro_root"></div>
            <div class="field"><label>{{ t('shiroIdentity') }}</label><input v-model="config.shiro_identity"></div>
            <div class="field"><label>{{ t('uiLanguage') }}</label><select v-model="config.ui_language"><option value="zh">中文</option><option value="ja">日本語</option><option value="en">English</option></select></div>
            <div class="field" style="grid-column:1/-1"><label>{{ t('inlineSkill') }}</label><textarea v-model="config.skill_text" :placeholder="t('inlineSkillPlaceholder')"></textarea></div>
          </div>
          <div class="toolbar" style="margin-top:14px"><button class="primary" @click="saveConfig">{{ t('save') }}</button></div>
        </section>

        <section v-if="activeView === 'memory'" class="grid">
          <div class="card pad">
            <div class="toolbar">
              <select v-model="memoryFilter"><option value="">{{ t('all') }}</option><option>active</option><option>stale</option><option>contradicted</option><option>archived</option><option>deleted</option></select>
              <button class="secondary" @click="loadMemories">{{ t('loadMemories') }}</button>
              <button class="secondary" @click="refreshMemoryOs">{{ t('memoryOs') }}</button>
            </div>
          </div>
          <div class="card pad" v-if="memoryOs"><h3>{{ t('memoryOs') }}</h3><pre class="log-box">{{ JSON.stringify(memoryOs, null, 2) }}</pre></div>
          <div class="memory-card" v-for="memory in memories" :key="memory.id">
            <strong>#{{ memory.id }} · {{ memory.status }} · {{ memory.memory_layer }}</strong>
            <div>{{ memory.content }}</div>
            <div class="memory-meta"><span class="chip">{{ t('reason') }}: {{ memory.reason || '-' }}</span><span class="chip">{{ t('links') }}: {{ (memory.links || []).join(', ') || '-' }}</span><span class="chip">{{ t('evidence') }}: {{ (memory.evidence || []).join('; ') || '-' }}</span></div>
            <div class="memory-meta" v-if="memory.lifecycle"><span class="chip">{{ t('lifecycle') }}: {{ memory.lifecycle.decay_risk || '-' }}</span><span class="chip">{{ memory.lifecycle.protected ? 'protected' : 'unprotected' }}</span></div>
            <div class="toolbar"><button class="secondary" @click="updateMemory(memory, 'active')">{{ t('markActive') }}</button><button class="secondary" @click="updateMemory(memory, 'stale')">{{ t('markStale') }}</button><button class="secondary" @click="updateMemory(memory, 'contradicted')">{{ t('markContradicted') }}</button><button class="secondary" @click="updateMemory(memory, 'archived')">{{ t('archive') }}</button><button class="danger" @click="deleteMemory(memory)">{{ t('delete') }}</button></div>
          </div>
          <p class="note" v-if="!memories.length">{{ t('noMemories') }}</p>
        </section>

        <section v-if="activeView === 'planning'" class="grid">
          <div class="grid three">
            <div class="metric"><span>{{ t('deviceTime') }}</span><strong>{{ planning && planning.device_context ? planning.device_context.iso : '-' }}</strong></div>
            <div class="metric"><span>{{ t('localLocation') }}</span><strong>{{ planning && planning.device_context ? planning.device_context.location : '-' }}</strong></div>
            <div class="metric"><span>{{ t('weeklySchedule') }}</span><strong>{{ planning && planning.schedule ? planning.schedule.week_start : '-' }}</strong></div>
          </div>
          <div class="card pad">
            <div class="toolbar">
              <button class="secondary" @click="loadPlanning">{{ t('refresh') }}</button>
              <button class="primary" @click="regeneratePlanning">{{ t('regenerateSchedule') }}</button>
            </div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('currentPlanningContext') }}</h3>
              <pre class="log-box">{{ planning ? planning.current_context : '' }}</pre>
            </div>
            <div class="card pad">
              <h3>{{ t('currentAnchor') }}</h3>
              <div v-if="planning && planning.current_anchor" class="memory-card">
                <strong>{{ planning.current_anchor.title || planning.current_anchor.id }}</strong>
                <p>{{ planning.current_anchor.summary }}</p>
                <div class="memory-meta">
                  <span class="chip" v-for="dim in (planning.current_anchor.persona_dimensions || [])" :key="dim">{{ dim }}</span>
                  <span class="chip">{{ planning.current_anchor.source_file }}</span>
                </div>
              </div>
              <pre class="log-box">{{ planning ? planning.current_anchor_context : '' }}</pre>
            </div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('referenceSources') }}</h3>
              <div class="memory-card" v-for="source in (planning && planning.sources ? planning.sources : [])" :key="source.id">
                <strong>{{ source.title }}</strong>
                <p>{{ source.summary }}</p>
                <a class="subtle" :href="source.url" target="_blank" rel="noreferrer">{{ source.url }}</a>
              </div>
            </div>
          </div>
          <div class="card pad">
            <h3>{{ t('weeklySchedule') }}</h3>
            <div class="grid" v-if="planning && planning.schedule">
              <div class="memory-card" v-for="day in planning.schedule.days" :key="day.date">
                <strong>{{ day.date }} · {{ day.weekday }} <span v-if="day.holiday">· {{ day.holiday }}</span></strong>
                <div class="memory-meta">
                  <span class="chip" v-for="block in day.blocks" :key="day.date + block.start + block.kind">{{ block.start }}-{{ block.end }} {{ block.title }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="card pad">
            <h3>{{ t('webSearch') }}</h3>
            <div class="copy-box">
              <input v-model="planningQuery" :placeholder="t('searchPlaceholder')">
              <button class="primary" @click="runPlanningSearch">{{ t('runSearch') }}</button>
            </div>
            <p class="note" v-if="planningSearch && planningSearch.error">{{ planningSearch.error }}</p>
            <div class="grid" v-if="planningSearch && planningSearch.results">
              <div class="memory-card" v-for="item in planningSearch.results" :key="item.url">
                <strong>{{ item.title }}</strong>
                <a class="subtle" :href="item.url" target="_blank" rel="noreferrer">{{ item.url }}</a>
              </div>
            </div>
          </div>
        </section>

        <section v-if="activeView === 'background'" class="grid">
          <div class="grid three">
            <div class="metric"><span>{{ t('backgroundStatus') }}</span><strong>{{ background.paused ? t('backgroundPaused') : (background.active_job ? t('backgroundActive') : t('online')) }}</strong></div>
            <div class="metric"><span>{{ t('backgroundIdle') }}</span><strong>{{ background.idle_seconds || 0 }}</strong></div>
            <div class="metric"><span>{{ t('backgroundEligibility') }}</span><strong>{{ background.eligible_llm ? 'LLM' : (background.eligible_non_llm ? 'light' : '-') }}</strong></div>
          </div>
          <div class="card pad warning">
            <h3>{{ t('backgroundTitle') }}</h3>
            <p>{{ t('singleGpuHint') }}</p>
            <div class="toolbar">
              <button class="secondary" @click="refreshBackground">{{ t('refresh') }}</button>
              <button class="secondary" @click="pauseBackground">{{ t('pauseBackground') }}</button>
              <button class="primary" @click="resumeBackground">{{ t('resumeBackground') }}</button>
            </div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('runBackgroundJob') }}</h3>
              <div class="grid">
                <div class="field">
                  <label>{{ t('backgroundJobType') }}</label>
                  <select v-model="backgroundRunForm.job_type">
                    <option value="planning_regenerate">planning_regenerate</option>
                    <option value="autonomous_learning">autonomous_learning</option>
                    <option value="memory_os_snapshot">memory_os_snapshot</option>
                    <option value="memory_consolidation">memory_consolidation</option>
                    <option value="release_inactive_models">release_inactive_models</option>
                  </select>
                </div>
                <label><input type="checkbox" v-model="backgroundRunForm.force"> {{ t('backgroundForce') }}</label>
                <button class="primary" @click="runBackgroundJob">{{ t('runBackgroundJob') }}</button>
              </div>
            </div>
            <div class="card pad">
              <h3>{{ t('backgroundStatus') }}</h3>
              <pre class="log-box">{{ JSON.stringify(background, null, 2) }}</pre>
            </div>
          </div>
          <div class="card pad">
            <h3>{{ t('recentBackgroundJobs') }}</h3>
            <div class="memory-card" v-for="job in (background.recent_jobs || []).slice().reverse()" :key="job.id">
              <strong>{{ job.job_type }} · {{ job.status }}</strong>
              <p>{{ job.message || job.reason || job.session_id }}</p>
              <div class="memory-meta"><span class="chip">{{ job.session_id || '-' }}</span><span class="chip">{{ job.created_ts }}</span></div>
            </div>
          </div>
        </section>

        <section v-if="activeView === 'tools'" class="grid">
          <div class="grid three">
            <div class="metric"><span>{{ t('toolCategory') }}</span><strong>{{ selectedTool ? selectedTool.category : '-' }}</strong></div>
            <div class="metric"><span>{{ t('toolRequiresSession') }}</span><strong>{{ selectedTool && selectedTool.requires_session ? 'yes' : 'no' }}</strong></div>
            <div class="metric"><span>{{ t('toolRequiresLlm') }}</span><strong>{{ selectedTool && selectedTool.requires_llm ? 'yes' : 'no' }}</strong></div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('toolRun') }}</h3>
              <div class="field">
                <label>{{ t('toolName') }}</label>
                <select v-model="toolRunForm.tool_name" @change="selectTool(toolRunForm.tool_name)">
                  <option v-for="tool in tools" :key="tool.name" :value="tool.name">{{ tool.name }}</option>
                </select>
              </div>
              <p class="note" v-if="selectedTool">{{ selectedTool.description }}</p>
              <div class="memory-meta" v-if="selectedTool">
                <span class="chip">{{ t('toolCategory') }}: {{ selectedTool.category }}</span>
                <span class="chip">{{ t('toolMutates') }}: {{ selectedTool.mutates ? 'yes' : 'no' }}</span>
                <span class="chip">{{ t('toolRequiresLlm') }}: {{ selectedTool.requires_llm ? 'yes' : 'no' }}</span>
              </div>
              <div class="field">
                <label>{{ t('toolArguments') }}</label>
                <textarea class="textarea-code" v-model="toolRunForm.arguments"></textarea>
              </div>
              <div class="toolbar">
                <button class="secondary" @click="refreshTools">{{ t('refresh') }}</button>
                <button class="primary" @click="runTool">{{ t('toolRun') }}</button>
              </div>
            </div>
            <div class="card pad">
              <h3>{{ t('toolOutput') }}</h3>
              <pre class="log-box">{{ toolOutput ? JSON.stringify(toolOutput, null, 2) : '' }}</pre>
            </div>
          </div>
          <div class="card pad">
            <h3>{{ t('toolActions') }}</h3>
            <div class="memory-card" v-for="action in toolActions.slice().reverse()" :key="action.id">
              <strong>{{ action.tool_name }} · {{ action.status }}</strong>
              <p>{{ action.error || action.session_id }}</p>
              <div class="memory-meta">
                <span class="chip">{{ action.created_at }}</span>
                <span class="chip">{{ action.duration_ms }}ms</span>
                <span class="chip">{{ action.actor }}</span>
              </div>
            </div>
          </div>
        </section>

        <section v-if="activeView === 'shiro'" class="grid">
          <div class="grid three">
            <div class="metric"><span>{{ t('shiroEnabled') }}</span><strong>{{ shiro.enabled ? 'yes' : 'no' }}</strong></div>
            <div class="metric"><span>{{ t('online') }}</span><strong>{{ shiro.available ? 'yes' : 'no' }}</strong></div>
            <div class="metric"><span>{{ t('shiroIdentity') }}</span><strong>{{ shiro.identity || config.shiro_identity || '白' }}</strong></div>
            <div class="metric"><span>{{ t('emotionState') }}</span><strong>{{ ((shiro.state || {}).emotion || {}).primary || '-' }}</strong></div>
            <div class="metric"><span>{{ t('live2dSignal') }}</span><strong>{{ (shiro.live2d || ((shiro.state || {}).emotion || {}).live2d || {}).expression || '-' }}</strong></div>
            <div class="metric"><span>Motion</span><strong>{{ (shiro.live2d || ((shiro.state || {}).emotion || {}).live2d || {}).motion || '-' }}</strong></div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('thoughtContext') }}</h3>
              <pre class="log-box">{{ shiro.thought_context || (shiro.error ? shiro.error : '') }}</pre>
            </div>
            <div class="card pad">
              <h3>{{ t('observeStimulus') }}</h3>
              <div class="field"><label>{{ t('stimulusSource') }}</label><input v-model="shiroObserveForm.source"></div>
              <div class="field"><label>{{ t('stimulusText') }}</label><textarea class="textarea-code" v-model="shiroObserveForm.text"></textarea></div>
              <div class="toolbar">
                <button class="secondary" @click="refreshShiro">{{ t('refresh') }}</button>
                <button class="primary" @click="observeShiroStimulus">{{ t('observeStimulus') }}</button>
              </div>
            </div>
          </div>
          <div class="card pad">
            <h3>{{ t('toolIntentions') }}</h3>
            <div class="field"><label>{{ t('intentionText') }}</label><textarea class="textarea-code" v-model="shiroIntentForm.text" placeholder="帮我读 C:\\docs\\paper.pdf，并上网搜解法"></textarea></div>
            <div class="toolbar"><button class="primary" @click="inferShiroToolIntentions">{{ t('inferToolIntentions') }}</button></div>
            <div class="memory-card" v-for="item in shiroIntentions" :key="item.tool_name + item.desire">
              <strong>{{ item.tool_name }} · {{ item.risk_level || '-' }}</strong>
              <p>{{ item.reason }}</p>
              <div class="memory-meta">
                <span class="chip">{{ item.requires_confirmation ? 'confirm' : 'auto-ok' }}</span>
                <span class="chip">{{ item.external_action ? 'external' : 'local' }}</span>
                <span class="chip">{{ item.outcome_memory_policy }}</span>
              </div>
              <pre class="log-box">{{ JSON.stringify(item.suggested_arguments || {}, null, 2) }}</pre>
            </div>
          </div>
          <div class="card pad">
            <h3>{{ t('shiroStatus') }}</h3>
            <pre class="log-box">{{ JSON.stringify(shiro.state || shiro, null, 2) }}</pre>
          </div>
          <div class="card pad">
            <h3>{{ t('recentTransitions') }}</h3>
            <div class="memory-card" v-for="item in (shiro.recent_transitions || []).slice().reverse()" :key="item.timestamp + item.source">
              <strong>{{ item.source }} · {{ item.timestamp }}</strong>
              <p>{{ (item.notes || []).join('; ') }}</p>
              <div class="memory-meta">
                <span class="chip" v-for="(value, key) in item.signals" :key="key">{{ key }}: {{ value }}</span>
              </div>
            </div>
          </div>
        </section>

        <section v-if="activeView === 'pet'" class="grid">
          <div class="grid three">
            <div class="metric"><span>{{ t('petConnection') }}</span><strong>{{ vts.authenticated ? t('petAuthenticated') : (vts.connected ? t('petConnected') : t('petDisconnected')) }}</strong></div>
            <div class="metric"><span>{{ t('emotionState') }}</span><strong>{{ ((shiro.state || {}).emotion || {}).primary || '-' }}</strong></div>
            <div class="metric"><span>{{ t('live2dSignal') }}</span><strong>{{ (shiro.live2d || ((shiro.state || {}).emotion || {}).live2d || {}).expression || '-' }}</strong></div>
          </div>
          <div class="grid two">
            <div class="card pad pet-stage">
              <div class="pet-avatar" :class="[((shiro.state || {}).emotion || {}).primary || 'neutral']">
                <div class="pet-face">
                  <span></span><span></span>
                </div>
              </div>
              <h3>{{ t('petTitle') }}</h3>
              <p>{{ t('petSetupHint') }}</p>
              <div class="toolbar">
                <button class="primary" @click="vtsConnect">{{ t('petConnect') }}</button>
                <button class="secondary" @click="vtsRequestToken">{{ t('petRequestToken') }}</button>
                <button class="secondary" @click="vtsAuthenticate">{{ t('petAuthenticate') }}</button>
                <button class="secondary" @click="vtsRefresh">{{ t('petRefresh') }}</button>
                <button class="danger" @click="vtsDisconnect">{{ t('petDisconnect') }}</button>
              </div>
            </div>
            <div class="card pad">
              <h3>{{ t('petModel') }}</h3>
              <div class="field"><label>{{ t('petModelPath') }}</label><input :value="petModel && petModel.model_root || ''" readonly></div>
              <div class="field"><label>{{ t('petVtsUrl') }}</label><input v-model="vts.url"></div>
              <div class="field"><label>{{ t('petCurrentModel') }}</label><pre class="log-box">{{ JSON.stringify(vts.currentModel || {}, null, 2) }}</pre></div>
              <p class="warn-text" v-if="vts.error">{{ vts.error }}</p>
              <p v-if="vts.lastAction">{{ vts.lastAction }}</p>
            </div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('petExpression') }}</h3>
              <div class="field">
                <label>{{ t('petExpression') }}</label>
                <select v-model="vts.expressionFile">
                  <option v-for="item in (petModel && petModel.expressions ? petModel.expressions : [])" :key="item.file" :value="item.file">
                    {{ item.name }} / {{ item.file }} {{ item.exists ? '' : '(missing)' }}
                  </option>
                </select>
              </div>
              <div class="toolbar">
                <button class="primary" @click="syncPetWithShiro">{{ t('petSyncEmotion') }}</button>
                <button class="secondary" @click="vtsTriggerExpression()">{{ t('petTriggerExpression') }}</button>
              </div>
            </div>
            <div class="card pad">
              <h3>{{ t('petAvailableHotkeys') }}</h3>
              <div class="field">
                <label>{{ t('petHotkey') }}</label>
                <select v-model="vts.hotkeyId">
                  <option v-for="item in vts.hotkeys" :key="item.hotkeyID" :value="item.hotkeyID">
                    {{ item.name }} / {{ item.type }}
                  </option>
                </select>
              </div>
              <div class="toolbar">
                <button class="secondary" @click="vtsTriggerHotkey()">{{ t('petTriggerHotkey') }}</button>
              </div>
              <pre class="log-box">{{ JSON.stringify(vts.hotkeys || [], null, 2) }}</pre>
            </div>
          </div>
        </section>

        <section v-if="activeView === 'learning'" class="grid">
          <div class="grid three">
            <div class="metric"><span>{{ t('learningStatus') }}</span><strong>{{ (learning.job && (learning.job.active ? 'running' : learning.job.message)) || (learning.runtime && learning.runtime.status) || '-' }}</strong></div>
            <div class="metric"><span>{{ t('learningRepo') }}</span><strong>{{ learning.repo && learning.repo.exists ? 'local' : 'missing' }}</strong></div>
            <div class="metric"><span>{{ t('learningAdapter') }}</span><strong>{{ learning.runtime && learning.runtime.completed_steps || 0 }}</strong></div>
          </div>
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('learningTitle') }}</h3>
              <div class="field"><label>{{ t('shiroIdentity') }}</label><input v-model="learningForm.session_id"></div>
              <div class="field"><label>{{ t('learningSubject') }}</label><input v-model="learningForm.subject" placeholder="数学 / 小学 / 高中"></div>
              <div class="grid two">
                <div class="field"><label>{{ t('maxTokens') }}</label><input type="number" v-model.number="learningForm.max_new_tokens"></div>
                <div class="field"><label>{{ t('learningMaxSteps') }}</label><input type="number" v-model.number="learningForm.max_steps"></div>
                <div class="field"><label>{{ t('learningInterval') }}</label><input type="number" step="0.5" v-model.number="learningForm.interval_seconds"></div>
                <label><input type="checkbox" v-model="learningForm.use_model"> {{ t('learningUseModel') }}</label>
              </div>
              <div class="toolbar">
                <button class="secondary" @click="bootstrapLearningShiro">{{ t('learningBootstrap') }}</button>
                <button class="secondary" @click="refreshLearning">{{ t('refresh') }}</button>
                <button class="primary" @click="runLearningOnce">{{ t('learningRunOnce') }}</button>
                <button class="primary" @click="startLearning">{{ t('learningStart') }}</button>
                <button class="danger" @click="stopLearning">{{ t('learningStop') }}</button>
              </div>
            </div>
            <div class="card pad">
              <h3>{{ t('learningRepo') }}</h3>
              <p>{{ learning.repo && learning.repo.local_path }}</p>
              <pre class="log-box">{{ learning.repo && learning.repo.download_hint }}</pre>
              <h3>{{ t('learningAdapter') }}</h3>
              <p>{{ learning.runtime && learning.runtime.adapter_candidate_path }}</p>
            </div>
          </div>
          <div class="card pad">
            <h3>{{ t('learningStatus') }}</h3>
            <pre class="log-box">{{ JSON.stringify(learning, null, 2) }}</pre>
          </div>
        </section>

        <section v-if="activeView === 'training'" class="grid two">
          <div class="card pad">
            <div class="grid">
              <a class="subtle" href="/training/template">{{ t('downloadTemplate') }}</a>
              <div class="field"><label>{{ t('trainModelPath') }}</label><input v-model="trainingForm.model_path"></div>
              <div class="field"><label>{{ t('trainDataFile') }}</label><input v-model="trainingForm.data_file"></div>
              <div class="field"><label>{{ t('trainOutputDir') }}</label><input v-model="trainingForm.output_dir"></div>
              <div class="grid two"><div class="field"><label>{{ t('epochs') }}</label><input type="number" step="0.1" v-model.number="trainingForm.epochs"></div><div class="field"><label>{{ t('learningRate') }}</label><input type="number" step="0.000001" v-model.number="trainingForm.learning_rate"></div><div class="field"><label>{{ t('batchSize') }}</label><input type="number" v-model.number="trainingForm.per_device_train_batch_size"></div><div class="field"><label>{{ t('gradAccum') }}</label><input type="number" v-model.number="trainingForm.gradient_accumulation_steps"></div></div>
              <label><input type="checkbox" v-model="trainingForm.online"> {{ t('allowOnline') }}</label>
              <div class="toolbar"><button class="primary" @click="startTraining">{{ t('startTraining') }}</button><button class="secondary" @click="refreshTraining">{{ t('refresh') }}</button><button class="danger" @click="stopTraining">{{ t('stopTraining') }}</button></div>
            </div>
          </div>
          <div class="card pad"><h3>{{ t('trainingStatus') }}</h3><pre class="log-box">{{ JSON.stringify(training, null, 2) }}</pre></div>
        </section>

        <section v-if="activeView === 'line'" class="grid">
          <div class="grid two">
            <div class="card pad">
              <h3>{{ t('lineRuntime') }}</h3>
              <div class="grid two"><div class="field"><label>{{ t('lineHost') }}</label><input v-model="lineRuntimeForm.host"></div><div class="field"><label>{{ t('linePort') }}</label><input type="number" v-model.number="lineRuntimeForm.port"></div></div>
              <div class="toolbar"><button class="primary" @click="startLineRuntime">{{ t('startLine') }}</button><button class="secondary" @click="refreshLineRuntime">{{ t('refresh') }}</button><button class="danger" @click="stopLineRuntime">{{ t('stopLine') }}</button></div>
              <pre class="log-box">{{ lineRuntime.log_tail || JSON.stringify(lineRuntime, null, 2) }}</pre>
            </div>
            <div class="card pad warning">
              <h3>{{ t('tunnelTitle') }}</h3>
              <div class="field"><label>{{ t('tunnelTarget') }}</label><input v-model="tunnelTarget"></div>
              <div class="toolbar"><button class="primary" @click="startTunnel">{{ t('generateTunnel') }}</button><button class="secondary" @click="refreshTunnel">{{ t('refresh') }}</button><button class="danger" @click="stopTunnel">{{ t('stopTunnel') }}</button></div>
              <p class="note">{{ t('tunnelHint') }}</p>
              <div class="copy-box"><code>{{ tunnel.webhook_url || 'https://.../callback' }}</code><button class="secondary" @click="copyText(tunnel.webhook_url)">{{ t('copy') }}</button></div>
              <pre class="log-box">{{ tunnel.log_tail || JSON.stringify(tunnel, null, 2) }}</pre>
            </div>
          </div>
          <div class="card pad"><h3>{{ t('ttsCommand') }}</h3><p>{{ t('ttsCommandText') }}</p><code>G\\start_roleweaver_tts_api.bat</code></div>
          <div class="card pad">
            <div class="grid two">
              <div class="field"><label>{{ t('envText') }}</label><textarea class="textarea-code" v-model="lineSettings.env_text"></textarea></div>
              <div class="field"><label>{{ t('policyText') }}</label><textarea class="textarea-code" v-model="lineSettings.surface_policy_text"></textarea></div>
            </div>
            <div class="toolbar" style="margin-top:14px"><button class="secondary" @click="loadLineSettings">{{ t('refresh') }}</button><button class="primary" @click="saveLineSettings">{{ t('saveLineSettings') }}</button></div>
          </div>
        </section>

        <section v-if="activeView === 'evaluation'" class="grid two">
          <div class="card pad">
            <div class="grid">
              <div class="field"><label>{{ t('userProbe') }}</label><textarea v-model="personaProbe.user_text"></textarea></div>
              <div class="field"><label>{{ t('assistantProbe') }}</label><textarea v-model="personaProbe.assistant_text"></textarea></div>
              <div class="grid two"><div class="field"><label>{{ t('category') }}</label><input v-model="personaProbe.category"></div><div class="field"><label>{{ t('surface') }}</label><select v-model="personaProbe.surface"><option>web</option><option>line</option><option>tts</option><option>image</option></select></div></div>
              <button class="primary" @click="runPersonaScore">{{ t('runScore') }}</button>
            </div>
          </div>
          <div class="card pad"><h3>{{ t('score') }}</h3><pre class="log-box">{{ JSON.stringify(personaScore, null, 2) }}</pre><h3>{{ t('regressionCommands') }}</h3><pre class="log-box">runtime\\Scripts\\python.exe eval\\persona_regression\\run_persona_eval.py --local --config-file roleweaver.config.csv --score-persona-kernel
runtime\\Scripts\\python.exe eval\\persona_regression\\run_persona_interview.py --local --config-file roleweaver.config.csv --score-persona-kernel
runtime\\Scripts\\python.exe eval\\persona_regression\\run_long_dialogue_drift.py --local --config-file roleweaver.config.csv --score-persona-kernel</pre></div>
        </section>

        <section v-if="activeView === 'docs'" class="grid">
          <div class="card pad"><h3>{{ t('flowTitle') }}</h3><div class="flow-row"><div class="flow-node" v-for="node in flowNodes" :key="node.title"><strong>{{ node.title }}</strong><span>{{ node.body }}</span></div></div></div>
          <div class="card pad"><h3>{{ t('memoryFlowTitle') }}</h3><div class="flow-row"><div class="flow-node" v-for="node in memoryFlowNodes" :key="node"><strong>{{ node }}</strong><span>{{ t('docsBody') }}</span></div></div></div>
        </section>
      </main>
      <div class="toast" :class="{show: toastText}">{{ toastText }}</div>
    </div>
  `,
}).mount("#app");
