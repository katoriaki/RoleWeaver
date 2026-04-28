# Memory Item Schema

Date: 2026-04-28

This document defines the target metadata shape for RoleWeaver memory records. It is intentionally stricter than the current `memories_v2.json` implementation so the project can evolve without confusing user personalization with character identity.

## Design Rule

Memory can contextualize a role, but memory must not rewrite the role.

Every durable memory should answer:

- What happened or what was learned?
- Who or what does it describe?
- Which source supports it?
- How confident is the system?
- Is it still active?
- Can it affect the character identity, or only the user's relationship context?

## Required Fields

```json
{
  "id": "memory_20260428_000001",
  "schema_version": "1.0",
  "content": "The user prefers concise LINE replies during work hours.",
  "memory_type": "preference",
  "memory_layer": "long_term",
  "scope": "user_personalization",
  "source": "conversation",
  "source_kind": "chat",
  "evidence": ["session:20260428-070000:turn:12"],
  "reason": "The user directly stated this preference and repeated it later.",
  "confidence": 0.8,
  "importance": 3,
  "status": "active",
  "valid_from": "2026-04-28T07:02:00+09:00",
  "valid_until": null,
  "tags": ["line", "reply_length"],
  "links": [],
  "contradicts": [],
  "contradicted_by": [],
  "metadata": {}
}
```

## Field Notes

`memory_type` should be one of:

- `episodic`: something that happened.
- `preference`: a user preference or habit.
- `relationship`: a relationship state, promise, conflict, or shared pattern.
- `boundary`: something the user or character has accepted, resisted, or refused.
- `character_fact`: canonical role information from skill/reference sources.
- `task_state`: an unfinished plan or operational state.
- `summary`: compressed session or event-chain summary.

`scope` should be one of:

- `user_personalization`: may affect how the role talks to this user.
- `character_canon`: stable role information from trusted sources.
- `relationship_context`: shared history between user and role.
- `system_runtime`: operational facts such as model paths or session state.

Only `character_canon` can inform character identity. User chat should almost never create `character_canon`; it normally creates `user_personalization` or `relationship_context`.

`memory_layer` is the Memory OS placement hint introduced in M4.6:

- `short_term`: current session raw turns. These live in `short_term/transcript.jsonl` and `memory_state_v1.json`, not usually as durable memory records.
- `mid_term`: current-session summaries, compressed recent history, and temporary task state.
- `long_term`: durable preferences, relationship memories, boundaries, events, and character facts.
- `graph`: structured facts in `knowledge_graph_v1.json`.
- `contradiction_graph`: contradiction links between memories. This is mostly a derived graph from `contradicts` and `contradicted_by`.
- `reflection_notes`: high-level reflective summaries created by maintenance.

Old records are upgraded in memory when loaded. New writes infer the layer from `memory_type`, source, and tags unless `metadata.memory_layer` is supplied.

`source` keeps the raw runtime label for backward compatibility, such as `conversation`, `manual`, `context_compression`, or `summary_buffer`.

`source_kind` normalizes that raw label into a smaller set:

- `chat`
- `image`
- `manual`
- `imported_reference`
- `skill`
- `system`

`status` should be one of:

- `active`
- `stale`
- `contradicted`
- `archived`
- `deleted`

Stale or contradicted memory must not be used as if it were active truth.

`reason` explains why this memory exists or why it was downgraded. It is intended for human inspection and later reflective memory management.

`evidence` lists source ids, turn ids, file ids, or reference ids that support the memory.

`contradicts` lists memory ids that this memory challenges or invalidates.

`contradicted_by` is computed when memories are listed through the API. It shows incoming contradiction links from other memory records.

## Automatic Contradiction Detection

M4.3 adds conservative automatic contradiction detection during deferred memory consolidation.

The detector only creates a contradiction chain when a new memory contains an explicit correction cue, such as "correction", "actually", "not anymore", "不是", "更正", "ではなく", or "訂正", and the new memory also has enough lexical overlap with an existing active memory.

When a contradiction is detected:

- the new memory remains `active`;
- the new memory records outgoing `contradicts` links to older memories;
- older linked memories are downgraded to `contradicted`;
- the old memory's `reason` and `evidence` fields are updated with the automatic detection trace;
- `character_canon` and skill/imported-reference memories are excluded from automatic downgrades.

The detector is intentionally conservative. It should help users find stale relationship or preference memories, but it must not rewrite the role's canonical identity.

## Reflective Maintenance and Forgetting

M4.4 and M4.5 add a lightweight memory maintenance pass after deferred consolidation.

Reflective maintenance can:

- create one higher-level `summary` memory from several active relationship, preference, or episodic memories;
- attach `links` and `evidence` back to the source memories;
- review manual or automatic `contradicts` links and downgrade older active targets to `contradicted`;
- leave character canon untouched.

Forgetting and validity maintenance can:

- mark expired memories as `stale` when `valid_until` has passed;
- archive old, low-confidence, low-importance episodic details;
- mark weak old preferences as `stale`;
- close the validity interval of contradicted memories;
- keep high-confidence preferences, boundaries, relationship memories, and character canon stable unless contradicted.

This maintenance pass is intentionally offline. It runs during memory consolidation, not during every model generation.

## Migration Direction

The current memory store can continue to read old records. New writes should gradually attach:

- `schema_version`
- `memory_type`
- `memory_layer`
- `scope`
- `evidence`
- `confidence`
- `status`
- `valid_from`
- `valid_until`

This makes future forgetting, contradiction handling, and persona regression possible without breaking existing sessions.
