#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/Users/oojia/OpenForge
source .venv_wsl/bin/activate

cp openanalog/forge/topologies/comparator.py /tmp/comparator.py.post
cp openanalog/forge/topology_variants.py /tmp/topology_variants.py.post

echo "=== POST-REFACTOR BATCH (blocks) ==="
python scripts/compare_comparator_batch.py post > /tmp/comparator_batch_post.json

git checkout HEAD -- openanalog/forge/topologies/comparator.py openanalog/forge/topology_variants.py

echo "=== PRE-REFACTOR BATCH (HEAD) ==="
python scripts/compare_comparator_batch.py pre > /tmp/comparator_batch_pre.json

cp /tmp/comparator.py.post openanalog/forge/topologies/comparator.py
cp /tmp/topology_variants.py.post openanalog/forge/topology_variants.py

python scripts/diff_comparator_batch.py
