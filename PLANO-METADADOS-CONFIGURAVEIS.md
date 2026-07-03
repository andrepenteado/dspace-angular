# Plano: Metadados configuráveis nas páginas de item (simplificada e completa)

> **Status:** aguardando aprovação — nada foi implementado ainda.
> **Data:** 03/07/2026
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
- O `submission-form.xml` do backend **já está atualizado** para preenchimento desses campos.
- **Falta apenas a exibição no frontend** — escopo deste plano.

## Decisão de abordagem

No DSpace 7.x isso **não é configurável nativamente** — os campos da página simplificada
são fixos no template e a página completa imprime a chave crua (`{{mdEntry.key}}`).

Foram consideradas duas saídas:

| Abordagem | Prós | Contras |
|---|---|---|
| Tema exclusivo por cliente | Isolamento total | Uma pasta de tema por cliente para manter sincronizada a cada upgrade; replicação de templates |
| **Config via `AcessoAcademicoConfig`** (escolhida) | Template único para todos; comportamento por deployment via `config.yml`; mesma imagem Docker; sem rebuild; default vazio = zero impacto nos demais clientes | Exige edição pontual (uma vez só) nos templates do tema `custom` |

A diferença entre clientes aqui é só **dados** (quais campos e quais labels), não estrutura
visual — por isso a abordagem *data-driven* via config, aproveitando o padrão já existente
no projeto (`acessoAcademico` no `config.yml` → `default-app-config.ts` → `appConfig`
injetado nos componentes, como o header e a home já fazem).

## Alterações planejadas

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

**Arquivos:**
- `src/themes/custom/app/item-page/simple/item-types/publication/publication.component.ts`
- `src/themes/custom/app/item-page/simple/item-types/publication/publication.component.html`

Passos:
1. No `.ts` do tema, descomentar/apontar `templateUrl` para o HTML local e injetar
   `APP_CONFIG` (mesmo padrão do header: `@Inject(APP_CONFIG) public appConfig: AppConfig`).
2. Copiar o conteúdo do template base
   (`src/app/item-page/simple/item-types/publication/publication.component.html`)
   para o HTML do tema.
3. Adicionar ao final da coluna principal:

```html
<ds-generic-item-page-field *ngFor="let md of appConfig.acessoAcademico.itemPage.metadadosAdicionais"
    [item]="object"
    [fields]="md.campos"
    [label]="md.label"
    [separator]="md.separador">
</ds-generic-item-page-field>
```

> O `label` passa pelo pipe `translate` internamente; quando a chave não existe no i18n,
> o pipe exibe o texto como veio — então o texto em português definido no config aparece direto.

**Opcional:** replicar o mesmo loop em
`src/themes/custom/app/item-page/simple/item-types/untyped-item/untyped-item.component.html`
(já customizado no commit "Customização de metadados de resumo") para itens sem entity type.

### 4. Página completa — label com fallback para o nome técnico

**Arquivos:**
- `src/themes/custom/app/item-page/full/full-item-page.component.ts`
- `src/themes/custom/app/item-page/full/full-item-page.component.html`

Passos:
1. No `.ts` do tema, apontar `templateUrl` para HTML local e injetar `APP_CONFIG`
   (atenção: o construtor do componente base tem várias dependências — repassar via `super`).
2. Copiar o template base (`src/app/item-page/full/full-item-page.component.html`) e trocar:

```html
<!-- antes -->
<td>{{mdEntry.key}}</td>

<!-- depois -->
<td>{{ appConfig.acessoAcademico.itemPage.labelsMetadados[mdEntry.key] || mdEntry.key }}</td>
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
| Mapa `labelsMetadados` no `config.yml` (**escolhida**) | ✅ | Zero mudança no backend, funciona para anônimo, sem requisição extra, cobre qualquer campo. O mapa pode ser **gerado uma única vez** por script a partir do `submission-form.xml` do cliente (extração offline em tempo de configuração — **não** requer montar o XML como volume no frontend); campo novo no futuro = rodar o script de novo ou adicionar a linha à mão |

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

1. **Merge de arrays no config:** o merge do `config.yml` sobre os defaults no DSpace 7
   pode mesclar arrays por índice em vez de substituir. Como o default é array vazio,
   tende a funcionar — mas é o **primeiro ponto a testar**. Se der problema, modelar
   `metadadosAdicionais` como objeto (chave = nome do campo) em vez de array.
2. **Config parcial:** cliente que definir `acessoAcademico` sem `itemPage` não pode
   quebrar — validar se o merge preenche com o default ou proteger os templates com
   safe navigation (`appConfig.acessoAcademico.itemPage?.metadadosAdicionais`).
3. **Upgrades do DSpace:** os templates copiados para o tema `custom` (publication e
   full-item-page) precisam ser re-comparados com o base a cada upgrade de versão —
   custo único e compartilhado, não por cliente.

## Pendências (para retomar)

- [ ] Aprovação da implementação
- [x] Lista dos metadados que o cliente quer a mais na página simplificada — definida em 03/07/2026:
  | Label | Campo |
  |---|---|
  | Orientador | `dc.contributor.advisor` |
  | Coorientador | `dc.contributor.other` |
  | Organizador | `dc.contributor.editor` |
  | Coordenador | `dc.contributor.coordinator` |
- [x] Metadados customizados criados no banco do cliente e `submission-form.xml` atualizado (03/07/2026)
- [ ] Tabela completa de labels para a página `/full` — como ela exibe **todos** os metadados
  do item, o cliente precisa fornecer o label de cada campo em uso; campos sem label exibem
  o nome técnico
- [ ] Escrever script de extração `submission-form.xml` → entradas `labelsMetadados` do
  `config.yml` (execução única/offline; basta obter uma cópia do XML do cliente, sem
  volume compartilhado no Swarm)
- [ ] Confirmar se o cliente também usa itens sem entity type (define se replica no `untyped-item`)

## Verificação após implementar

1. Subir com `config.yml` **sem** `itemPage` → páginas idênticas ao comportamento atual
   (garante que os demais clientes não são afetados).
2. Subir com `itemPage` preenchido → conferir metadados extras na página simplificada
   e labels na página completa.
3. Conferir campo multivalorado com `separador`.
4. Conferir metadado sem label definido na página completa → deve exibir o nome técnico.
