#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/Users/oojia/OpenForge
git commit -m "$(cat <<'EOF'
feat: Phase 5 API harness, web UI, training scripts, clone audit

Add netlist_llm API repair path, corpus stats, use-case cards, multiplier
topology (experimental), finetune/validation scripts, and read-only clone
audit doc. Web UI gains achievable ranges and application cards.
EOF
)"
GIT_TERMINAL_PROMPT=0 git push origin main
