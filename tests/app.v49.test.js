/*
 * 똑똑쌤 v49 — 카드 열기/찜 분리 · .btn-sm 경계 · 정산 인쇄 쪽나눔 · 시트 스크롤 복원 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v49.test.js
 *
 * 이 스위트가 고정하는 것
 *   · 선생님 카드는 role=button이 아니고, 카드 안에 다른 버튼이 들어가지 않는다(중첩 인터랙티브 0)
 *   · Tab 정지점은 카드 전체를 덮는 열기 버튼(.t-open) 1개 + 고른 카드의 하트 1개
 *   · 하트의 Space/Enter는 찜만 바꾸고 프로필을 열지 않는다 / 방향키는 그대로 카드를 옮긴다
 *   · 요약 카드 안 텍스트형 아웃라인 버튼도 --edge-ctl 3:1 경계를 갖는다
 *   · 인쇄: 회차·카드 한 건은 쪼개지지 않고, 표 머리는 매 쪽 반복하며, 화면 등장 모션은 종이에서 끝난 상태
 *   · 시트를 닫으면 보던 스크롤 자리로 돌아온다(훅 노출)
 *   · 단가·수수료·정산·시드·백업 스키마·시연용 배지는 그대로
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
      if (o.wide) {
        window.matchMedia = function (q) {
          return { media: q, matches: /min-width:1280px/.test(q), addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} };
        };
      }
      if (o.onWindow) o.onWindow(window);
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
const key = (el, k, extra) => {
  const w = el.ownerDocument.defaultView;
  const ev = new w.KeyboardEvent('keydown', Object.assign({ key: k, bubbles: true, cancelable: true }, extra || {}));
  el.dispatchEvent(ev);
  return ev;
};

/* CSS 블록 하나의 본문 (중괄호 균형) */
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
const V49_AT = STYLE.indexOf('17. v49');
const V49_PRINT = block('@media print', V49_AT) || '';

