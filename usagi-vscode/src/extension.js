'use strict';

const vscode = require('vscode');
const path = require('node:path');
const { execFile } = require('node:child_process');
const { resolvePython, compilerArgs, diagnosticRange, pythonEnv } = require('./core');

const HINTS = {
  '우사기!': '메인을 시작합니다. !우사기로 닫고 0으로 종료합니다.',
  '!우사기': '메인을 닫고 종료 코드 0을 반환합니다.',
  '우나!': '함수 선언. 우나! 하치와레: 함수명 다음에 냠! 자료형 이름을 적습니다.',
  '우~나!': '함수를 닫고 뒤의 식을 반환합니다. 반환형은 식에서 추론합니다.',
  '냠!': '매개변수 하나를 선언하거나 호출 인자 하나를 넘깁니다. 값은 왼쪽부터 평가합니다.',
  '꿀꺽!': '인자 전달을 끝내고 함수를 호출합니다.',
  '야하!': '일반 문장을 끝냅니다.',
  '얏!': '정수형 선언. 실수 값을 넣으면 소수 부분을 0 방향으로 버립니다.',
  '야얏!': '야얏! 크기 변수명: 0으로 초기화한 정수 배열. 인덱스 변수명으로 원소에 접근합니다. 인덱스는 0부터 시작합니다.',
  '핫!': '실수형 선언.',
  '하치와레!': '문자열 자료형. 하치! 내용 와레!로 값을 작성합니다.',
  '하치와레:': '사용자 이름의 시작. 야만 반복한 변수명은 접두사를 생략할 수 있습니다.',
  '하치!': '문자열 시작. 같은 줄의 첫 와레!까지 읽습니다.',
  '와레!': '문자열 종료.',
  '하아?': '문자열 변수에 공백을 포함한 한 줄을 입력합니다. 숫자는 냠?으로 입력하세요.',
  '냠?': '선언된 정수·실수형에 따라 숫자를 입력합니다. 여러 대상은 쉼표로 구분하며 공백·탭·줄바꿈을 건너뜁니다.',
  '우이!': '하치! … 와레! 문자열 안에서 실제 개행 문자로 바뀝니다.',
  '우~라~': '식의 값을 출력하고 줄바꿈합니다.',
  '갸웃?': '조건식을 한 번 계산하고 양수·0·음수 반응으로 분기합니다.',
  '야호!': '갸웃? 값이 양수일 때의 본문.',
  '하아...': '갸웃? 값이 0일 때의 본문.',
  '우우...': '갸웃? 값이 음수일 때의 본문.',
  '갸웃!': '세 반응 분기를 닫습니다.',
  '우쨔?': '정수 횟수를 한 번 계산해 그만큼 반복합니다.',
  '우쨔!': '횟수 반복을 닫습니다.',
  '뿌야!': '같은 함수의 가장 안쪽 횟수 반복에서 남은 횟수. 읽기 전용입니다.',
  '푸루룻!': '본문을 최소 한 번 실행하는 반복을 시작합니다.',
  '푸루룻?': '조건이 양수이면 반복합니다. 조건 변수는 반복 전에 선언하세요.',
  '삐익!': '가장 안쪽 반복에서 탈출합니다. 야하!로 문장을 닫습니다.',
  '휙!': '다음 차례로 갑니다. 푸루룻!에서는 마지막 조건도 검사합니다.',
  '하!': '더하기.', '하아!': '빼기.', '하핫!': '곱하기.', '푸루!': '나누기.', '푸루루!': '정수 나머지.',
  '야~하!': '이미 선언한 변수에 대입합니다.', '우라!': '식의 여는 괄호.', '우라라!': '식의 닫는 괄호.',
  '우랏!': '별도의 변수 범위 블록을 엽니다.', '우라랏!': '변수 범위 블록을 닫습니다.'
};

