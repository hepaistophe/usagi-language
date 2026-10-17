// npm-installed Playwright, or USAGI_PLAYWRIGHT pointing to its package directory.
const {chromium} = require(process.env.USAGI_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const context = await browser.newContext();
    const page = await context.newPage(), errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    const url = process.env.USAGI_QA_URL || 'http://127.0.0.1:4174';
    const wait = state => page.waitForFunction(s => document.querySelector('#status').textContent === s, state, {timeout: 60000});
    let bundleRequests = 0;
    context.on('request', request => {if (request.url().includes('/runtime/bundle.json')) bundleRequests++;});
    await page.goto(url, {waitUntil: 'domcontentloaded'});
    await wait('준비됨');
    assert.equal(bundleRequests, 1, 'Prepare the runtime before the first Run');

    await page.locator('#code').fill('우사기!\n우쨔? 뿌르뿌르릇 하핫! 뿌르뿌르릇\n우~라~ 뿌르 야하!\n우쨔!\n!우사기');
    const start = Date.now();
    await page.locator('#run').click(); await wait('실행 완료');
    assert.equal(await page.locator('#stdout').textContent(), '1\n'.repeat(10000));
    assert.ok(await page.locator('#stdout span').count() < 30, 'Output must not create one DOM node per line');
    console.log(`10,000 output lines: ${Date.now() - start} ms; complete output, batched DOM`);

    // Repeated runs reuse the booted runtime, but not the previous terminal log.
    await page.locator('#examples').selectOption('hello');
    await page.locator('#run').click(); await wait('실행 완료');
    assert.equal(bundleRequests, 1);
    assert.equal(await page.locator('#stdout').textContent(), '야하! 우사기 랭귀지에 온 걸 환영해!\n');
    // Buffered text must survive a runtime error, and precede its diagnostic.
    await page.locator('#code').fill('우사기! 우~라~ 뿌르 야하! 우~라~ 뿌르 푸루! 뿌 야하! !우사기');
    await page.locator('#run').click(); await wait('오류');
    assert.equal(await page.locator('#stdout').textContent(), '1\n');
    assert.match(await page.locator('#stderr').textContent(), /0으로/);
    // A large output remains bounded, with already emitted text retained.
    await page.locator('#code').fill('우사기! 우쨔? 뿌르뿌르릇 하핫! 뿌르뿌르릇 우~라~ 하치! abcdefg 와레! 야하! 우쨔! !우사기');
    await page.locator('#run').click(); await wait('오류');
    assert.match(await page.locator('#stderr').textContent(), /64 KiB/);
    assert.equal(await page.locator('#stdout').textContent(), 'abcdefg\n'.repeat(8192));
    assert.deepEqual(errors, []);

    // A failed background preload must be recoverable with Run, without a reload.
    const retryContext = await browser.newContext();
    let requests = 0;
    await retryContext.route('**/runtime/bundle.json', route => ++requests === 1 ? route.abort() : route.continue());
    const retryPage = await retryContext.newPage(), retryErrors = [];
    retryPage.on('pageerror', error => retryErrors.push(String(error)));
    await retryPage.goto(url, {waitUntil: 'domcontentloaded'});
    await retryPage.waitForFunction(() => document.querySelector('#status').textContent === '준비 실패 · Run으로 재시도', null, {timeout:60000});
    await retryPage.locator('#run').click();
    await retryPage.waitForFunction(() => document.querySelector('#status').textContent === '실행 완료', null, {timeout:60000});
    assert.equal(requests, 2);
    assert.deepEqual(retryErrors, []);
    console.log('Eager loading, runtime reuse, partial output, output limit, failed preload recovery: passed');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
