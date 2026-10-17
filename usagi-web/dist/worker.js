// Only fixed application Python runs here. User text is data, parsed as Usagi.
const BASE = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';
let pyodide;
let resolveInput, running = false;
let output = '', outputTimer;
function flushOutput() {
  clearTimeout(outputTimer); outputTimer = undefined;
  if (output) { postMessage({type: 'output', text: output}); output = ''; }
}
function emit(text) {
  output += text;
  if (output.length >= 4096) flushOutput();
  else outputTimer ??= setTimeout(flushOutput, 16);
}
function readLine() {
  // Prompts must reach the terminal before it accepts input.
  flushOutput();
  postMessage({type: 'input-request'});
  return new Promise(resolve => {resolveInput = resolve;});
}
async function initialize() {
  // Fetch our small source bundle while the Python runtime is booting, instead
  // of starting four extra requests only after that runtime is ready.
  const [runtime, sources] = await Promise.all([
    import(`${BASE}pyodide.mjs`).then(({loadPyodide}) => loadPyodide({indexURL: BASE})),
    fetch(new URL('./runtime/bundle.json', import.meta.url)).then(response => {
      if (!response.ok) throw new Error('실행 파일을 읽을 수 없습니다.');
      return response.json();
    })
  ]);
  pyodide = runtime;
  pyodide.FS.mkdirTree('/home/pyodide/usagi');
  for (const path of ['usagi/__init__.py', 'usagi/numbers.py', 'usagi/compiler.py', 'interpreter.py']) {
    pyodide.FS.writeFile(`/home/pyodide/${path}`, sources[path]);
  }
  pyodide.runPython('from interpreter import run_json_async\nimport json\nasync def _terminal_read():\n    return json.loads(await _read())');
  postMessage({type: 'ready'});
}
const ready = initialize().then(() => true).catch(error => {
  postMessage({type: 'init-error', message: String(error)});
  return false; // Preloading may happen without a run waiting on this promise.
});
self.onmessage = async ({data}) => {
  if (data.type === 'input') {if (resolveInput) {const resolve = resolveInput; resolveInput = undefined; resolve(JSON.stringify(data.value));} return;}
  if (data.type !== 'run' || running) return;
  running = true;
  try {
    if (!await ready) return;
    pyodide.globals.set('_source', data.source);
    pyodide.globals.set('_emit', emit);
    pyodide.globals.set('_read', readLine);
    postMessage({type: 'started'});
    const start = performance.now();
    const result = JSON.parse(await pyodide.runPythonAsync('await run_json_async(_source, "", _emit, _terminal_read)'));
    flushOutput();
    postMessage({type: 'result', ...result, elapsed: performance.now() - start});
  } catch (error) {
    flushOutput();
    postMessage({type: 'error', message: `실행기를 시작하지 못했어요. 다시 Run을 눌러 주세요.\n${String(error)}`});
  } finally {
    running = false;
    if (pyodide) for (const key of ['_source', '_emit', '_read']) pyodide.globals.delete(key);
  }
};
