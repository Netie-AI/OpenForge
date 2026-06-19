#!/usr/bin/env bash
cd /mnt/c/Users/oojia/OpenForge
git commit -m "$(cat <<'EOF'
feat: Phase 6 comparator block decomposition with regression gate

Extract tail_current_source, differential_pair, current_mirror, and
output stage into forge/blocks; comparator composes them with identical
ngspice behavior verified by pre/post 50-sim batch comparison.
EOF
)"
