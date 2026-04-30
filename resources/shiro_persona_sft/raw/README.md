# Shiro persona SFT raw data

Put local, legally usable SFT files here.

Expected layout:

```text
raw/<source_id>/*.jsonl
raw/<source_id>/*.csv
```

JSONL rows:

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

CSV files need `user,assistant` columns.

The builder treats non-Shiro sources as trait-pattern references only. They must not become Shiro's identity, canon, or memory.

For local Plastic Memories / Isla scenario extraction, use:

```text
resources/shiro_persona_sft/extract_plastic_memories_isla.py
```

The generated rows should go under:

```text
raw/limited_memory_ai/plastic_memories_isla.jsonl
```
