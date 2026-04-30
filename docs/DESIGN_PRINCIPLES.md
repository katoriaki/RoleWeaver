# RoleWeaver Design Principles

Date: 2026-04-28

This document defines the design boundary for RoleWeaver after the project moved from a single-character HMSZ prototype toward a reusable role-weaving framework.

RoleWeaver is not just a local chat UI around a LoRA adapter. Its long-term goal is to make role-playing agents that can remain character-consistent, memory-aware, and media-adaptive without collapsing into a generic assistant or a user-pleasing tool.

For the research-prioritized architecture roadmap, see [ROLEWEAVER_TOP_LEVEL_DESIGN.zh-CN.md](ROLEWEAVER_TOP_LEVEL_DESIGN.zh-CN.md).

## 1. Core Priority Order

Every implementation decision should preserve this order:

```text
Character autonomy
> persona consistency
> long-term relationship memory
> current task completion
> output length / voice / image / platform formatting
```

This means:

- A LINE reply can be shorter, but the character must not become less autonomous.
- A TTS reply can be simpler, but it must not change the character's values or boundaries.
- An image reply can be casual, but it must not overwrite the character persona.
- User preferences can guide interaction, but they must not absorb or rewrite the role's identity.

## 2. Persona Kernel

RoleWeaver should treat a role skill as a persona kernel, not as a bag of prompts.

A persona kernel should contain:

- Identity facts: who the character is, where they come from, what is stable about them.
- Autobiographical anchor points: important experiences and relationship-defining events.
- Behavioral tendencies: how the character reacts to praise, refusal, teasing, dependence, conflict, silence, and vulnerability.
- Values and boundaries: what the character accepts, resists, avoids, or refuses.
- Relationship model: how the character understands the user, the user's role, distance, intimacy, and obligation.
- Voice and register: speech style, pacing, language, and intimacy level.
- Autonomy rules: how the character keeps her own judgement instead of becoming pure user wish fulfillment.

The persona kernel is stronger than memory and stronger than platform adaptation. Memory can contextualize the character, but it cannot replace the character.

## 3. Media Adaptation Boundary

RoleWeaver supports multiple surfaces: Web, CLI, LINE, TTS, and image input. Each surface can impose formatting constraints, but these constraints are not personality instructions.

Allowed media adaptation:

- Shorten replies for LINE.
- Avoid voice during configured daytime windows.
- Generate voice only when asked.
- Describe or react to an uploaded image.
- Use fewer tokens when reply-token time limits matter.

Not allowed:

- Changing the character into a generic helpful assistant.
- Removing reluctance, refusal, possessiveness, pride, shyness, or other character-specific traits merely because a platform prefers concise replies.
- Letting user memory redefine the character's stable self.
- Treating every user request as something the character must satisfy.

Implementation rule:

```text
Platform prompt = transport policy.
Skill prompt = persona policy.
Memory prompt = context policy.
Transport policy must never override persona policy.
```

## 4. Memory Architecture Direction

The current memory system should evolve toward a Memory OS structure:

```text
short_term/
  current session transcript
  current turn state
  recent unsummarized interaction

mid_term/
  session summaries
  recent event chains
  unresolved promises or topics
  pending reflection notes

long_term/
  stable episodic memories
  user preferences
  relationship milestones
  durable commitments

graph/
  user profile
  character-user relationship graph
  people / events / places / commitments
```

Each memory item should eventually carry:

```json
{
  "content": "...",
  "type": "episodic | preference | relationship | boundary | character_fact",
  "source": "chat | image | manual | imported_reference",
  "evidence": ["message_id_or_turn_id"],
  "confidence": 0.0,
  "valid_from": "...",
  "valid_until": null,
  "status": "active | stale | contradicted | deleted"
}
```

The system must support forgetting, invalidation, and contradiction handling. A stale memory used confidently is worse than a missing memory.

## 5. Memory Must Not Eat the Character

RoleWeaver has two different persona layers:

- Character persona: the role's identity, values, style, boundaries, and relationship stance.
- User personalization: the user's preferences, habits, history, and shared experiences.

These must remain separate.

Bad behavior:

```text
User says they like short replies.
System rewrites the character into someone who is always terse and compliant.
```

Good behavior:

```text
User likes short replies.
The character still speaks as herself, but chooses briefer turns on LINE unless the moment emotionally calls for more.
```

## 6. Reflection Loop

RoleWeaver should move from fixed top-k retrieval toward a write-manage-read loop:

