#!/usr/bin/env bash
# Compatibilidade: o instalador único mantém dependências e units alinhados.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/install.sh" "$@"
