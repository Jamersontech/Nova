# 0047 — The Conversation Provider Is Anthropic, Behind the Existing Gateway

**Status:** **Proposed**
**Proposed:** 2026-08-16 — Conversation slice, under ADR 0044
**Section:** 05 — `D-08` was fixed by Section 05 as criteria and deferred as a product choice
**Resolves:** `D-08` — for the Conversation capability. Reopened per Section 05's own terms:
`Q-06` and `Q-03` are answered (James, 2026-08-15/16), which is the condition
`DEFERRED_DECISIONS.md` set for this decision.

## Decision

**Conversation calls Anthropic's Messages API, model `claude-sonnet-5`, through the existing
`ModelGateway` and the existing `RealAnthropicTransport`. Nothing above the gateway knows the
provider exists.**

The application's entire knowledge of the provider is one declaration:

```python
CONVERSATION_PROFILE = CapabilityProfile(
    name="conversation",
    permitted_providers=frozenset({"anthropic"}),
    permitted_models=frozenset({"claude-sonnet-5"}),
)
```

That is a `CapabilityProfile` — the shape `I-98` requires: routing declared ahead of time, never
selected by model output at call time. Removing or replacing the provider is editing this
constant and registering a different transport. No provider-specific logic exists anywhere in
the application layer (`PR-1`, `PR-9`).

## Why Anthropic, measured against the fixed criteria

`MODEL_GATEWAY_ARCHITECTURE.md` §8 fixed nine criteria (`PR-1`–`PR-9`) precisely so this
decision would be a measurement, not a preference:

| | Status |
| --- | --- |
| `PR-1` expressible as a profile | **Yes** — shown above; the gateway seam was built for exactly this |
| `PR-2` no-training commitment | **Yes, as an assurance** — Anthropic's commercial terms commit to not training on API customer content. Per §8's own words this is *accepted on trust*; verification is `D-39`, unresolved, and the `T-15` residual stands |
| `PR-3` stated retention/logging | **Yes, as an assurance** — same posture as `PR-2` |
| `PR-4` data residency | **Compatible with `Q-06`** — James accepted cloud processing with few external processors; one model provider is the minimal set |
| `PR-5` no cross-request context reuse | **Yes, as an assurance** — the Messages API is stateless per request; NOVA sends full context each call |
| `PR-6` structured output | **Yes** — sufficient for the one marker Conversation parses (below) |
| `PR-7` revocable credential | **Yes** — a console-revocable API key, held as `control-plane/anthropic` by reference; rotation is an environment change, not a code change (`MG-13`) |
| `PR-8` measurable | **Yes** — per-call token usage is returned and already logged (metadata only) by the transport |
| `PR-9` removable | **Yes** — delete one constant and one registration; the gateway, PDP, boundary and UI are untouched |

**And one criterion no other candidate can match today:** the transport already exists and has
been **validated against the real API** — the real-provider validation run drove NOVA's
control-plane credential path to `api.anthropic.com` and proved I-98/I-99 held against genuine
model output, including output that named a hostile provider. Choosing a different provider
would mean writing and validating a new egress boundary to gain nothing this slice needs.

**Model choice.** `claude-sonnet-5` for Conversation: the conversation surface is NOVA's primary
interface and carries interpretation work (proposing actions from natural language), which is
worth a capable model. The earlier validation run used a smaller model for cost-capped protocol
validation; that remains the right tool for that job. The model ID is one string in one profile
— changing it is not an architectural event.

## What the decision does NOT change

- **`I-94`–`I-99` govern every call.** Conversation reaches the provider only through
  `ModelGateway.call`: per-call authorization, one scope per request, classification egress
  gates, fixed routing, computed cost charged to a budget before egress, response taint computed
  from the request.
- **The credential stays at the egress boundary** (`I-103`, `I-22`): resolved from the
  environment inside the transport at send time, never held upstream, never logged, sanitized
  out of error text.
- **Model output holds no authority.** A response is text with computed taint. The one
  structured thing Conversation reads from it — a proposal marker — creates a *pending approval*
  through the existing `ApprovalService`, which is the same as creating nothing until James
  decides.
- **Multiple providers are not added.** `I-97` supports a permitted *set*; the set has one
  member because the slice needs one. Fallback across providers is a future edit to a frozenset,
  not new architecture.

## Reversibility

**High.** One profile constant, one binding registration, one transport already in the tree.
The conversation service, seam routes, approval flow and tests are provider-blind. `PR-9` was a
criterion precisely so this paragraph could be short.
