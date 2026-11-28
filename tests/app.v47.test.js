/*
 * 똑똑쌤 v47 — 목록 키보드 이동 · 스켈레톤 로딩 · 미세 마감 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v47.test.js
 *
 * 이 스위트가 고정하는 것
 *   · 1280px 3칸에서 목록을 ↑/↓·Home/End로 옮겨 다니고 오른쪽 프로필 열이 따라 바뀐다
 *   · Enter는 프로필 열로 초점을 옮기고, Esc는 열을 닫아 고른 카드로 돌아온다
 *   · 스켈레톤은 기본이 꺼짐(지금까지와 동일)이고, 켜면 실제 카드와 같은 수·높이를 먼저 예약한다
 *   · 스켈레톤·빈 자리 안내·가운뎃점 줄바꿈 같은 v47 규칙의 위치(좁은 화면에 새지 않음)
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
      if (o.wide) {
        /* 1280px 데스크톱으로 인식시킨다(jsdom에는 matchMedia가 없다) */
        window.matchMedia = function (q) {
          return {
            media: q, matches: /min-width:1280px/.test(q),
            addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}
          };
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
const V47_AT = STYLE.indexOf('13. v47');
const V47_1280 = mediaBlock('@media(min-width:1280px)', V47_AT) || '';

async function run() {
  /* ── 1) 버전·부팅 ─────────────────────────────────────────────── */
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const $ = (s, r) => (r || doc).querySelector(s);
  const $$ = (s, r) => Array.from((r || doc).querySelectorAll(s));
  ok('A1 meta v47', ($('meta[name="app-version"]') || {}).content === 'v48', ($('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));
  ok('A3 v45 테마 훅 유지', !!w.__ttokttokTheme && w.__ttokttokTheme.version === 'v45');
  ok('A4 v44 탭 스크롤 훅 유지', !!w.__ttokttokTabScroll && w.__ttokttokTabScroll.version === 'v44');
  ok('A5 v47 스켈레톤 훅 노출', !!w.__ttokttokSkeleton && w.__ttokttokSkeleton.version === 'v47', w.__ttokttokSkeleton);
  ok('A6 스켈레톤 기본값은 꺼짐', !!w.__ttokttokSkeleton && w.__ttokttokSkeleton.on === false);
  ok('A7 조작 훅 노출', !!(w.__ttSkeleton && w.__ttSkeleton.set && w.__ttSkeleton.delay && w.__ttSkeleton.render));

  /* ── 2) CSS 규칙의 위치와 값 ─────────────────────────────────── */
  ok('B1 v47 CSS 절이 있다', V47_AT > 0);
  ok('B2 키보드 안내는 기본이 숨김', /\.kbd-hint\{display:none\}/.test(STYLE));
  ok('B3 키보드 안내는 1280부터 보인다', /\.kbd-hint\{display:flex/.test(V47_1280));
  ok('B4 1280 안내는 두 칸을 다 쓴다(목록이 2칸으로 밀리지 않게)', /#teacherMainCol > #teacherKbdHint\{grid-column:1\/-1\}/.test(V47_1280));
  ok('B5 키보드 초점 링은 is-kb일 때만', /body\.is-kb #teacherList \.teacher:focus-visible\{outline:2px solid var\(--blue\)/.test(V47_1280));
  ok('B6 스켈레톤 카드는 높이를 예약한다', /\.teacher\.is-skel\{--tt-skel-h:246px;height:var\(--tt-skel-h\)/.test(STYLE));
  ok('B7 폭별 기본 높이(768 251 · 1024 253 · 1280 197)', /\.teacher\.is-skel\{--tt-skel-h:251px/.test(STYLE) &&
    /\.teacher\.is-skel\{--tt-skel-h:253px/.test(STYLE) && /\.teacher\.is-skel\{--tt-skel-h:197px/.test(STYLE));
  ok('B7b 320 기본 높이 296px', /\.teacher\.is-skel\{--tt-skel-h:296px\}/.test(STYLE));
  ok('B8 스켈레톤 막대·아바타·칩 클래스', /\.sk-bar\{/.test(STYLE) && /\.sk-av\{/.test(STYLE) && /\.sk-chip\{/.test(STYLE));
  ok('B9 동작 줄이기에서 스켈레톤 물결이 멈춘다', /\.tt-skel::after\{animation:none!important\}/.test(STYLE));
  ok('B10 낭독 전용 클래스', /\.sr-only\{position:absolute!important/.test(STYLE));
  ok('B11 선택 카드와 상세 열을 잇는 왼쪽 띠', /#teacherList \.teacher\.is-selected::before\{/.test(STYLE));
  ok('B12 빈 자리 안내는 기본이 숨김', /\.teacher-pane-empty\{display:none\}/.test(STYLE));
  ok('B13 빈 자리 안내는 1280의 2번째 칸', /#teacherMainCol \.teacher-pane-empty\{display:flex;grid-column:2/.test(V47_1280));
  ok('B14 고른 카드가 있으면 빈 자리 안내는 숨는다', /#teacherMainCol\.has-pane \.teacher-pane-empty\{display:none\}/.test(V47_1280));
  ok('B15 v47 규칙은 v46 절 뒤에 있다', V47_AT > STYLE.indexOf('12. v46'));
  ok('B16 1024~1279 카드 보정 규칙', /@media\(min-width:1024px\) and \(max-width:1279px\)\{[\s\S]*#teacherList \.teacher\{padding:14px\}/.test(STYLE));
  ok('B17 지역 줄은 아이콘과 한 줄에 묶인다', /\.t-region\{flex-wrap:nowrap/.test(STYLE) && /\.t-region > span\{flex:1 1 auto/.test(STYLE));

  /* ── 3) 마크업: 안내·낭독 영역·목록·빈 자리 ─────────────────── */
  const hint = $('#teacherKbdHint'), live = $('#teacherNavLive'), list = $('#teacherList');
  ok('C1 키보드 안내가 결과 열 안에 있다', !!hint && !!$('#teacherMainCol') && hint.closest('#teacherMainCol') === $('#teacherMainCol'));
  ok('C2 안내는 목록보다 위에 있다', !!hint && !!list && (hint.compareDocumentPosition(list) & 4) !== 0);
  ok('C3 안내에 ↑↓·Enter·Esc 키 표기', hint && hint.textContent.includes('Enter') && hint.textContent.includes('Esc') && hint.textContent.includes('↑'));
  ok('C4 낭독 영역은 role=status sr-only', live && live.getAttribute('role') === 'status' &&
    live.getAttribute('aria-live') === 'polite' && live.className.includes('sr-only'));
  ok('C5 목록은 키보드 단축키를 알린다', list && list.getAttribute('aria-keyshortcuts') === 'ArrowUp ArrowDown Home End Enter');
  ok('C6 목록은 처음엔 바쁘지 않다', list && list.getAttribute('aria-busy') === 'false');
  ok('C7 빈 자리 안내가 목록 옆에 있다', !!$('#teacherPaneEmpty') && $('#teacherPaneEmpty').getAttribute('aria-hidden') === 'true');
  ok('C8 빈 자리 안내 문구', /프로필이 여기에 열려요/.test($('#teacherPaneEmpty').textContent));
  ok('C9 관리자에 로딩 표시 시연 절', !!$('#adminSkelSec') && !!$('#adminSkelToggle') && !!$('#adminSkelPeek'));
  ok('C10 시연 절은 시연용 배지', /시연용/.test($('#adminSkelSec').textContent));
  ok('C11 토글은 radiogroup·두 칸', $('#adminSkelToggle').getAttribute('role') === 'radiogroup' &&
    $$('#adminSkelToggle [data-skel-opt]').length === 2);
  ok('C12 토글 기본값은 끄기', $('#adminSkelToggle [data-skel-opt="off"]').getAttribute('aria-checked') === 'true' &&
    $('#adminSkelToggle [data-skel-opt="on"]').getAttribute('aria-checked') === 'false');

  /* ── 4) 스켈레톤 동작(켜면 자리를 잡고 채운다) ────────────────── */
  w.__ttSkeleton.delay(90);
  click($('[data-login="customer"]'));
  await sleep(300);
  click($('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(250);
  ok('D1 스켈레톤이 꺼져 있으면 바로 카드', $$('#teacherList .teacher').length === 8 && !$('#teacherList .is-skel'),
    $$('#teacherList .teacher').length);
  /* jsdom은 레이아웃이 없어 카드 높이가 0 — 높이를 알려 주고 예약 방식을 본다 */
  ok('D2 잰 높이가 없으면 기본 높이로 그린다', w.__ttSkeleton.state().height === null, w.__ttSkeleton.state());
  const realH = w.__ttSkeleton.measure(197);
  ok('D2b 높이를 기억한다', realH === 197 && w.__ttSkeleton.state().height === 197, realH);

  ok('D3 토글로 켠다', w.__ttSkeleton.set(true) === true);
  await sleep(60);
  ok('D4 켜면 토글 표시가 바뀐다', $('#adminSkelToggle [data-skel-opt="on"]').getAttribute('aria-checked') === 'true');
  ok('D5 켜짐 안내 문구', /켜져 있어요/.test($('#adminSkelState').textContent));
  w.__ttSkeleton.render();
  await sleep(30);
  const skels = $$('#teacherList .teacher.is-skel');
  ok('D6 목록이 스켈레톤으로 바뀐다(결과 수만큼)', skels.length === 8, skels.length);
  ok('D7 스켈레톤은 누를 수 있는 카드가 아니다', $$('#teacherList [data-teacher]').length === 0);
  ok('D8 스켈레톤 중에는 aria-busy', $('#teacherList').getAttribute('aria-busy') === 'true');
  ok('D9 스켈레톤은 낭독에서 빠진다', skels.every((el) => el.getAttribute('aria-hidden') === 'true'));
  ok('D10 기억한 높이를 예약한다', ($('#teacherList').getAttribute('style') || '').includes('--tt-skel-h: ' + realH + 'px'),
    $('#teacherList').getAttribute('style'));
  ok('D10b 예약한 높이는 카드 한 장의 실제 높이와 같다', realH === 197);
  ok('D11 불러오는 중을 낭독한다', /불러오는 중/.test($('#teacherNavLive').textContent), $('#teacherNavLive').textContent);
  await sleep(180);
  ok('D12 지연 뒤 실제 카드로 채운다', $$('#teacherList .teacher').length === 8 && $$('#teacherList .is-skel').length === 0);
  ok('D13 채운 뒤 aria-busy 해제', $('#teacherList').getAttribute('aria-busy') === 'false');
  ok('D14 첫 카드 이름이 보인다', /박서준/.test($('#teacherList').textContent));

  /* 필터를 바꾸면 그 결과 수만큼 스켈레톤을 그린다 */
  click($('#teacherFilters [data-cat="stroke"]'));
  await sleep(30);
  ok('D15 필터 결과 수만큼 스켈레톤', $$('#teacherList .is-skel').length === 3, $$('#teacherList .is-skel').length);
  await sleep(160);
  ok('D16 필터 뒤 실제 카드 3명', $$('#teacherList .teacher').length === 3, $$('#teacherList .teacher').length);
  click($('#teacherFilters [data-cat="all"]'));
  await sleep(160);

  /* 끄면 곧바로 돌아온다 */
  w.__ttSkeleton.set(false);
  w.__ttSkeleton.render();
  await sleep(20);
  ok('D17 끄면 스켈레톤 없이 바로 카드', $$('#teacherList .teacher').length === 8 && $$('#teacherList .is-skel').length === 0);

  /* ── 5) 키보드 이동 — 좁은 화면(시트) ────────────────────────── */
  const cards = $$('#teacherList .teacher');
  cards[0].focus();
  ok('E1 첫 카드에 초점', doc.activeElement === cards[0]);
  key(cards[0], 'ArrowDown');
  ok('E2 ↓로 다음 카드', doc.activeElement === cards[1], doc.activeElement && doc.activeElement.getAttribute('data-teacher'));
  await sleep(80);
  ok('E3 이동을 낭독(2/8)', /2\/8/.test($('#teacherNavLive').textContent), $('#teacherNavLive').textContent);
  key(cards[1], 'ArrowUp');
  ok('E4 ↑로 앞 카드', doc.activeElement === cards[0]);
  key(cards[0], 'ArrowUp');
  ok('E5 첫 카드에서 ↑는 그대로', doc.activeElement === cards[0]);
  key(cards[0], 'End');
  ok('E6 End는 마지막 카드', doc.activeElement === cards[cards.length - 1]);
  key(cards[cards.length - 1], 'ArrowDown');
  ok('E7 마지막에서 ↓는 그대로', doc.activeElement === cards[cards.length - 1]);
  key(cards[cards.length - 1], 'Home');
  ok('E8 Home은 첫 카드', doc.activeElement === cards[0]);
  key(cards[0], 'Enter');
  await sleep(120);
  ok('E9 Enter로 상세 시트가 열린다(좁은 화면)', $('#teacherSheet').classList.contains('is-open'));
  ok('E10 시트에 그 선생님', /박서준/.test($('#teacherSheetBody').textContent));
  const escEv = key(doc.body, 'Escape');
  await sleep(120);
  ok('E11 Esc로 시트를 닫는다', !$('#teacherSheet').classList.contains('is-open'));
  ok('E12 Esc 기본 동작을 막는다', escEv.defaultPrevented !== false);
  key(cards[1], ' ');
  await sleep(120);
  ok('E13 Space로도 시트가 열린다', $('#teacherSheet').classList.contains('is-open') && /이하늘/.test($('#teacherSheetBody').textContent));
  click($('#teacherSheet [data-sheet-close]'));
  await sleep(120);
  const evCtrl = key(cards[0], 'ArrowDown', { ctrlKey: true });
  ok('E14 Ctrl+↓는 가로채지 않는다', evCtrl.defaultPrevented === false);

  /* ── 6) 키보드 이동 — 1280px 3칸(프로필 열) ─────────────────── */
  const B = makeDom({ wide: true });
  await waitBooted(B.window);
  const bw = B.window, bd = B.doc;
  const b$ = (s) => bd.querySelector(s);
  const b$$ = (s) => Array.from(bd.querySelectorAll(s));
  ok('F1 부팅 오류 0(넓은 화면)', !B.errors.length, B.errors.slice(0, 2));
  bw.__ttSkeleton.set(false, { silent: true });
  click(b$('[data-login="customer"]'));
  await sleep(300);
  click(b$('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(250);
  const bc = b$$('#teacherList .teacher');
  ok('F2 카드 8명', bc.length === 8, bc.length);
  ok('F3 처음에는 상세 열이 닫혀 있다', b$('#teacherPane').hidden === true);
  bc[0].focus();
  key(bc[0], 'ArrowDown');
  await sleep(80);
  ok('F4 ↓로 다음 카드에 초점', bd.activeElement === bc[1]);
  ok('F5 오른쪽 프로필 열이 열린다', b$('#teacherPane').hidden === false);
  ok('F6 열에 그 선생님 프로필', /이하늘/.test(b$('#teacherPane').textContent));
  ok('F7 고른 카드에 aria-current', bc[1].getAttribute('aria-current') === 'true' && !bc[0].hasAttribute('aria-current'));
  ok('F8 빈 자리 안내는 숨는다', b$('#teacherMainCol').classList.contains('has-pane'));
  key(bd.activeElement, 'ArrowDown');
  await sleep(80);
  ok('F9 ↓↓로 3번째 카드·열 갱신', /정민아/.test(b$('#teacherPane').textContent) && bd.activeElement === bc[2]);
  ok('F10 열은 스크롤 위에서 시작', b$('#teacherPane').scrollTop === 0);
  key(bc[2], 'Enter');
  await sleep(120);
  ok('F11 Enter는 프로필 열 안으로 초점을 옮긴다', b$('#teacherPane').contains(bd.activeElement) &&
    bd.activeElement.getAttribute('data-pane-open') !== null);
  ok('F12 시트를 겹쳐 띄우지 않는다', !b$('#teacherSheet').classList.contains('is-open'));
  key(bd.activeElement, 'Escape');
  await sleep(120);
  ok('F13 Esc는 열을 닫는다', b$('#teacherPane').hidden === true);
  ok('F14 Esc는 고른 카드로 초점을 돌린다', bd.activeElement === bc[2]);
  ok('F15 닫으면 빈 자리 안내가 돌아온다', !b$('#teacherMainCol').classList.contains('has-pane'));
  /* 시트가 열려 있으면 Esc는 시트부터 닫는다(열은 그대로) */
  bc[0].focus();
  key(bc[0], 'Enter');
  await sleep(120);
  b$('#teacherSheet').classList.add('is-open');
  key(bd.body, 'Escape');
  await sleep(120);
  ok('F16 다른 시트가 열려 있으면 열은 그대로', b$('#teacherPane').hidden === false && !b$('#teacherSheet').classList.contains('is-open'));
  click(b$('#teacherPane [data-pane-close]'));
  await sleep(80);
  ok('F17 닫기 버튼도 열을 닫는다', b$('#teacherPane').hidden === true);

  /* 넓은 화면 스켈레톤: 프로필 열도 자리를 잡고 채운다 */
  bw.__ttSkeleton.delay(90);
  bw.__ttSkeleton.set(true, { silent: true });
  b$$('#teacherList .teacher')[0].focus();
  key(b$$('#teacherList .teacher')[0], 'Enter');
  await sleep(30);
  ok('F18 프로필 열 스켈레톤', !!b$('#teacherPane .pane-skel') && b$('#teacherPane').getAttribute('aria-busy') === 'true');
  ok('F19 스켈레톤 중에도 열은 열려 있다', b$('#teacherPane').hidden === false);
  await sleep(180);
  ok('F20 지연 뒤 실제 프로필', !b$('#teacherPane .pane-skel') && /박서준/.test(b$('#teacherPane').textContent));
  ok('F21 채운 뒤 aria-busy 해제', b$('#teacherPane').getAttribute('aria-busy') === 'false');

  /* ── 7) 가운뎃점 줄바꿈·카드 텍스트 ─────────────────────────── */
  ok('G1 메타의 가운뎃점은 뒤 어절과 붙는다', /·(\u00A0|&nbsp;)/.test($('#teacherList').innerHTML),
    $('#teacherList .t-meta').innerHTML);
  ok('G2 지역 줄은 span으로 묶여 있다', !!$('#teacherList .t-region > span'));
  ok('G3 카드에 이름·지역·후기', /박서준/.test($('#teacherList').textContent) && /방문/.test($('#teacherList').textContent));

  /* ── 8) 불변 규칙(돈·시드·백업) ─────────────────────────────── */
  const model = w.__ttokttokModel || {};
  ok('H1 단가 90,000원', /90,000/.test(HTML));
  ok('H2 재방문 단가 70,000원', /70,000/.test(HTML));
  ok('H3 수수료 22.2%', /22\.2/.test(HTML));
  ok('H4 정산 D+3·15일/말일', /D\+3/.test(HTML) && /15일/.test(HTML));
  ok('H5 시드 예약번호', /TT-261021-7302/.test(HTML));
  ok('H6 시연용 배지', /시연용/.test(HTML));
  ok('H7 백업 스키마 ttokttok.v23', /ttokttok\.v23/.test(HTML));
  ok('H8 Supabase·결제 연결 없음', !/supabase\.co|js\.stripe\.com|iamport/i.test(HTML));

  /* ── 9) 중복 id 0 ───────────────────────────────────────────── */
  const ids = $$('[id]').map((el) => el.id);
  const dup = ids.filter((id, i) => ids.indexOf(id) !== i);
  ok('I1 중복 id 0', dup.length === 0, dup.slice(0, 5));

  console.log('\nRESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
    process.exit(1);
  }
}

run().catch((e) => { console.error(e); process.exit(2); });
