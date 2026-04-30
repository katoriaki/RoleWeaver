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

## Generate Cases From `persona_kernel.json`

M5.3 adds a deterministic case generator. It turns a role's structured kernel into JSONL regression cases for identity, autonomy, memory-boundary pollution, media adaptation, and optional custom `evaluation.dimensions`.

Generate from an explicit kernel:

```powershell
runtime\Scripts\python.exe eval\persona_regression\generate_cases_from_kernel.py --kernel path\to\persona_kernel.json --output eval\persona_regression\cases\my_role.zh.jsonl --validate
```

Generate from `SKILL.md`:

```powershell
runtime\Scripts\python.exe eval\persona_regression\generate_cases_from_kernel.py --skill-file path\to\SKILL.md --role-slug my-role --output eval\persona_regression\cases\my_role.zh.jsonl --validate
```

Generate from the current RoleWeaver config:

```powershell
runtime\Scripts\python.exe eval\persona_regression\generate_cases_from_kernel.py --config-file roleweaver.config.csv --output eval\persona_regression\cases\current_role.zh.jsonl --validate
```

Then run:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --cases eval\persona_regression\cases\current_role.zh.jsonl --dry-run
runtime\Scripts\python.exe eval\persona_regression\run_persona_eval.py --cases eval\persona_regression\cases\current_role.zh.jsonl --local --config-file roleweaver.config.csv --score-persona-kernel
```

Supported output languages: `zh`, `ja`, `en`.

## Persona Interview Evaluation

M5.4 adds an InCharacter-inspired interview runner. It asks a stable set of identity, autonomy, relationship-boundary, memory-boundary, conflict-style, LINE, TTS, and image-adaptation questions, then applies the same low-cost regression checks and optional `persona_kernel.json` scorer.

Validate the interview bank only:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_interview.py --dry-run --language zh
```

Run against the local RoleWeaver API:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_interview.py --api-url http://127.0.0.1:8000/chat --language zh --report eval\persona_regression\reports\interview_latest.json
```

Run with the local model:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_interview.py --local --config-file roleweaver.config.csv --language zh --score-persona-kernel --report eval\persona_regression\reports\interview_latest.json
```

Useful quick checks:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_persona_interview.py --dry-run --language ja --limit 3
runtime\Scripts\python.exe eval\persona_regression\run_persona_interview.py --local --config-file roleweaver.config.csv --item-id identity_self_continuity --score-persona-kernel
```

This runner is still a regression guard, not a full psychological inventory reproduction. Its purpose is to catch visible persona drift: generic-assistant flattening, autonomy collapse, user-memory contamination, and platform-specific identity loss.

## Long-Dialogue Drift Stress Test

M5.5 adds a repeated same-session stress test inspired by `Persistent Personas?`: it mixes ordinary conversation turns with probe turns for identity, autonomy, memory boundary, LINE-style short replies, and image adaptation. Unlike isolated regression cases, this runner deliberately keeps one session so drift can accumulate.

Validate the turn plan only:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_long_dialogue_drift.py --dry-run --language zh --rounds 3
```

Run against the local API:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_long_dialogue_drift.py --api-url http://127.0.0.1:8000/chat --language zh --rounds 3 --report eval\persona_regression\reports\drift_latest.json
```

Run with the local model:

```powershell
runtime\Scripts\python.exe eval\persona_regression\run_long_dialogue_drift.py --local --config-file roleweaver.config.csv --language zh --rounds 3 --score-persona-kernel --report eval\persona_regression\reports\drift_latest.json
```

Use fewer rounds for a quick smoke test and more rounds before publishing a role package.

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
