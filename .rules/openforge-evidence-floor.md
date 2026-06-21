# OpenForge Evidence Floor

## Rule

Evidence beats claims. No implementation claim is accepted without attached proof.

## Minimum proof requirements

- Code changes: scoped `git diff` or changed function excerpts.
- Verification: verbatim command output.
- Artifacts: file paths and brief contents/meaning.
- Missing runs: explicit `not verified` section.

## Gate language

Use only one of: `working`, `partial`, `broken`, `unverified`.

Do not label a gate `working` if a blocking verification item is missing.

## Subagent policy

- `dv-verifier` is read-only and blocking by default for gate-critical checks.
- Background verifier is allowed only for non-gate diagnostics.
