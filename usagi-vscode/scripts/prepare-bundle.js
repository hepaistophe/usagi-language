'use strict';

const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = path.resolve(root, '..', 'usagi-compiler', 'usagi');
const destination = path.join(root, 'compiler', 'usagi');
const docs = path.join(root, 'docs');
fs.mkdirSync(destination, { recursive: true });
fs.mkdirSync(docs, { recursive: true });
for (const item of fs.readdirSync(source, { withFileTypes: true })) {
  if (item.isFile() && /\.(?:py|c)$/.test(item.name)) fs.copyFileSync(path.join(source, item.name), path.join(destination, item.name));
}
const specification = fs.readFileSync(path.resolve(root, '..', 'USAGI_LANGUAGE_SPEC.md'), 'utf8')
  .replaceAll('usagi-compiler/README.md', '../README.md').replaceAll('USAGI_COMPILER_PLAN.md', '../README.md');
fs.writeFileSync(path.join(docs, 'USAGI_LANGUAGE_SPEC.md'), specification, 'utf8');
const compiler = fs.readFileSync(path.join(source, 'compiler.py'), 'utf8');
const keywordBlock = compiler.match(/KEYWORDS = \{([\s\S]*?)\n\}/)[1];
const words = [...keywordBlock.matchAll(/"([^"]+)":\s*"([^"]+)"/g)].map(match => ({ word: match[1], kind: match[2] }));
const escape = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const alternation = entries => entries.map(escape).sort((a, b) => b.length - a.length).join('|');
const all = alternation(words.map(item => item.word));
const match = (name, kinds) => ({ name, match: `(?<!\\S)(?:${alternation(words.filter(item => kinds.includes(item.kind)).map(item => item.word))})(?!\\S)` });
const grammar = {
  name: 'Usagi', scopeName: 'source.usagi', fileTypes: ['usagi'], patterns: [
    { name: 'string.quoted.usagi', begin: '(?<!\\S)(하치!)', beginCaptures: { 1: { name: 'punctuation.definition.string.begin.usagi' } },
      end: '(와레!)|(?=$)', endCaptures: { 1: { name: 'punctuation.definition.string.end.usagi' } } },
    { name: 'entity.name.usagi', begin: '(?<!\\S)(하치와레:)[ \\t]+', beginCaptures: { 1: { name: 'storage.modifier.usagi' } },
      end: `(?=$)|(?=[ \\t]+(?:(?:${all})(?!\\S)|야+(?!\\S)|[뿌르릇~.]+(?!\\S)|하치!))` },
    match('invalid.deprecated.usagi', ['OLD_STRING']),
    match('storage.type.usagi', ['INT', 'REAL', 'STRING', 'CHAR']),
    match('keyword.operator.usagi', ['ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'ASSIGN']),
    match('punctuation.section.usagi', ['LPAREN', 'RPAREN', 'OPEN', 'CLOSE', 'END']),
    match('constant.language.usagi', ['REMAINING']),
    match('keyword.control.usagi', ['MAIN', 'MAIN_END', 'FUNCTION', 'RETURN', 'INPUT', 'OUTPUT', 'SIGN', 'SIGN_END', 'POSITIVE', 'ZERO', 'NEGATIVE', 'COUNT', 'COUNT_END', 'REPEAT', 'REPEAT_TEST', 'BREAK', 'CONTINUE', 'FEED', 'SWALLOW']),
    { name: 'constant.numeric.usagi', match: '(?<!\\S)[뿌르릇~.]+(?!\\S)' },
    { name: 'variable.language.usagi', match: '(?<!\\S)야+(?!\\S)' }
  ]
};
fs.mkdirSync(path.join(root, 'syntaxes'), { recursive: true });
fs.writeFileSync(path.join(root, 'syntaxes', 'usagi.tmLanguage.json'), JSON.stringify(grammar, null, 2) + '\n');
console.log(`Bundled compiler and ${words.length} language tokens.`);
