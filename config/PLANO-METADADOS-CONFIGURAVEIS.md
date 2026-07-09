# Plano: Metadados configuráveis nas páginas de item (simplificada e completa)

> **Status:** ✅ IMPLEMENTADO em 08/07/2026 (aprovado pelo André no mesmo dia).
> **Data:** 03/07/2026 · **Revisado/validado contra o código:** 08/07/2026
>
> **Arquivos alterados na implementação:**
> - `src/config/acesso-academico-config.interface.ts` — nova chave `itemPage`
> - `src/config/default-app-config.ts` — defaults vazios
> - `src/environments/environment.test.ts` — bloco `acessoAcademico` (era exigido
>   pelo tipo `BuildConfig` e estava ausente; necessário para os testes)
> - `src/app/item-page/simple/item-types/publication/publication.component.ts/.html` — loop de metadados adicionais
> - `src/app/item-page/simple/item-types/untyped-item/untyped-item.component.ts/.html` — idem
> - `src/app/item-page/full/full-item-page.component.ts/.html` — label com fallback
> - `src/app/item-page/**/*.spec.ts` (3 arquivos) — provider `APP_CONFIG` nos TestBeds
> - `scripts/extract-metadata-labels.js` — script de extração de labels do submission-forms.xml
> - `config/acesso-academico-unesc.yml` — bloco `itemPage` pronto para o deployment da UNESC,
>   gerado de `config/submission-forms.xml-unesc`
> - `config/config.yml` — exemplo comentado
> **Contexto:** demanda de um cliente específico; a solução deve valer para todos sem
> afetar os demais clientes (sem branch exclusivo, sem replicação de código).

## Demanda do cliente

1. **Página simplificada** (`/entities/publication/{uuid}`): exibir metadados adicionais
   além dos que o DSpace mostra por padrão.
2. **Página completa** (`/entities/publication/{uuid}/full`): a página lista **todos** os
   metadados do item (não há lista fixa); a mudança é apenas trocar o nome técnico
   (ex.: `dc.title`) pelo label amigável (ex.: "Título") na primeira coluna da tabela.

### Situação do backend (03/07/2026)

- Os metadados customizados (ex.: `dc.contributor.coordinator`) **já foram criados no
  banco** (metadata registry) do cliente.
- O `submission-forms.xml` do backend **já está atualizado** para preenchimento desses campos.
- **Falta apenas a exibição no frontend** — escopo deste plano.

## Validação do plano contra o código (08/07/2026)

Análise feita diretamente no branch `dspace-7_x`:

1. ✅ **Abordagem via config confirmada como a correta.** O mecanismo
   `config.yml` → `buildAppConfig()` (`src/config/config.server.ts`) → `mergeConfig()`
   já é usado pelo `acessoAcademico` existente (header/home) e se estende naturalmente.

2. ✅ **Risco de merge de arrays eliminado.** `mergeConfig()` em
   `src/config/config.util.ts:30` define `arrayMerge: (dest, source) => sourceArray` —
   ou seja, um array vindo do `config.yml` **substitui inteiro** o default (não mescla
   por índice). O default vazio `[]` é seguro; não é preciso remodelar como objeto.

3. ✅ **Config parcial é segura.** O `deepmerge` preenche chaves ausentes com os
   defaults: cliente que definir `acessoAcademico` sem `itemPage` herda
   `{ metadadosAdicionais: [], labelsMetadados: {} }`. Ainda assim, manter safe
   navigation (`?.`) nos templates como cinto de segurança.

4. ⚠️ **CORREÇÃO IMPORTANTE — o tema `custom` está INATIVO.** O plano original
   (03/07) mandava editar `src/themes/custom/app/item-page/...`, mas:
   - A lista de temas ativa (`default-app-config.ts`, `themes:`) contém apenas
     `{ name: 'dspace' }`; todas as entradas `custom` estão comentadas e o
     `config.yml` não define `themes`.
   - Os componentes do tema custom são *stubs*: `publication.component.ts` e
     `full-item-page.component.ts` do tema apontam `templateUrl`/`styleUrls`
     **de volta para os arquivos base** — editar os HTML do tema não teria efeito algum.
   - O padrão já adotado neste branch é **editar os templates base diretamente**
     (commit `97aa31cbe` "Customização de metadados de resumo" alterou
     `src/app/item-page/simple/item-types/untyped-item/untyped-item.component.html`
     e `src/app/item-page/field-components/metadata-values/`).

   **Decisão revisada:** editar os componentes base em `src/app/item-page/...`,
   seguindo o padrão do branch. Isso **simplifica** o plano: não há cópia de template
   para o tema nem repasse de dependências via `super` — basta adicionar
   `@Inject(APP_CONFIG)` ao construtor já existente dos componentes base.
   (Trade-off: aumenta a superfície de merge nos upgrades do DSpace, mas o branch
   já assumiu esse custo e ativar o tema custom agora seria mudança bem maior.)

