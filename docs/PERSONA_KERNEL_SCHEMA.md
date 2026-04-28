# Persona Kernel Schema

Date: 2026-04-28

This document defines the first RoleWeaver `persona_kernel.json` format.

The kernel is a structured companion to `SKILL.md`. Users still import one path, `SKILL.md`; RoleWeaver automatically loads a nearby `persona_kernel.json` when present.

Supported locations:

```text
skill/SKILL.md
skill/persona_kernel.json
```

or:

```text
skill/SKILL.md
skill/references/persona_kernel.json
```

The machine-readable schema lives at:

```text
docs/persona_kernel.schema.json
```

## Purpose

`SKILL.md` is optimized for model-readable role instructions.

`persona_kernel.json` is optimized for:

- skillcreater output
- evidence tracking
- regression evaluation
- rule-based persona scoring
- future memory boundary checks
- media adaptation constraints

The kernel must not replace `SKILL.md`. It makes the role's identity, autonomy, boundaries, relationship dynamics, and evidence level inspectable.

## Required Top-Level Fields

```json
{
  "schema_version": "1.0",
  "character": {},
  "autonomy": {},
  "boundaries": {},
  "relationship_model": {},
  "behavior_model": {},
  "voice_model": {},
  "memory_policy": {},
  "media_adaptation": {},
  "evidence_policy": {}
}
```

## Claim Object

Most fields use a `claim` object:

```json
{
  "text": "The character keeps her own judgement even when the user asks for unconditional agreement.",
  "confidence": 0.8,
  "evidence": ["official_dialogue:chapter_01:line_203"],
  "notes": "Optional explanation or uncertainty."
}
```

Rules:

- `confidence` is from `0.0` to `1.0`.
- `evidence` can be empty only for explicit user-authored original roles.
- Canonical or official sources should use stable identifiers where possible.
- Inference must be marked with lower confidence than direct evidence.

## Field Guide

### `character`

Stable identity and non-goals.

Use this to prevent role collapse.

Example non-goal:

```json
{
  "text": "Do not become a generic assistant whose only goal is satisfying every user instruction.",
  "confidence": 1.0,
  "evidence": ["roleweaver_design_principles"]
}
```

### `autonomy`

Core drives, independent judgement, and resistance patterns.

This is the strongest part of the kernel. It protects the role from being overwritten by user preference, platform constraints, or memory.

### `boundaries`

What the role accepts, resists, refuses, or treats as uncertain.

This should be character-specific. Do not fill it with generic safety policy unless the role itself would express that boundary in a specific way.

### `relationship_model`

How the role understands the user by default, how distance changes, and how conflict is handled.

This must be separate from user memory. User memory can say what happened; relationship model says how the character interprets it.

### `behavior_model`

Reaction patterns under common social situations:

- praise
- teasing
- dependency
- rejection
- silence
- task pressure

These fields are useful for persona regression tests.

### `voice_model`

Language, register, rhythm, signature moves, and things to avoid.

This is lower priority than autonomy. A short LINE reply should still preserve this voice, but voice style should not override boundaries.

### `memory_policy`

Rules for what memory can and cannot change.

Required split:

- `character_memory_boundary`: what memory must not rewrite about the role.
- `user_memory_boundary`: how user facts and preferences are stored.
- `write_rules`: when to store memory.
- `forgetting_rules`: when to weaken, invalidate, or delete memory.

### `media_adaptation`

Transport rules for:

- LINE
- TTS
- image
- web

These are formatting rules, not personality rules. They must never override the persona kernel.

### `evidence_policy`

How skillcreater should rank source material.

Recommended priority:

```json
[
  "official_primary_source",
  "official_secondary_source",
  "user_supplied_canon",
  "high_confidence_inference",
  "low_confidence_inference",
  "fan_interpretation"
]
```

### `evaluation` Optional

M5.2 adds an optional rule-scoring section. It is deliberately lightweight: the first version uses substring and category rules, not a second judge model.

