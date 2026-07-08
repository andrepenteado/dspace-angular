# Conector OAI-PMH — DSpace 7.6

Artefatos da fase de levantamento e planejamento da integração OAI-PMH deste fork
customizado do DSpace (padrão `acessoAcademico`).

## Conteúdo

| Arquivo | Descrição |
|---------|-----------|
| [`docs/endpoints-publicacao.md`](docs/endpoints-publicacao.md) | Levantamento dos endpoints REST do DSpace 7.6 necessários para uma publicação completa (autenticação/CSRF, coleção, workspaceitem, metadados, upload, licença, depósito, workflow, verificação). |
| [`scripts/submeter_publicacao.py`](scripts/submeter_publicacao.py) | Script Python que executa a submissão completa de uma publicação via REST API. |
| [`scripts/publicacao.exemplo.json`](scripts/publicacao.exemplo.json) | Exemplo de configuração/payload da publicação para o script. |
| [`docs/plano-conector-spring-boot.md`](docs/plano-conector-spring-boot.md) | Plano de implementação (sem código ainda) do conector OAI-PMH em Spring Boot 4 / Java 25 — escopo enxuto: origem única Pergamum por cliente, worker agendado sem API de administração; evoluções registradas na seção "Sugestões futuras". |

## Como usar o script de submissão

```bash
cd conector-oai-pmh/scripts
pip install -r requirements.txt

# copie e edite o exemplo (servidor, coleção, metadados, arquivos)
cp publicacao.exemplo.json minha-publicacao.json

DSPACE_USER=usuario@exemplo.br DSPACE_PASSWORD=senha \
    python submeter_publicacao.py --config minha-publicacao.json
```

O script imprime cada etapa executada e, ao final, o UUID/handle do item criado
(ou o status de aguardo no workflow, se a coleção tiver revisão).

## Próximos passos

> **⏸ Aguardando o cliente informar o endpoint OAI-PMH da base Pergamum.**
> Com a URL em mãos, o primeiro passo é validar o `oai_dc` real exposto
> (campos preenchidos, encoding, granularidade de datas) para calibrar o
> crosswalk antes de iniciar a fase 0.

Seguir as fases descritas no plano (`docs/plano-conector-spring-boot.md`):
setup do projeto Spring Boot 4 → cliente OAI-PMH do Pergamum → cliente DSpace
(porta do script Python para Java) → crosswalk/registry → implantação piloto.
