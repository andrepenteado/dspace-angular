#!/usr/bin/env node
/**
 * Extrai os labels dos metadados de um submission-forms.xml do DSpace e imprime
 * as entradas `labelsMetadados` prontas para o bloco `acessoAcademico.itemPage`
 * do config.yml (ver config/PLANO-METADADOS-CONFIGURAVEIS.md).
 *
 * Uso:
 *   node scripts/extract-metadata-labels.js <submission-forms.xml> [form1,form2,...] [--only]
 *
 * O segundo argumento (opcional) é a lista de formulários em ordem de
 * prioridade: quando o mesmo campo aparece em mais de um formulário com labels
 * diferentes, vence o do formulário listado primeiro. Formulários não listados
 * são processados depois, na ordem do documento — a menos que `--only` seja
 * passado, caso em que apenas os formulários listados são considerados (útil
 * para ignorar formulários openAIRE, que reaproveitam campos comuns com labels
 * de outro contexto, ex.: dc.identifier.uri = "Project web page").
 *
 * Exemplo:
 *   node scripts/extract-metadata-labels.js config/submission-forms.xml-unesc publicationStep,traditionalpageone,traditionalpagetwo --only
 */

const { readFileSync } = require('fs');

const args = process.argv.slice(2);
const only = args.includes('--only');
const positional = args.filter((a) => a !== '--only');

const xmlPath = positional[0];
if (!xmlPath) {
  console.error('Uso: node scripts/extract-metadata-labels.js <submission-forms.xml> [form1,form2,...] [--only]');
  process.exit(1);
}

const priority = (positional[1] || '').split(',').map((s) => s.trim()).filter(Boolean);
const xml = readFileSync(xmlPath, 'utf8');

// Coleta os formulários na ordem do documento
let forms = [];
const formRegex = /<form\s+name="([^"]+)"\s*>([\s\S]*?)<\/form>/g;
let formMatch;
while ((formMatch = formRegex.exec(xml)) !== null) {
  forms.push({ name: formMatch[1], body: formMatch[2] });
}

if (only) {
  forms = forms.filter((form) => priority.includes(form.name));
}

// Reordena: formulários prioritários primeiro, demais na ordem do documento
forms.sort((a, b) => {
  const ia = priority.indexOf(a.name);
  const ib = priority.indexOf(b.name);
  return (ia === -1 ? priority.length : ia) - (ib === -1 ? priority.length : ib);
});

const tag = (block, name) => {
  const m = block.match(new RegExp(`<${name}>([^<]*)</${name}>`));
  return m ? m[1].trim() : '';
};

// Primeiro formulário (na ordem de prioridade) a definir um campo vence
const labels = new Map();
for (const form of forms) {
  const fieldRegex = /<field>([\s\S]*?)<\/field>/g;
  let fieldMatch;
  while ((fieldMatch = fieldRegex.exec(form.body)) !== null) {
    const block = fieldMatch[1];
    const schema = tag(block, 'dc-schema');
    const element = tag(block, 'dc-element');
    const label = tag(block, 'label');
    if (!schema || !element || !label) {
      continue;
    }
    const qualifier = tag(block, 'dc-qualifier');
    const key = [schema, element, qualifier].filter(Boolean).join('.');
    if (!labels.has(key)) {
      labels.set(key, label);
    }
  }
}

console.log('  labelsMetadados:');
for (const [key, label] of labels) {
  console.log(`    ${key}: '${label.replace(/'/g, "''")}'`);
}
