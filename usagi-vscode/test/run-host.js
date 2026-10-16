'use strict';

const path = require('node:path');
const fs = require('node:fs');
const { runTests } = require('@vscode/test-electron');

async function main() {
  const extension = path.resolve(__dirname, '..');
  const work = path.resolve(extension, '..', '..', 'work', 'vscode-host');
  const workspace = path.join(work, 'workspace');
  const python = process.env.USAGI_TEST_PYTHON;
  const code = process.env.USAGI_TEST_VSCODE;
  if (!python || !code) throw new Error('USAGI_TEST_PYTHON과 USAGI_TEST_VSCODE에 실행 파일 경로를 지정하세요.');
  fs.mkdirSync(path.join(workspace, '.vscode'), { recursive: true });
  fs.writeFileSync(path.join(workspace, '.vscode', 'settings.json'), JSON.stringify({ 'usagi.pythonPath': python, 'usagi.checkOnType': true }));
  fs.copyFileSync(path.resolve(extension, '..', 'usagi-compiler/examples/feeding_arguments.usagi'), path.join(workspace, 'feeding_arguments.usagi'));
  fs.copyFileSync(path.resolve(extension, '..', 'usagi-compiler/examples/arrays_and_input.usagi'), path.join(workspace, 'arrays_and_input.usagi'));
  await runTests({ vscodeExecutablePath: code,
    extensionDevelopmentPath: process.env.USAGI_TEST_EXTENSION_PATH || extension,
    extensionTestsPath: path.join(extension, 'test', 'suite', 'index.js'),
    launchArgs: [workspace, '--user-data-dir', path.join(work, 'profile'), '--extensions-dir', path.join(work, 'extensions'),
      '--disable-workspace-trust', '--disable-extensions', '--disable-gpu', '--skip-welcome', '--skip-release-notes', '--use-inmemory-secretstorage',
      ...(process.env.USAGI_TEST_NO_SANDBOX === '1' ? ['--no-sandbox'] : [])],
    extensionTestsEnv: { USAGI_TEST_WORKSPACE: workspace },
    extensionTestsKind: 'extensionHost'
  });
}

main().catch(error => { console.error(error); process.exitCode = 1; });
