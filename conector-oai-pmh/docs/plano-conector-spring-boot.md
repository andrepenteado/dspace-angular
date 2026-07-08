# Plano — Conector OAI-PMH Pergamum → DSpace (Spring Boot 4 / Java 25)

> **Status: planejamento — sem implementação ainda.**
> **Aguardando o cliente informar o endpoint OAI-PMH da base Pergamum** para
> validar o formato real dos registros e iniciar a fase 0.

## 1. Objetivo

Serviço enxuto que coleta registros de **uma única origem OAI-PMH por cliente — a base
Pergamum** — e os deposita como publicações no DSpace 7.6 via REST API, reutilizando o
fluxo de submissão levantado em [`endpoints-publicacao.md`](endpoints-publicacao.md) e
validado pelo script `scripts/submeter_publicacao.py`.

Premissas desta fase:

- **1 origem fixa** (endpoint OAI-PMH do Pergamum do cliente), configurada por arquivo —
  sem cadastro dinâmico de fontes.
- **1 coleção de destino** no DSpace (configurável).
- **Sem interface/API de administração** — o serviço roda como worker agendado.
- **Sem testes automatizados e sem observabilidade** nesta fase — foco em código mínimo
  e legível para entendimento e evolução (ver [Sugestões futuras](#8-sugestões-futuras)).

## 2. Stack tecnológica

| Componente | Escolha | Justificativa |
|------------|---------|---------------|
| Linguagem | **Java 25 (LTS)** | Records e pattern matching para modelar as respostas OAI; virtual threads ficam disponíveis quando precisarmos de concorrência. |
| Framework | **Spring Boot 4** (Spring Framework 7) | `RestClient` para os dois clientes HTTP (Pergamum OAI e DSpace REST); agendamento nativo. |
| Parsing XML | **JAXB (`jakarta.xml.bind`)** | O schema OAI-PMH 2.0 + `oai_dc` do Pergamum é pequeno e estável; dispensa libs externas de OAI. |
| Persistência | **Spring Data JPA + H2 em arquivo** (trocável por PostgreSQL via config) | Estado mínimo: último datestamp coletado + deduplicação. H2 embutido elimina dependência de infra nesta fase. |
| Agendamento | `@Scheduled` (cron via configuração) | Instância única — sem lock distribuído. |
| Retry | Tratamento manual simples de `503 + Retry-After` e reexecução na próxima janela agendada | Suficiente para uma origem; resiliência sofisticada fica para depois. |
| Empacotamento | Docker (mesmo registry das imagens deste fork) | Segue o padrão de deploy por cliente do projeto. |

## 3. Estrutura do projeto (módulo único, pacotes simples)

```
conector-oai-pmh/
└── src/main/java/br/com/apcode/conectoroai/
    ├── ConectorOaiApplication.java
    ├── harvest/      → cliente OAI-PMH do Pergamum:
    │                   Identify (sanidade), ListRecords com resumptionToken,
    │                   coleta incremental via from={ultimoDatestamp}
    ├── mapping/      → crosswalk fixo oai_dc (Pergamum) → seções de submissão DSpace,
    │                   com mapa de valores configurável no application.yml
    ├── deposit/      → cliente REST DSpace: CSRF + JWT, workspaceitem, PATCH de
    │                   metadados, licença, depósito (porta direta do script Python)
    └── registry/     → 2 entidades JPA: HarvestRun e HarvestedRecord
                        (estado incremental + deduplicação)
```

### 3.1 Fluxo principal

```
[@Scheduled cron] →
   1. Identify no Pergamum (sanidade + granularidade de datas)
   2. ListRecords?metadataPrefix=oai_dc&from={ultimaColeta}[&set={set}]
      └─ pagina via resumptionToken até esgotar
   3. Para cada <record>:
      a. já coletado (oai_identifier no registry)? → pula
      b. status="deleted"? → apenas registra (sem ação no DSpace nesta fase)
      c. crosswalk oai_dc → metadados por seção (mapping)
      d. depósito no DSpace (deposit):
         POST workspaceitem → PATCH metadados → PATCH licença → POST workflowitems
      e. grava oai_identifier ↔ item UUID DSpace
   4. Persiste datestamp da coleta (próxima execução é incremental)
```

> Upload de fulltext fica fora desta fase: o Pergamum via `oai_dc` normalmente expõe só
> metadados (link do exemplar em `dc:identifier`, que será mapeado como metadado, não
> como bitstream).

### 3.2 Modelo de dados (registry — 2 tabelas)

- **HarvestRun** — `id`, início/fim, janela `from/until`, totais
  (coletados/depositados/ignorados/erros), status.
- **HarvestedRecord** — `oai_identifier` (único), `datestamp`, `dspace_item_uuid`,
  status (`DEPOSITED/DELETED/ERROR`), última mensagem de erro.

### 3.3 Configuração (application.yml — tudo por cliente aqui)

```yaml
conector:
  pergamum:
    base-url: https://pergamum.cliente.br/oai/oai2.php
    metadata-prefix: oai_dc
    set: null                       # opcional
  dspace:
    server: https://repositorio.cliente.br/server
    usuario: conta-servico@cliente.br
    senha: ${DSPACE_SENHA}
    colecao-uuid: xxxx-xxxx-xxxx
  agenda:
    cron: "0 0 3 * * *"             # coleta diária às 3h
  crosswalk:                        # oai_dc → seções DSpace
    traditionalpageone:
      dc.title:              { de: "dc:title", obrigatorio: true }
      dc.contributor.author: { de: "dc:creator", multiplo: true }
      dc.date.issued:        { de: "dc:date", transformar: "primeiroAno" }
      dc.type:               { de: "dc:type", mapa-valores: { "Livro": "Livro" } }
      dc.publisher:          { de: "dc:publisher" }
      dc.description.abstract: { de: "dc:description", idioma: "pt_BR" }
      dc.identifier.citation: { de: "dc:identifier" }
    traditionalpagetwo:
      dc.subject:            { de: "dc:subject", multiplo: true }
```

Segue o mesmo espírito do padrão `acessoAcademico` deste fork: **um binário único,
comportamento por cliente via configuração**.

### 3.4 Cliente DSpace (deposit) — pontos de atenção já validados no script

- Rotação do token CSRF a cada resposta (`DSPACE-XSRF-TOKEN`) — interceptor no `RestClient`.
- JWT: login sob demanda; em 401, um único re-login e repete o request.
- Depósito com `Content-Type: text/uri-list`.
- Validação pré-depósito: consultar `errors` do workspaceitem e marcar o registro como
  `ERROR` com a mensagem, sem interromper a coleta dos demais.
- Conta de serviço dedicada no DSpace com permissão de submissão só na coleção alvo.

## 4. Regras do protocolo OAI-PMH a cobrir

- Verbos usados: `Identify`, `ListRecords` (e `GetRecord` para reprocesso pontual).
- Paginação por `resumptionToken` (opaco; se expirar → `badResumptionToken` → reinicia a janela).
- Coleta incremental com `from` respeitando a granularidade anunciada no `Identify`.
- `noRecordsMatch` não é falha (janela sem novidades).
- HTTP 503 com `Retry-After` → aguardar e repetir.
- Registros `status="deleted"` → apenas registrar nesta fase.

## 5. Execução e operação

- **Worker agendado**: sobe, agenda o cron e coleta. Sem endpoint HTTP exposto.
- **Coleta manual**: flag de linha de comando (`--coletar-agora`, opcionalmente
  `--desde=YYYY-MM-DD` para recarga) executa uma coleta e encerra — útil na implantação
  e para reprocessos.
- **Acompanhamento**: logs estruturados + consulta direta às 2 tabelas do registry.

## 6. Fases de implementação

| Fase | Entrega | Critério de pronto |
|------|---------|--------------------|
| **0. Setup** | Projeto Spring Boot 4/Java 25, Dockerfile, config exemplo | Build + imagem gerada |
| **1. Cliente OAI** | `harvest`: Identify + ListRecords com resumptionToken e incremental, JAXB | Coleta completa contra o Pergamum real do cliente piloto |
| **2. Cliente DSpace** | `deposit`: porta do fluxo do script Python para Java | Item depositado no DSpace de homologação |
| **3. Crosswalk + registry** | `mapping` via YAML + estado/deduplicação | Coleta incremental idempotente ponta a ponta |
| **4. Implantação piloto** | Docker no cliente piloto, cron ativo, recarga inicial | Base Pergamum refletida na coleção DSpace |

## 7. Riscos e decisões em aberto

1. **Formato real do Pergamum**: validar na fase 1 o `oai_dc` exposto pela versão do
   Pergamum do cliente (campos efetivamente preenchidos, encoding, granularidade de datas).
2. **Workflow de revisão**: itens coletados entram no workflow da coleção? Recomendação:
   sim no piloto (curadoria humana), migrando para coleção sem workflow quando o
   crosswalk estiver maduro.
3. **Volume da recarga inicial**: bases Pergamum podem ter centenas de milhares de
   registros; a primeira carga deve rodar com `--desde` fatiado se necessário.
4. **Spring Boot 4 é recente**: validar compatibilidade das dependências (springdoc não
   se aplica; JPA/H2 ok) na fase 0.

## 8. Sugestões futuras (fora do escopo desta fase)

Itens removidos do plano original para manter o projeto enxuto — registrados aqui para
evolução posterior:

1. **Múltiplas origens OAI-PMH** — cadastro dinâmico de fontes (`HarvestSource` como
   entidade, crosswalk por fonte), permitindo coletar de outros repositórios/periódicos
   além do Pergamum.
2. **API administrativa** — CRUD de fontes, disparo/pausa de coletas, relatórios e
   reprocessamento via REST (`/api/fontes`, `/api/registros/{id}/reprocessar`), com
   segurança OAuth2/API key.
3. **Observabilidade** — Spring Boot Actuator + Micrometer/Prometheus com métricas por
   fonte (coletados, depositados, falhas) e dashboard.
4. **Testes automatizados** — JUnit 6, WireMock simulando o provedor OAI e Testcontainers
   (PostgreSQL + DSpace demo) para testes de integração do fluxo completo.
5. **Resiliência avançada** — Resilience4j (retry com backoff, rate limiter, circuit
   breaker por fonte) no lugar do tratamento manual de 503.
6. **Modularização formal** — Spring Modulith para impor fronteiras entre `harvest`,
   `mapping`, `deposit` e `registry` quando o projeto crescer.
7. **Alta disponibilidade** — múltiplas réplicas com ShedLock para o agendamento.
8. **Atualização e retirada de itens** — quando o `datestamp` de um registro mudar,
   atualizar o item arquivado (PATCH em `/api/core/items/{uuid}`); registros
   `deleted` retirando o item no DSpace (política configurável).
9. **Deduplicação cruzada por DOI/ISBN** — além do `oai_identifier`, para quando houver
   múltiplas fontes.
10. **Upload de fulltext** — baixar e anexar PDFs quando a origem expuser link direto.
11. **Exposição OAI-PMH (proxy/fachada)** — agregar, filtrar ou enriquecer o provider
    nativo do DSpace (`{SERVER}/oai/request`) por cliente.
12. **PostgreSQL gerenciado** — migrar o registry de H2 para o PostgreSQL da infra do
    cliente, com Flyway, quando sair do piloto.