function activate(context) {
  const diagnostics = vscode.languages.createDiagnosticCollection('usagi');
  const output = vscode.window.createOutputChannel('Usagi');
  const pending = new Map();
  let pythonPromise;
  let toolErrorShown = false;
  const config = () => vscode.workspace.getConfiguration('usagi');
  const python = () => pythonPromise ||= resolvePython(config().get('pythonPath', '')).catch(error => { pythonPromise = undefined; throw error; });
  const isUsagi = document => document.languageId === 'usagi';

  function cancel(uri) {
    const previous = pending.get(uri);
    if (previous) { clearTimeout(previous.timer); previous.child?.kill(); previous.resolve?.(undefined); pending.delete(uri); }
  }

  function check(document, announce = false) {
    const key = document.uri.toString();
    cancel(key);
    if (!isUsagi(document) || !vscode.workspace.isTrusted) return Promise.resolve(undefined);
    const state = { version: document.version };
    pending.set(key, state);
    return new Promise(resolve => {
      state.resolve = resolve;
      state.timer = setTimeout(async () => {
        try {
          const interpreter = await python();
          if (pending.get(key) !== state || document.isClosed) return resolve(undefined);
          const source = document.getText();
          const filename = document.uri.scheme === 'file' ? document.uri.fsPath : 'untitled.usagi';
          const args = compilerArgs(context.extensionPath, interpreter, 'check', filename, { stdin: true, json: true });
          state.child = execFile(interpreter.file, args, { cwd: context.extensionPath, env: pythonEnv(), windowsHide: true,
            encoding: 'utf8', timeout: 10000, maxBuffer: 2 * 1024 * 1024 }, (error, stdout, stderr) => {
            if (pending.get(key) !== state || document.isClosed || document.version !== state.version) return resolve(undefined);
            pending.delete(key);
            try {
              if (error && !stdout.trim()) throw new Error(stderr.trim() || error.message);
              const result = JSON.parse(stdout);
              const items = result.diagnostics.map(item => {
                const range = diagnosticRange(source, item);
                const diagnostic = new vscode.Diagnostic(new vscode.Range(range.line, range.start, range.line, range.end), item.message, vscode.DiagnosticSeverity.Error);
                diagnostic.source = 'Usagi';
                return diagnostic;
              });
              diagnostics.set(document.uri, items);
              if (announce) vscode.window.showInformationMessage(items.length ? `우사기: 오류 ${items.length}개를 찾았습니다.` : '우사기: 검사 통과!');
              resolve(result);
            } catch (failure) { fail(failure, announce); resolve(undefined); }
          });
          state.child.stdin.on('error', () => {});
          state.child.stdin.end(source, 'utf8');
        } catch (error) { if (pending.get(key) === state) pending.delete(key); fail(error, announce); resolve(undefined); }
      }, announce ? 0 : 350);
    });
  }

  function fail(error, announce) {
    output.appendLine(error.message);
    if (announce || !toolErrorShown) { toolErrorShown = true; vscode.window.showErrorMessage(error.message); }
  }

  async function activeDocument(uri) {
    const document = uri instanceof vscode.Uri ? await vscode.workspace.openTextDocument(uri) : vscode.window.activeTextEditor?.document;
    if (!document || !isUsagi(document)) throw new Error('.usagi 파일을 먼저 여세요.');
    return document;
  }

  async function runTask(command, uri) {
    if (!vscode.workspace.isTrusted) throw new Error('실행·빌드는 신뢰한 작업 영역에서 사용할 수 있습니다.');
    const document = await activeDocument(uri);
    if (!(await document.save()) || document.uri.scheme !== 'file') return undefined;
    const interpreter = await python();
    const filename = document.uri.fsPath;
    const folder = path.dirname(filename);
    const stem = path.basename(filename, path.extname(filename));
    const destination = command === 'emit-c' ? path.join(folder, 'build', `${stem}.c`) :
      command === 'build' ? path.join(folder, 'build', `${stem}${process.platform === 'win32' ? '.exe' : '.out'}`) : undefined;
    const execution = new vscode.ProcessExecution(interpreter.file,
      compilerArgs(context.extensionPath, interpreter, command, filename, { output: destination, clang: config().get('clangPath', '') }),
      { cwd: folder, env: pythonEnv() });
    const task = new vscode.Task({ type: 'usagi', command, file: filename }, vscode.workspace.getWorkspaceFolder(document.uri) || vscode.TaskScope.Global,
      `우사기 ${command}: ${path.basename(filename)}`, 'usagi', execution);
    task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Dedicated, focus: command === 'run', clear: true };
    return vscode.tasks.executeTask(task);
  }

  function command(id, action) {
    context.subscriptions.push(vscode.commands.registerCommand(id, async (...args) => {
      try { return await action(...args); } catch (error) { fail(error, true); return undefined; }
    }));
  }

  command('usagi.runFile', uri => runTask('run', uri));
  command('usagi.buildFile', uri => runTask('build', uri));
  command('usagi.emitC', uri => runTask('emit-c', uri));
  command('usagi.checkFile', async uri => {
    if (!vscode.workspace.isTrusted) throw new Error('검사는 신뢰한 작업 영역에서 사용할 수 있습니다.');
    return check(await activeDocument(uri), true);
  });
  command('usagi.newFile', async () => {
    const document = await vscode.workspace.openTextDocument({ language: 'usagi', content: '우사기!\n    우~라~ 하치! 야하! 와레! 야하!\n!우사기\n' });
    return vscode.window.showTextDocument(document);
  });
  command('usagi.openGuide', async () => vscode.commands.executeCommand('markdown.showPreview', vscode.Uri.file(path.join(context.extensionPath, 'docs', 'USAGI_LANGUAGE_SPEC.md'))));

  context.subscriptions.push(diagnostics, output,
    vscode.workspace.onDidOpenTextDocument(document => { if (config().get('checkOnType', true)) check(document); }),
    vscode.workspace.onDidChangeTextDocument(event => { if (config().get('checkOnType', true)) check(event.document); }),
    vscode.workspace.onDidCloseTextDocument(document => { cancel(document.uri.toString()); diagnostics.delete(document.uri); }),
    vscode.workspace.onDidGrantWorkspaceTrust(() => { for (const document of vscode.workspace.textDocuments) if (config().get('checkOnType', true)) check(document); }),
    vscode.workspace.onDidChangeConfiguration(event => {
      if (!event.affectsConfiguration('usagi')) return;
      pythonPromise = undefined; toolErrorShown = false;
      for (const key of pending.keys()) cancel(key);
      diagnostics.clear();
      if (config().get('checkOnType', true)) for (const document of vscode.workspace.textDocuments) check(document);
    }),
    vscode.languages.registerHoverProvider('usagi', { provideHover(document, position) {
      const range = document.getWordRangeAtPosition(position, /\S+/g);
      const word = range && document.getText(range);
      return HINTS[word] ? new vscode.Hover(new vscode.MarkdownString(`**${word}**\n\n${HINTS[word]}`), range) : undefined;
    } }),
    { dispose() { for (const key of pending.keys()) cancel(key); } });
  if (config().get('checkOnType', true)) for (const document of vscode.workspace.textDocuments) check(document);
  return { diagnostics, check };
}

module.exports = { activate };
