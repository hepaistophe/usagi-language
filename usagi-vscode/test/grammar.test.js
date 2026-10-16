'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const textmate = require('vscode-textmate');
const oniguruma = require('vscode-oniguruma');
let grammar;

test.before(async () => {
  const bytes = fs.readFileSync(require.resolve('vscode-oniguruma/release/onig.wasm'));
  await oniguruma.loadWASM(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  const registry = new textmate.Registry({ onigLib: Promise.resolve({ createOnigScanner: patterns => new oniguruma.OnigScanner(patterns), createOnigString: text => new oniguruma.OnigString(text) }),
    loadGrammar: async () => textmate.parseRawGrammar(fs.readFileSync(require.resolve('../syntaxes/usagi.tmLanguage.json'), 'utf8'), 'usagi.json') });
  grammar = await registry.loadGrammar('source.usagi');
});

function scopeAt(text, word) {
  const position = text.indexOf(word);
  const tokens = grammar.tokenizeLine(text).tokens;
  return tokens.find(token => token.startIndex <= position && position < token.endIndex)?.scopes || [];
}

test('Feeding syntax, short variables and numbers have distinct scopes', () => {
  const source = '얏! 야 하치와레: 더하기 냠! 뿌르 냠! 뿌르르 꿀꺽! 야하!';
  assert(scopeAt(source, '냠!').includes('keyword.control.usagi'));
  assert(scopeAt(source, '뿌르').includes('constant.numeric.usagi'));
  assert(scopeAt(source, '야 ').includes('variable.language.usagi'));
  assert(scopeAt(source, '더하기').includes('entity.name.usagi'));
  assert(!scopeAt(source, '냠!').includes('entity.name.usagi'));
});

test('Language words inside a quoted string remain string contents', () => {
  const source = '우~라~ 하치! 갸웃? 하치와레: 냠! 꿀꺽! 와레! 야하!';
  assert(scopeAt(source, '냠!').includes('string.quoted.usagi'));
  assert(!scopeAt(source, '냠!').includes('keyword.control.usagi'));
  assert(scopeAt(source, '야하!').includes('punctuation.section.usagi'));
});

test('A missing string delimiter does not color the following line as a string', () => {
  const first = grammar.tokenizeLine('하치! 닫힘 없음');
  const next = grammar.tokenizeLine('우사기!', first.ruleStack);
  assert(next.tokens[0].scopes.includes('keyword.control.usagi'));
  assert(!next.tokens[0].scopes.includes('string.quoted.usagi'));
});
