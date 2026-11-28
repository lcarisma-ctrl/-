/*
 * 똑똑쌤 v51 — 표기 통일 · 시트 제스처(바깥 탭·뒤로가기) · 인쇄/PDF 백지 방지 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v51.test.js
 *
 * 이 스위트가 고정하는 것
 *   · 날짜는 `11.28 (토)` / `2026.11.28 (토)` 두 가지, 기간은 `11.24~11.30`
 *     — 붙임표(2026-11-28)·슬래시(11/28)·한글(11월 28일)·요일 괄호 앞 공백 없음(11.28(토))은 쓰지 않는다
 *   · 시간 `09:30`·범위 `09:30~10:30`, 금액 `90,000원`·`-32,340원`, 비율 `22.2%`, 전화 `010-9218-8577`
 *   · 화면(보호자·선생님·관리자)에서 실제로 그려진 글자에 어긋난 날짜 표기가 없다
 *   · 시트를 열면 배경 스크롤이 잠기고, 바깥을 누르면 닫힌다(시작 화면 시트는 닫지 않는다)
 *   · 브라우저 뒤로가기(popstate)는 시트만 하나씩 닫고 페이지를 떠나지 않는다
 *   · 인쇄 CSS가 모션·그림자·블러를 끄고 불투명도 1로 고정한다(Chromium PDF 백지 방지)
 *   · 단가·수수료·정산·시드 예약은 그대로
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const STYLE = (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1];
const FIXED_NOW = new Date('2026-11-26T13:00:00.000Z').getTime();

let pass = 0;
const fails = [];
function ok(name, cond, extra) {
  if (cond) { pass++; } else { fails.push(name + (extra !== undefined ? ' :: ' + JSON.stringify(extra) : '')); }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function makeDom(opts) {
  const o = opts || {};
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
      const RealDate = window.Date;
      function FixedDate(...args) { return args.length ? new RealDate(...args) : new RealDate(FIXED_NOW); }
      FixedDate.prototype = RealDate.prototype;
      FixedDate.now = () => FIXED_NOW;
      FixedDate.parse = RealDate.parse;
      FixedDate.UTC = RealDate.UTC;
      window.Date = FixedDate;
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}
async function waitBooted(w) {
  const until = Date.now() + 40000;
  while (!w.__ttokttokBooted && Date.now() < until) await sleep(20);
  return !!w.__ttokttokBooted;
}
const click = (el) => el && el.dispatchEvent(new el.ownerDocument.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));
const key = (el, k) => {
  const w = el.ownerDocument.defaultView;
  el.dispatchEvent(new w.KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }));
};
const popstate = (w) => w.dispatchEvent(new w.PopStateEvent('popstate', { state: null }));

function block(header, from) {
  const i = STYLE.indexOf(header, from || 0);
  if (i < 0) return null;
  const start = STYLE.indexOf('{', i);
  let d = 0;
  for (let p = start; p < STYLE.length; p++) {
    if (STYLE[p] === '{') d++;
    else if (STYLE[p] === '}') { d--; if (!d) return STYLE.slice(start + 1, p); }
  }
  return null;
}
const V51_AT = STYLE.indexOf('19. v51');
const V51_PRINT = block('@media print', V51_AT) || '';

/* 화면에 그려진 글자에서 v51 규칙에 어긋나는 날짜 표기를 찾는다 */
function badDateText(root) {
  const out = [];
  const skip = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT']);
  const walk = (el) => {
    if (skip.has(el.tagName)) return;
    if (el.closest && el.closest('.sprite, svg, .bar-lab, .settle-chart, .dday-badge, .date-chip, .week-chip')) return;
    /* 닫힌 시트·숨김 영역은 화면에 보이지 않는다 — 검사 대상이 아니다 */
    if (el.closest && el.closest('.sheet-backdrop:not(.is-open), .backdrop:not(.is-open), .gate:not(.is-open), [hidden]')) return;
    const own = Array.from(el.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim();
    if (own) {
      if (/(?<![\d-])\d{4}-\d{1,2}-\d{1,2}(?![\d-])/.test(own)) out.push('hyphen ' + own.slice(0, 40));
      if (/\d{1,2}\s*월\s*\d{1,2}\s*일/.test(own)) out.push('korean ' + own.slice(0, 40));
      if (/\d{1,2}\.\d{1,2}\(/.test(own)) out.push('tight ' + own.slice(0, 40));
      const slash = own.match(/(?<![\d/])\d{1,2}\/\d{1,2}(?![\d/])/g) || [];
      slash.forEach((s) => {
        if (/통증 \d+\/\d+/.test(own) || /\d+\/\d+ 완료/.test(own) || /^[\d/]+$/.test(own)) return;
        if (/제출 서류 \d+\/\d+/.test(own) || /유효기간 \d{2}\/\d{2}/.test(own)) return;   /* 진행률·카드 유효기간 */
        out.push('slash ' + s + ' :: ' + own.slice(0, 40));
      });
      const md = own.match(/(?<![\d.])(\d{1,2})\.(\d{2})(?![\d.])(?!\s*\()/g) || [];
      md.forEach((s) => {
        const [mo, da] = s.split('.').map(Number);
        if (mo < 1 || mo > 12 || da < 1 || da > 31) return;            /* 0.77 같은 측정값 */
        const i = own.indexOf(s);
        const before = own.slice(0, i);
        if (before.split('(').length > before.split(')').length) return; /* 괄호 속 근거일 */
        if (/\d{1,2}\.\d{1,2}\s*~/.test(own) || /~\s*\d{1,2}\.\d{1,2}/.test(own)) return; /* 기간 */
        out.push('noday ' + s + ' :: ' + own.slice(0, 40));
      });
    }
    Array.from(el.children).forEach(walk);
  };
  walk(root);
  return out;
}

async function run() {
  /* ── 1) 버전·훅 ─────────────────────────────────────────────── */
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));
  ok('A1 meta v51', ($('meta[name="app-version"]') || {}).content === 'v51', ($('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 표기 훅 있음', !!w.__ttokttokModel.fmt && w.__ttokttokModel.fmt.version === 'v51');
  ok('A4 제스처 훅 있음', !!w.__ttokttokSheets51 && w.__ttokttokSheets51.version === 'v51');
  ok('A5 v51 CSS 절이 v50 다음에 있다', V51_AT > 0 && V51_AT > STYLE.indexOf('18. v50'));

  /* ── 2) 표기 함수 ───────────────────────────────────────────── */
  const F = w.__ttokttokModel.fmt;
  ok('B1 날짜(짧게)', F.dateShort('2026-11-28') === '11.28 (토)', F.dateShort('2026-11-28'));
  ok('B2 날짜(연도)', F.dateFull('2026-11-28') === '2026.11.28 (토)', F.dateFull('2026-11-28'));
  ok('B3 괄호 속 근거일은 요일 생략', F.fullNoWeekday('2026-11-26') === '2026.11.26', F.fullNoWeekday('2026-11-26'));
  ok('B4 월·일만', F.md('2026-12-07') === '12.07', F.md('2026-12-07'));
  ok('B5 기간은 ~로 잇는다', F.range('2026-11-24', '2026-11-30') === '11.24~11.30', F.range('2026-11-24', '2026-11-30'));
  ok('B6 요일이 맞다(월~일)', ['2026-11-23', '2026-11-24', '2026-11-25', '2026-11-26', '2026-11-27', '2026-11-28', '2026-11-29']
    .map((d) => F.dateShort(d).slice(-2, -1)).join('') === '월화수목금토일',
    ['2026-11-23', '2026-11-24', '2026-11-25', '2026-11-26', '2026-11-27', '2026-11-28', '2026-11-29'].map((d) => F.dateShort(d)));
  ok('B7 없는 날짜는 빈 문자열', F.dateShort('') === '' && F.dateFull('nope') === '');
  ok('B8 시각 두 자리', F.time('9:30') === '09:30' && F.time('10:30') === '10:30', [F.time('9:30'), F.time('10:30')]);
  ok('B9 시각 범위', F.timeRange('9:30', '10:30') === '09:30~10:30', F.timeRange('9:30', '10:30'));
  ok('B10 금액', F.money(90000) === '90,000원' && F.money(0) === '0원', [F.money(90000), F.money(0)]);
  ok('B11 음수 금액', F.money(-32340) === '-32,340원', F.money(-32340));
  ok('B12 비율', F.rate(22.22) === '22.2%' && F.rate(3.3) === '3.3%', [F.rate(22.22), F.rate(3.3)]);
  ok('B13 전화', F.phone('01092188577') === '010-9218-8577' && F.phone('0319198577') === '031-919-8577',
    [F.phone('01092188577'), F.phone('0319198577')]);
  ok('B14 날짜 칩·주간 칩은 점 표기', w.__ttokttokModel.dateLabelOf('2026-12-07') === '12.07' &&
    w.__ttokttokModel.mdSlashOf('2026-12-07') === '12.07', w.__ttokttokModel.mdSlashOf('2026-12-07'));

  /* ── 3) 화면 글자 전수: 어긋난 날짜 0 ─────────────────────────── */
  click($('[data-login="customer"]'));
  await sleep(300);
  const bad = [];
  for (const tab of ['home', 'teachers', 'booking', 'journal', 'mypage']) {
    click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="' + tab + '"]'));
    await sleep(240);
    badDateText(doc.body).forEach((x) => bad.push('customer/' + tab + ' ' + x));
  }
  /* 예약 날짜 칩·내역 시트·알림·주간 리포트 */
  click($('#mpBookLink'));
  await sleep(260);
  badDateText(doc.body).forEach((x) => bad.push('accountSheet ' + x));
  key(doc.activeElement || doc.body, 'Escape');
  await sleep(120);
  click($('#mpNotifRow'));
  await sleep(240);
  badDateText(doc.body).forEach((x) => bad.push('notifSheet ' + x));
  key(doc.activeElement || doc.body, 'Escape');
  await sleep(120);
  ok('C1 보호자 화면 날짜 표기 어긋남 0', bad.length === 0, bad.slice(0, 6));

  /* 선생님 모드 */
  doc.getElementById('entryGate').classList.add('is-open');
  await sleep(120);
  click($('[data-login="therapist"]'));
  await sleep(360);
  const badT = [];
  for (const tab of ['tp-home', 'tp-schedule', 'tp-journal', 'tp-settle', 'tp-mypage']) {
    click($('.tabbar[data-mode="therapist"] .tabbtn[data-tab="' + tab + '"]'));
    await sleep(240);
    badDateText(doc.body).forEach((x) => badT.push('partner/' + tab + ' ' + x));
  }
  click($('#tpsScreen [data-stl-preview]'));
  await sleep(360);
  badDateText(doc.body).forEach((x) => badT.push('settlementPrintSheet ' + x));
  key(doc.activeElement || doc.body, 'Escape');
  await sleep(200);
  ok('C2 선생님·정산서 날짜 표기 어긋남 0', badT.length === 0, badT.slice(0, 6));

  /* 관리자 */
  doc.getElementById('entryGate').classList.add('is-open');
  await sleep(120);
  click($('[data-login="admin"]'));
  await sleep(420);
  const badA = badDateText(doc.body).map((x) => 'admin ' + x);
  ok('C3 관리자 화면 날짜 표기 어긋남 0', badA.length === 0, badA.slice(0, 6));
  ok('C4 정산서 지급일·확정일은 요일까지', /2026\.1[12]\.\d{2} \([일월화수목금토]\)/.test(
    (doc.getElementById('settlementPrintBody') || {}).textContent || ''), true);

  /* ── 4) 시트 제스처: 스크롤 잠금·바깥 탭·뒤로가기 ───────────────── */
  const sheet = (id) => doc.getElementById(id);
  const open = (id) => sheet(id).classList.contains('is-open');
  // 관리자 화면에서 보호자 모드로 돌아간다
  doc.getElementById('entryGate').classList.add('is-open');
  await sleep(100);
  click($('[data-login="customer"]'));
  await sleep(320);

  $$('.sheet-backdrop.is-open').forEach((el) => el.classList.remove('is-open'));
  click($('#mpBookLink'));
  await sleep(260);
  ok('D1 시트를 열면 배경 스크롤 잠금', doc.body.style.overflow === 'hidden' && doc.body.classList.contains('sheet-open'), doc.body.style.overflow);
  ok('D2 열린 시트마다 되돌리기 기록 1개', w.__ttokttokSheets51.history().pushed === 1, w.__ttokttokSheets51.history());
  /* 시트 안을 누르면 닫히지 않는다 */
  click($('#accountSheet .sheet'));
  await sleep(160);
  ok('D3 시트 안 탭으로는 닫히지 않는다', open('accountSheet'));
  /* 바깥(배경)을 누르면 닫힌다 */
  const bd = sheet('accountSheet');
  bd.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
  await sleep(240);
  ok('D4 바깥 탭으로 시트가 닫힌다', !open('accountSheet'), open('accountSheet'));
  ok('D5 닫으면 스크롤 잠금 해제', doc.body.style.overflow === '' && !doc.body.classList.contains('sheet-open'), doc.body.style.overflow);
  ok('D6 닫으면 기록도 지운다', w.__ttokttokSheets51.history().pushed === 0, w.__ttokttokSheets51.history());

  /* 시작 화면 시트(휴대폰 번호·서비스 지역)는 시트라서 바깥 탭으로 닫힌다 */
  const gateSheet = sheet('gateSheet');
  gateSheet.classList.add('is-open');
  await sleep(160);
  gateSheet.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
  await sleep(200);
  ok('D7 시작 화면 시트도 바깥 탭으로 닫힌다', !gateSheet.classList.contains('is-open'));
  /* 앱 입구(.gate)는 바깥 탭 개념이 없다 — 로그인 화면이 사라지면 안 된다 */
  const entryGate = doc.getElementById('entryGate');
  entryGate.classList.add('is-open');
  await sleep(140);
  entryGate.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
  await sleep(160);
  ok('D7-1 로그인 화면(.gate)은 바깥 탭으로 사라지지 않는다', entryGate.classList.contains('is-open'), entryGate.className);
  entryGate.classList.remove('is-open');
  await sleep(140);

  /* Escape는 그대로 닫는다 */
  click($('#mpBookLink'));
  await sleep(260);
  key(doc.activeElement || doc.body, 'Escape');
  await sleep(220);
  ok('D8 Escape로 닫힌다', !open('accountSheet'));

  /* 뒤로가기: 시트만 하나씩 닫힌다 */
  click($('#mpNotifRow'));
  await sleep(260);
  ok('D9 알림 시트 열림', open('notifSheet'));
  popstate(w);
  await sleep(260);
  ok('D10 뒤로가기 1번 = 시트 1개', !open('notifSheet'));
  ok('D11 앱은 그대로(페이지를 떠나지 않는다)', !!(doc.getElementById('appRoot') || doc.getElementById('screen-home')));
  ok('D12 뒤로가기로 닫은 뒤 기록 0', w.__ttokttokSheets51.history().pushed === 0, w.__ttokttokSheets51.history());

  /* 겹친 시트: 뒤로가기는 맨 위 하나만 */
  click($('#mpNotifRow'));
  await sleep(240);
  w.__ttokttokModel.openNotifPreview({ id: 'qa51', kind: 'visit', title: 'QA', body: 'QA 본문', audience: 'customer' });
  await sleep(300);
  ok('D13 겹친 시트 2장', open('notifSheet') && open('notifPreviewSheet'));
  popstate(w);
  await sleep(260);
  ok('D14 뒤로가기 → 맨 위만 닫힌다', !open('notifPreviewSheet') && open('notifSheet'), [open('notifPreviewSheet'), open('notifSheet')]);
  ok('D15 남은 시트를 위해 기록을 다시 건다', w.__ttokttokSheets51.history().pushed === 1, w.__ttokttokSheets51.history());
  popstate(w);
  await sleep(260);
  ok('D16 한 번 더 → 남은 시트도 닫힌다', !open('notifSheet'));
  ok('D17 기록 0', w.__ttokttokSheets51.history().pushed === 0, w.__ttokttokSheets51.history());

  /* 화면 전환·모드 전환에서 기록이 새지 않는다 */
  ok('D18 시트가 없을 때 기록 0', w.__ttokttokSheets51.history().pushed === 0, w.__ttokttokSheets51.history());

  /* 모든 시트·모달: 바깥 탭이면 닫히고, 시트 안을 누르면 닫히지 않는다 */
  const ALL_SHEETS = ['#notifPreviewSheet', '#tpNotiSheet', '#receiptModal', '#chatSheet', '#rejectSheet', '#appSheet',
    '#reviewSheet', '#manageSheet', '#settlementPrintSheet', '#weeklySheet', '#reportSheet', '#safetySheet', '#faqSheet',
    '#paySheet', '#notifSheet', '#couponSheet', '#accountSheet', '#roleSheet', '#guideSheet', '#teacherSheet',
    '#gateSheet', '#regionSheet'];
  const notClosed = [], closedByInside = [], missing = [];
  for (const id of ALL_SHEETS) {
    const el = doc.getElementById(id.slice(1));
    if (!el) { missing.push(id); continue; }
    el.classList.add('is-open');
    await sleep(90);
    el.querySelector('.sheet') ? (el.querySelector('.sheet').dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }))) : null;
    await sleep(70);
    if (!el.classList.contains('is-open')) closedByInside.push(id);
    el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
    await sleep(90);
    if (el.classList.contains('is-open')) notClosed.push(id);
  }
  ok('D19 검사한 시트·모달 22종이 모두 있다', missing.length === 0, missing);
  ok('D20 시트 안을 눌러 닫힌 곳 0', closedByInside.length === 0, closedByInside);
  ok('D21 바깥 탭으로 닫히지 않은 시트 0', notClosed.length === 0, notClosed);
  ok('D22 검사 뒤 시트가 모두 닫혀 있다', $$('.sheet-backdrop.is-open, .backdrop.is-open').length === 0,
    $$('.sheet-backdrop.is-open, .backdrop.is-open').map((x) => x.id));

  /* ── 5) 인쇄/PDF 백지 방지 CSS ─────────────────────────────── */
  ok('E1 v51 인쇄 절이 있다', V51_AT > 0);
  ok('E2 인쇄에서 애니메이션을 끈다', /animation:none!important/.test(V51_PRINT));
  ok('E3 인쇄에서 불투명도 1', /opacity:1!important/.test(V51_PRINT));
  ok('E4 인쇄에서 그림자·블러·마스크를 끈다',
    /box-shadow:none!important/.test(V51_PRINT) && /backdrop-filter:none!important/.test(V51_PRINT) && /mask-image:none!important/.test(V51_PRINT));
  ok('E5 인쇄에서 모션 시작 프레임(변형)을 지운다', /transform:none!important/.test(V51_PRINT));
  ok('E6 대상은 body 전체(카드·시트·문서 모두)', /body \*,body \*::before,body \*::after/.test(V51_PRINT), V51_PRINT.slice(0, 60));
  ok('E7 인쇄 대상 지정 규칙은 그대로', /\.sheet-backdrop\.is-print\{display:block!important\}/.test(STYLE) && !!w.__ttokttokPrint);
  ok('E8 화면 모션은 그대로(인쇄 절 밖)', /@keyframes/.test(STYLE) && /animation:slideUpFade|slideUpFade/.test(STYLE));

  /* ── 6) 불변: 단가·수수료·정산·시드 ─────────────────────────── */
  const M = w.__ttokttokModel;
  ok('F1 단가 90,000/70,000', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000,
    [M.pricing.consumerPrice, M.pricing.teacherPayout]);
  ok('F2 수수료 22.2%', Math.abs((M.pricing.platformFeeRate || 0) - 0.2222) < 1e-6, M.pricing.platformFeeRate);
  ok('F3 정산 D+3 · 15일/말일', M.settlementRule.confirmDays === 3 && M.settlementRule.payDays.length === 2,
    M.settlementRule);
  ok('F4 시드 예약 TT-261021-7302', (M.reservations() || []).some((b) => b.no === 'TT-261021-7302'),
    (M.reservations() || []).map((b) => b.no).slice(0, 5));
  ok('F5 예약번호 표기 규칙 그대로', M.isValidReservationNo('TT-261021-7302') === true);

  A.window.close();
  console.log('\n=== v51 jsdom: ' + pass + ' 통과 / ' + fails.length + ' 실패 ===');
  if (fails.length) {
    fails.forEach((f) => console.log('  ✗ ' + f));
    process.exit(1);
  }
}

run().catch((e) => { console.error(e); process.exit(1); });