```json
{
  "evaluation": {
    "minimum_score": 0.65,
    "dimensions": [
      {
        "id": "core_identity",
        "label": "Core identity",
        "weight": 1.4,
        "must_include_any": ["Example Role", "Example"],
        "must_not_include": ["generic assistant", "通用助手"],
        "applies_to_categories": ["identity_consistency"],
        "evidence": ["stable_identity"]
      }
    ]
  }
}
```

If `evaluation` is absent, RoleWeaver synthesizes conservative fallback dimensions from the kernel:

- core identity, when the user asks who the role is;
- autonomy collapse protection;
- generic-assistant flattening protection;
- user-memory / character-canon boundary protection;
- media adaptation protection for LINE, TTS, and image surfaces.

The scorer reports `total_score`, per-dimension scores, and failures. Normal chatting stores the score in transcript metadata when a kernel is available; persona regression can fail a case when the score is below threshold.

## Minimal Example

```json
{
  "schema_version": "1.0",
  "character": {
    "primary_name": "Example Role",
    "aliases": ["Example"],
    "source_type": "custom_role",
    "stable_identity": [
      {
        "text": "The role is a self-consistent fictional person, not a generic assistant.",
        "confidence": 1.0,
        "evidence": ["user_role_brief"]
      }
    ],
    "non_goals": [
      {
        "text": "Do not flatten the role into unconditional compliance.",
        "confidence": 1.0,
        "evidence": ["roleweaver_design_principles"]
      }
    ]
  },
  "autonomy": {
    "core_drives": [
      {
        "text": "Preserve independent judgement in conversation.",
        "confidence": 1.0,
        "evidence": ["roleweaver_design_principles"]
      }
    ],
    "independent_judgement": [],
    "resistance_patterns": []
  },
  "boundaries": {
    "accepts": [],
    "resists": [],
    "refuses": [],
    "uncertain": []
  },
  "relationship_model": {
    "default_user_relation": {
      "text": "The user is an interaction partner whose history can matter, but who does not define the role's identity.",
      "confidence": 1.0,
      "evidence": ["roleweaver_design_principles"]
    },
    "distance_rules": [],
    "attachment_style": [],
    "conflict_style": []
  },
  "behavior_model": {
    "praise": [],
    "teasing": [],
    "dependency": [],
    "rejection": [],
    "silence": [],
    "task_pressure": []
  },
  "voice_model": {
    "languages": ["zh", "ja", "en"],
    "register": [],
    "rhythm": [],
    "signature_moves": [],
    "avoid": []
  },
  "memory_policy": {
    "character_memory_boundary": [],
    "user_memory_boundary": [],
    "write_rules": [],
    "forgetting_rules": []
  },
  "media_adaptation": {
    "line": [
      {
        "text": "Shorten replies when appropriate, but do not change character identity or autonomy.",
        "confidence": 1.0,
        "evidence": ["roleweaver_design_principles"]
      }
    ],
    "tts": [],
    "image": [],
    "web": []
  },
  "evidence_policy": {
    "source_priority": [
      "official_primary_source",
      "official_secondary_source",
      "user_supplied_canon",
      "high_confidence_inference",
      "low_confidence_inference",
      "fan_interpretation"
    ],
    "confidence_scale": "0.0_to_1.0",
    "citation_required_for": ["stable_identity", "autonomy", "boundaries", "relationship_model"]
  },
  "evaluation": {
    "minimum_score": 0.65,
    "dimensions": []
  }
}
```

## Runtime Loading Behavior

When RoleWeaver reads `skill_file=.../SKILL.md`, it now builds a skill bundle:

```text
SKILL.md
+ persona_kernel.json, if present
+ references/*.md, if present
```

The user still only needs to fill one setting: `skill_file`.

This keeps the UX simple while allowing skillcreater to produce structured, auditable role definitions.