5. ℹ️ **Componente certo para a página simplificada.** Itens com entity type
   `Publication` renderizam `publication.component.html`; itens **sem** entity type
   renderizam `untyped-item.component.html` (que já tem a customização do resumo neste
   branch — inclusive `publication.component.html` base **não** tem essa customização).
   Aplicar o loop de metadados adicionais **nos dois** para cobrir ambos os casos.

## Decisão de abordagem

No DSpace 7.x isso **não é configurável nativamente** — os campos da página simplificada
são fixos no template e a página completa imprime a chave crua
(`{{mdEntry.key}}` em `src/app/item-page/full/full-item-page.component.html:21`).

Alternativas consideradas:

| Abordagem | Prós | Contras |
|---|---|---|
| Tema exclusivo por cliente | Isolamento total | Tema custom hoje está inativo; uma pasta de tema por cliente para sincronizar a cada upgrade; replicação de templates |
| Labels/campos via i18n (`pt.json5`) | Usa mecanismo nativo de tradução | Assets i18n são compilados na imagem — mudança exige rebuild e valeria para **todos** os clientes da mesma imagem; não resolve "quais campos exibir" por deployment |
| REST `/api/config/submissionforms` em runtime | Labels viriam do backend | Exige autenticação no DSpace 7 (anônimo recebe 401); ver análise detalhada abaixo |
| **Config via `AcessoAcademicoConfig`** (escolhida) | Template único; comportamento por deployment via `config.yml`; mesma imagem Docker; sem rebuild; default vazio = zero impacto nos demais clientes | Mapa de labels mantido manualmente (mitigável com script de extração) |

A diferença entre clientes aqui é só **dados** (quais campos e quais labels), não estrutura
visual — por isso a abordagem *data-driven* via config, aproveitando o padrão já existente
no projeto (`acessoAcademico` no `config.yml` → `default-app-config.ts` → `appConfig`
injetado nos componentes, como o header e a home já fazem).

## Alterações planejadas (revisadas em 08/07/2026)

### 1. Estender a interface de config

**Arquivo:** `src/config/acesso-academico-config.interface.ts`

```ts
export class AcessoAcademicoConfig implements Config {

    logotipo: string;

    titulo: string;

    subTitulo: string;

    itemPage: {
        // Metadados extras exibidos na página simplificada (após os campos padrão)
        metadadosAdicionais: { campos: string[]; label: string; separador?: string }[];
        // Labels da página completa (/full); campo ausente = exibe o nome técnico
        labelsMetadados: { [campo: string]: string };
    };

}
```

### 2. Defaults vazios (garante zero impacto nos demais clientes)

**Arquivo:** `src/config/default-app-config.ts`

```ts
acessoAcademico: AcessoAcademicoConfig = {
    logotipo: 'dspace-logo.svg',
    titulo: 'Biblioteca Virtual',
    subTitulo: 'Publicação online para testes e dissertações',
    itemPage: {
        metadadosAdicionais: [],
        labelsMetadados: {}
    }
};
```

### 3. Página simplificada — loop sobre os metadados do config

**Arquivos (componentes BASE, não o tema custom — ver validação item 4):**
- `src/app/item-page/simple/item-types/publication/publication.component.ts` + `.html`
- `src/app/item-page/simple/item-types/untyped-item/untyped-item.component.ts` + `.html`

Passos:
1. No `.ts`, injetar o config no construtor (mesmo padrão do header). Como esses
   componentes herdam de `ItemComponent`, repassar as deps do pai via `super`:

```ts
constructor(
  protected routeService: RouteService,
  protected router: Router,
  @Inject(APP_CONFIG) public appConfig: AppConfig,
) {
  super(routeService, router);
}
```

2. Adicionar ao final da coluna principal do HTML (nos dois templates):

```html
<ds-generic-item-page-field *ngFor="let md of appConfig.acessoAcademico.itemPage?.metadadosAdicionais"
    [item]="object"
    [fields]="md.campos"
    [label]="md.label"
    [separator]="md.separador">
</ds-generic-item-page-field>
```

