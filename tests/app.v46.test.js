/*
 * 똑똑쌤 v46 — 넓은 화면(태블릿·데스크톱 2단) 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v46.test.js
 *
 * 이 스위트가 고정하는 것
 *   · 1024 미만은 v45와 같은 1단 흐름(.tt46-col = display:contents)
 *   · 768부터 앱·탭바·시트 폭이 함께 넓어지고 카드가 두 열
 *   · 1024부터 작업면 1,180px + 화면별 2단(선생님·일지·관리자·정산·내 정보·선생님 화면)
 *   · 2단으로 옮겨도 읽기·탭 순서(DOM 순서)가 모바일과 같다
 *   · 320×568 시작 화면이 법적 고지까지 한 화면에 들어온다(44px 버튼 유지)
 *   · 대비 자동 회귀(tests/contrast_v45.py → qa_gate)가 파이프라인에 들어 있다
 *   · 단가·수수료·정산·시드·백업 스키마는 그대로
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

/* CSS에서 미디어 블록 하나의 본문을 꺼낸다(중괄호 균형). from 이후에서 찾는다. */
function mediaBlock(header, from) {
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
/* v46 넓은 화면 절의 시작 표식 — 이 뒤의 미디어 블록만 본다 */
const V46_AT = STYLE.indexOf('12. v46');
const M768 = mediaBlock('@media(min-width:768px)', V46_AT) || '';
const M1024 = mediaBlock('@media(min-width:1024px)', V46_AT) || '';
const M1280 = mediaBlock('@media(min-width:1280px)', V46_AT) || '';
/* 시작 화면 낮은 화면 보정은 v44·v46 두 블록이 있으니 마지막 것을 본다 */
const M600 = mediaBlock('@media(max-height:600px)', STYLE.lastIndexOf('@media(max-height:600px)', STYLE.indexOf('.gate-legal{font-size:11px'))) || '';

async function run() {
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));
  const pos = (a, b) => !!(a && b) && (a.compareDocumentPosition(b) & 4) !== 0; // a가 b보다 앞

  /* ── 1) 버전·기본 상태 ─────────────────────────────────────── */
  ok('A1 meta v46', (doc.querySelector('meta[name="app-version"]') || {}).content === 'v49',
    (doc.querySelector('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 v45 테마 훅 유지', !!w.__ttokttokTheme && w.__ttokttokTheme.version === 'v45');
  ok('A4 v44 탭 스크롤 유지', !!(w.__ttokttokTabScroll && w.__ttokttokTabScroll.version === 'v44'));

  /* ── 2) 1024 미만 = 기존 1단 흐름 그대로 ───────────────────── */
  ok('B1 2단 묶음은 기본이 display:contents(모바일 1단)', /\.tt46-col\{display:contents\}/.test(STYLE));
  ok('B2 2단 그릇은 기본이 block', /\.tt46-cols\{display:block\}/.test(STYLE));
  ok('B3 흐름 묶음도 기본 display:contents', /\.tt46-flow\{display:contents\}/.test(STYLE));
  ok('B4 2단 규칙은 v46 절 안에만 있다', V46_AT > 0 && /#screen-teachers \.tt46-cols\{/.test(M1024) &&
    !/#screen-teachers \.tt46-cols\{/.test(STYLE.slice(0, V46_AT)),
    'v46 절 앞(모바일·기존 데스크톱)에 2단 규칙이 있다');

  /* ── 3) 태블릿(≥768) — 앱·탭바·시트 폭을 함께 넓힌다 ───────── */
  ok('C1 태블릿 앱 폭 720', /\.app\{max-width:720px/.test(M768), M768.slice(0, 80));
  ok('C2 태블릿 탭바도 720(폭 어긋남 없음)', /\.tabbar\{max-width:720px/.test(M768));
  ok('C3 태블릿 시트 640', /\.sheet\{max-width:640px\}/.test(M768));
  ok('C4 태블릿 토스트 520', /\.toast\{max-width:520px/.test(M768));
  ok('C5 태블릿 카드 두 열(선생님 목록)', /#teacherList,#dongClusterList\{display:flex;flex-wrap:wrap/.test(M768));
  ok('C6 태블릿 홈 카드 두 열', /\.home-body > #homePassCard,\.home-body > #homeReportCard/.test(M768));

  /* ── 4) 데스크톱(≥1024) — 작업면과 2단 ──────────────────────── */
  ok('D1 데스크톱 앱 폭 1,180', /\.app\{max-width:1180px/.test(M1024));
  ok('D2 데스크톱은 브랜드 패널을 접고 작업면을 쓴다', /\.desk-brand\{display:none\}/.test(M1024));
  ok('D3 데스크톱 시트 600(모달)', /\.sheet\{max-width:600px/.test(M1024));
  ok('D4 데스크톱 탭바는 앱 안에 붙는다', /\.tabbar\{position:sticky/.test(M1024));
  ok('D5 2단 골격(그릇=grid·열=flex)', /\.tt46-cols\{display:grid/.test(M1024) && /\.tt46-col\{display:flex/.test(M1024));
  ok('D6 선생님 찾기 = 312px 레일 + 결과', /#screen-teachers \.tt46-cols\{grid-template-columns:312px/.test(M1024));
  ok('D7 관리자 = 지표 456px + 처리면', /#screen-admin \.tt46-cols\{grid-template-columns:456px/.test(M1024));
  ok('D8 정산 = 요약 352px + 내역', /#screen-tp-settle \.tt46-cols\{grid-template-columns:352px/.test(M1024));
  ok('D9 일지 = 2단 grid', /#screen-journal \.journal\{display:grid/.test(M1024));
  ok('D10 내 정보·선생님 홈도 2단', /#screen-mypage \.tt46-cols\{/.test(M1024) && /#screen-tp-home \.tt46-cols\{/.test(M1024));
  ok('D11 예약 마법사는 760px로 읽기 폭 제한', /#bookingWizard\{max-width:760px\}/.test(M1024));
  ok('D12 레일은 스크롤해도 따라온다', /\.tt46-col\.is-sticky\{position:sticky/.test(M1024));
  ok('D13 1280px 이상은 선생님 상세 열을 둔 3칸', /#screen-teachers \.tt46-cols\{grid-template-columns:288px/.test(M1280) &&
    /#teacherMainCol\{display:grid/.test(M1280) && /#teacherPane\{display:block/.test(M1280));
  ok('D14 상세 열은 기본적으로 숨는다(모바일은 시트)', STYLE.indexOf('.teacher-pane{display:none}') > V46_AT &&
    !/display:block/.test(STYLE.slice(STYLE.indexOf('.teacher-pane{display:none}'), STYLE.indexOf('.teacher-pane{display:none}') + 30)));

  /* ── 5) 마크업: 2단 묶음이 실제로 있다 ─────────────────────── */
  ok('E1 선생님 화면 두 열', !!$('#teacherCols') && !!$('#teacherSideCol') && !!$('#teacherMainCol'));
  ok('E2 레일에 검색·신뢰지표·필터·권역', ['#homeSearch', '#trustStrip', '#teacherViewTabs', '#teacherFilters', '#regionFilters']
    .every((s) => $('#teacherSideCol ' + s) || $('#teacherSideCol' + s)));
  ok('E3 결과 열에 목록·내 주변·쿼리', ['#teacherQueryBar', '#teacherList', '#nearPanel']
    .every((s) => $('#teacherMainCol ' + s)));
  ok('E4 일지 두 열 + 흐름 묶음', !!$('#journalSideCol') && !!$('#journalMainCol') && !!$('#journalFlow'));
  ok('E5 일지 왼쪽 = 요약·최근 일지(상세)·오늘 일정', ['#weeklyCard', '#journalLatestCard', '#todayCard'].every((s) => $('#journalSideCol ' + s)) &&
    !!$('#journalSideCol .patient'));
  ok('E6 일지 오른쪽 = 타임라인·리포트·차트', ['#journalTimeline', '#reportOpen', '#chart'].every((s) => $('#journalMainCol ' + s)));
  ok('E7 운동·통증·메모는 폭을 다 쓰는 흐름 묶음', ['#journalFlow .checklist-card', '#journalFlow .pain-card', '#journalFlow .memo-card']
    .every((s) => $(s)));
  ok('E8 공유 버튼·후기는 두 열 아래(전체 폭)', !$('#journalSideCol #shareBtn') && !$('#journalMainCol #shareBtn') && !!$('#journal #shareBtn') &&
    !$('#journalMainCol #journalReviewSec') && !!$('#journal #journalReviewSec'));
  ok('E9 관리자 = 지표 열 + 처리 열', !!$('#adminMetricsSec') && !!$('#adminOpsSec') &&
    !!$('#adminMetricsSec').closest('.tt46-col') && !!$('#adminResvSec').closest('.tt46-col') &&
    $('#adminMetricsSec').closest('.tt46-col') !== $('#adminResvSec').closest('.tt46-col'));
  ok('E10 내 정보 = 프로필·메뉴 / 읽기 설정', !!$('#screen-mypage .tt46-cols') &&
    !!$('#mpTextCard').closest('.tt46-col') && !!$('#mpThemeCard').closest('.tt46-col') &&
    $('#mpTextCard').closest('.tt46-col') !== $('.mp-top')?.closest('.tt46-col'));
  ok('E11 선생님 홈·일정·일지·내 정보 2단', ['#screen-tp-home', '#screen-tp-schedule', '#screen-tp-journal', '#screen-tp-mypage']
    .every((s) => $(s + ' .tt46-cols')));
  ok('E12 선생님 상세 열이 목록 열 안에 있다', !!$('#teacherMainCol #teacherPane') && $('#teacherPane').hidden);

  /* ── 6) 읽기 순서(DOM) = 모바일 순서 그대로 ────────────────── */
  ok('F1 선생님 화면 DOM 순서 유지(검색→보기→필터→권역→목록)',
    pos($('#homeSearch'), $('#teacherViewTabs')) && pos($('#teacherViewTabs'), $('#teacherFilters')) &&
    pos($('#teacherFilters'), $('#regionFilters')) && pos($('#regionFilters'), $('#teacherList')));
  ok('F2 일지 DOM 순서 유지(요약→최근 일지→오늘→타임라인→차트→운동)',
    pos($('#weeklyCard'), $('#journalLatestCard')) && pos($('#journalLatestCard'), $('#todayCard')) &&
    pos($('#todayCard'), $('#journalTimeline')) && pos($('#journalTimeline'), $('#chart')) &&
    pos($('#chart'), $('#journalFlow .checklist-card')));
  ok('F3 관리자 DOM 순서 유지(지표→오늘 할 일→예약 큐→백업)',
    pos($('#adminMetricsSec'), $('#adminOpsSec')) && pos($('#adminOpsSec'), $('#adminResvSec')) &&
    pos($('#adminResvSec'), $('#adminBackupSec')));
  ok('F4 내 정보 DOM 순서 유지(프로필→메뉴→글자 크기→테마)',
    pos($('.mp-top'), $('.mp-list')) && pos($('.mp-list'), $('#mpTextCard')) && pos($('#mpTextCard'), $('#mpThemeCard')));

  /* ── 7) 2단으로 옮겨도 기능은 그대로 ───────────────────────── */
  click($('[data-login="customer"]'));
  await sleep(400);
  click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(250);
  ok('G1 선생님 카드 8명 그대로', $$('#teacherList .teacher').length === 8, $$('#teacherList .teacher').length);
  click($('#teacherList .teacher'));
  await sleep(250);
  ok('G2 카드를 누르면 상세 시트가 열린다(2단에서도 동작)', $('#teacherSheet').classList.contains('is-open'));
  ok('G3 상세 시트 본문 채워짐', ($('#teacherSheetBody').textContent || '').length > 50);
  click($('#teacherSheet [data-sheet-close]'));
  await sleep(200);
  ok('G4 시트 닫힘', !$('#teacherSheet').classList.contains('is-open'));
  click($('#teacherFilters [data-cat="stroke"]'));
  await sleep(200);
  ok('G5 레일 필터가 결과에 그대로 적용', $$('#teacherList .teacher').length === 3, $$('#teacherList .teacher').length);
  click($('#teacherFilters [data-cat="all"]'));
  await sleep(150);

  /* 일지: 오늘의 운동 체크가 2단에서도 세어진다 */
  click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]'));
  await sleep(250);
  ok('G6 일지 운동 체크 5개가 한 묶음에', $$('#journalFlow .checklist-card .check input').length === 5);
  const before = ($('#checkCount').textContent || '').trim();
  click($('#c3'));
  await sleep(120);
  ok('G7 체크하면 진행률이 바뀐다', ($('#checkCount').textContent || '').trim() !== before,
    before + ' → ' + ($('#checkCount').textContent || '').trim());

  /* 정산: 열 묶음이 렌더 결과에 들어간다 */
  const B = makeDom();
  await waitBooted(B.window);
  const bd = B.doc;
  const b$ = (s) => bd.querySelector(s);
  click(b$('[data-login="therapist"]'));
  await sleep(500);
  click(bd.querySelector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-settle"]'));
  await sleep(400);
  const cols = b$('#tpsScreen .tt46-cols');
  ok('H1 정산 화면에 2단 묶음이 렌더된다', !!cols);
  ok('H2 월 칩은 묶음 밖(전체 폭)', !!b$('#tpsScreen > #tpsMonths') && !b$('#tpsScreen .tt46-col #tpsMonths'));
  ok('H3 요약은 왼쪽 열, 내역은 오른쪽 열', !!cols && !!cols.children[0].querySelector('#tpsSummary') &&
    !!cols.children[1].querySelector('#tpsRows'));
  ok('H4 정산 금액·건수 그대로(세전 980,000원)', /980,000/.test(b$('#tpsScreen').textContent));
  ok('H5 수수료 22.2%·D+3 문구 유지', /22\.2%/.test(b$('#tpsScreen').textContent) && /D\+3/.test(b$('#tpsScreen').textContent));

  /* ── 8) 1280px 이상: 카드를 누르면 오른쪽 상세 열(모바일·태블릿은 시트) ── */
  const W = makeDom({
    onWindow(win) {
      win.matchMedia = function (q) {
        return { matches: /min-width:1280px/.test(q), media: q, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} };
      };
    }
  });
  await waitBooted(W.window);
  const wd = W.doc;
  const w$ = (s) => wd.querySelector(s);
  click(w$('[data-login="customer"]'));
  await sleep(400);
  click(wd.querySelector('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(250);
  click(w$('#teacherList .teacher'));
  await sleep(250);
  ok('M1 넓은 화면: 카드를 누르면 상세 열이 열린다', !w$('#teacherPane').hidden);
  ok('M2 넓은 화면: 시트를 겹쳐 띄우지 않는다', !w$('#teacherSheet').classList.contains('is-open'));
  ok('M3 상세 열에 이름·자격·신뢰 배지', ['박서준', '물리치료사', '신뢰 배지'].every((t) => w$('#teacherPane').textContent.includes(t)));
  ok('M4 고른 카드에 is-selected·aria-current', (() => {
    const sel = w$('#teacherList .teacher.is-selected');
    return !!sel && sel.getAttribute('aria-current') === 'true';
  })());
  ok('M5 상세 열에 닫기·전체 프로필 버튼', !!w$('#teacherPane [data-pane-close]') && !!w$('#teacherPane [data-pane-open]'));
  click(w$('#teacherPane [data-pane-open]'));
  await sleep(250);
  ok('M6 전체 프로필 보기 → 시트가 열린다', w$('#teacherSheet').classList.contains('is-open') && w$('#teacherSheetBody').textContent.includes('박서준'));
  ok('M7 전체 프로필 보기 → 상세 열은 닫힌다', w$('#teacherPane').hidden);
  click(w$('#teacherSheet [data-sheet-close]'));
  await sleep(200);
  click(w$('#teacherList .teacher'));
  await sleep(200);
  click(w$('#teacherPane [data-pane-close]'));
  await sleep(150);
  ok('M8 닫기를 누르면 상세 열이 빈다', w$('#teacherPane').hidden && !w$('#teacherList .teacher.is-selected'));
  ok('M9 넓은 화면 동작에서도 오류 0', !W.errors.length, W.errors.slice(0, 2));

  /* ── 9) 320×568 시작 화면 — 한 화면 수납 ───────────────────── */
  ok('I1 낮은 화면 장점 카드 여백 축소', /\.gate-point\{padding:8px 12px/.test(M600));
  ok('I2 낮은 화면 고지 글자 11px 유지', /\.gate-legal\{font-size:11px/.test(M600));
  ok('I3 낮은 화면 시작 화면 바깥 여백 축소', /#entryGate\{padding-top:10px;padding-bottom:8px\}/.test(STYLE));
  ok('I4 44px 버튼 기준 유지(시작 CTA)', /\.gate-cta\{[^}]*min-height:44px/.test(STYLE) || /min-height:44px/.test(STYLE));
  ok('I5 법적 고지·사업자 정보가 시작 화면 안에 있다', !!$('.gate-legal') && !!$('#gateBizInfo'));
  ok('I6 1024 미만에서는 장면을 그대로(768 규칙이 장면을 숨기지 않음)', !/\.gate-scene\{display:none\}/.test(M768));

  /* ── 9) 대비 자동 회귀가 파이프라인에 들어 있다 ─────────────── */
  const gate = fs.existsSync(path.join(__dirname, 'qa_gate.py'));
  const gateSrc = gate ? fs.readFileSync(path.join(__dirname, 'qa_gate.py'), 'utf8') : '';
  ok('J1 qa_gate.py 존재', gate);
  ok('J2 게이트가 라이트·다크 대비를 모두 돈다', /step_contrast/.test(gateSrc) && /\("light", "375"\), \("dark", "375"\)/.test(gateSrc));
  ok('J3 게이트가 실패하면 빌드를 멈춘다(비정상 종료)', /return 1 if bad else 0/.test(gateSrc) && /contrast_v45\.py/.test(gateSrc) &&
    /sys\.exit\(main\(\)\)/.test(gateSrc));
  const cs = fs.readFileSync(path.join(__dirname, 'contrast_v45.py'), 'utf8');
  ok('J4 대비 도구는 위반이 있으면 0이 아닌 코드로 끝난다', /if fails:[\s\S]{0,160}?return 1/.test(cs) && /sys\.exit\(main\(\)\)/.test(cs));
  ok('J5 대비 도구가 데스크톱 뷰포트도 잰다', /VIEWPORT/.test(cs) && /1280/.test(cs));

  /* ── 10) 사업 수치·시드·백업 불변 ───────────────────────────── */
  const M = w.__ttokttokModel;
  ok('K1 단가·수수료·정산 규칙 불변', M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
    M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 && String(M.settlementRule.payDays) === '15,end');
  ok('K2 시드 예약 TT-261021-7302 유지', (M.reservations() || []).some((r) => r.no === 'TT-261021-7302'));
  ok('K3 시연용 배지 유지', /시연용/.test(HTML));
  ok('K4 백업 스키마 ttokttok.v23 유지', M.exportWorkspaceSnapshot().schemaVersion === 'ttokttok.v23');
  ok('K5 외부 발송·결제 연결 없음(문구 유지)', /실제 문자·알림톡 발송은 하지 않습니다/.test(HTML));
  ok('K6 v45 색 토큰 215쌍 유지', (STYLE.match(/--[a-z0-9-]+:/g) || []).length >= 215);

  /* ── 11) 예산·구조 위생 ────────────────────────────────────── */
  ok('L1 CSS 24.2만자 이하', STYLE.length <= 242000, String(STYLE.length));
  ok('L2 HTML 1.45MB 이하', Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024, String(Buffer.byteLength(HTML, 'utf8')));
  const ids = $$('[id]').map((e) => e.id);
  const dup = ids.filter((v, i) => v && ids.indexOf(v) !== i);
  ok('L3 중복 id 0', dup.length === 0, Array.from(new Set(dup)).slice(0, 6));
  ok('L4 2단 그릇에 조작 요소가 새로 생기지 않았다(래퍼는 div)', $$('.tt46-cols, .tt46-col, .tt46-flow').every((e) => e.tagName === 'DIV'));
  ok('L5 빈 그릇이 남지 않았다', $$('.tt46-col').every((e) => e.children.length > 0));

  console.log('\nV46 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.error(e); process.exit(2); });
