'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const vscode = require('vscode');

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(predicate, timeout = 10000) {
  const start = Date.now();
  while (!predicate()) { if (Date.now() - start > timeout) throw new Error('Timed out waiting for diagnostics'); await pause(100); }
}

async function task(command) {
  let subscription;
  let timer;
  const completion = new Promise((resolve, reject) => {
    subscription = vscode.tasks.onDidEndTaskProcess(event => {
      if (event.execution.task.definition.type !== 'usagi') return;
      clearTimeout(timer); subscription.dispose(); resolve(event.exitCode);
    });
    timer = setTimeout(() => { subscription.dispose(); reject(new Error(`Task timed out: ${command}`)); }, 60000);
  });
  try {
    const execution = await vscode.commands.executeCommand(command);
    assert(execution, `No task execution for ${command}`);
    assert.equal(await completion, 0, command);
  } finally { clearTimeout(timer); subscription?.dispose(); }
}

async function run() {
  const extension = vscode.extensions.getExtension('usagi-local.usagi-language');
  assert(extension, 'VSIX extension was not discovered');
  await extension.activate();
  assert(vscode.workspace.isTrusted);
  const workspace = process.env.USAGI_TEST_WORKSPACE;
  const filename = path.join(workspace, 'feeding_arguments.usagi');
  const document = await vscode.workspace.openTextDocument(filename);
  const editor = await vscode.window.showTextDocument(document);
  assert.equal(document.languageId, 'usagi');
  const commands = await vscode.commands.getCommands(true);
  for (const command of ['usagi.runFile', 'usagi.checkFile', 'usagi.buildFile', 'usagi.emitC', 'usagi.newFile', 'usagi.openGuide']) assert(commands.includes(command));
  const original = document.getText();
  const result = await vscode.commands.executeCommand('usagi.checkFile');
  assert.equal(result?.ok, true, JSON.stringify(result));
  console.log('HOST PASS: activation, .usagi association, commands and bundled compiler');

  const hoverLine = original.split('\n').findIndex(line => line.includes('냠!'));
  const hover = await vscode.commands.executeCommand('vscode.executeHoverProvider', document.uri, new vscode.Position(hoverLine, document.lineAt(hoverLine).text.indexOf('냠!') + 1));
  assert(hover.length > 0);
  console.log('HOST PASS: keyword hover');

  const replace = text => editor.edit(builder => builder.replace(new vscode.Range(0, 0, document.lineCount, 0), text));
  await replace('우사기!\n우~라~ 야 야하!\n!우사기\n');
  await until(() => vscode.languages.getDiagnostics(document.uri).some(item => item.message.includes('선언되지 않은 변수')));
  assert(document.isDirty, 'Diagnostics should work without saving');
  await replace(original);
  await until(() => vscode.languages.getDiagnostics(document.uri).length === 0);
  await document.save();
  console.log('HOST PASS: live diagnostics on unsaved edits and clearing after repair');

  await task('usagi.emitC');
  assert(fs.readFileSync(path.join(workspace, 'build', 'feeding_arguments.c'), 'utf8').includes('int64_t us_f1('));
  await task('usagi.buildFile');
  const executable = path.join(workspace, 'build', `feeding_arguments${process.platform === 'win32' ? '.exe' : '.out'}`);
  const native = spawnSync(executable, [], { encoding: 'utf8', timeout: 5000, windowsHide: true });
  assert.equal(native.status, 0);
  assert.equal(native.stdout.replaceAll('\r\n', '\n'), '5\n우사기!\n');
  await task('usagi.runFile');
  console.log('HOST PASS: emit C, build native executable, verified output and terminal run');

  await vscode.commands.executeCommand('usagi.newFile');
  assert.equal(vscode.window.activeTextEditor.document.languageId, 'usagi');
  assert(vscode.window.activeTextEditor.document.isUntitled);
  await vscode.commands.executeCommand('workbench.action.revertAndCloseActiveEditor');
  console.log('HOST PASS: new program command');
}

module.exports = { run };
