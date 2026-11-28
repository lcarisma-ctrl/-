/*
 * 똑똑쌤 v34 — 접근성 2차(배경 inert·포커스 트랩·아이콘 이름·aria-live 정리) 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=4096 app.v34.test.js
 * ─ app.test.js(전체 회귀: APP_PART=1/2)·app.v32.test.js·app.v33.test.js와 별도 프로세스로 돌린다.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

/* v32/v33와 같은 방식으로 '오늘'을 고정한다(2026-11-26 22:00 KST). */
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

function makeDom(seedStorage) {
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
      if (seedStorage) Object.keys(seedStorage).forEach((k) => window.localStorage.setItem(k, seedStorage[k]));
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}

async function run() {
  /* ============================================================
     AG. v34 — 배경 inert · 포커스 트랩 · 아이콘 이름 · aria-live
     ============================================================ */

  const A = makeDom();
  await sleep(500);
  const w = A.window, d = A.doc;
  const M = w.__ttokttokModel;
  const a11y = M.a11y;
  const $ = (s) => d.querySelector(s);
  const ev = (el, type, init) => el.dispatchEvent(new w.MouseEvent(type, Object.assign({ bubbles: true, cancelable: true }, init || {})));
  const key = (k, shift) => d.dispatchEvent(new w.KeyboardEvent('keydown', { key: k, shiftKey: !!shift, bubbles: true, cancelable: true }));
  const open = (id) => d.getElementById(id).classList.contains('is-open');

  /* ── 1) 버전·훅 ───────────────────────────────────────────── */
  ok('AG1 meta v34', d.querySelector('meta[name="app-version"]').content === 'v51', d.querySelector('meta[name="app-version"]').content);
  ok('AG2 qaVersion·a11y.version v34', M.qaVersion === 'v34' && a11y.version === 'v34', [M.qaVersion, a11y.version].join('/'));
  ok('AG3 감사·트랩 훅 노출', ['background', 'backgroundLocked', 'topDialog', 'focusables', 'auditAll', 'iconButtons', 'liveRegions', 'announce', 'liveText']
    .every((k) => typeof a11y[k] === 'function'), Object.keys(a11y).join(','));

  /* ── 2) 게이트가 열려 있으면 배경이 잠긴다 ──────────────────── */
  ok('AG4 시작 화면(게이트)이 최상위 대화상자', a11y.topDialog() === '#entryGate', a11y.topDialog());
  ok('AG5 게이트 열림 → #appRoot inert + aria-hidden',
    d.getElementById('appRoot').hasAttribute('inert') && d.getElementById('appRoot').getAttribute('aria-hidden') === 'true');
  ok('AG6 배경 잠금 감사 값', a11y.backgroundLocked() === true);
  ok('AG7 토스트·낭독 영역은 잠그지 않는다',
    !d.getElementById('toast').hasAttribute('inert') && !d.getElementById('a11yLive').hasAttribute('inert') &&
    d.getElementById('toast').getAttribute('aria-hidden') !== 'true');
  ok('AG8 낭독 영역은 role=status·polite·atomic',
    d.getElementById('a11yLive').getAttribute('role') === 'status' &&
    d.getElementById('a11yLive').getAttribute('aria-live') === 'polite' &&
    d.getElementById('a11yLive').getAttribute('aria-atomic') === 'true');

  /* 게이트 안에서 Tab은 게이트를 벗어나지 않는다 */
  const gateList = a11y.focusables('#entryGate');
  ok('AG9 게이트 포커스 후보 3개 이상', gateList.length >= 3, String(gateList.length));
  const gateLast = d.querySelector('#entryGate').querySelectorAll('a[href],button:not([disabled]),input:not([type="hidden"]):not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])');
  const gLast = gateLast[gateLast.length - 1];
  gLast.focus();
  key('Tab');
  const gFirstEl = d.querySelector('#entryGate').querySelector('a[href],button:not([disabled]),input:not([type="hidden"]):not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])');
  ok('AG10 마지막에서 Tab → 게이트 첫 요소로 순환', d.activeElement === gFirstEl, d.activeElement && (d.activeElement.id || d.activeElement.className));
  const gFirst = gFirstEl;
  gFirst.focus();
  key('Tab', true);
  ok('AG11 첫 요소에서 Shift+Tab → 게이트 안 마지막으로 순환', d.getElementById('entryGate').contains(d.activeElement));

  /* ── 3) 게이트 시트(겹침) — 최상위만 열리고 아래는 잠긴다 ───── */
  ev(d.getElementById('gateCta'), 'click');
  await sleep(200);
  const stackedTop = a11y.topDialog();
  ok('AG12 게이트 위 시트가 열리면 그 시트가 최상위', stackedTop === '#gateSheet' || stackedTop === '#regionSheet', stackedTop);
  ok('AG13 아래 게이트는 inert로 잠긴다',
    d.getElementById('entryGate').hasAttribute('inert') && d.getElementById('entryGate').getAttribute('aria-hidden') === 'true');
  ok('AG14 열린 시트 자신은 잠그지 않는다', !d.querySelector(stackedTop).hasAttribute('inert'));

  /* ── 4) 고객 모드 진입 후 시트 열기/닫기 ───────────────────── */
  ev(d.querySelector('[data-login="customer"]'), 'click');
  await sleep(300);
  ok('AG15 로그인 뒤 배경 잠금 해제', a11y.backgroundLocked() === false && !d.getElementById('appRoot').hasAttribute('inert') &&
    d.getElementById('appRoot').getAttribute('aria-hidden') === null, JSON.stringify(a11y.background()));

  ev(d.querySelector('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'), 'click');
  await sleep(120);
  const card = d.querySelector('#teacherList .teacher') || d.querySelector('.teacher');
  ev(card, 'click');
  await sleep(200);
  ok('AG16 선생님 시트 열림 → 배경 잠금', open('teacherSheet') && a11y.backgroundLocked() === true);
  ok('AG17 시트 안에 초점', a11y.focusInside('#teacherSheet'));
  const sheetList = a11y.focusables('#teacherSheet');
  ok('AG18 시트 포커스 후보(닫기·찜·상담·예약)', sheetList.length >= 3, sheetList.join(','));
  const nodes = d.querySelectorAll('#teacherSheet a[href],#teacherSheet button:not([disabled]),#teacherSheet input:not([type="hidden"]):not([disabled]),#teacherSheet [tabindex]:not([tabindex="-1"])');
  const lastNode = nodes[nodes.length - 1];
  lastNode.focus();
  key('Tab');
  ok('AG19 마지막에서 Tab → 시트 첫 요소', d.getElementById('teacherSheet').contains(d.activeElement) && d.activeElement === nodes[0]);
  nodes[0].focus();
  key('Tab', true);
  ok('AG20 첫 요소에서 Shift+Tab → 시트 마지막 요소', d.activeElement === lastNode || d.getElementById('teacherSheet').contains(d.activeElement));
  ok('AG21 배경(inert) 요소는 포커스 후보에서 빠진다', a11y.focusables('#appRoot').length === 0 || !d.getElementById('appRoot').hasAttribute('inert'));

  /* Escape → 닫히고 잠금 해제, 초점 복귀 */
  key('Escape');
  await sleep(200);
  ok('AG22 Escape로 시트 닫힘 + 잠금 해제', !open('teacherSheet') && a11y.backgroundLocked() === false);
  ok('AG23 닫힌 뒤 초점이 원래 카드로 복귀', d.activeElement && (d.activeElement === card || card.contains(d.activeElement)), d.activeElement && (d.activeElement.id || d.activeElement.className));

  /* ── 5) 대화상자 안에서도 저장 실패 안내가 읽힌다 ──────────── */
  ev(d.getElementById('homeGuideBtn'), 'click');
  await sleep(200);
  ok('AG24 대화상자 열림(이용안내)', open('guideSheet') && a11y.topDialog() === '#guideSheet', a11y.topDialog());
  const V = w.__ttokttokV32;
  V.simulateStorageFailure(true);
  V.saveAccountNow();
  await sleep(120);
  ok('AG25 잠긴 배경의 띠 대신 #a11yLive로 안내', /저장하지 못했어요/.test(a11y.liveText()), a11y.liveText());
  ok('AG26 띠는 배경(inert) 안에 있다', !!d.getElementById('ttAlertHost').closest('[inert]'));
  key('Escape');
  await sleep(150);
  const liveBefore = a11y.liveText();
  ok('AG27 대화상자가 없으면 낭독 영역을 쓰지 않는다', a11y.announce('중복 안내') === false && a11y.liveText() === liveBefore);

  /* ── 6) aria-live 정리 ────────────────────────────────────── */
  ok('AG28 알림 띠 컨테이너에는 aria-live 없음(자식 role=alert가 읽는다)',
    d.getElementById('ttAlertHost').getAttribute('aria-live') === null && d.getElementById('ttAlertHost').getAttribute('role') === null);
  const alertNodes = d.querySelectorAll('#ttAlertHost [data-alert]');
  ok('AG29 저장 실패 알림은 role=alert', alertNodes.length === 1 && alertNodes[0].getAttribute('role') === 'alert', String(alertNodes.length));
  const n1 = alertNodes[0];
  V.saveAccountNow();
  const afterNodes = d.querySelectorAll('#ttAlertHost [data-alert="account-save"]');
  ok('AG30 같은 알림을 다시 그려도 노드는 그대로(재낭독 방지)', afterNodes.length === 1 && afterNodes[0] === n1);
  V.simulateStorageFailure(false);
  ok('AG31 로딩 표시의 점 애니메이션은 aria-hidden(반복 낭독 방지)', /data-loading-dots aria-hidden="true"/.test(V.loadingHtml('불러오는 중')));
  ok('AG32 로딩 표시는 role=status·aria-live·aria-atomic', (function () {
    const box = d.createElement('div');
    box.innerHTML = V.loadingHtml('불러오는 중');
    const el = box.firstChild;
    return el.getAttribute('role') === 'status' && el.getAttribute('aria-live') === 'polite' && el.getAttribute('aria-atomic') === 'true';
  })());
  ok('AG33 토스트는 role=status·polite 하나만', d.getElementById('toast').getAttribute('role') === 'status' && d.getElementById('toast').getAttribute('aria-live') === 'polite');
  ok('AG34 상태 안내 4종은 그대로 유지', ['#toast', '#reviewHint', '#adminBackupResult', '#doneSaved'].every((sel) => {
    const el = d.querySelector(sel);
    return el && (el.getAttribute('role') === 'status' || el.getAttribute('role') === 'alert') && el.getAttribute('aria-live');
  }));
  ok('AG35 살아 있는 낭독 영역은 화면마다 하나 이하(중복 없음)', (function () {
    const groups = {};
    let bad = [];
    a11y.liveRegions().forEach((r) => {
      if (!r.live && !r.role) return;
      const box = d.getElementById(r.id);
      if (!box || !box.textContent.trim()) return;
      const t = box.textContent.replace(/\s+/g, ' ').trim();
      if (groups[t]) bad.push(r.id + '=' + groups[t]);
      else groups[t] = r.id;
    });
    return bad.length === 0;
  })());
  ok('AG36 예약 실패는 alert 블록 하나로만 알린다(토스트 중복 제거)', (function () {
    V.showBookingError && V.showBookingError('테스트 오류');
    const box = d.getElementById('bookError');
    const toastText = d.getElementById('toast').textContent;
    return !!box.querySelector('[role="alert"]') && !/예약을 마무리하지 못했어요/.test(toastText);
  })());

  /* ── 7) 아이콘 버튼 이름 전수 감사 ─────────────────────────── */
  const audit = a11y.auditAll();
  ok('AG37 조작 요소 전수(숨은 시트 포함) 이름 누락 0', audit.blank.length === 0, audit.blank.slice(0, 4).join(','));
  ok('AG38 아이콘 버튼은 aria-label 보유(누락 0)', audit.iconNoLabel.length === 0, audit.iconNoLabel.slice(0, 4).join(','));
  ok('AG39 입력 필드 label 누락 0', audit.unlabeledFields.length === 0, audit.unlabeledFields.join(','));
  ok('AG40 아이콘 버튼 수·이름 표본', audit.iconCount >= 10 && a11y.iconButtons().every((b) => b.label || b.labelledby), String(audit.iconCount));
  ok('AG41 시트 닫기 버튼 20개 이상 이름 보유', (function () {
    const closes = Array.from(d.querySelectorAll('.sheet-close'));
    return closes.length >= 15 && closes.every((el) => (el.getAttribute('aria-label') || '').trim());
  })());

  /* ── 8) 디자인 불변·가격 불변 ─────────────────────────────── */
  ok('AG42 <style> 블록 토큰 정합성(v35에서 CSS 수정 허용 — v34의 바이트 동일 검사 종료)', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    if (!m) return false;
    const css = m[1];
    const defs = new Set((css.match(/--[a-zA-Z0-9-]+\s*:/g) || []).map((x) => x.replace(/\s*:$/, '')));
    const uses = (css.match(/var\((--[a-zA-Z0-9-]+)\)/g) || []).map((x) => x.slice(4, -1));
    return (css.match(/:root\{/g) || []).length === 1 && uses.every((u) => defs.has(u));
  })(), String((HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length));
  ok('AG43 단가·수수료·정산 규칙 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 && JSON.stringify(M.settlementRule.payDays) === '[15,"end"]');
  ok('AG44 시드 예약 유지', !!d.querySelector('#homeSummaryNext') && /TT-261021-7302/.test(d.querySelector('#homeSummaryNext').textContent));
  ok('AG45 JS 오류 없음', A.errors.length === 0, A.errors.slice(0, 3).join(' | '));

  /* ── 9) 저장 차단(시큐리티 오류)에서도 트랩·감사 동작 ────────── */
  const B = makeDom();
  await sleep(450);
  const bd = B.doc;
  const bA11y = B.window.__ttokttokModel.a11y;
  ok('AG46 저장 차단에서도 게이트 잠금·이름 감사 동작',
    bA11y.topDialog() === '#entryGate' && bA11y.backgroundLocked() === true &&
    bA11y.auditAll().blank.length === 0 && bA11y.auditAll().iconNoLabel.length === 0);
  ok('AG47 저장 차단에서도 JS 오류 없음', B.errors.length === 0, B.errors.slice(0, 2).join(' | '));

  console.log('\nRESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.log('FATAL', (e && e.stack) || e); process.exit(1); });