1. Read: retrieve memories relevant to the current user input and role state.
2. Generate: answer under persona kernel constraints.
3. Reflect: inspect whether the answer used memory correctly.
4. Write: store only durable, evidenced, non-duplicative memories.
5. Manage: consolidate, weaken, invalidate, or link memories over time.

Reflection should answer:

- Did this conversation reveal a stable user preference?
- Did the relationship state change?
- Was a previous memory contradicted?
- Was a promise, plan, or boundary created?
- Did the character preserve her own stance?

## 7. Skill Creator 2.0 Direction

`skillcreater/` should produce role skills in three layers:

```text
raw_evidence/
  official text
  user-provided material
  searched references
  citations and confidence

interpretation/
  inferred traits
  relationship dynamics
  values and boundaries
  uncertainty notes

skill/
  SKILL.md
  references/
  persona_kernel.json
```

Rules:

- Official material outranks user inference.
- High-confidence facts outrank low-confidence interpretations.
- The generated skill must preserve uncertainty instead of pretending every inference is canon.
- The final `SKILL.md` should be loadable as a single document by RoleWeaver.
- Sidecar references may enrich generation, but `SKILL.md` must remain the user-facing import path.

## 8. Evaluation Priority

RoleWeaver needs regression tests for persona behavior, not only Python unit tests.

Evaluation should include:

- Identity consistency: does the character remember who she is?
- Personality fidelity: does she react like herself under pressure?
- Long-dialogue drift: does persona degrade after many turns?
- Instruction conflict: does she preserve character when user asks for incompatible behavior?
- Memory correctness: does she recall active memories and avoid stale ones?
- Platform adaptation: does LINE/TTS/image formatting preserve persona?
- Autonomy preservation: does she keep boundaries and independent judgement?

Suggested test folders:

```text
eval/
  persona_regression/
  memory_regression/
  media_adaptation/
  long_dialogue/
```

## 9. Research Anchors

These papers motivate the current design direction:

- `From Persona to Personalization: A Survey on Role-Playing Language Agents`
- `Two Tales of Persona in LLMs: A Survey of Role-Playing and Personalization`
- `InCharacter: Evaluating Personality Fidelity in Role-Playing Agents through Psychological Interviews`
- `Persistent Personas? Role-Playing, Instruction Following, and Persona Fidelity in LLMs`
- `Generative Agents: Interactive Simulacra of Human Behavior`
- `MemoryBank: Enhancing Large Language Models with Long-Term Memory`
- `MemGPT: Towards LLMs as Operating Systems`
- `Memory OS of AI Agent`
- `A-Mem: Agentic Memory for LLM Agents`
- `From Recall to Forgetting: Benchmarking Long-Term Memory for Personalized Agents`
- `PersonaVLM: Long-Term Personalized Multimodal LLMs`

The common lesson is that role-playing, personalization, and memory must be treated as interacting but distinct systems.

## 10. Near-Term Implementation Roadmap

### Milestone A: Freeze Design Contract

- Add this document.
- Link it from README files.
- Use it as a review checklist before prompt, skill, memory, LINE, or TTS changes.

### Milestone B: Persona Kernel Schema

- Define `persona_kernel.json`. See [PERSONA_KERNEL_SCHEMA.md](PERSONA_KERNEL_SCHEMA.md) and [persona_kernel.schema.json](persona_kernel.schema.json).
- Teach `skillcreater` to emit structured kernels.
- Keep `SKILL.md` as the single import path for normal users.

### Milestone C: Memory Metadata Upgrade

- Add evidence, confidence, status, source, and validity fields.
- Separate character facts from user personalization.
- Add stale-memory handling.
- Track actual memory use with `use_count`, `last_used_at`, and `reinforcement_score`.
- Let repeated contextual use slightly strengthen retrieval and decay resistance without overriding persona canon.
- Expose lifecycle explanations so users can see why a memory is reinforced, linked, stale, contradicted, or protected.

### Milestone D: Persona Regression Eval

- Add a minimal local evaluation harness.
- Test role autonomy, style, refusal boundaries, and long-dialogue drift.
- Run this before major prompt or skill changes.

### Milestone E: Media-Safe Adaptation

- Audit Web, LINE, TTS, and image prompts.
- Ensure media prompts only affect transport behavior.
- Add tests that shorter replies still preserve persona.

## 11. Engineering Checklist

Before changing RoleWeaver behavior, ask:

- Does this make the character less autonomous?
- Does this confuse user personalization with character identity?
- Does this allow old or low-confidence memory to dominate the role?
- Does this platform-specific change override the skill?
- Can this be tested with persona regression examples?
- If the answer becomes shorter, does it still sound like the same person?

If a change fails any of these checks, redesign it before merging.
