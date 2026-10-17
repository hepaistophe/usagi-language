const {chromium}=require(process.env.USAGI_PLAYWRIGHT || 'playwright');
const assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  try {
    const page=await browser.newPage(), errors=[];
    page.on('pageerror',error=>errors.push(String(error)));
    await page.goto(process.env.USAGI_QA_URL || 'http://127.0.0.1:4174');
    await page.waitForFunction(()=>document.querySelector('#code').value.includes('우사기!'));
    const wait=state=>page.waitForFunction(s=>document.querySelector('#status').textContent===s,state,{timeout:60000});
    assert.equal(await page.locator('.version').innerText(),'v1.1.0');
    await page.locator('#code').fill('우사기!\n우~라! 하치! 숫자: 와레! 야하!\n얏! 야 뿌 야하!\n냠? 야 야하!\n우~라! 모몽가! 우라! 야 우라라! 시사! 하치! 병 와레! 야하!\n!우사기');
    await page.locator('#run').click();await wait('입력 대기');
    assert.equal(await page.locator('#stdout').textContent(),'숫자:');
    await page.locator('#stdin').fill('99');await page.locator('#stdin').press('Enter');await wait('실행 완료');
    assert.equal(await page.locator('#stdout').textContent(),'숫자:› 99\n99병');
    await page.locator('#examples').selectOption('beer');await page.locator('#run').click();await wait('실행 완료');
    let expected='';
    for(let n=99;n>0;n--){
      expected+=`${n}병의 맥주가 벽에 있네!\n${n}병의 맥주!\n한 병 내려서 돌려 마시자!\n`;
      expected+=n>1?`${n-1}병의 맥주가 벽에 남았네!\n\n`:'이제 벽에는 맥주가 없네!\n\n';
    }
    expected+='맥주가 한 병도 없네!\n가게에 가서 99병을 더 사 오자!\n';
    assert.equal(await page.locator('#stdout').textContent(),expected);
    await page.locator('#code').fill('우사기! 우~라~ 하치! 병 와레! 시사! 뿌르 야하! !우사기');
    await page.locator('#run').click();await wait('오류');
    assert.match(await page.locator('#stderr').textContent(),/시사!/);
    assert.deepEqual(errors,[]);
    console.log('v1.1 browser: prompt before input, exact int string conversion, concat, no trailing newline, all 99 verses, invalid types: passed');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