> O `label` passa pelo pipe `translate` internamente; quando a chave não existe no i18n,
> o pipe exibe o texto como veio — então o texto em português definido no config aparece direto.

### 4. Página completa — label com fallback para o nome técnico

**Arquivos (componente BASE):**
- `src/app/item-page/full/full-item-page.component.ts` + `.html`

Passos:
1. No `.ts`, adicionar `@Inject(APP_CONFIG) public appConfig: AppConfig` como parâmetro
   extra do construtor **já existente** (o componente tem ~10 deps próprias; como a
   edição é no base, não há repasse via `super` para as novas — só acrescentar o parâmetro).
2. No HTML (linha 21), trocar:

```html
<!-- antes -->
<td>{{mdEntry.key}}</td>

<!-- depois -->
<td>{{ appConfig.acessoAcademico.itemPage?.labelsMetadados?.[mdEntry.key] || mdEntry.key }}</td>
```

> **Importante:** o registry do DSpace não guarda um "label de exibição" por metadado
> (a REST API `/api/core/metadatafields` expõe apenas element/qualifier/scope note),
> então não há de onde buscar o label automaticamente. O mapa `labelsMetadados` no
> `config.yml` precisa cobrir **todos os campos usados pelo cliente**; campo sem
> entrada no mapa cai no fallback e exibe o nome técnico (comportamento atual).

#### Alternativas avaliadas para a origem dos labels (análise de 03/07/2026)

| Origem | Viável? | Observações |
|---|---|---|
| Banco de dados (`metadatafieldregistry`) | ❌ | A tabela só tem `schema`/`element`/`qualifier`/`scope_note`; não existe label de exibição no banco |
| REST `/api/config/submissionforms` em runtime | ⚠️ | Os labels já são expostos por esse endpoint (é o que a tela de submissão usa), **mas ele exige usuário autenticado no DSpace 7** — visitante anônimo recebe 401. Exigiria: (1) alteração no backend liberando leitura anônima; (2) resolver qual formulário se aplica ao item (via coleção); (3) campos fora do formulário (ex.: `dc.date.accessioned`, `dc.description.provenance`) continuariam sem label; (4) uma chamada REST a mais por página |
| Mapa `labelsMetadados` no `config.yml` (**escolhida**) | ✅ | Zero mudança no backend, funciona para anônimo, sem requisição extra, cobre qualquer campo. O mapa pode ser **gerado uma única vez** por script a partir do `submission-forms.xml` do cliente (extração offline em tempo de configuração — **não** requer montar o XML como volume no frontend); campo novo no futuro = rodar o script de novo ou adicionar a linha à mão |

A alternativa via REST fica registrada como evolução futura caso a manutenção do mapa
no yml se torne um incômodo.

### 5. Exemplo comentado no config

**Arquivo:** `config/config.yml` (e `config.example.yml` se aplicável)

```yaml
acessoAcademico:
  logotipo: 'dspace-logo.jpg'
  titulo: 'DSpace'
  subTitulo: 'Publicação online para testes e dissertações'
  # Descomente e ajuste apenas no deployment do cliente que usa o recurso.
  # Campos já definidos pelo cliente para a página simplificada (03/07/2026):
  # itemPage:
  #   metadadosAdicionais:
  #     - campos: [ 'dc.contributor.advisor' ]
  #       label: 'Orientador'
  #     - campos: [ 'dc.contributor.other' ]
  #       label: 'Coorientador'
  #     - campos: [ 'dc.contributor.editor' ]
  #       label: 'Organizador'
  #     - campos: [ 'dc.contributor.coordinator' ]
  #       label: 'Coordenador'
  #   labelsMetadados:
  #     dc.title: 'Título'
  #     dc.contributor.advisor: 'Orientador'
  #     dc.date.issued: 'Data de publicação'
```

## Pontos de atenção / riscos

1. ~~**Merge de arrays no config**~~ — **resolvido na validação de 08/07/2026:**
   `mergeConfig()` substitui arrays inteiros (`config.util.ts:30`); default `[]` é seguro.
2. **Config parcial:** o `deepmerge` preenche chaves ausentes com o default, mas os
   templates usam safe navigation (`itemPage?.`) como proteção extra (ex.: config
   antiga sem a chave em ambiente que não re-mesclou defaults).
3. **Upgrades do DSpace:** os componentes base editados (publication, untyped-item,
   full-item-page) entram na lista de arquivos a re-conferir a cada upgrade — mesmo
   custo já assumido pelo branch com `untyped-item` e `metadata-values` (commit
   `97aa31cbe`); custo único e compartilhado, não por cliente.
