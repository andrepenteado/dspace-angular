#!/usr/bin/env bash
#
# Levanta o DSpace Angular em modo desenvolvimento, sem precisar de IDE,
# contra o backend de demonstração do projeto DSpace (demo.dspace.org,
# dados fictícios — definido em config/config.yml).
#
# Uso:
#   ./scripts/start-dev.sh            # config padrão (config/config.yml)
#   ./scripts/start-dev.sh unesc     # aplica config/acesso-academico-unesc.yml
#                                    # por cima (metadados configuráveis do cliente)
#
# A UI sobe em http://localhost:4000. Mudanças em config/*.yml exigem
# reiniciar o script (o config é embutido no bundle no início do serve).

set -euo pipefail
cd "$(dirname "$0")/.."

# O build de desenvolvimento do DSpace Angular estoura o heap padrão do Node
export NODE_OPTIONS="--max_old_space_size=4096${NODE_OPTIONS:+ $NODE_OPTIONS}"

if ! command -v node > /dev/null; then
  echo "ERRO: node não encontrado no PATH (requer Node 18)." >&2
  exit 1
fi

case "$(node -v)" in
  v18.*) ;;
  *) echo "AVISO: Node recomendado é 18.x (encontrado $(node -v))." >&2 ;;
esac

if ! command -v yarn > /dev/null; then
  echo "ERRO: yarn não encontrado no PATH (npm install -g yarn)." >&2
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "==> Instalando dependências (primeira execução)..."
  yarn install
fi

if [ $# -ge 1 ]; then
  CONFIG_CLIENTE="config/acesso-academico-$1.yml"
  if [ ! -f "$CONFIG_CLIENTE" ]; then
    echo "ERRO: $CONFIG_CLIENTE não existe." >&2
    exit 1
  fi
  export DSPACE_APP_CONFIG_PATH="$CONFIG_CLIENTE"
  echo "==> Config do cliente aplicada: $CONFIG_CLIENTE"
fi

echo "==> Subindo em http://localhost:4000 (backend: demo.dspace.org)..."
exec yarn run start:dev
