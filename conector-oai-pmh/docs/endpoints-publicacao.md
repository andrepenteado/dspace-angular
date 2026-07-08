# Endpoints REST do DSpace 7.6 para uma publicação completa

Levantamento feito a partir do backend REST usado por este frontend customizado
(`src/app/core/submission/*`). A URL base do servidor é definida em `config/config.yml`
(`rest.host` + `rest.nameSpace`), ex.: `https://demo.dspace.org/server`.

Todos os endpoints abaixo são relativos a `{SERVER}` (ex.: `https://repositorio.exemplo.br/server`).

O processo de submissão ativo neste fork é o **`traditional`** (ver
`config/item-submission.xml-unesc`), com os passos: `collection`,
`traditionalpageone`, `traditionalpagetwo`, `upload` e `license`.

---

## 1. Sessão e segurança (obrigatório antes de tudo)

| # | Método | Endpoint | Função |
|---|--------|----------|--------|
| 1.1 | `GET` | `/api/security/csrf` | Obtém o token CSRF. O token vem no header de resposta `DSPACE-XSRF-TOKEN` e no cookie `DSPACE-XSRF-COOKIE`. |
| 1.2 | `POST` | `/api/authn/login` | Autenticação. Body `application/x-www-form-urlencoded`: `user=<email>&password=<senha>`. Exige header `X-XSRF-TOKEN`. Resposta traz `Authorization: Bearer <JWT>`. |
| 1.3 | `GET` | `/api/authn/status` | Confirma que a sessão está autenticada. |
| 1.4 | `POST` | `/api/authn/logout` | Encerra a sessão (opcional, ao final). |

**Regras importantes:**
- Todo request de escrita (`POST`/`PATCH`/`PUT`/`DELETE`) precisa do header `X-XSRF-TOKEN` + cookie `DSPACE-XSRF-COOKIE`.
- O token CSRF **rotaciona**: sempre que uma resposta trouxer o header `DSPACE-XSRF-TOKEN`, atualize o valor usado nos próximos requests.
- O JWT vai no header `Authorization: Bearer <token>` de todos os requests após o login.

## 2. Descoberta da coleção de destino

| # | Método | Endpoint | Função |
|---|--------|----------|--------|
| 2.1 | `GET` | `/api/core/collections/search/findSubmitAuthorized?query=<texto>` | Lista as coleções nas quais o usuário logado pode submeter (é o que o frontend usa no dropdown de coleção). |
| 2.2 | `GET` | `/api/core/collections/{uuid}` | Detalhe de uma coleção conhecida. |
| 2.3 | `GET` | `/api/config/submissiondefinitions/search/findByCollection?uuid={uuid}` | Definição de submissão (passos/seções) aplicável à coleção. |
| 2.4 | `GET` | `/api/config/submissionforms/{nome}` | Campos do formulário de uma seção (ex.: `traditionalpageone`) — útil para validar metadados obrigatórios. |

## 3. Criação e preenchimento do workspace item (rascunho da publicação)

| # | Método | Endpoint | Função |
|---|--------|----------|--------|
| 3.1 | `POST` | `/api/submission/workspaceitems?owningCollection={uuid}` | Cria o item de trabalho (rascunho). Body vazio, `Content-Type: application/json`. Retorna o `id` do workspaceitem e as seções. |
| 3.2 | `PATCH` | `/api/submission/workspaceitems/{id}` | Preenche metadados via **JSON Patch** (`Content-Type: application/json`). Ver exemplo abaixo. |
| 3.3 | `GET` | `/api/submission/workspaceitems/{id}` | Consulta o estado atual (inclui `errors` de validação por seção). |

### Exemplo de PATCH de metadados (seções `traditionalpageone`/`traditionalpagetwo`)

```json
[
  { "op": "add", "path": "/sections/traditionalpageone/dc.title",
    "value": [ { "value": "Título da publicação", "language": "pt_BR" } ] },
  { "op": "add", "path": "/sections/traditionalpageone/dc.contributor.author",
    "value": [ { "value": "Sobrenome, Nome", "language": null } ] },
  { "op": "add", "path": "/sections/traditionalpageone/dc.date.issued",
    "value": [ { "value": "2026-07-08", "language": null } ] },
  { "op": "add", "path": "/sections/traditionalpageone/dc.type",
    "value": [ { "value": "Artigo", "language": null } ] },
  { "op": "add", "path": "/sections/traditionalpageone/dc.description.abstract",
    "value": [ { "value": "Resumo...", "language": "pt_BR" } ] },
  { "op": "add", "path": "/sections/traditionalpagetwo/dc.subject",
    "value": [ { "value": "Palavra-chave", "language": null } ] }
]
```