async function run() {
  /* ── 1) 버전·부팅·훅 ─────────────────────────────────────────── */
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));
  ok('A1 meta v49', ($('meta[name="app-version"]') || {}).content === 'v49', ($('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 v48 로빙·인쇄 훅 유지(v49)', !!w.__ttokttokRoving && w.__ttokttokRoving.version === 'v49' &&
    !!w.__ttokttokPrint && w.__ttokttokPrint.version === 'v49' && typeof w.__ttokttokPrint.runner === 'function');
  ok('A4 v49 CSS 절이 있다', V49_AT > 0 && V49_AT > STYLE.indexOf('14. v48'));

  /* ── 2) 카드 구조: 열기 버튼과 하트가 형제 ───────────────────── */
  click($('[data-login="customer"]'));
  await sleep(260);
  click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(320);
  const cards = () => $$('#teacherList .teacher');
  const openers = () => $$('#teacherList .teacher .t-open');
  ok('B1 카드 8명', cards().length === 8, cards().length);
  ok('B2 카드는 role=button이 아니다', cards().every((c) => !c.hasAttribute('role')), cards()[0].getAttribute('role'));
  ok('B3 카드 자체는 Tab 정지점이 아니다', cards().every((c) => !c.hasAttribute('tabindex')));
  ok('B4 카드마다 열기 버튼이 있다', openers().length === 8 && openers().every((b) => b.tagName === 'BUTTON'));
  ok('B5 열기 버튼에 이름이 있다', openers().every((b) => /선생님 상세 프로필 보기$/.test(b.getAttribute('aria-label') || '')),
    openers()[0].getAttribute('aria-label'));
  ok('B6 열기 버튼은 장식 없이 빈 버튼(카드 전체를 덮는다)', openers().every((b) => b.textContent.trim() === ''));
  ok('B7 하트는 열기 버튼의 자식이 아니라 형제', cards().every((c) => {
    const h = c.querySelector('.t-fav');
    return h && h.parentElement === c && !h.closest('.t-open');
  }));
  ok('B8 카드 안 조작 요소는 열기 버튼 + 하트 둘뿐', cards().every((c) => c.querySelectorAll('button').length === 2));
  ok('B9 중첩 인터랙티브 0(훅으로 센 값)', w.__ttokttokRoving.nestedButtons() === 0, w.__ttokttokRoving.nestedButtons());
  ok('B10 전 화면에 role=button 안 버튼 0', (function () {
    const bad = [];
    $$('[role="button"]').forEach((el) => { if (el.querySelector('button,a[href]')) bad.push(el.className); });
    return bad.length === 0;
  })());

  /* ── 3) 로빙 탭인덱스: 열기 버튼 1개 + 고른 카드의 하트 ───────── */
  const tabStops = () => openers().filter((b) => b.getAttribute('tabindex') === '0');
  const heartsOn = () => $$('#teacherList .t-fav').filter((b) => b.getAttribute('tabindex') === '0');
  ok('C1 목록 정지점 1개', tabStops().length === 1 && w.__ttokttokRoving.tabStops() === 1);
  ok('C2 첫 카드 열기 버튼이 정지점', openers()[0].getAttribute('tabindex') === '0');
  ok('C3 Tab 정지점은 고른 카드의 하트 하나뿐', heartsOn().length === 1 && heartsOn()[0].closest('.teacher') === cards()[0],
    heartsOn().length);
  key(openers()[0], 'ArrowDown');
  ok('C4 ↓ 다음 카드의 열기 버튼으로', doc.activeElement === openers()[1], doc.activeElement && doc.activeElement.className);
  ok('C5 정지점도 함께 옮겨간다', tabStops()[0] === openers()[1] && heartsOn()[0].closest('.teacher') === cards()[1]);

  /* 하트: Space·Enter는 찜만, 프로필은 열리지 않는다 */
  const heart0 = cards()[0].querySelector('.t-fav');
  const before = heart0.getAttribute('aria-pressed');
  const evSpace = key(heart0, ' ');
  await sleep(60);
  ok('C6 하트의 Space는 프로필을 열지 않는다', !$('#teacherSheet').classList.contains('is-open'));
  ok('C7 하트의 Space는 목록 이동으로 새지 않는다(기본 동작 유지)', evSpace.defaultPrevented === false);
  const evEnter = key(heart0, 'Enter');
  await sleep(60);
  ok('C8 하트의 Enter도 프로필을 열지 않는다', !$('#teacherSheet').classList.contains('is-open') && evEnter.defaultPrevented === false);
  ok('C9 하트 상태는 그대로(클릭 전)', heart0.getAttribute('aria-pressed') === before, [before, heart0.getAttribute('aria-pressed')]);
  key(heart0, 'ArrowDown');
  ok('C10 하트에서 ↓는 다음 카드로', doc.activeElement === openers()[1]);
  click(heart0);
  await sleep(60);
  ok('C11 하트를 누르면 찜만 바뀐다', heart0.getAttribute('aria-pressed') === 'true' && !$('#teacherSheet').classList.contains('is-open'));

  /* 열기 버튼: Enter/클릭으로 프로필 */
  click(openers()[0]);
  await sleep(120);
  ok('C12 열기 버튼을 누르면 시트가 열린다', $('#teacherSheet').classList.contains('is-open'));
  ok('C13 시트에 그 선생님', /박서준/.test($('#teacherSheetBody').textContent));
  key(doc.body, 'Escape');
  await sleep(120);
  ok('C14 Esc로 닫힌다', !$('#teacherSheet').classList.contains('is-open'));
  key(openers()[1], 'Enter');
  await sleep(120);
  ok('C15 Enter로도 열린다', $('#teacherSheet').classList.contains('is-open') && /이하늘/.test($('#teacherSheetBody').textContent));
  click($('#teacherSheet [data-sheet-close]'));
  await sleep(100);
  ok('C16 닫으면 초점이 목록의 열기 버튼으로 돌아온다',
    !!doc.activeElement && doc.activeElement.classList.contains('t-open') && !!doc.activeElement.closest('#teacherList'),
    [openers().indexOf(doc.activeElement), doc.activeElement && doc.activeElement.className]);
  /* 누른 카드로 돌아오는지는 '클릭으로 연 경우'에 본다(jsdom은 Enter로 click을 만들지 않는다) */
  click(openers()[2]);
  await sleep(120);
  click($('#teacherSheet [data-sheet-close]'));
  await sleep(120);
  ok('C16b 클릭으로 연 시트는 그 카드의 열기 버튼으로',
    doc.activeElement === openers()[2], [openers().indexOf(doc.activeElement), doc.activeElement && doc.activeElement.className]);
  /* 시트를 닫으면 스크롤 자리 복원 훅이 남는다 */
  ok('C17 스크롤 복원 훅 노출', !!w.__ttokttokSheetScroll && w.__ttokttokSheetScroll.version === 'v49',
    w.__ttokttokSheetScroll);

  /* ── 4) 경계: .btn-sm 아웃라인 ──────────────────────────────── */
  ok('D1 요약 카드 보조 버튼 규칙이 있다',
    /body #homeSummaryRebook \.btn-outline\.btn-sm\{[^}]*border:1px solid var\(--edge-ctl\)/.test(STYLE));
  ok('D2 그 규칙에 44px 터치 높이가 있다', /body #homeSummaryRebook \.btn-outline\.btn-sm\{[^}]*min-height:44px/.test(STYLE));
  ok('D3 v49 규칙이 레거시 텍스트형 규칙보다 구체적(같은 카드 안에서 이긴다)',
    /#homeSummaryRebook \.btn-outline\{background:transparent;border:0/.test(STYLE) && /body #homeSummaryRebook \.btn-outline\.btn-sm\{/.test(STYLE));
  const rebookBtn = (function () {
    const el = $$('#homeSummaryRebook .btn-outline.btn-sm')[0];
    return el || null;
  })();
  ok('D4 요약 카드에 아웃라인 보조 버튼이 있다', !!rebookBtn, rebookBtn && rebookBtn.textContent.trim());

  /* ── 5) 인쇄: 쪽나눔·표 머리·모션·머리글 ────────────────────── */
  ok('E1 인쇄 회차는 통째로(break-inside)', /\[data-print-row\][^{]*\{[^}]*break-inside:avoid/.test(V49_PRINT));
  ok('E2 인쇄 요약 카드도 통째로', /\[data-print-keep\]/.test(V49_PRINT) && /\.admin-card/.test(V49_PRINT));
  ok('E3 표 머리는 매 쪽 반복', /thead\{display:table-header-group\}/.test(V49_PRINT));
  ok('E4 표 행은 쪼개지지 않는다', /tr,th,td\{break-inside:avoid/.test(V49_PRINT));
  ok('E5 좁은 화면 2단은 종이에서 한 줄로', /\.tt46-cols\{display:block!important\}/.test(V49_PRINT));
  ok('E6 화면 등장 모션은 종이에서 끝난 상태', /\.tt-reveal\{opacity:1!important;transform:none!important\}/.test(V49_PRINT));
  ok('E7 종이 머리·꼬리 요소가 있다', !!$('#printRunner') && !!$('#printFoot') && !!$('#printRunnerTitle'));
  ok('E8 머리·꼬리는 화면에서 숨는다', /#printRunner,#printFoot\{display:none\}/.test(STYLE));
  ok('E9 머리·꼬리는 인쇄에서 보인다', /#printRunner\{display:flex!important;position:fixed/.test(V49_PRINT) &&
    /#printFoot\{display:block!important;position:fixed/.test(V49_PRINT));
  /* 정산서 미리보기 본문: 회차마다 data-print-row, 요약·머리는 keep */
  click($('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-settle"]'));
  await sleep(300);
  const preview = w.__ttokttokModel.openStatementPreview();
  await sleep(150);
  const rows = $$('#settlementPrintBody [data-print-row]');
  ok('E10 정산서 회차마다 인쇄 잠금 표시', rows.length === (preview && preview.rows ? preview.rows.length : rows.length) && rows.length > 0, rows.length);
  ok('E11 정산서 머리·요약은 통째로', $$('#settlementPrintBody [data-print-keep]').length === 2,
    $$('#settlementPrintBody [data-print-keep]').length);
  const mark = w.__ttokttokPrint.mark();
  await sleep(30);
  ok('E12 인쇄 대상은 정산서 시트', mark === 'settlementPrintSheet', mark);
  ok('E13 종이 머리글에 문서 이름·월·선생님이 들어간다', /정산 명세서/.test($('#printRunnerTitle').textContent) &&
    /2026년 11월/.test($('#printRunnerTitle').textContent) && /선생님/.test($('#printRunnerTitle').textContent),
    $('#printRunnerTitle').textContent);
  ok('E14 종이 머리에 발급일·시연용 표기', /발급/.test($('#printRunnerNote').textContent) && /시연용/.test($('#printRunnerNote').textContent),
    $('#printRunnerNote').textContent);
  ok('E15 종이 꼬리에 상호·대표·문의·시연용', /상호 똑똑쌤/.test($('#printFoot').textContent) && /031-919-8577/.test($('#printFoot').textContent) &&
    /시연용/.test($('#printFoot').textContent));

  /* ── 6) 긴 글 마감 ─────────────────────────────────────────── */
  ok('F1 긴 이름·지역은 줄바꿈으로 감싼다', /\.t-name,\.h-name,\.admin-name,\.req-top b,\.sheet-title,\.li-main b\{[^}]*overflow-wrap:anywhere/.test(STYLE));
  ok('F2 요청 카드 머리는 접힌다', /\.req-top\{flex-wrap:wrap\}/.test(STYLE) && /\.req-top b\{flex:1 1 auto\}/.test(STYLE));
  ok('F3 한국어는 어절 우선(keep-all)', /\.t-meta,\.t-region,\.req-meta,\.req-pay,\.admin-meta,\.fine\{[^}]*word-break:keep-all/.test(STYLE));

  /* ── 7) 넓은 화면: 방향키로 프로필 열이 따라온다 ─────────────── */
  const B = makeDom({ wide: true });
  await waitBooted(B.window);
  const bw = B.window, bd = B.doc;
  const b$ = (s) => bd.querySelector(s);
  const b$$ = (s) => Array.from(bd.querySelectorAll(s));
  click(b$('[data-login="customer"]'));
  await sleep(300);
  click(b$('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(300);
  const bOpen = b$$('#teacherList .t-open');
  bOpen[0].focus();
  key(bOpen[0], 'ArrowDown');
  await sleep(80);
  ok('G1 1280 ↓ 다음 카드 열기 버튼', bd.activeElement === bOpen[1], bd.activeElement && bd.activeElement.className);
  ok('G2 오른쪽 프로필 열이 따라온다', b$('#teacherPane').hidden === false && /이하늘/.test(b$('#teacherPane').textContent));
  key(bOpen[1], 'Enter');
  await sleep(120);
  ok('G3 Enter는 프로필 열 안으로 초점', b$('#teacherPane').contains(bd.activeElement));
  key(bd.activeElement, 'Escape');
  await sleep(120);
  ok('G4 Esc는 고른 카드의 열기 버튼으로', bd.activeElement === bOpen[1]);
  ok('G5 1280 오류 0', !B.errors.length, B.errors.slice(0, 2));

  /* ── 8) 비즈니스 규칙 불변 ─────────────────────────────────── */
  const M = w.__ttokttokModel;
  const pr = M && M.pricing;
  ok('H1 단가 90,000/70,000·수수료 22.2%', pr && pr.consumerPrice === 90000 && pr.teacherPayout === 70000 && pr.platformFeeRate === 0.2222,
    pr && pr.consumerPrice);
  ok('H2 정산 D+3·15일/말일', pr && pr.settlementConfirmDays === 3 && JSON.stringify(pr.settlementPayDays) === '[15,"end"]');
  ok('H3 시드 예약 TT-261021-7302', /TT-261021-7302/.test(HTML));
  ok('H4 백업 스키마 ttokttok.v23', /ttokttok\.v23/.test(HTML));
  ok('H5 시연용 배지', /시연용/.test(HTML));
  ok('H6 외부 연결 없음(fetch/XMLHttpRequest/supabase)', !/\bfetch\(|XMLHttpRequest|supabase\.co/i.test(HTML));
  ok('H7 중복 id 0', (function () {
    const ids = $$('[id]').map((el) => el.id);
    return ids.filter((v, i) => ids.indexOf(v) !== i).length === 0;
  })());

  console.log('\n=== v49 jsdom: ' + pass + ' 통과 / ' + fails.length + ' 실패 ===');
  if (fails.length) {
    fails.forEach((f) => console.log('  ✗ ' + f));
    process.exitCode = 1;
  }
}

run().catch((e) => { console.error(e); process.exitCode = 1; });
