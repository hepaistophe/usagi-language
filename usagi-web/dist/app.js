const $ = id => document.getElementById(id);
const code = $('code'), stdin = $('stdin'), log = $('stdout'), stderr = $('stderr'), scroll = $('terminal-scroll');
let worker, busy = false, waiting = false, runTimer, loadTimer, samples, queued = [], usedTime = 0, activeSince = 0, inputBytes = 0;
let pendingLog = [], paint;
const DRAFT_KEY = 'usagi-playground-v1';
function setStatus(text, state = '') { $('status').textContent = text; $('status').dataset.state = state; }
function lines() { $('line-numbers').textContent = Array.from({length: code.value.split('\n').length}, (_, i) => i + 1).join('\n'); $('line-numbers').scrollTop = code.scrollTop; }
function save() { try { localStorage.setItem(DRAFT_KEY, JSON.stringify({code: code.value, sample: $('examples').value})); } catch {} }
function active(value) { busy = value; $('run').disabled = value; $('stop').disabled = !value; $('examples').disabled = value; }
function inputEnabled(value) { waiting = value; stdin.disabled = !value; $('send').disabled = !value; $('eof').disabled = !value; $('sample-input').disabled = !value; stdin.placeholder = value ? '입력하고 Enter를 누르세요…' : busy ? '프로그램이 실행 중이에요…' : 'Run을 눌러 프로그램을 실행하세요.'; }
function pauseClock() { clearTimeout(runTimer); if (activeSince) usedTime += performance.now() - activeSince; activeSince = 0; }
function startClock() { activeSince = performance.now(); runTimer = setTimeout(() => { terminate('시간 초과', 'error'); showError('연산 시간이 10초를 넘었어요. 반복 조건을 확인하거나 로컬 컴파일러를 사용해 주세요.'); $('timing').textContent = '10초 제한으로 중지 (입력 대기 제외)'; }, Math.max(0, 10000 - usedTime)); }
function flushTerminal() {
  cancelAnimationFrame(paint); paint = undefined;
  if (!pendingLog.length) return;
  const fragment = document.createDocumentFragment();
  for (const {text, kind} of pendingLog) {
    const span = document.createElement('span'); span.textContent = text;
    if (kind) span.className = kind;
    fragment.append(span);
  }
  pendingLog = []; log.append(fragment);
  scroll.scrollTop = scroll.scrollHeight; $('copy').disabled = false;
}
function append(text, kind = '') {
  const last = pendingLog.at(-1);
  if (last?.kind === kind) last.text += text;
  else pendingLog.push({text, kind});
  paint ??= requestAnimationFrame(flushTerminal);
}
function showError(message) { flushTerminal(); stderr.textContent = message; stderr.hidden = false; scroll.scrollTop = scroll.scrollHeight; }
function finish() { pauseClock(); clearTimeout(loadTimer); flushTerminal(); active(false); inputEnabled(false); queued = []; stdin.value = ''; }
function fail(message) { showError(message); setStatus('오류', 'error'); finish(); }
function terminate(message, state = '') { worker?.terminate(); worker = undefined; finish(); setStatus(message, state); }
function sendLine(value) {
  inputEnabled(false); append(value === null ? '› [EOF]\n' : `› ${value}\n`, 'input-echo');
  setStatus('실행 중', 'running'); startClock(); worker.postMessage({type: 'input', value});
}
function createWorker() {
  const instance = new Worker(new URL('./worker.js', import.meta.url), {type: 'module'});
  instance.onmessage = ({data}) => {
    if (worker !== instance) return;
    if (data.type === 'ready') {
      clearTimeout(loadTimer); instance.ready = true;
      if (!busy && $('status').textContent === '실행 도구 준비 중…') setStatus('준비됨');
      return;
    }
    if (data.type === 'error' || data.type === 'init-error') {
      instance.terminate(); worker = undefined; clearTimeout(loadTimer);
      if (busy) {fail(data.message); $('timing').textContent = '실행기 로드 실패';}
      else setStatus('준비 실패 · Run으로 재시도', 'error');
      return;
    }
    if (!busy) return;
    if (data.type === 'started') {clearTimeout(loadTimer); startClock(); setStatus('실행 중', 'running');}
    else if (data.type === 'output') {append(data.text);}
    else if (data.type === 'input-request') {
      pauseClock();
      if (queued.length) sendLine(queued.shift());
      else {flushTerminal(); inputEnabled(true); setStatus('입력 대기', 'loading'); $('timing').textContent = '입력하고 Enter를 누르세요 · Ctrl+D 입력 종료'; stdin.focus(); scroll.scrollTop = scroll.scrollHeight;}
    } else if (data.type === 'result') {
      finish(); if (data.stderr) showError(data.stderr);
      $('timing').textContent = `${Math.round(usedTime)} ms · 종료 코드 ${data.exitCode} · 입력 대기 제외`;
      setStatus(data.exitCode === 0 ? '실행 완료' : '오류', data.exitCode === 0 ? 'success' : 'error');
      if (!log.textContent && !data.stderr) {log.textContent = '출력 없이 실행이 끝났어요.'; log.classList.add('empty');}
    }
  };
  instance.onerror = event => {if (worker !== instance) return; event.preventDefault(); instance.terminate(); worker = undefined; fail('실행 도구를 불러오지 못했어요. 인터넷 연결을 확인한 뒤 다시 Run을 눌러 주세요.');};
  return instance;
}
function warmup(showStatus = true) {
  if (worker) return;
  try {
    worker = createWorker();
    if (showStatus) setStatus('실행 도구 준비 중…', 'loading');
    loadTimer = setTimeout(() => {
      worker?.terminate(); worker = undefined;
      if (busy) fail('실행 도구를 불러오는 데 오래 걸리고 있어요. 다시 Run을 눌러 주세요.');
      else setStatus('준비 실패 · Run으로 재시도', 'error');
    }, 60000);
  } catch {setStatus('Run을 눌러 실행을 준비하세요');}
}
function run() {
  if (busy) return;
  save(); active(true); usedTime = 0; activeSince = 0; inputBytes = 0; queued = []; stdin.value = ''; inputEnabled(false);
  log.textContent = ''; log.classList.remove('empty'); stderr.textContent = ''; stderr.hidden = true; $('copy').disabled = true;
  setStatus(worker?.ready ? '실행 준비' : '실행 도구 준비 중…', 'loading'); $('timing').textContent = '프로그램을 준비하고 있어요';
  clearTimeout(loadTimer);
  loadTimer = setTimeout(() => {terminate('로드 시간 초과', 'error'); showError('실행 도구를 불러오는 데 오래 걸리고 있어요. 인터넷 연결을 확인하고 다시 실행해 주세요.');},60000);
  try {worker ??= createWorker(); worker.postMessage({type: 'run', source: code.value});} catch {terminate('오류', 'error'); fail('이 브라우저에서 실행기를 시작할 수 없어요. 최신 브라우저로 접속해 주세요.');}
}
$('run').addEventListener('click', run);
$('stop').addEventListener('click', () => {terminate('중지됨'); $('timing').textContent = '사용자가 실행을 중지했어요'; warmup(false);});
$('terminal-form').addEventListener('submit', event => {
  event.preventDefault(); if (!waiting) return;
  const value = stdin.value.replaceAll('\r\n','\n'); inputBytes += new TextEncoder().encode(value).length + 1;
  if (inputBytes > 1048576) {terminate('입력 한도 초과','error'); showError('입력은 실행 한 번에 최대 1 MiB까지 가능합니다.'); return;}
  queued = value.split('\n'); if (queued.length > 1 && queued.at(-1) === '') queued.pop();
  stdin.value = ''; sendLine(queued.shift());
});
function eof() {if (waiting) {queued = []; sendLine(null);}}
$('eof').addEventListener('click', eof);
stdin.addEventListener('keydown', event => {
  if (event.isComposing) return;
  if (event.key === 'Enter' && !event.shiftKey) {event.preventDefault(); $('terminal-form').requestSubmit();}
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'd') {event.preventDefault(); eof();}
});
$('sample-input').addEventListener('click', () => {if (waiting) {stdin.value = samples[$('examples').value]?.stdin ?? ''; stdin.focus();}});
code.addEventListener('input', () => {lines(); save(); if(samples) sampleHint();});
code.addEventListener('scroll', () => {$('line-numbers').scrollTop = code.scrollTop;});
document.addEventListener('keydown', event => {if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.isComposing) {event.preventDefault(); if (waiting && document.activeElement === stdin) $('terminal-form').requestSubmit(); else run();}});
code.addEventListener('keydown', event => {if (event.key === 'Tab') {event.preventDefault(); code.setRangeText('    ',code.selectionStart,code.selectionEnd,'end'); lines(); save();}});
$('copy').addEventListener('click', async () => {try {await navigator.clipboard.writeText(log.textContent + (stderr.hidden ? '' : stderr.textContent)); $('copy').textContent = '복사했어요'; setTimeout(()=>{$('copy').textContent='기록 복사';},1500);} catch {$('copy').textContent='기록을 선택해 복사해 주세요';}});
function sampleHint() {const sample=samples[$('examples').value]; $('sample-input').hidden = !sample?.stdin || sample.code !== code.value; $('sample-input').disabled = !waiting;}
function loadSample(key) {code.value=samples[key].code; lines(); save(); sampleHint();}
$('examples').addEventListener('change',event=>loadSample(event.target.value));
// Start loading while the user reads or edits, without running their program.
warmup();
try {
  const response=await fetch('./samples.json'); if (!response.ok) throw new Error('examples'); samples=await response.json();
  let draft; try {draft=JSON.parse(localStorage.getItem(DRAFT_KEY));} catch {}
  if (draft && typeof draft.code==='string') {code.value=draft.code; $('examples').value=samples[draft.sample]?draft.sample:'hello'; lines(); sampleHint();}
  else loadSample('hello');
} catch {fail('예제를 불러오지 못했어요. 페이지를 새로고침해 주세요.'); $('run').disabled=true;}