4. **Testes unitários existentes:** ao injetar `APP_CONFIG` nos construtores, os
   `.spec.ts` desses componentes precisam prover o token (usar `APP_CONFIG` +
   `environment` de teste, como outros specs do projeto fazem).

## Pendências (para retomar)

- [x] Aprovação da implementação (08/07/2026)
- [x] Lista dos metadados que o cliente quer a mais na página simplificada — definida em 03/07/2026:
  | Label | Campo |
  |---|---|
  | Orientador | `dc.contributor.advisor` |
  | Coorientador | `dc.contributor.other` |
  | Organizador | `dc.contributor.editor` |
  | Coordenador | `dc.contributor.coordinator` |
- [x] Metadados customizados criados no banco do cliente e `submission-forms.xml` atualizado (03/07/2026)
- [x] Tabela completa de labels para a página `/full` — gerada em 08/07/2026 a partir de
  `config/submission-forms.xml-unesc` → `config/acesso-academico-unesc.yml`. Labels que o
  cliente não customizou permanecem nos textos default em inglês do DSpace ("Date of
  Issue" etc.) e podem ser traduzidos à mão direto no yml, sem rebuild. Campos de sistema
  (`dc.date.accessioned`, `dc.description.provenance`, ...) ficaram como sugestões
  comentadas no arquivo.
- [x] Script de extração escrito em 08/07/2026: `scripts/extract-metadata-labels.js`.
  Uso: `node scripts/extract-metadata-labels.js <xml> [formulários,...] [--only]` —
  a lista de formulários define a prioridade em caso de campo repetido; `--only`
  restringe aos formulários listados (importante para excluir os formulários openAIRE,
  que dão labels de outro contexto a campos comuns, ex.: `dc.identifier.uri` =
  "Project web page").
- [x] ~~Confirmar se o cliente também usa itens sem entity type~~ — decidido em 08/07/2026:
  aplicar o loop em `publication` **e** `untyped-item`, cobrindo os dois casos
  (o branch já customiza o `untyped-item`, indicando que há itens sem entity type em uso)

## Verificação após implementar

Verificado localmente em 08/07/2026:

- [x] Specs dos 3 componentes alterados (`publication`, `untyped-item`, `full-item-page`):
  **67/67 testes passando** (inclui a compilação AOT dos templates novos); eslint sem erros.
- [x] Merge do config simulado com `buildAppConfig()`:
  - **sem** yml externo → `itemPage: { metadadosAdicionais: [], labelsMetadados: {} }`
    (defaults vazios; demais clientes não são afetados);
  - **com** `DSPACE_APP_CONFIG_PATH=config/acesso-academico-unesc.yml` → 4 campos em
    `metadadosAdicionais` e 43 entradas em `labelsMetadados` carregados corretamente.

Restante, a conferir num deployment real (homologação da UNESC):

1. Metadados extras visíveis na página simplificada e labels na página completa.
2. Campo multivalorado com `separador`.
3. Metadado sem label na página completa → exibe o nome técnico (fallback).

## Ajustes de 08/07/2026 (2ª rodada, após revisão do André)

- Labels de `config/acesso-academico-unesc.yml` traduzidos para pt-BR e campos de
  sistema ativados (`dc.date.accessioned`, `dc.date.available`, `dc.identifier.uri`,
  `dc.description.provenance`).
- Na página simplificada, os metadados adicionais foram movidos para o **início** da
  primeira coluna (antes da miniatura/arquivos), em `publication` e `untyped-item`.
  Specs re-executados: OK.

## Ajustes de 09/07/2026 (validação com banco local da UNESC)

- Ambiente local de testes: `docker/docker-compose-local-db.yml` (backend 7.6 +
  Solr contra o banco PostgreSQL do host, restaurado de produção da UNESC) e
  `config/acesso-academico-local.yml` (`rest` local + cópia do bloco da UNESC);
  uso: `./scripts/start-dev.sh local`.
- Posição final dos metadados adicionais na página simplificada: **coluna da
  direita, entre Descrição (`dc.description`) e Palavras-chave (`dc.subject`)**,
  em `publication` e `untyped-item`.
- Valores múltiplos dos metadados adicionais agora quebram linha por padrão
  (`[separator]="md.separador || '<br>'"`); `separador` no YAML sobrepõe.
- Labels novos (campos encontrados na base real): `dc.coverage.spatial`
  (Cobertura espacial), `dc.date.created` (Data de criação), `dspace.entity.type`
  (Tipo de entidade) — adicionados também no inventário do apdevops.
- `historyApiFallback: true` no dev server (`webpack/webpack.browser.ts`) para
  acessar rotas profundas por URL no modo desenvolvimento.
- Achado de dados: item `8c0d9686-4882-4390-a6ee-26b82147f22b` com
  `dspace.entity.type` duplicado abortava o `index-discovery -b` (índice ficava
  pela metade). Corrigido no banco local (removida a linha `place=1`);
  **verificar/corrigir em produção da UNESC** com a mesma query e reindexar.
- Makefile: build da imagem atualizado para `1.1.0-dist` (casando com o
  `versaoFrontend` da UNESC no inventário).

## Adequação da role Ansible `apcode.docker.dspace` (proposta de 08/07/2026)

### Como a role funciona hoje (avaliação)

- `tasks/main.yml` faz loop sobre `dspace.clientes` do host_vars
  (`inventarios/acessoacademico/host_vars/dspace.acessoacademico.com.br.yml`:
  unicap, ucsal, unesc) e inclui `tasks/instance.yml` por cliente.
- Por instância (`{{ diretorio.raiz }}/dspace-<nome>/`): `Makefile`,
  `docker-compose.yml` e `config.yml` são **templates** renderizados com
  `dspace = inst`; `submission-forms.xml` é **um arquivo único compartilhado**
  (`files/submission-forms.xml`) copiado igual para os 3 clientes.
- `templates/config.yml` do frontend só tem `defaultLanguage` + `acessoAcademico`
  (logotipo/titulo/subTitulo, vindos do inventário).
- O compose monta `./config.yml` no frontend e `./submission-forms.xml` em
  `/dspace/config/submission-forms.xml` no backend; a imagem do frontend é fixa
  (`ghcr.io/andrepenteado/dspace-angular/7_x:1.0.0-dist`); deploy via
  `make start` → `docker stack deploy`.

### O que a nova funcionalidade exige

1. `config.yml` por cliente com `acessoAcademico.itemPage` (só para a UNESC por ora).
2. `submission-forms.xml` **próprio da UNESC** (com os campos novos) sem alterar o
   compartilhado dos demais — hoje a role não suporta XML por cliente.
3. Volume novo do `item-submission.xml` no backend (só UNESC).
4. Imagem nova do frontend contendo a funcionalidade (a `1.0.0-dist` não a tem).

### Proposta — IMPLEMENTADA em 08/07/2026 com os ajustes decididos pelo André:

- **Item D (revisado no mesmo dia)**: versão da imagem do frontend **por cliente no
  inventário** (`versaoFrontend`, com fallback `1.0.0-dist` no template do compose).
  unicap/ucsal ficam em `1.0.0-dist`; unesc recebe `1.1.0-dist` — tag nova a ser
  buildada/publicada deste branch com a feature (frontend antigo ignora `itemPage`).
- **Item C simplificado**: em vez de pasta por cliente + `first_found`, os XMLs ficam
  em `files/` com **sufixo** (`submission-forms.xml-default`, `submission-forms.xml-unesc`,
  `item-submission.xml-default`, `item-submission.xml-unesc`) e o inventário ganhou
  duas propriedades por cliente (`submissionForms` / `itemSubmission`) apontando a
  variante; sem a propriedade, usa `-default`. Assim vários clientes podem compartilhar
  a mesma customização. O `item-submission.xml` agora é montado para **todos** os
  clientes (a variante `-default` é o arquivo do branch upstream `dspace-7_x`;
  o `-unesc` difere dele em exatamente 1 linha: `default` → `Publication` no name-map).
- **Melhoria opcional aplicada**: strings do `templates/config.yml` agora passam por
  `| to_json` (títulos com `:` não quebram mais o YAML).
- **Nomes corrigidos**: `submission-form.xml-*` (singular) → `submission-forms.xml-*`
  (nome que o DSpace espera), tanto na role quanto nas cópias de documentação deste
  repo (`config/`). O `config/submission-forms.xml-default` deste repo é idêntico ao
  que a role usava como compartilhado — a renomeação é transparente para unicap/ucsal.
- Renderização validada localmente (simulação Jinja dos 3 clientes): unicap/ucsal
  **sem** `itemPage` (arquivo igual ao atual), unesc com 4 campos e 47 labels, YAML
  válido. Playbook **não** foi executado (a pedido).

#### Proposta original (para referência)

**A. Inventário — `itemPage` por cliente.** No cliente `unesc` do host_vars,
adicionar a chave `itemPage` com o conteúdo de `config/acesso-academico-unesc.yml`
(deste repo). Clientes sem a chave = comportamento atual. O inventário já é o lugar
dos dados por cliente (titulo, logotipo, ...).

**B. `templates/config.yml` — renderização condicional:**

```jinja
defaultLanguage: pt-BR

acessoAcademico:
  logotipo: {{ dspace.logotipo }}
  titulo: {{ dspace.titulo }}
  subTitulo: {{ dspace.subTitulo }}
{% if dspace.itemPage is defined %}
  itemPage:
{{ dspace.itemPage | to_nice_yaml(indent=2) | indent(width=4, first=true) }}
{% endif %}
```

Sem `itemPage` no inventário, o arquivo gerado é **byte a byte idêntico** ao atual
→ zero impacto em unicap/ucsal (o frontend preenche os defaults vazios via deepmerge).

**C. XMLs do backend por cliente com fallback.** Mover os arquivos deste repo para a
role (o lar deles é o devops, não o frontend):
- `config/submission-forms.xml-unesc` → `roles/dspace/files/unesc/submission-forms.xml`
  (⚠️ atenção ao nome: o DSpace espera `submission-forms.xml`, com "s" — o arquivo
  aqui está no singular);
- `config/item-submission.xml-unesc` → `roles/dspace/files/unesc/item-submission.xml`.

Em `tasks/instance.yml`, resolver por cliente com fallback para o compartilhado:

```yaml
- name: "{{ inst.nome | upper }}: Resolver XMLs de submissão"
  ansible.builtin.set_fact:
    submission_forms_src: "{{ lookup('ansible.builtin.first_found',
      [inst.nome ~ '/submission-forms.xml', 'submission-forms.xml'],
      paths=[role_path ~ '/files']) }}"
    item_submission_src: "{{ lookup('ansible.builtin.first_found',
      [inst.nome ~ '/item-submission.xml'],
      paths=[role_path ~ '/files'], errors='ignore') }}"

# copiar submission_forms_src (substitui a task atual de submission-forms.xml)
# copiar item_submission_src para {{ instancia_dir }}/item-submission.xml
#   quando item_submission_src | length > 0
```

No `templates/docker-compose.yml`, serviço `dspace`, volume condicional (passar
`item_submission_src` no `vars:` da task que renderiza o compose):

```jinja
    volumes:
      - ./assetstore:/dspace/assetstore
      - ./submission-forms.xml:/dspace/config/submission-forms.xml
{% if item_submission_src | default('') | length > 0 %}
      - ./item-submission.xml:/dspace/config/item-submission.xml
{% endif %}
```

**D. Imagem do frontend parametrizada por cliente** (rollout seguro/canário):

```jinja
    image: {{ dspace.imagem_frontend | default('ghcr.io/andrepenteado/dspace-angular/7_x:1.0.0-dist') }}
```

No inventário, só a UNESC recebe `imagem_frontend: ...:1.1.0-dist` (imagem nova com
a feature). Validada a homologação, promove-se a nova tag como default e remove-se o
override. Mesmo que um cliente antigo receba o `config.yml` com `itemPage`, a imagem
velha apenas ignora as chaves extras — não quebra.

### Sequência de rollout

1. Buildar/publicar a imagem nova do dspace-angular (tag sugerida `1.1.0-dist`) a
   partir deste branch (`Dockerfile.dist`).
2. Aplicar A–D no apdevops e rodar o playbook com `--check --diff` primeiro:
   **para unicap e ucsal não pode haver diff**; para unesc, diff em compose
   (imagem + volume), config.yml (itemPage) e XMLs.
3. `make start` (stack deploy) na unesc: compose mudou → serviços redeployam.
   Backend reinicia com os XMLs novos (metadados já existem no registry desde
   03/07; o form muda a tela de submissão).
4. Observação operacional: se no futuro **só** o `config.yml` mudar (ex.: ajustar um
   label), o `docker stack deploy` não reinicia o serviço (compose inalterado) —
   usar `docker service update --force dspace-<nome>_dspace-angular`.

### Observação de melhoria (não regressão)

`templates/config.yml` não quota as strings (`titulo: {{ dspace.titulo }}`);
um título contendo `:` quebraria o YAML. Vale trocar por `| to_json` (quota
automaticamente) na mesma mexida — opcional.
