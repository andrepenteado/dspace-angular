#!/usr/bin/env python3
"""
Submete uma publicação completa no DSpace 7.6 via REST API.

Fluxo implementado (ver docs/endpoints-publicacao.md):
  1. GET  /api/security/csrf                                  -> token CSRF
  2. POST /api/authn/login                                    -> JWT
  3. GET  /api/core/collections/search/findSubmitAuthorized   -> coleção (se não informada por uuid)
  4. POST /api/submission/workspaceitems?owningCollection=... -> workspaceitem
  5. PATCH metadados (JSON Patch nas seções traditionalpageone/traditionalpagetwo)
  6. POST  multipart (upload dos arquivos)
  7. PATCH licença (granted=true)
  8. POST /api/workflow/workflowitems (text/uri-list)         -> depósito
  9. GET  /api/core/items/{uuid}                              -> confirmação

Uso:
  pip install -r requirements.txt
  python submeter_publicacao.py --config publicacao.exemplo.json

  # ou informando credenciais por variáveis de ambiente:
  DSPACE_USER=admin@exemplo.br DSPACE_PASSWORD=senha \
      python submeter_publicacao.py --config publicacao.exemplo.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests


class DSpaceClient:
    """Cliente mínimo da REST API do DSpace 7.x com tratamento de CSRF e JWT."""

    def __init__(self, server: str, verify_ssl: bool = True):
        # server ex.: https://demo.dspace.org/server
        self.server = server.rstrip("/")
        self.api = f"{self.server}/api"
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.csrf_token: str | None = None
        self.jwt: str | None = None

    # ---------- infraestrutura ----------

    def _headers(self, extra: dict | None = None) -> dict:
        h = {}
        if self.csrf_token:
            h["X-XSRF-TOKEN"] = self.csrf_token
        if self.jwt:
            h["Authorization"] = self.jwt
        if extra:
            h.update(extra)
        return h

    def _update_tokens(self, resp: requests.Response) -> None:
        # O DSpace rotaciona o token CSRF: sempre usar o mais recente.
        new_csrf = resp.headers.get("DSPACE-XSRF-TOKEN")
        if new_csrf:
            self.csrf_token = new_csrf
        new_auth = resp.headers.get("Authorization")
        if new_auth:
            self.jwt = new_auth

    def request(self, method: str, path: str, ok=(200, 201, 204), **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{self.api}{path}"
        headers = self._headers(kwargs.pop("headers", None))
        resp = self.session.request(method, url, headers=headers, **kwargs)
        self._update_tokens(resp)
        if resp.status_code not in ok:
            raise RuntimeError(
                f"{method} {url} -> HTTP {resp.status_code}\n{resp.text[:2000]}"
            )
        return resp

    # ---------- passos do fluxo ----------

    def init_csrf(self) -> None:
        self.request("GET", "/security/csrf", ok=(200, 204, 404))
        if not self.csrf_token:
            # fallback: qualquer GET na raiz da API também emite o token
            self.request("GET", "")
        print(f"[1] CSRF obtido: {self.csrf_token[:8]}…")

    def login(self, user: str, password: str) -> None:
        self.request(
            "POST", "/authn/login",
            data={"user": user, "password": password},
        )
        if not self.jwt:
            raise RuntimeError("Login não retornou header Authorization (JWT).")
        status = self.request("GET", "/authn/status").json()
        print(f"[2] Autenticado: {status.get('authenticated')} como {user}")

    def find_collection(self, query: str) -> dict:
        resp = self.request(
            "GET", "/core/collections/search/findSubmitAuthorized",
            params={"query": query, "size": 5},
        ).json()
        cols = resp.get("_embedded", {}).get("collections", [])
        if not cols:
            raise RuntimeError(
                f"Nenhuma coleção autorizada encontrada para '{query}'."
            )
        col = cols[0]
        print(f"[3] Coleção: {col['name']} ({col['uuid']})")
        return col

    def create_workspaceitem(self, collection_uuid: str) -> dict:
        wsi = self.request(
            "POST", f"/submission/workspaceitems?owningCollection={collection_uuid}",
            headers={"Content-Type": "application/json"},
        ).json()
        print(f"[4] Workspaceitem criado: id={wsi['id']}")
        return wsi

    def patch_workspaceitem(self, wsi_id: int, operations: list) -> dict:
        return self.request(
            "PATCH", f"/submission/workspaceitems/{wsi_id}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(operations),
        ).json()

    def add_metadata(self, wsi_id: int, metadata_por_secao: dict) -> None:
        ops = []
        for secao, campos in metadata_por_secao.items():
            for campo, valores in campos.items():
                if isinstance(valores, (str, dict)):
                    valores = [valores]
                ops.append({
                    "op": "add",
                    "path": f"/sections/{secao}/{campo}",
                    "value": [
                        v if isinstance(v, dict) else {"value": v, "language": None}
                        for v in valores
                    ],
                })
        self.patch_workspaceitem(wsi_id, ops)
        print(f"[5] Metadados aplicados ({len(ops)} campos)")

    def upload_file(self, wsi_id: int, filepath: Path, description: str | None = None) -> None:
        with open(filepath, "rb") as fh:
            self.request(
                "POST", f"/submission/workspaceitems/{wsi_id}",
                files={"file": (filepath.name, fh)},
            )
        print(f"[6] Arquivo enviado: {filepath.name}")
        if description:
            # o arquivo recém-enviado é o último da lista; aqui assumimos envio sequencial
            wsi = self.request("GET", f"/submission/workspaceitems/{wsi_id}").json()
            files = wsi.get("sections", {}).get("upload", {}).get("files", [])
            idx = len(files) - 1
            self.patch_workspaceitem(wsi_id, [{
                "op": "add",
                "path": f"/sections/upload/files/{idx}/metadata/dc.description",
                "value": [{"value": description, "language": None}],
            }])

    def grant_license(self, wsi_id: int) -> None:
        self.patch_workspaceitem(wsi_id, [
            {"op": "add", "path": "/sections/license/granted", "value": "true"},
        ])
        print("[7] Licença de depósito aceita")

    def check_errors(self, wsi_id: int) -> None:
        wsi = self.request("GET", f"/submission/workspaceitems/{wsi_id}").json()
        errors = wsi.get("errors", [])
        if errors:
            raise RuntimeError(
                "Validação da submissão falhou:\n" + json.dumps(errors, indent=2, ensure_ascii=False)
            )

    def deposit(self, wsi_id: int) -> dict:
        resp = self.request(
            "POST", "/workflow/workflowitems",
            headers={"Content-Type": "text/uri-list"},
            data=f"{self.api}/submission/workspaceitems/{wsi_id}",
        )
        result = resp.json() if resp.text else {}
        print("[8] Depósito realizado")
        return result

    def get_item(self, uuid: str) -> dict:
        return self.request("GET", f"/core/items/{uuid}").json()


def main() -> int:
    parser = argparse.ArgumentParser(description="Submete uma publicação no DSpace 7.6")
    parser.add_argument("--config", required=True, help="Arquivo JSON da publicação (ver publicacao.exemplo.json)")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Desabilita verificação de certificado SSL")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base_dir = Path(args.config).resolve().parent

    user = os.environ.get("DSPACE_USER") or cfg.get("user")
    password = os.environ.get("DSPACE_PASSWORD") or cfg.get("password")
    if not user or not password:
        print("ERRO: informe credenciais via DSPACE_USER/DSPACE_PASSWORD ou no JSON (user/password).", file=sys.stderr)
        return 1

    client = DSpaceClient(cfg["server"], verify_ssl=not args.no_verify_ssl)

    # 1-2. sessão
    client.init_csrf()
    client.login(user, password)

    # 3. coleção
    if cfg.get("collectionUuid"):
        collection_uuid = cfg["collectionUuid"]
        print(f"[3] Coleção informada: {collection_uuid}")
    else:
        collection_uuid = client.find_collection(cfg["collectionQuery"])["uuid"]

    # 4. workspaceitem
    wsi = client.create_workspaceitem(collection_uuid)
    wsi_id = wsi["id"]

    try:
        # 5. metadados
        client.add_metadata(wsi_id, cfg["metadata"])

        # 6. arquivos
        for f in cfg.get("files", []):
            path = (base_dir / f["path"]).resolve()
            client.upload_file(wsi_id, path, f.get("description"))

        # 7. licença
        client.grant_license(wsi_id)

        # validação antes do depósito
        client.check_errors(wsi_id)

        # 8. depósito
        result = client.deposit(wsi_id)
    except Exception:
        print(f"\nFalha na submissão. O rascunho permanece em: "
              f"{client.api}/submission/workspaceitems/{wsi_id}", file=sys.stderr)
        raise

    # 9. confirmação
    item = result.get("_embedded", {}).get("item") or {}
    item_uuid = item.get("uuid")
    if item_uuid:
        item = client.get_item(item_uuid)
        print("\n=== Publicação submetida com sucesso ===")
        print(f"  Item UUID : {item['uuid']}")
        print(f"  Handle    : {item.get('handle') or '(atribuído após aprovação no workflow)'}")
        print(f"  Arquivado : {item.get('inArchive')}")
        if not item.get("inArchive"):
            print("  Status    : aguardando aprovação no workflow da coleção")
    else:
        print("\nDepósito enviado; resposta sem item embutido (provável workflow de revisão).")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
