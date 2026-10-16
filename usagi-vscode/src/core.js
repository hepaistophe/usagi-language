'use strict';

const path = require('node:path');
const childProcess = require('node:child_process');

const pythonEnv = () => ({ ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', PYTHONDONTWRITEBYTECODE: '1' });

function execFile(file, args, options = {}) {
  return new Promise((resolve, reject) => {
    childProcess.execFile(file, args, { windowsHide: true, encoding: 'utf8', timeout: 5000, maxBuffer: 1024 * 1024, ...options },
      (error, stdout, stderr) => error ? reject(Object.assign(error, { stdout, stderr })) : resolve({ stdout, stderr }));
  });
}

async function resolvePython(configured = '', platform = process.platform, execute = execFile) {
  const candidates = configured.trim() ? [{ file: configured.trim(), args: [] }] :
    (platform === 'win32' ? [{ file: 'py', args: ['-3'] }, { file: 'python', args: [] }, { file: 'python3', args: [] }] :
      [{ file: 'python3', args: [] }, { file: 'python', args: [] }]);
  for (const candidate of candidates) {
    try {
      const { stdout } = await execute(candidate.file, [...candidate.args, '-I', '-c', 'import json,sys;print(json.dumps(list(sys.version_info[:2])))'], { env: pythonEnv() });
      const [major, minor] = JSON.parse(stdout.trim());
      if (major === 3 && minor >= 12) return candidate;
    } catch { /* Try the next interpreter, without executing a shell. */ }
  }
  throw new Error('Python 3.12 이상을 찾지 못했습니다. 설정의 Usagi: Python Path에 python.exe 전체 경로를 지정하세요.');
}

function compilerArgs(extensionPath, python, command, source, { output, clang, stdin = false, json = false } = {}) {
  const args = [...python.args, '-I', '-X', 'utf8', path.join(extensionPath, 'compiler', 'run_usagi.py'), command, source];
  if (output) args.push('-o', output);
  if (clang && (command === 'build' || command === 'run')) args.push('--cc', clang);
  if (stdin) args.push('--stdin');
  if (json) args.push('--json');
  return args;
}

function diagnosticRange(source, diagnostic) {
  const lines = source.split(/\r?\n/);
  const line = Math.min(Math.max(0, (Number(diagnostic.line) || 1) - 1), lines.length - 1);
  const points = [...lines[line]];
  const offset = Math.min(Math.max(0, (Number(diagnostic.column) || 1) - 1), points.length);
  const length = Math.max(1, Number(diagnostic.length) || 1);
  return {
    line,
    start: points.slice(0, offset).join('').length,
    end: points.slice(0, Math.min(points.length, offset + length)).join('').length
  };
}

module.exports = { resolvePython, compilerArgs, diagnosticRange, pythonEnv };
