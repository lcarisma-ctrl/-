/*
 * 똑똑쌤 v44 — 시작 화면 장면·탭별 스크롤 기억·한국어 문단 리듬 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v44.test.js
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
  if (cond) { pass++; } else { fails.push(name + (extra ? ' :: ' + extra : '')); }
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

async function run() {
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));

  ok('A1 meta v44', (doc.querySelector('meta[name="app-version"]') || {}).content === 'v49',
    (doc.querySelector('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));

  /* ── 1) 시작 화면 장면 ─────────────────────────────────────── */
  const scene = $('.gate-scene');
  ok('B1 시작 화면에 장면(창·선생님·보호자·지팡이·새싹·매트)', !!scene &&
    $$('.gate-scene svg path, .gate-scene svg circle, .gate-scene svg rect, .gate-scene svg ellipse').length >= 12,
    scene ? String($$('.gate-scene svg *').length) : 'none');
  ok('B2 장면은 장식(aria-hidden) + 한 줄 캡션', scene.getAttribute('aria-hidden') === 'true' &&
    /집에서 시작하는 회복/.test($('.gate-scene figcaption').textContent));
  ok('B3 낮은 화면(839px 이하)에서는 장면을 접는다', /@media\(max-height:839px\)\{\.gate-scene\{display:none\}\}/.test(STYLE));
  ok('B4 시작 화면 필수 요소는 그대로', !!$('#gateCta') && !!$('#gateRegionBtn') && $$('.gate-point').length === 4);

  /* ── 2) 탭별 스크롤 기억 ──────────────────────────────────── */
  ok('C1 탭 스크롤 훅 v44', w.__ttokttokTabScroll && w.__ttokttokTabScroll.version === 'v44',
    JSON.stringify(w.__ttokttokTabScroll));
  ok('C2 탭 이동은 keepScroll로 부른다', /showTab\(tabName, true, true\)/.test(HTML));
  ok('C3 이전 탭 위치를 저장한다', /tabScroll\[currentTab\] = window\.scrollY/.test(HTML) &&
    /var backTo = keepScroll \? \(tabScroll\[name\] \|\| 0\) : 0;/.test(HTML));
  ok('C4 탭 이동이 오류 없이 동작', (function () {
    click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
    click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]'));
    return $('#screen-home').classList.contains('is-active') && w.__ttokttokTabScroll.current === 'home';
  })(), JSON.stringify(w.__ttokttokTabScroll && w.__ttokttokTabScroll.current));

  /* ── 3) 한국어 문단 리듬 ──────────────────────────────────── */
  ok('D1 문단은 text-wrap:pretty(마지막 줄 한 단어 방지)', /p,\.fine,\.sheet-desc[^{]*\{text-wrap:pretty\}/.test(STYLE));
  ok('D2 제목은 text-wrap:balance', /h1,h2,\.hh-title,\.wstep-title,\.sec-title,\.mp-title,\.sheet-title\{text-wrap:balance\}/.test(STYLE));
  ok('D3 값 숫자는 고정폭(tabular-nums) 한 규칙으로', /\.sum-row > b,\.sum-line > b,\.adm-n,\.adm-r,\.total b,\.book-total b,\.settle-cell b\{font-variant-numeric:tabular-nums\}/.test(STYLE));

  /* ── 4) 앞선 버전 기능 유지 ───────────────────────────────── */
  ok('E1 v43 인트로 컷신 유지', !!$('#intro .in-teacher') && /var INTRO_MS = 2100;/.test(HTML));
  ok('E2 v42 홈 네 장 유지', !!$('#homePassCard') && !!$('#homeReportCard') && !!$('#homeRebookCard'));
  ok('E3 v42 글자 크기 3단 유지', $$('#mpTextSize [data-textsize]').length === 3);
  ok('E4 v43 빈 상태 그림 유지', /empty-art/.test(w.__ttokttokUI.emptyHtml('admin-resv')));
  const M = w.__ttokttokModel;
  ok('E5 사업 수치·정책·시드 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
    String(M.settlementRule.payDays) === '15,end' &&
    (M.reservations() || []).some((r) => r.no === 'TT-261021-7302'));
  ok('E6 CSS·HTML 예산', STYLE.length <= 242000 && Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024,
    STYLE.length + ' / ' + Buffer.byteLength(HTML, 'utf8'));

  console.log('\nV44 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.error(e); process.exit(2); });
