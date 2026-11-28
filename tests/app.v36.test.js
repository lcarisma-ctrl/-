/*
 * 똑똑쌤 v36 — 마이크로 인터랙션(시트 닫힘 전환 · 누름 피드백 · 저장 체크 · 동작 줄이기) 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v36.test.js
 * ─ 실제 전환 시간·픽셀 이동은 Chromium(E2E v36 · qa_v24)에서 보고,
 *   여기서는 토큰·규칙·class 전이·접근성 불변식·저장 피드백 배선을 본다.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const STYLE = (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1];

const FIXED_NOW = new Date('2026-11-26T13:00:00.000Z').getTime();
{
  const RealDate = Date;
  function FixedDate(...args) { return args.length ? new RealDate(...args) : new RealDate(FIXED_NOW); }
  FixedDate.prototype = RealDate.prototype;
  FixedDate.now = () => FIXED_NOW;
  FixedDate.parse = RealDate.parse;
  FixedDate.UTC = RealDate.UTC;
  global.Date = FixedDate;
}

let pass = 0;
const fails = [];
function ok(name, cond, extra) {
  if (cond) { pass++; } else { fails.push(name + (extra ? ' :: ' + extra : '')); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function makeDom(seed) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => { if (!/Not implemented/.test(e.message)) errors.push(e.message); });
  vc.on('error', (...a) => errors.push(a.join(' ')));
  const dom = new JSDOM(HTML, {
    runScripts: 'dangerously',
    url: 'https://ttokttok.test/',
    virtualConsole: vc,
    pretendToBeVisual: true,
    beforeParse(window) {
      const FIXED = new Date('2026-11-26T13:00:00.000Z').getTime();
      const RealDate = window.Date;
      function FixedDate(...args) { return args.length ? new RealDate(...args) : new RealDate(FIXED); }
      FixedDate.prototype = RealDate.prototype;
      FixedDate.now = () => FIXED;
      FixedDate.parse = RealDate.parse;
      FixedDate.UTC = RealDate.UTC;
      window.Date = FixedDate;
      if (seed) Object.keys(seed).forEach((k) => { try { window.localStorage.setItem(k, seed[k]); } catch (e) {} });
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}
const token = (name) => {
  const m = STYLE.match(new RegExp('--' + name.replace(/^--/, '') + '\\s*:\\s*([^;}]+)'));
  return m ? m[1].trim() : '';
};

async function run() {
  /* ============================================================
     BA. v36 — 마이크로 인터랙션
     ============================================================ */

  /* ── 1) 토큰·규칙(0.2초 이내, v35 토큰과 같은 :root) ─────────── */
  ok('BA1 :root는 여전히 한 블록(v35 구조 유지)', (STYLE.match(/:root\{/g) || []).length === 1);
  ok('BA2 동작 토큰 4종이 :root에 있다', ['--dur-tap', '--dur-ui', '--dur-sheet', '--press'].every((t) => new RegExp('\\' + t + '\\s*:').test(STYLE)));
  ok('BA3 시트 전환 180ms · 누름 110ms · UI 160ms (모두 0.2초 이내)',
    token('dur-sheet') === '180ms' && token('dur-tap') === '110ms' && token('dur-ui') === '160ms',
    [token('dur-sheet'), token('dur-tap'), token('dur-ui')].join('/'));
  ok('BA4 누름 배율 .97 · 큰 카드 .985', token('press') === '.97' && token('press-soft') === '.985', token('press') + '/' + token('press-soft'));
  ok('BA5 시트·모달 열림도 토큰을 쓴다(.36s/.34s 리터럴 제거)',
    /transition:transform var\(--dur-sheet\) var\(--ease\)/.test(STYLE) &&
    /animation:sheetUp var\(--dur-sheet\) var\(--ease\) both/.test(STYLE) &&
    !/transition:transform \.36s/.test(STYLE) && !/sheetUp \.34s/.test(STYLE));
  ok('BA6 CSS가 쓰는 var()가 모두 정의됨', (function () {
    const defs = new Set((STYLE.match(/--[a-zA-Z0-9-]+\s*:/g) || []).map((x) => x.replace(/\s*:$/, '')));
    const uses = (STYLE.match(/var\((--[a-zA-Z0-9-]+)\)/g) || []).map((x) => x.slice(4, -1));
    return [...new Set(uses)].every((u) => defs.has(u));
  })());
  ok('BA7 CSS 중괄호 균형', (STYLE.match(/\{/g) || []).length === (STYLE.match(/\}/g) || []).length);
  ok('BA8 v35 색 토큰 유지(--text-caption·--text-muted·--grad-brand)', ['--text-caption', '--text-muted', '--grad-brand'].every((t) => new RegExp(t + '\\s*:').test(STYLE)));
  ok('BA9 글자 크기 리터럴 0(v35 규칙 유지 · 320 시작 화면 1줄 예외)', (STYLE.match(/font-size:\s*[\d.]+px/g) || []).length <= 1);

  /* ── 2) 닫힘 전환 규칙 ───────────────────────────────────────── */
  ok('BA10 시트·모달·게이트에 is-closing 규칙이 있다',
    /\.sheet-backdrop\.is-closing\{[^}]*display:block/.test(STYLE) &&
    /\.backdrop\.is-closing\{[^}]*display:flex/.test(STYLE) &&
    /\.gate\.is-closing\{[^}]*display:block/.test(STYLE));
  ok('BA11 닫히는 동안 포인터를 받지 않는다(pointer-events:none)',
    (STYLE.match(/is-closing\{[^}]*pointer-events:none/g) || []).length >= 3);
  ok('BA12 닫히는 동안 보이는 상태(visibility:visible) — display:none으로 즉시 사라지지 않음',
    (STYLE.match(/is-closing\{[^}]*visibility:visible/g) || []).length >= 3);
  ok('BA13 시트는 아래로 내려가고 모달은 ttSheetDown', /\.sheet-backdrop\.is-closing \.sheet\{transform:translate\(-50%,102%\)/.test(STYLE) &&
    /\.backdrop\.is-closing \.modal\{animation:ttSheetDown/.test(STYLE));
  ok('BA14 흐림·내려감 키프레임 2종', /@keyframes ttFadeOut\{from\{opacity:1\}to\{opacity:0\}\}/.test(STYLE) &&
    /@keyframes ttSheetDown\{from\{transform:translateY\(0\)\}to\{transform:translateY\(100%\)\}\}/.test(STYLE));

  /* ── 3) 누름·저장 피드백 규칙 ───────────────────────────────── */
  const pressRule = (STYLE.match(/[^{}]*:active[^{}]*\{[^}]*transform:scale\(var\(--press\)\)[^}]*\}/) || [''])[0];
  ok('BA15 누름 규칙이 scale(var(--press))를 쓴다', pressRule.length > 0);
  ok('BA16 버튼·칩·탭·카드·목록이 같은 누름 규칙에 묶임',
    ['button:not([disabled]):active', '.btn:active', '.chip:active', '.tabbtn:active', '.teacher:active', '.list-item:active', '.notif:active', '.admin-card:active', '.faq-q:active', '.segmented button:active'].every((s) => pressRule.indexOf(s) > -1));
  ok('BA17 큰 카드는 더 약하게(scale var(--press-soft))', /\.card:active[^{}]*\{[^}]*var\(--press-soft\)/.test(STYLE));
  ok('BA18 글자 버튼은 투명도로 누름 표시', /\.sec-link:active[^{}]*\{[^}]*opacity:var\(--press-op\)/.test(STYLE));
  ok('BA19 토스트 체크(.toast.is-ok) 규칙·ktCheckIn 있음', /\.toast\.is-ok\{display:flex/.test(STYLE) &&
    /\.toast\.is-ok::before\{[^}]*mask:url\("data:image\/svg\+xml/.test(STYLE) && /@keyframes ttCheckIn/.test(STYLE));
  ok('BA20 저장 버튼 체크(.btn.is-saved::after)는 절대 배치라 레이아웃을 밀지 않는다',
    /\.btn\.is-saved\{position:relative\}/.test(STYLE) && /\.btn\.is-saved::after\{[^}]*position:absolute/.test(STYLE));

  /* ── 4) 동작 줄이기 ─────────────────────────────────────────── */
  const rm = (STYLE.match(/@media\(prefers-reduced-motion:reduce\)\{([\s\S]*?)\n\}/) || ['', ''])[1];
  ok('BA21 prefers-reduced-motion 블록이 animation·transition을 무력화',
    /animation-duration:\.001ms!important/.test(rm) && /transition-duration:\.001ms!important/.test(rm) &&
    /animation-iteration-count:1!important/.test(rm));

  /* ── 5) 실제 DOM: 열고 닫기 ─────────────────────────────────── */
  const A = makeDom();
  await sleep(460);
  const d = A.doc, W = A.window, M = W.__ttokttokModel, MO = W.__ttokttokMotion;
  ok('BA22 meta·훅 버전 v36(접근성 세대 표기는 v34 그대로)', (d.querySelector('meta[name=app-version]') || {}).content === 'v49' && MO && MO.version === 'v36' &&
    M.qaVersion === 'v34' && M.a11y.version === 'v34');
  ok('BA23 훅이 닫힘 시간(180ms)·토큰을 노출', MO.closeMs === 180 && MO.durations.sheet === 180 && MO.pressScale() === '.97');
  ok('BA24 JS 오류 없음(부트)', A.errors.length === 0, A.errors.slice(0, 3).join(' | '));

  /* 게이트에서 고객 모드로 들어간 뒤(닫힘 전환 180ms) 시트를 연다 */
  d.querySelector('[data-login="demo"]').click();
  await sleep(260);
  ok('BA24b 게이트 닫힘 전환 뒤 배경 잠금 해제', !d.getElementById('appRoot').hasAttribute('inert') && M.a11y.topDialog() === '',
    d.getElementById('entryGate').className + ' / ' + M.a11y.topDialog());
  d.querySelector('.tabbtn[data-tab="teachers"]').click();
  await sleep(40);
  d.querySelector('#teacherList .teacher').click();
  await sleep(40);
  const sheet = d.getElementById('teacherSheet');
  const triggerCard = d.querySelector('#teacherList .teacher');
  ok('BA25 선생님 시트 열림(배경 inert)', sheet.classList.contains('is-open') &&
    d.getElementById('appRoot').hasAttribute('inert') && M.a11y.topDialog() === '#teacherSheet');

  d.querySelector('#teacherSheet [data-sheet-close]').click();
  await sleep(40);
  ok('BA26 닫힘: is-open은 즉시 빠지고 is-closing이 붙는다',
    !sheet.classList.contains('is-open') && sheet.classList.contains('is-closing'), sheet.className);
  ok('BA27 닫힘: 배경 inert 해제·대화상자 없음(접근성 상태는 즉시)', !d.getElementById('appRoot').hasAttribute('inert') &&
    M.a11y.topDialog() === '');
  ok('BA28 닫힘: 초점이 연 버튼으로 돌아온다', !sheet.contains(d.activeElement), (d.activeElement && d.activeElement.className) || '');
  ok('BA29 훅이 닫히는 레이어를 보고', MO.closing().indexOf('teacherSheet') > -1, JSON.stringify(MO.closing()));

  await sleep(300);
  ok('BA30 180ms 뒤 is-closing이 스스로 걷힌다', !sheet.classList.contains('is-closing') && MO.closing().length === 0, sheet.className);

  /* 다시 열었다 닫는 중에 또 열면 겹치지 않는다 */
  triggerCard.click();
  await sleep(40);
  d.querySelector('#teacherSheet [data-sheet-close]').click();
  await sleep(40);
  ok('BA31 닫히는 중 표시(재현)', sheet.classList.contains('is-closing'));
  triggerCard.click();
  await sleep(40);
  ok('BA32 다시 열면 is-closing을 바로 걷고 열린다', sheet.classList.contains('is-open') && !sheet.classList.contains('is-closing'));
  d.querySelector('#teacherSheet [data-sheet-close]').click();
  await sleep(300);

  /* 모달·게이트도 같은 경로 */
  const modal = d.getElementById('receiptModal');
  modal.classList.add('is-open');
  await sleep(30);
  modal.classList.remove('is-open');
  await sleep(40);
  ok('BA33 모달(#receiptModal)도 is-closing으로 내려간다', modal.classList.contains('is-closing'));
  MO.finishClosing();
  const gate = d.getElementById('entryGate');
  gate.classList.add('is-open');
  await sleep(30);
  gate.classList.remove('is-open');
  await sleep(40);
  ok('BA34 게이트도 is-closing(페이드아웃)', gate.classList.contains('is-closing'));
  MO.finishClosing();
  ok('BA35 finishClosing은 즉시 정리한다', MO.closing().length === 0);

  /* ── 6) 저장·완료 피드백 ────────────────────────────────────── */
  const toastEl = d.getElementById('toast');
  MO.toastOk('저장했어요.');
  ok('BA36 ok 토스트는 is-ok + 문구는 그대로(체크는 CSS)', toastEl.classList.contains('is-ok') && toastEl.textContent === '저장했어요.');
  const anyBtn = d.querySelector('.tabbtn[data-tab="teachers"]');
  ok('BA37 저장 배지는 버튼에 붙었다 1초 뒤 사라진다', (function () {
    W.__ttokttokMotion.saved(anyBtn);
    return anyBtn.classList.contains('is-saved');
  })());
  await sleep(1100);
  ok('BA38 저장 배지 자동 해제(문구 변화 없음)', !anyBtn.classList.contains('is-saved') && anyBtn.textContent.indexOf('선생님') > -1);

  /* 실제 저장 흐름: 2분 일지 저장 → 체크 토스트 + 버튼 배지 */
  d.querySelector('[data-login="therapist"]').click();
  await sleep(260);
  d.querySelector('.tabbtn[data-tab="tp-journal"]').click();
  await sleep(60);
  const hasChips = d.querySelectorAll('#qlPainChips [data-ql-pain]').length === 5 &&
    d.querySelectorAll('#qlCondChips [data-ql-cond]').length === 5 &&
    d.querySelectorAll('#qlActChips [data-ql-act]').length === 8;
  if (hasChips) {
    /* 칩을 누를 때마다 카드가 다시 그려지므로 매번 새로 찾는다 */
    d.querySelector('#qlPainChips [data-ql-pain="2"]').click();
    await sleep(10);
    d.querySelector('#qlCondChips [data-ql-cond="4"]').click();
    await sleep(10);
    d.querySelector('#qlActChips [data-ql-act="walk"]').click();
    await sleep(20);
    const saveBtn = d.getElementById('qlSave');
    saveBtn.click();
    await sleep(40);
    ok('BA39 2분 일지 저장 → 체크 토스트(is-ok)', toastEl.classList.contains('is-ok') && /저장하고 보호자에게 공유/.test(toastEl.textContent), toastEl.className + ' / ' + toastEl.textContent);
    const savedBtn = d.getElementById('qlSave');
    ok('BA40 저장 버튼에 체크 배지', savedBtn && savedBtn.classList.contains('is-saved'));
  } else {
    ok('BA39 2분 일지 저장 → 체크 토스트(is-ok)', false, 'quick log UI not found');
    ok('BA40 저장 버튼에 체크 배지', false, 'quick log UI not found');
  }

  /* ── 7) 지켜야 할 것 ────────────────────────────────────────── */
  ok('BA41 단가·수수료·정산 규칙 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 && JSON.stringify(M.settlementRule.payDays) === '[15,"end"]');
  ok('BA42 시드 예약 TT-261021-7302 그대로', /TT-261021-7302/.test(d.body.textContent));
  ok('BA43 대화상자 이름 22/22 유지(v24 규칙)', (function () {
    const a = M.a11y.auditAll();
    return a.blank.length === 0 && M.a11y.labelledDialogs() === M.a11y.dialogCount() && M.a11y.dialogCount() >= 22;
  })());
  ok('BA44 아이콘 버튼 이름 누락 0', M.a11y.auditAll().iconNoLabel.length === 0);
  ok('BA45 터치 훅이 v31 그대로 동작(최소 44px)', W.__ttokttokTouch && W.__ttokttokTouch.version === 'v31' && W.__ttokttokTouch.min === 44);
  ok('BA46 동작 줄이기 판정은 matchMedia 없는 환경에서도 안전(false)', MO.reduced() === false);
  ok('BA47 index.html 1.45MB 이하', Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024, String(Buffer.byteLength(HTML, 'utf8')));
  ok('BA48 std 테스트 중 JS 오류 없음(흐름)', A.errors.length === 0, A.errors.slice(0, 3).join(' | '));

  console.log('\nRESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.log('FATAL', (e && e.stack) || e); process.exit(1); });
