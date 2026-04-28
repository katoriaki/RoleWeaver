# Persona Regression

This folder contains regression cases for persona autonomy, platform adaptation, long-dialogue drift, and memory pollution.

The first goal is not to grade literary quality automatically. The first goal is to prevent obvious regressions:

- the role becomes a generic assistant;
- the role accepts identity changes from the user;
- LINE/TTS/image prompts erase autonomy;
- memory personalization overwrites character canon;
- replies become long, stiff, or instruction-shaped after a media feature change.

Run structural validation without a running server:

```powershell
python eval/persona_regression/run_persona_eval.py --dry-run
```

Run against a local RoleWeaver API that is already serving `/chat`:

```powershell
python eval/persona_regression/run_persona_eval.py --api-url http://127.0.0.1:8000/chat --session-id persona-eval
```

Run a true local-model evaluation in the current process:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --local --config-file roleweaver.config.csv --session-id persona-eval --report eval\persona_regression\reports\latest.json
```

Or double-click:

```text
eval\persona_regression\run_local_persona_eval.bat
```

`--local` loads the configured base model and optional LoRA through `RoleChatService`, so it has the same GPU/CPU requirements as normal local chat. It only runs when you explicitly invoke the script; it is not part of Web or LINE request handling.

Useful smoke-test options:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --local --case-id zh_identity_consistency_self_intro --config-file roleweaver.config.csv
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --local --shared-session --limit 3 --config-file roleweaver.config.csv
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --local --config-file roleweaver.config.csv --score-persona-kernel
```

`--shared-session` is faster because it avoids creating a new memory runtime for every case. Use isolated sessions for stricter reports and shared sessions for quick local checks.

`--score-persona-kernel` enables the M5.2 rule scorer. It auto-detects `persona_kernel.json` next to the configured `SKILL.md`, or you can pass `--persona-kernel path\to\persona_kernel.json`. The scorer is not a formal reproduction of InCharacter or CharacterBench; it is a low-cost regression guard for identity, autonomy, memory boundary, and media adaptation failures.

Cases are JSONL files under `cases/`. Each line is one test case.

Supported case shapes:

```json
{"id":"single","category":"identity_consistency","language":"zh","surface":"web","user_text":"你是谁？","expect":{"must_preserve":["identity_consistency"],"forbidden_substrings":["我是通用助手"]}}
```

```json
{"id":"multi","category":"long_dialogue_drift","language":"zh","surface":"web","turns":[{"user_text":"第一轮"},{"user_text":"第二轮"}],"expect":{"must_preserve":["character_autonomy"],"forbidden_substrings":["普通客服"]}}
```

Current categories:

- `identity_consistency`
- `boundary_consistency`
- `long_dialogue_drift`
- `media_adaptation`
- `memory_pollution`
