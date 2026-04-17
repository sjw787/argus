#!/bin/bash
# Installs the pre-push coverage hook into .git/hooks/.
# Run once after cloning: bash scripts/install-hooks.sh

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
HOOK_SRC="$ROOT/scripts/pre-push"
HOOK_DEST="$ROOT/.git/hooks/pre-push"

if [ ! -f "$HOOK_SRC" ]; then
  echo "❌  Hook script not found at scripts/pre-push"
  exit 1
fi

cp "$HOOK_SRC" "$HOOK_DEST"
chmod +x "$HOOK_DEST"

echo "✅ Pre-push hook installed at .git/hooks/pre-push"
echo "   Coverage will be checked before every push."