> A seção correta de cada campo `dc.*` é a definida em `config/submission-forms.xml-unesc`.
> Campos obrigatórios neste fork: `dc.title` e `dc.date.issued` (ano no mínimo).

## 4. Upload de arquivos (bitstreams)

| # | Método | Endpoint | Função |
|---|--------|----------|--------|
| 4.1 | `POST` | `/api/submission/workspaceitems/{id}` | Upload do arquivo. `Content-Type: multipart/form-data`, campo **`file`**. Um request por arquivo. |
| 4.2 | `PATCH` | `/api/submission/workspaceitems/{id}` | Ajustes no arquivo enviado (descrição, condições de acesso/embargo) via JSON Patch em `/sections/upload/files/{n}/...`. |

Exemplo de descrição do arquivo:

```json
[
  { "op": "add", "path": "/sections/upload/files/0/metadata/dc.description",
    "value": [ { "value": "Texto completo", "language": null } ] }
]
```

## 5. Aceite da licença de depósito

| # | Método | Endpoint | Função |
|---|--------|----------|--------|
| 5.1 | `PATCH` | `/api/submission/workspaceitems/{id}` | `[ { "op": "add", "path": "/sections/license/granted", "value": "true" } ]` |

## 6. Depósito (finaliza a submissão)

| # | Método | Endpoint | Função |
|---|--------|----------|--------|
| 6.1 | `POST` | `/api/workflow/workflowitems` | **Deposita** o item. `Content-Type: text/uri-list`; body = URI do workspaceitem: `{SERVER}/api/submission/workspaceitems/{id}`. |

Comportamento:
- Se a coleção **tem workflow** de revisão → cria um `workflowitem` (aguarda aprovação de revisor).
- Se **não tem workflow** → o item é arquivado imediatamente e recebe handle.

### Endpoints do workflow (quando há revisão)

| # | Método | Endpoint | Função |
|---|--------|----------|--------|
| 6.2 | `GET` | `/api/workflow/workflowitems/{id}` | Estado do item no workflow. |
| 6.3 | `GET` | `/api/workflow/pooltasks/search/findByUser?uuid={epersonUuid}` | Tarefas disponíveis para o revisor. |
| 6.4 | `POST` | `/api/workflow/claimedtasks` | Revisor assume a tarefa (`text/uri-list` com a URI da pooltask). |
| 6.5 | `POST` | `/api/workflow/claimedtasks/{id}` | Decisão: form-data `submit_approve=true` (ou `submit_reject` + `reason`). |

## 7. Verificação do item publicado

| # | Método | Endpoint | Função |
|---|--------|----------|--------|
| 7.1 | `GET` | `/api/core/items/{uuid}` | Item arquivado (`inArchive: true`, metadados, handle). |
| 7.2 | `GET` | `/api/core/items/{uuid}/bundles` → `/api/core/bundles/{uuid}/bitstreams` | Arquivos do item. |
| 7.3 | `GET` | `/api/pid/find?id=hdl:{handle}` | Resolução por handle. |
| 7.4 | `GET` | `{SERVER}/oai/request?verb=GetRecord&metadataPrefix=oai_dc&identifier=oai:{host}:{handle}` | O item exposto via **OAI-PMH** (após reindexação do OAI — relevante para o conector). |

---

## Sequência mínima resumida

```
GET  /api/security/csrf                                  → token CSRF
POST /api/authn/login                                    → JWT
GET  /api/core/collections/search/findSubmitAuthorized   → uuid da coleção
POST /api/submission/workspaceitems?owningCollection=…   → id do rascunho
PATCH /api/submission/workspaceitems/{id}                → metadados
POST /api/submission/workspaceitems/{id} (multipart)     → arquivo(s)
PATCH /api/submission/workspaceitems/{id}                → licença granted=true
POST /api/workflow/workflowitems (text/uri-list)         → depósito
GET  /api/core/items/{uuid}                              → confirmação
```

O script `scripts/submeter_publicacao.py` implementa exatamente essa sequência.
