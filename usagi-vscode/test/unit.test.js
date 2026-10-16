'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const { resolvePython, compilerArgs, diagnosticRange } = require('../src/core');

test('Python discovery rejects an old interpreter and accepts Python 3.12+', async () => {
  const calls = [];
  const result = await resolvePython('', 'win32', async (file, args) => {
    calls.push({ file, args });
    return { stdout: file === 'py' ? '[3,11]' : '[3,12]' };
  });
  assert.equal(result.file, 'python');
  assert.equal(calls.length, 2);
  assert(calls.every(call => call.args.includes('-I')));
});

test('Configured Python path stays a single executable, with no shell interpretation', async () => {
  const filename = 'C:\\path with spaces\\python.exe';
  const result = await resolvePython(filename, 'win32', async file => {
    assert.equal(file, filename);
    return { stdout: '[3,14]' };
  });
  assert.deepEqual(result, { file: filename, args: [] });
});

test('Unavailable Python reports actionable error', async () => {
  await assert.rejects(resolvePython('', 'linux', async () => { throw new Error('missing'); }), /Python 3.12/);
});

test('Compiler arguments preserve file paths and select bundled runner', () => {
  const extension = path.resolve('folder with spaces');
  const args = compilerArgs(extension, { args: ['-3'] }, 'build', 'a; b.usagi', { output: 'out file.exe', clang: 'C:\\Clang Tools\\clang.exe' });
  assert.deepEqual(args, ['-3', '-I', '-X', 'utf8', path.join(extension, 'compiler', 'run_usagi.py'), 'build', 'a; b.usagi', '-o', 'out file.exe', '--cc', 'C:\\Clang Tools\\clang.exe']);
});

test('Diagnostics convert code-point columns to VS Code UTF-16 offsets', () => {
  assert.deepEqual(diagnosticRange('😀 야\n', { line: 1, column: 3, length: 1 }), { line: 0, start: 3, end: 4 });
  assert.deepEqual(diagnosticRange('', { line: 99, column: 99 }), { line: 0, start: 0, end: 0 });
});

test('Package bundles Python, runtime, grammar, snippets and stable language version', () => {
  const root = path.resolve(__dirname, '..');
  const manifest = require('../package.json');
  assert.equal(manifest.version, '1.0.0');
  for (const file of ['compiler/run_usagi.py', 'compiler/usagi/compiler.py', 'compiler/usagi/runtime.c', 'syntaxes/usagi.tmLanguage.json', 'snippets/usagi.json', 'docs/USAGI_LANGUAGE_SPEC.md']) {
    assert(fs.statSync(path.join(root, file)).isFile(), file);
  }
  assert.equal(manifest.capabilities.untrustedWorkspaces.supported, 'limited');
  assert.equal(manifest.dependencies, undefined);
});
