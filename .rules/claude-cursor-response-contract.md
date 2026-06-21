# Claude-Cursor Response Contract (OF-C2C-v1)

All cross-agent handoffs should start with:

```text
Protocol: OF-C2C-v1
Role: <Claude reviewer | Cursor executor>
Intent: <review | execution | clarification>
Decision: <accept | accept_with_followup | needs_patch | needs_runtime_verification | blocked>
```

## Claude required sections

1. Findings (highest severity first)
2. Evidence accepted
3. Missing evidence / open questions
4. Cursor next steps

## Cursor required sections

1. Implemented
2. Verification output (verbatim)
3. Evidence for review (diff or function excerpts)
4. Not verified
5. Why / thought process (1–3 sentences: approach vs alternatives, tradeoff, what to reconsider if wrong)
6. Message for Claude

If no findings exist, Claude should explicitly say so and still list residual risk.
