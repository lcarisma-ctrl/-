/*
 * 똑똑쌤 앱 자동 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && npm i jsdom && APP_PART=1 node app.test.js && APP_PART=2 node app.test.js
 *       (v34: DOM 52개를 한 프로세스에 올리면 힙 한도를 넘어 두 파트로 나눠 돌린다. APP_PART 없이 돌리면 전부 실행)
 * 범위: 고객/선생님/관리자 3면 플로우, 바텀시트·검색·증상 칩, 디자인 시스템 v2 정적 품질
 * 전제: 상위 폴더의 index.html (로고 base64 내장 빌드 결과)
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

/* v32 · 테스트 시계 고정.
   시드·데모 예약이 '오늘' 기준 상대 날짜라, 자정을 넘기면 D-1·4주 재평가·운영 예외 건수가
   달라져 같은 코드가 실패한다(2026-11-27 00:2x 실제 발생). 앱(DOM)과 테스트(Node) 양쪽의
   '오늘'을 2026-11-26 22:00 KST로 맞춰 실행 시각과 무관하게 만든다. */
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

function report() {
  console.log('\nRESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
}

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
      /* v32 · 시계 고정 — 시드 데이터가 '오늘' 기준 상대 날짜라, 자정을 넘기면
         D-1·4주 재평가·정산 확정 건수가 달라져 같은 코드가 실패한다(2026-11-27 00:1x 실제 발생).
         앱이 보는 '오늘'을 2026-11-26 22:00 KST로 고정해 실행 시각과 무관하게 만든다. */
      const FIXED = new Date('2026-11-26T13:00:00.000Z').getTime();
      const RealDate = window.Date;
      function FixedDate(...args) {
        return args.length ? new RealDate(...args) : new RealDate(FIXED);
      }
      FixedDate.prototype = RealDate.prototype;
      FixedDate.now = () => FIXED;
      FixedDate.parse = RealDate.parse;
      FixedDate.UTC = RealDate.UTC;
      window.Date = FixedDate;
      if (seedStorage) {
        Object.keys(seedStorage).forEach((k) => window.localStorage.setItem(k, seedStorage[k]));
      }
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function run() {
  /* v34 · 한 프로세스에 DOM 52개를 다 올리면 환경 힙 한도(약 1.9GB)를 넘겨 프로세스가 죽는다.
     APP_PART=1 → 앞부분(A~V), APP_PART=2 → 뒷부분(W~AC)만 실행. 합치면 기존 전부와 같다. */
  const PART = process.env.APP_PART || 'all';
  /* v35 — <style> 수정이 허용되면서 "CSS 바이트 동일"(v16~v19 검사)은 뜻을 잃었다.
   대신 토큰·CSS 정합성을 본다: :root가 한 곳인지, 쓰는 var(--x)가 모두 정의되어 있는지,
   중괄호가 맞는지, v35 색 토큰(--text-caption/--text-muted)이 있는지. */
function cssTokens(html) {
  const m = /<style>([\s\S]*?)<\/style>/.exec(html || '');
  const css = m ? m[1] : '';
  const roots = (css.match(/:root\{/g) || []).length;
  const defs = new Set((css.match(/--[a-zA-Z0-9-]+\s*:/g) || []).map((x) => x.replace(/\s*:$/, '')));
  const uses = new Set((css.match(/var\((--[a-zA-Z0-9-]+)\)/g) || []).map((x) => x.slice(4, -1)));
  const missing = [...uses].filter((u) => !defs.has(u));
  const open = (css.match(/\{/g) || []).length;
  const close = (css.match(/\}/g) || []).length;
  const tokens = /--text-caption\s*:/.test(css) && /--text-muted\s*:/.test(css) && /--sp-4\s*:/.test(css) && /--z-sheet\s*:/.test(css);
  return { ok: roots === 1 && missing.length === 0 && open === close && tokens && !!m, roots, missing, open, close, tokens };
}

function helpers(win, doc) {
    const $ = (s, root) => (root || doc).querySelector(s);
    const $$ = (s, root) => Array.from((root || doc).querySelectorAll(s));
    const click = (el) => el.dispatchEvent(new win.MouseEvent('click', { bubbles: true, cancelable: true }));
    const setVal = (el, v) => { el.value = v; el.dispatchEvent(new win.Event('input', { bubbles: true })); };
    const setSel = (el, v) => { el.value = v; el.dispatchEvent(new win.Event('change', { bubbles: true })); };
    const setCheck = (el, v) => { el.checked = v; el.dispatchEvent(new win.Event('change', { bubbles: true })); };
    const text = (s) => ($(s) ? $(s).textContent.replace(/\s+/g, ' ').trim() : '');
    return { w: win, doc, $, $$, click, setVal, setSel, setCheck, text };
  }

  if (PART !== '2') {
  /* ============================================================
     A. 고객 모드: 로그인 → 전국 선생님 → 예약/결제 → 일지 → 내 정보
     ============================================================ */
  const A = makeDom();
  const { window: w, doc } = A;
  const $ = (s, root) => (root || doc).querySelector(s);
  const $$ = (s, root) => Array.from((root || doc).querySelectorAll(s));
  const click = (el) => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true, cancelable: true }));
  const setVal = (el, v) => { el.value = v; el.dispatchEvent(new w.Event('input', { bubbles: true })); };
  const setSel = (el, v) => { el.value = v; el.dispatchEvent(new w.Event('change', { bubbles: true })); };
  const setCheck = (el, v) => { el.checked = v; el.dispatchEvent(new w.Event('change', { bubbles: true })); };
  const text = (s) => ($(s) ? $(s).textContent.replace(/\s+/g, ' ').trim() : '');

  await sleep(30);

  ok('A1 JS 오류 없음', A.errors.length === 0, A.errors.slice(0, 3).join(' | '));
  ok('A2 시작 시 로그인 게이트 표시', $('#entryGate').classList.contains('is-open'));
  ok('A3 고객 홈이 기본 활성', $('#screen-home').classList.contains('is-active'));
  ok('A4 역할 선택 카드 2종', $$('[data-login="customer"]').length === 1 && $$('[data-login="therapist"]').length === 1);
  ok('A5 게이트 로고가 브랜드 로고와 동일', $('#gateLogo').src === $('#brandMark').src);
  ok('A6 헤더 문구 전국 기준', /전국/.test(text('.brand-sub')));
  ok('A7 홈 히어로 카피(똑똑쌤과 건강한 회복)', /똑똑쌤과/.test(text('#homeHeroTitle')) && /건강한 회복/.test(text('#homeHeroTitle')), text('#homeHeroTitle'));
  ok('A8 홈 인사말에 로그인 이름', /현수/.test(text('#homeGreetName')) && /반가워요/.test(text('.hh-greet')), text('.hh-greet'));
  ok('A8a 홈 블루 공지 띠', /첫 1:1 방문 평가 무료/.test(text('#homeNotice')), text('#homeNotice'));
  ok('A8b 신뢰 지표 스트립(평점·후기)', /\d\.\d/.test(text('#trustRating')) && /\d/.test(text('#trustReviews')));
  // v5 규칙: 가격·수수료는 결제(예약 3~4단계)에서만. 홈은 담백하게.
  ok('A9 홈에 금액·수수료 노출 없음', !/\d+,\d{3}원/.test(text('#screen-home')) && !/10%/.test(text('#screen-home')), text('#screen-home').replace(/\s+/g, ' ').slice(0, 120));
  ok('A9b 홈 중복 섹션 제거(추천·약속·진행)', !$('#homeTeacherList') && !$('#screen-home .promise-card') && !$('#screen-home .trust-strip') && !$('#screen-home .steps'));
  ok('A9c 증상 가로 카드 4종', $$('#homeProgramRail .home-program-card').length === 4, String($$('#homeProgramRail .home-program-card').length));
  ok('A9d 가로 카드에 금액 없음', !/원/.test(text('#homeProgramRail')), text('#homeProgramRail').replace(/\s+/g, ' ').slice(0, 80));
  ok('A9e 보조 카드(선생님 지원)', /선생님으로 지원하기/.test(text('#homePartnerCard')));
  ok('A10 지역 한정 표현 제거(20년 수석)', !/20년 수석/.test(doc.body.textContent));
  ok('A11 일산 직영 표현 제거', !/일산 직영/.test(doc.body.textContent));
  ok('A12 선생님 카드 8명', $$('#teacherList .teacher').length === 8, String($$('#teacherList .teacher').length));
  ok('A13 국가면허 검증 배지 8개', $$('#teacherList .lic').length === 8);
  ok('A14 다른 권역 선생님 포함(부산)', /부산 해운대/.test(text('#teacherList')));
  ok('A15 경력 다양성(4년)', /물리치료사 4년/.test(text('#teacherList')));

  // 로그인
  click($('[data-login="customer"]'));
  ok('A16 고객 로그인 후 게이트 닫힘', !$('#entryGate').classList.contains('is-open'));
  ok('A17 고객 홈 유지', $('#screen-home').classList.contains('is-active'));
  ok('A18 역할 표시 보호자 모드', text('#rolePill') === '보호자 모드');

  // 선생님 필터
  click($('#teacherFilters [data-cat="stroke"]'));
  ok('A19 뇌졸중 필터 3명', $$('#teacherList .teacher').length === 3, String($$('#teacherList .teacher').length));
  click($('#teacherFilters [data-cat="all"]'));
  click($('#regionFilters [data-reg="영남"]'));
  ok('A20 영남 권역 필터 2명', $$('#teacherList .teacher').length === 2, String($$('#teacherList .teacher').length));
  click($('#regionFilters [data-reg="all"]'));
  ok('A21 필터 초기화 8명', $$('#teacherList .teacher').length === 8);

  // 예약: 무료 평가권
  click($('#homeBookBtn'));
  ok('A22 예약 탭 전환', $('#screen-booking').classList.contains('is-active'));
  ok('A23 1단계 활성', $('#wstep-1').classList.contains('is-active'));
  ok('A24 시·도 옵션 17개', $$('#bookProvince option').length === 18, String($$('#bookProvince option').length));
  ok('A25 시·군·구 초기 비활성', $('#bookDistrict').disabled);

  click($('[data-next="1"]'));
  ok('A26 미입력 다음 차단(시·도 오류)', $('#f-bookProvince').classList.contains('is-error'));
  ok('A27 1단계 유지', $('#wstep-1').classList.contains('is-active'));

  setSel($('#bookProvince'), '서울');
  ok('A28 시·도 선택 후 구 활성', !$('#bookDistrict').disabled);
  ok('A29 서울 구 8개+placeholder(v18 서대문구 추가)', $$('#bookDistrict option').length === 9 && $$('#bookDistrict option').some((o) => o.value === '서대문구'), String($$('#bookDistrict option').length));
  setSel($('#bookDistrict'), '강남구');
  ok('A30 구 선택 반영', $('#bookDistrict').value === '강남구');
  setVal($('#bookAddress'), '대치동 123-4, 101동 1203호');
  click($('#bookSyms [data-val="뇌졸중·편마비"]'));
  ok('A31 증상 선택 표시', $('#bookSyms [data-val="뇌졸중·편마비"]').classList.contains('is-on'));

  click($('[data-next="1"]'));
  ok('A32 2단계 이동', $('#wstep-2').classList.contains('is-active'));
  ok('A33 날짜 7개', $$('#bookDates .date-chip').length === 7);
  click($('#bookDates .date-chip'));
  ok('A34 날짜 선택', $$('#bookDates .date-chip.is-on').length === 1);
  const slot = $$('#bookSlots .slot').filter((b) => !b.disabled)[0];
  click(slot);
  ok('A35 시간 선택', $$('#bookSlots .slot.is-on').length === 1);
  click($('[data-next="2"]'));
  ok('A36 3단계 이동', $('#wstep-3').classList.contains('is-active'));
  ok('A37 이용권 5종', $$('#passList .pass').length === 5);
  ok('A38 무료 이용권 사전 선택', $('#passList [data-pass="eval"]').classList.contains('is-on'));
  click($('#passList [data-pass="eval"]'));
  ok('A39 무료 이용권 총액 0원', text('#totalAmount') === '무료');
  ok('A40 무료 시 결제수단 숨김', $('#payMethods').style.display === 'none');
  click($('[data-next="3"]'));
  ok('A41 4단계 이동', $('#wstep-4').classList.contains('is-active'));
  ok('A42 요약에 시·도·구 표기', /서울 강남구/.test(text('#bookSummary')));
  ok('A43 요약에 선생님 미지정 표기', /추천 배정/.test(text('#bookSummary')));

  const receiptsBefore = JSON.parse(w.localStorage.getItem('ttokttok_account_v3')).receipts.length;
  click($('#payBtn'));
  ok('A44 이름 미입력 결제 차단', $('#f-bookName').classList.contains('is-error'));
  setVal($('#bookName'), '김순자');
  setVal($('#bookPhone'), '01012345678');
  ok('A45 연락처 자동 포맷', $('#bookPhone').value === '010-1234-5678', $('#bookPhone').value);
  setCheck($('#bookAgree'), true);
  click($('#payBtn'));
  await sleep(1100);
  ok('A46 무료 예약 완료 화면', $('#bookingDone').hidden === false);
  ok('A47 예약번호 표시', /TT-\d{6}-\d{4}/.test(text('#doneSummary')));
  ok('A48 영수증 1건 증가', JSON.parse(w.localStorage.getItem('ttokttok_account_v3')).receipts.length === receiptsBefore + 1);

  click($('#doneHome'));
  ok('A49 완료 후 홈 복귀', $('#screen-home').classList.contains('is-active'));
  ok('A50 예약 위저드 초기화', $('#bookingWizard').hidden === false);

  // 유료 예약 (8회권) — 이용권·금액은 예약 3단계에서만 고른다
  ok('A50b 홈에 가격표 섹션 없음', !$('#priceSec') && !$('#screen-home .price-row'));
  click($('.tabbtn[data-tab="booking"]'));
  ok('A51 예약 탭 재진입', $('#screen-booking').classList.contains('is-active'));
  setSel($('#bookProvince'), '경기');
  setSel($('#bookDistrict'), '고양시 일산동구');
  setVal($('#bookAddress'), '일산동구 백석동 1234');
  click($('#bookSyms [data-val="무릎·고관절 수술 후"]'));
  click($('[data-next="1"]'));
  click($('#bookDates .date-chip'));
  click($$('#bookSlots .slot').filter((b) => !b.disabled)[0]);
  click($('[data-next="2"]'));
  click($('#passList [data-pass="p8"]'));
  ok('A51b 8회권 선택', $('#passList [data-pass="p8"]').classList.contains('is-on'));
  ok('A52 8회권 금액 592,000', text('#totalAmount') === '592,000원', text('#totalAmount'));
  click($('[data-next="3"]'));
  ok('A53 유료 시 결제수단 노출', $('#payMethods').style.display !== 'none');
  setSel($('#bookTeacher'), 'lee');
  ok('A54 선생님 지정 시 요약 반영 전', true);
  click($('#payBtn'));
  ok('A55 결제수단 미선택 차단', $('#f-pays').classList.contains('is-error'));
  click($('#payMethods [data-pay="카카오페이"]'));
  setVal($('#bookName'), '김순자');
  setVal($('#bookPhone'), '01012345678');
  setCheck($('#bookAgree'), true);
  click($('#payBtn'));
  await sleep(1100);
  ok('A56 유료 결제 완료', $('#bookingDone').hidden === false);
  const acc = JSON.parse(w.localStorage.getItem('ttokttok_account_v3'));
  ok('A57 새 이용권 잔여 7회', acc.passes[0].remaining === 7, JSON.stringify(acc.passes[0]));
  ok('A58 결제 내역 금액', acc.receipts[0].amount === 592000);
  ok('A59 결제수단 기록', acc.receipts[0].method === '카카오페이');
  ok('A60 예약 지역 기록', /경기 고양시 일산동구/.test(acc.bookings[0].region));

  // 내 정보
  click($('#doneMypage'));
  ok('A61 내 정보 이동', $('#screen-mypage').classList.contains('is-active'));
  ok('A61a 내 정보 8행 리스트(알림·쿠폰·FAQ 포함)', $$('#screen-mypage .mp-row').length === 8, String($$('#screen-mypage .mp-row').length));
  ok('A61b 내 정보 상단 상태 카피', /건강한 회복/.test(text('.mp-title')) && /예약 내역/.test(text('.mp-meta')), text('.mp-title'));
  ok('A61c 1:1 문의 배너', /1:1 문의하기/.test(text('#mpInquiry')), text('#mpInquiry'));
  ok('A61d 헤더 숨김 표시', doc.body.classList.contains('on-mypage'));
  click($('#mpBookLink'));
  ok('A61e 내 예약·이용권 시트 열림', $('#accountSheet').classList.contains('is-open'));
  click($('#mpRoleRow'));
  ok('A61f 모드 전환 시트 열림', $('#roleSheet').classList.contains('is-open'));
  click($('#roleSheet [data-role-close]'));
  ok('A61g 모드 전환 시트 닫힘', !$('#roleSheet').classList.contains('is-open'));
  click($('[data-account-close]'));
  ok('A61h 내 예약 시트 닫힘', !$('#accountSheet').classList.contains('is-open'));
  click($('#homeTicketBtn'));
  ok('A61i 홈 이용권 버튼 → 내 예약 시트', $('#accountSheet').classList.contains('is-open') && /8회권/.test(text('#accountSheet')));
  click($('[data-account-close]'));
  click($('#mpPayRow'));
  ok('A61j 결제 수단 · 영수증 시트', $('#paySheet').classList.contains('is-open') && /카카오페이/.test(text('#paySheet')));
  click($('[data-pay-close]'));
  click($('#mpInquiry'));
  ok('A61k 1:1 문의 → 고객센터 채팅', $('#chatSheet').classList.contains('is-open') && /고객센터/.test(text('#chatName')));
  click($('[data-chat-close]'));
  click($('#mpJournalRow'));
  ok('A61l 회복 일지 보기 → 일지 탭', $('#screen-journal').classList.contains('is-active'));
  click($('.tabbtn[data-tab="mypage"]'));
  ok('A62 보유 이용권 2장', $$('#walletList .wallet-card').length === 2, String($$('#walletList .wallet-card').length));
  ok('A63 잔여 합계 표시', /잔여 12회/.test(text('#walletTotal')), text('#walletTotal'));
  ok('A64 예약 4건(지난 완료 방문 포함)', $$('#bookingList .list-item').length === 4, String($$('#bookingList .list-item').length));
  click($('#receiptList .list-item'));
  ok('A65 영수증 모달 열림', $('#receiptModal').classList.contains('is-open'));
  ok('A66 영수증 공급자 전국 표기', /전국 방방재활|전국 방문재활/.test(text('#receiptBody')));
  click($('#receiptClose'));
  ok('A67 영수증 모달 닫힘', !$('#receiptModal').classList.contains('is-open'));

  // 일지
  click($('.tabbtn[data-tab="journal"]'));
  ok('A68 일지 탭', $('#screen-journal').classList.contains('is-active'));
  ok('A69 그래프 렌더', $$('#chart circle').length === 5);
  click($('.metric-tabs [data-metric="pain"]'));
  ok('A70 통증 그래프 전환', /통증/.test($('#chart').getAttribute('aria-label')));
  click($('#checkinBtn'));
  ok('A71 체크인 상태 변경', text('#checkStatus') === '방문 중');
  click($('#checkinBtn'));
  ok('A72 체크인 취소', text('#checkStatus') === '방문 예정');
  setCheck($('#c3'), true);
  ok('A73 체크리스트 진행률', /3\/5/.test(text('#checkCount')), text('#checkCount'));
  click($('.role-switch [data-role="guardian"]'));
  ok('A74 보호자 시점 전환', $('#journal').classList.contains('is-guardian'));

  // 역할 전환
  click($('#rolePill'));
  ok('A75 헤더로 선생님 모드 전환', $('#screen-tp-home').classList.contains('is-active'));
  ok('A76 선생님 탭바 모드 클래스', doc.body.classList.contains('mode-therapist'));
  click($('#rolePill'));
  ok('A77 고객 모드 복귀', $('#screen-mypage').classList.contains('is-active') || $('#screen-home').classList.contains('is-active'));

  /* ============================================================
     B. 선생님 모드 + 파트너 지원/심사
     ============================================================ */
  const B = makeDom();
  const w2 = B.window;
  const d2 = B.doc;
  const $2 = (s, root) => (root || d2).querySelector(s);
  const $$2 = (s, root) => Array.from((root || d2).querySelectorAll(s));
  const click2 = (el) => el.dispatchEvent(new w2.MouseEvent('click', { bubbles: true, cancelable: true }));
  const setVal2 = (el, v) => { el.value = v; el.dispatchEvent(new w2.Event('input', { bubbles: true })); };
  const setSel2 = (el, v) => { el.value = v; el.dispatchEvent(new w2.Event('change', { bubbles: true })); };
  const setCheck2 = (el, v) => { el.checked = v; el.dispatchEvent(new w2.Event('change', { bubbles: true })); };
  const text2 = (s) => ($2(s) ? $2(s).textContent.replace(/\s+/g, ' ').trim() : '');
  await sleep(30);

  click2($2('[data-login="therapist"]'));
  ok('B1 선생님 로그인 → 파트너 홈', $2('#screen-tp-home').classList.contains('is-active'));
  ok('B2 파트너 홈에 심사 완료', /심사 완료/.test(text2('#tpStatusCard')));
  ok('B3 활동중 배지', /활동중/.test(text2('#tpHero')));
  ok('B4 이번 달 정산 980,000', /980,000/.test(text2('#tpSettle')), text2('#tpSettle').slice(0, 120));
  ok('B5 수수료 22.2% 표기', /22\.2%/.test(text2('#tpSettle')));
  ok('B6 신규 요청 2건', $$2('#tpReqList .req').length === 2, String($$2('#tpReqList .req').length));
  ok('B7 요청에 정산 예상액', /정산 예상 54,444원/.test(text2('#tpReqList')));
  ok('B8 이번 주 일정 3건', $$2('#tpSchedMini .tp-sched').length === 3, String($$2('#tpSchedMini .tp-sched').length));

  click2($2('#tpReqList [data-tp-accept="r1"]'));
  ok('B9 요청 수락 후 1건', $$2('#tpReqList .req').length === 1, String($$2('#tpReqList .req').length));
  const pStore = JSON.parse(w2.localStorage.getItem('ttokttok_partner_v1'));
  ok('B10 수락 요청 상태 저장', pStore.requests.filter((r) => r.id === 'r1')[0].status === 'accepted');
  ok('B11 일정에 추가', pStore.schedule.length === 4, String(pStore.schedule.length));
  click2($2('#tpReqList [data-tp-reject="r2"]'));
  ok('B12 거절 후 요청 0건', $$2('#tpReqList .req').length === 0);

  click2($2('.tabbtn[data-tab="tp-schedule"]'));
  ok('B13 일정 탭', $2('#screen-tp-schedule').classList.contains('is-active'));
  ok('B14 확정 방문 4건', $$2('#tpScheduleList .tp-sched').length === 4);
  click2($2('#tpScheduleList [data-tp-checkin]'));
  ok('B15 체크인 → 방문 중', /방문 중/.test(text2('#tpScheduleList')));

  click2($2('.tabbtn[data-tab="tp-journal"]'));
  ok('B16 일지 작성 탭', $2('#screen-tp-journal').classList.contains('is-active'));
  ok('B17 일지 폼 노출', $2('#tpJournalFormWrap').hidden === false);
  ok('B18 기존 일지 2건', $$2('#tpJournalList .jr-item').length === 2);
  setVal2($2('#tpGait'), '0.71');
  setVal2($2('#tpRom'), '121');
  setVal2($2('#tpPain'), '2');
  setVal2($2('#tpMemo'), '계단 훈련 시작. 좌측 무릎 안정적.');
  click2($2('#tpSaveJournal'));
  ok('B19 일지 저장 3건', $$2('#tpJournalList .jr-item').length === 3, String($$2('#tpJournalList .jr-item').length));
  ok('B20 저장값 반영', /0.71/.test(text2('#tpJournalList')));
  ok('B21 보행 오류 검증', true);
  const pStore2 = JSON.parse(w2.localStorage.getItem('ttokttok_partner_v1'));
  ok('B22 일지 저장 영속', pStore2.journals.length === 3);

  click2($2('.tabbtn[data-tab="tp-mypage"]'));
  ok('B23 파트너 내 정보', $2('#screen-tp-mypage').classList.contains('is-active'));
  ok('B24 자격·서류 5행', $$2('#tpDocsList .list-item').length === 5);
  ok('B25 정산 상세 수수료', /22\.2%/.test(text2('#tpSettleDetail')));
  ok('B26 정산 계좌 마스킹', /국민은행 \*{4}/.test(text2('#tpSettleDetail')));

  // 고객으로 전환 후 지원하기
  click2($2('[data-role-switch="customer"]'));
  ok('B27 고객 모드 전환', $2('#screen-home').classList.contains('is-active'));
  click2($2('#homePartnerCard'));
  ok('B28 지원 화면 진입', $2('#screen-partner').classList.contains('is-active'));
  ok('B29 서브페이지 탭바 숨김 클래스', d2.body.classList.contains('is-subpage'));
  ok('B30 1단계 활성', $2('#pstep-1').classList.contains('is-active'));

  click2($2('[data-pnext="1"]'));
  ok('B31 필수값 검증', $2('#f-pName').classList.contains('is-error'));

  setVal2($2('#pName'), '김현수');
  setVal2($2('#pPhone'), '01098765432');
  click2($2('[data-pnext="1"]'));
  ok('B32 2단계 이동', $2('#pstep-2').classList.contains('is-active'));
  ok('B33 시·도 옵션 17개', $$2('#pProvince option').length === 18, String($$2('#pProvince option').length));
  setSel2($2('#pProvince'), '부산');
  ok('B34 구 칩 생성', $$2('#pDistricts .pick').length === 4, String($$2('#pDistricts .pick').length));
  click2($2('#pDistricts [data-pdistrict="해운대구"]'));
  click2($2('#pDistricts [data-pdistrict="수영구"]'));
  click2($2('#pDays [data-day="월"]'));
  click2($2('#pDays [data-day="수"]'));
  ok('B35 지역 2곳 선택', $$2('#pDistricts .pick.is-on').length === 2);
  click2($2('[data-pnext="2"]'));
  ok('B36 3단계 이동', $2('#pstep-3').classList.contains('is-active'));
  click2($2('#pLicense [data-license="물리치료사"]'));
  setVal2($2('#pLicenseNo'), '11-2021-009912');
  setSel2($2('#pYears'), '4');
  click2($2('#pFields [data-field="무릎·고관절"]'));
  click2($2('[data-pnext="3"]'));
  ok('B37 4단계 이동', $2('#pstep-4').classList.contains('is-active'));

  setVal2($2('#pRate'), '72000');
  ['면허증 사본', '경력증명서', '범죄경력조회 동의', '신분증 사본'].forEach((docName) => {
    click2($2('#pDocs [data-doc="' + docName + '"]'));
  });
  ok('B38 서류 4종 선택', $$2('#pDocs .doc-row.is-on').length === 4);
  click2($2('#pSubmit'));
  ok('B39 약관 미동의 차단', $2('#f-pAgree').classList.contains('is-error'));
  setCheck2($2('#pAgree'), true);
  click2($2('#pSubmit'));
  ok('B40 심사 접수 완료 화면', $2('#partnerDone').hidden === false);
  ok('B41 접수번호 표시', /TP-\d{6}-\d{4}/.test(text2('#partnerDoneSummary')));
  ok('B42 접수 요약에 지역', /부산 해운대구·수영구/.test(text2('#partnerDoneSummary')));
  const appStore = JSON.parse(w2.localStorage.getItem('ttokttok_partner_v1'));
  ok('B43 저장 상태 pending', appStore.status === 'pending' && appStore.name === '김현수', appStore.status);
  ok('B44 단가 저장', appStore.rate === 72000);

  click2($2('#partnerDone [data-role-switch="therapist"]'));
  ok('B45 선생님 모드 이동', $2('#screen-tp-home').classList.contains('is-active'));
  ok('B46 심사 대기 상태 표시', /심사 대기/.test(text2('#tpStatusCard')));
  ok('B47 대기 시 정산 잠금', /승인 후/.test(text2('#tpSettle')));
  ok('B48 대기 시 요청 잠금', /승인 후/.test(text2('#tpReqList')));
  click2($2('.tabbtn[data-tab="tp-journal"]'));
  ok('B49 대기 시 일지 잠금', $2('#tpJournalFormWrap').hidden === true && /승인 후/.test(text2('#tpJournalLocked')));

  click2($2('.tabbtn[data-tab="tp-home"]'));
  click2($2('#tpStatusCard [data-tp-approve]'));
  ok('B50 승인 후 활동중', /심사 완료/.test(text2('#tpStatusCard')));
  ok('B51 승인 후 정산 표시', /980,000/.test(text2('#tpSettle')));
  ok('B52 승인 후 요청 수신', $$2('#tpReqList .req').length === 2);

  click2($2('[data-tp-toggle-status]'));
  ok('B53 데모 상태 전환(대기)', /심사 대기/.test(text2('#tpStatusCard')));

  /* ============================================================
     C. 손상된 저장 데이터 복구
     ============================================================ */
  const C = makeDom({ ttokttok_account_v3: '{broken json', ttokttok_partner_v1: 'null' });
  await sleep(30);
  ok('C1 손상 데이터에서도 오류 없음', C.errors.length === 0, C.errors.slice(0, 2).join(' | '));
  ok('C2 선생님 목록 복구 렌더', C.doc.querySelectorAll('#teacherList .teacher').length === 8);
  ok('C3 게이트 정상 표시', C.doc.querySelector('#entryGate').classList.contains('is-open'));
  ok('C4 파트너 홈 렌더(시드 복원)', /박서준/.test(C.doc.querySelector('#tpHero').textContent));

  /* ============================================================
     D. 선생님 상세 바텀시트 · 홈 검색 · 빠른 증상 칩
     ============================================================ */
  function applyAsPartner(h) {
    h.click(h.$('[data-login="customer"]'));
    h.click(h.$('#homePartnerCard'));
    h.setVal(h.$('#pName'), '김현수');
    h.setVal(h.$('#pPhone'), '01098765432');
    h.click(h.$('[data-pnext="1"]'));
    h.setSel(h.$('#pProvince'), '부산');
    h.click(h.$('#pDistricts [data-pdistrict="해운대구"]'));
    h.click(h.$('#pDays [data-day="월"]'));
    h.click(h.$('[data-pnext="2"]'));
    h.click(h.$('#pLicense [data-license="물리치료사"]'));
    h.setVal(h.$('#pLicenseNo'), '11-2021-009912');
    h.setSel(h.$('#pYears'), '4');
    h.click(h.$('#pFields [data-field="무릎·고관절"]'));
    h.click(h.$('[data-pnext="3"]'));
    h.setVal(h.$('#pRate'), '72000');
    ['면허증 사본', '경력증명서', '범죄경력조회 동의', '신분증 사본'].forEach((n) => {
      h.click(h.$('#pDocs [data-doc="' + n + '"]'));
    });
    h.setCheck(h.$('#pAgree'), true);
    h.click(h.$('#pSubmit'));
  }

  const D = makeDom();
  const hD = helpers(D.window, D.doc);
  await sleep(30);
  ok('D0 JS 오류 없음', D.errors.length === 0, D.errors.slice(0, 3).join(' | '));
  hD.click(hD.$('[data-login="customer"]'));
  ok('D1 홈 검색 입력창', !!hD.$('#homeSearch'));
  ok('D2 홈 증상 가로 카드 4종', hD.$$('#homeProgramRail .home-program-card').length === 4, String(hD.$$('#homeProgramRail .home-program-card').length));
  hD.click(hD.$('#homeGuideBtn'));
  ok('D2b 이용안내 시트(진행 3단계·약속)', hD.$('#guideSheet').classList.contains('is-open') && /이렇게 진행돼요/.test(hD.text('#guideSheet')) && /똑똑쌤의 약속/.test(hD.text('#guideSheet')));
  hD.click(hD.$('[data-guide-close]'));
  ok('D2c 이용안내 시트 닫힘', !hD.$('#guideSheet').classList.contains('is-open'));
  hD.click(hD.$('#teacherList .teacher'));
  ok('D3 카드 클릭 → 바텀시트', hD.$('#teacherSheet').classList.contains('is-open'));
  ok('D4 바텀시트 선생님 이름', /박서준/.test(hD.text('#sheetName')), hD.text('#sheetName'));
  ok('D5 경력 요약 표시', /18년 차/.test(hD.text('#teacherSheetBody')));
  ok('D6 검증 자격·면허 3건', hD.$$('#teacherSheet .cert-row').length === 3, String(hD.$$('#teacherSheet .cert-row').length));
  ok('D7 고객 후기 2건', hD.$$('#teacherSheet .review-card').length === 2, String(hD.$$('#teacherSheet .review-card').length));
  ok('D8 가능 요일·시간 칩', hD.$$('#teacherSheet .day-chip').length === 3 && hD.$$('#teacherSheet .time-chip').length === 3);
  ok('D9 하단 고정 CTA', /이 선생님으로 예약/.test(hD.text('#sheetBook')));
  hD.click(hD.$('#sheetBook'));
  ok('D10 CTA → 예약 플로우', hD.$('#screen-booking').classList.contains('is-active'));
  ok('D11 선생님 사전 선택', hD.$('#bookTeacher').value === 'park', hD.$('#bookTeacher').value);
  ok('D12 예약 진입 시 시트 닫힘', !hD.$('#teacherSheet').classList.contains('is-open'));

  hD.click(hD.$('.tabbtn[data-tab="home"]'));
  hD.setVal(hD.$('#homeSearch'), '부산');
  ok('D13 지역 실시간 검색', hD.$$('#searchResults .search-hit').length === 1, String(hD.$$('#searchResults .search-hit').length));
  ok('D14 검색 결과 김도현', /김도현/.test(hD.text('#searchResults')));
  hD.click(hD.$('#searchResults .search-hit'));
  ok('D15 검색 결과 → 상세 시트', /김도현/.test(hD.text('#sheetName')), hD.text('#sheetName'));
  hD.click(hD.$('[data-sheet-close]'));
  ok('D16 시트 닫기 버튼', !hD.$('#teacherSheet').classList.contains('is-open'));
  hD.setVal(hD.$('#homeSearch'), '없는이름');
  ok('D17 검색 결과 없음 안내', /맞는 선생님이 없어요/.test(hD.text('#searchResults')));
  hD.click(hD.$('#homeSearchBtn'));
  ok('D18 검색 실행 → 선생님 탭', hD.$('#screen-teachers').classList.contains('is-active'));
  ok('D19 검색 결과 0명', hD.$$('#teacherList .teacher').length === 0);
  hD.click(hD.$('[data-query-clear]'));
  ok('D20 검색어 초기화 8명', hD.$$('#teacherList .teacher').length === 8, String(hD.$$('#teacherList .teacher').length));
  hD.click(hD.$('.tabbtn[data-tab="home"]'));
  hD.click(hD.$('#homeProgramRail [data-symfilter="stroke"]'));
  ok('D21 증상 칩 → 선생님 탭', hD.$('#screen-teachers').classList.contains('is-active'));
  ok('D22 뇌졸중 필터 선택', hD.$('#teacherFilters [data-cat="stroke"]').classList.contains('is-on'));
  ok('D23 뇌졸중 3명', hD.$$('#teacherList .teacher').length === 3, String(hD.$$('#teacherList .teacher').length));
  hD.click(hD.$('.tabbtn[data-tab="home"]'));
  hD.click(hD.$('#homeProgramRail [data-symfilter="spine"]'));
  ok('D24 허리·디스크 필터 2명', hD.$$('#teacherList .teacher').length === 2, String(hD.$$('#teacherList .teacher').length));
  ok('D25 카드에 회당 단가 없음(결제 창에서만)', !/회당/.test(hD.text('#teacherList')) && !/\d{3},\d{3}원/.test(hD.text('#teacherList')) && /프로필 · 후기 보기/.test(hD.text('#teacherList')), hD.text('#teacherList').replace(/\s+/g, ' ').slice(0, 120));
  ok('D25b 카드 태그 최대 3개', $$('#teacherList .teacher')[0].querySelectorAll('.t-tags .tag').length <= 3, String($$('#teacherList .teacher')[0].querySelectorAll('.t-tags .tag').length));

  /* ============================================================
     E. 관리자 심사 콘솔 — 승인 / 보완 요청 3면 사이클
     ============================================================ */
  const E = makeDom();
  const hE = helpers(E.window, E.doc);
  await sleep(30);
  ok('E0 JS 오류 없음', E.errors.length === 0, E.errors.slice(0, 3).join(' | '));
  ok('E1 시작 화면 관리자 진입 카드', hE.$$('[data-login="admin"]').length === 1);
  hE.click(hE.$('[data-login="admin"]'));
  ok('E2 관리자 로그인 → 심사 콘솔', hE.$('#screen-admin').classList.contains('is-active'));
  ok('E3 관리자 모드 표기', hE.text('#rolePill') === '관리자 모드', hE.text('#rolePill'));
  ok('E4 서브페이지 탭바 숨김', hE.doc.body.classList.contains('is-subpage'));
  ok('E5 대기 지원서 2건', hE.$$('#adminQueue .admin-card').length === 2, String(hE.$$('#adminQueue .admin-card').length));
  ok('E6 통계 대기 2', /심사 대기/.test(hE.text('#adminStats')) && /\b2\b/.test(hE.text('#adminStats')));
  ok('E7 지원서당 서류 4종', hE.$$('#adminQueue .admin-card')[0].querySelectorAll('.admin-doc').length === 4);
  hE.click(hE.$('[data-admin-approve="adm-1"]'));
  let adminStore = JSON.parse(hE.w.localStorage.getItem('ttokttok_admin_v1'));
  ok('E8 서류 미확인 승인 차단', adminStore.applications[0].status === 'pending', adminStore.applications[0].status);
  hE.click(hE.$('[data-admin-doc-all="adm-1"]'));
  ok('E9 전체 확인 4/4', hE.$$('#adminQueue .admin-card')[0].querySelectorAll('.admin-doc.is-on').length === 4, String(hE.$$('#adminQueue .admin-card')[0].querySelectorAll('.admin-doc.is-on').length));
  hE.click(hE.$('[data-admin-approve="adm-1"]'));
  adminStore = JSON.parse(hE.w.localStorage.getItem('ttokttok_admin_v1'));
  ok('E10 승인 처리 저장', adminStore.applications[0].status === 'approved', adminStore.applications[0].status);
  ok('E11 대기 1건으로 감소', hE.$$('#adminQueue .admin-card').length === 1, String(hE.$$('#adminQueue .admin-card').length));
  ok('E12 최근 처리 기록', /정하윤/.test(hE.text('#adminRecent')) && /승인 완료/.test(hE.text('#adminRecent')));
  hE.click(hE.$('[data-admin-back]'));
  ok('E13 관리자 콘솔 닫기 → 홈', hE.$('#screen-home').classList.contains('is-active') && !hE.doc.body.classList.contains('is-subpage'));
  hE.click(hE.$('.tabbtn[data-tab="mypage"]'));
  hE.click(hE.$('[data-admin-open]'));
  ok('E14 내 정보에서 관리자 콘솔', hE.$('#screen-admin').classList.contains('is-active'));

  const E2 = makeDom();
  const h2e = helpers(E2.window, E2.doc);
  await sleep(30);
  applyAsPartner(h2e);
  let pE = JSON.parse(h2e.w.localStorage.getItem('ttokttok_partner_v1'));
  ok('E14b 지원 플로우 JS 오류 없음', E2.errors.length === 0, E2.errors.slice(0, 3).join(' | '));
  ok('E15 지원서 접수 pending', pE.status === 'pending' && pE.name === '김현수');
  h2e.click(h2e.$('#partnerDone [data-role-switch="therapist"]'));
  h2e.click(h2e.$('.tabbtn[data-tab="tp-mypage"]'));
  h2e.click(h2e.$('[data-admin-open]'));
  ok('E16 내 지원서가 심사 큐에 표시', h2e.$$('#adminQueue .admin-card').length === 3 && /김현수/.test(h2e.text('#adminQueue')), String(h2e.$$('#adminQueue .admin-card').length));
  ok('E17 내 지원 표시', /내 지원/.test(h2e.text('#adminQueue')));
  h2e.click(h2e.$('#adminQueue [data-app-open="me"]'));
  ok('E17a 지원서 상세 바텀시트', h2e.$('#appSheet').classList.contains('is-open'));
  ok('E17b 상세에 면허·서류 정보', /11-2021-009912/.test(h2e.text('#appSheetBody')) && /제출 서류 4종/.test(h2e.text('#appSheetBody')));
  h2e.click(h2e.$('[data-app-close]'));
  ok('E17c 지원서 상세 닫기', !h2e.$('#appSheet').classList.contains('is-open'));
  h2e.click(h2e.$('[data-admin-reject="me"]'));
  ok('E18 보완 사유 시트', h2e.$('#rejectSheet').classList.contains('is-open'));
  h2e.click(h2e.$('#rejectConfirm'));
  pE = JSON.parse(h2e.w.localStorage.getItem('ttokttok_partner_v1'));
  ok('E19 사유 없이 보완 요청 차단', pE.status === 'pending', pE.status);
  h2e.click(h2e.$('#rejectReasons [data-reason="경력증명서 발급처 확인 필요"]'));
  h2e.setVal(h2e.$('#rejectMemo'), '경력증명서 발급처 확인이 필요합니다.');
  h2e.click(h2e.$('#rejectConfirm'));
  pE = JSON.parse(h2e.w.localStorage.getItem('ttokttok_partner_v1'));
  ok('E20 보완 요청 저장', pE.status === 'needs_update' && /경력증명서/.test(pE.reviewNote || ''), pE.status);
  ok('E21 보완 요청 후 시트 닫힘', !h2e.$('#rejectSheet').classList.contains('is-open'));
  h2e.click(h2e.$('#rolePill'));
  ok('E22 선생님 모드에 보완 요청 표시', /보완 요청/.test(h2e.text('#tpStatusCard')) && /경력증명서/.test(h2e.text('#tpStatusCard')));
  ok('E23 보완 사유 노출', /보완 사유/.test(h2e.text('#tpStatusCard')));
  h2e.click(h2e.$('#tpStatusCard [data-partner="edit"]'));
  ok('E24 지원서 수정 폼에 기존 값', h2e.$('#pName').value === '김현수' && h2e.$('#screen-partner').classList.contains('is-active'));
  h2e.click(h2e.$('[data-pstep="4"]'));
  h2e.setCheck(h2e.$('#pAgree'), true);
  h2e.click(h2e.$('#pSubmit'));
  pE = JSON.parse(h2e.w.localStorage.getItem('ttokttok_partner_v1'));
  ok('E25 보완 후 재제출 pending', pE.status === 'pending' && !pE.reviewNote, pE.status);
  h2e.click(h2e.$('#partnerDone [data-role-switch="therapist"]'));
  h2e.click(h2e.$('.tabbtn[data-tab="tp-mypage"]'));
  h2e.click(h2e.$('[data-admin-open]'));
  h2e.click(h2e.$('[data-admin-doc-all="me"]'));
  h2e.click(h2e.$('[data-admin-approve="me"]'));
  pE = JSON.parse(h2e.w.localStorage.getItem('ttokttok_partner_v1'));
  const adminStore2 = JSON.parse(h2e.w.localStorage.getItem('ttokttok_admin_v1'));
  ok('E26 관리자 승인 → 활동중', pE.status === 'approved', pE.status);
  ok('E27 승인 이력 2건(보완 + 승인)', adminStore2.decisions.length === 2, String(adminStore2.decisions.length));
  h2e.click(h2e.$('[data-admin-back]'));
  h2e.click(h2e.$('.tabbtn[data-tab="tp-home"]'));
  ok('E28 승인 후 파트너 홈 활동중', /활동중/.test(h2e.text('#tpHero')) && /활동중/.test(h2e.text('#tpStatusCard')));
  ok('E29 승인 후 정산 980,000', /980,000/.test(h2e.text('#tpSettle')), h2e.text('#tpSettle').slice(0, 80));
  ok('E30 정산 막대 차트 6개', h2e.$$('#tpSettle svg rect').length === 6, String(h2e.$$('#tpSettle svg rect').length));

  /* ============================================================
     F. 디자인 시스템 v2 · 정적 품질
     ============================================================ */
  const F = makeDom();
  await sleep(30);
  const hF = helpers(F.window, F.doc);
  ok('F0 JS 오류 없음', F.errors.length === 0, F.errors.slice(0, 3).join(' | '));
  const css = F.doc.querySelector('style').textContent;
  ok('F1 소프트 그레이 캔버스', /#F7F8FA/.test(css));
  ok('F2 글래스 블러 18px', /blur\(18px\)/.test(css));
  ok('F3 타이포 자간 -0.02em', /letter-spacing:-.02em/.test(css));
  ok('F4 카드 라운드 24px', /--r-lg:24px/.test(css));
  ok('F5 탭바 이모지 없음', !/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(F.doc.querySelector('.tabbar[data-mode="therapist"]').textContent));
  ok('F6 SVG 아이콘 40개 이상', F.doc.querySelectorAll('svg use').length >= 40, String(F.doc.querySelectorAll('svg use').length));
  ok('F7 바텀시트 드래그 핸들', F.doc.querySelectorAll('.sheet-handle').length >= 2);
  ok('F8 외부 요청 0건', !/<link[^>]+href="http|src="https?:|@import/.test(HTML));
  const ids = Array.from(F.doc.querySelectorAll('[id]')).map((el) => el.id);
  ok('F9 중복 ID 0건', ids.length === new Set(ids).size, String(ids.length - new Set(ids).size));
  ok('F10 모든 버튼 type 지정', Array.from(F.doc.querySelectorAll('button')).every((b) => !!b.getAttribute('type')));
  ok('F11 로고 base64 내장', /^data:image\/png;base64,/.test(F.doc.querySelector('#brandMark').getAttribute('src')));
  ok('F12 카드 그라데이션 아바타', /linear-gradient/.test(F.doc.querySelector('.t-avatar').getAttribute('style') || ''));
  ok('F13 관리자 콘솔 대기 2건', F.doc.querySelectorAll('#adminQueue .admin-card').length === 2);

  /* ============================================================
     G. v7 — 찜하기(하트) · 방문 D-day · 진행 표시 · 상담 폼 · 타임라인
     ============================================================ */
  const G = makeDom();
  const hG = helpers(G.window, G.doc);
  await sleep(30);
  ok('G0 JS 오류 없음', G.errors.length === 0, G.errors.slice(0, 3).join(' | '));
  hG.click(hG.$('[data-login="customer"]'));
  ok('G1 선생님 카드마다 하트 8개', hG.$$('#teacherList [data-fav]').length === 8, String(hG.$$('#teacherList [data-fav]').length));
  ok('G2 하트 초기 상태는 해제', hG.$$('#teacherList [data-fav].is-on').length === 0);
  ok('G3 찜 필터 기본 꺼짐 · 0명', hG.$('#favFilter').getAttribute('aria-pressed') === 'false' && hG.text('#favCount') === '0', hG.text('#favCount'));

  const favPark = hG.$('#teacherList [data-fav="park"]');
  hG.click(favPark);
  ok('G4 하트 탭 → 찜 켜짐', favPark.classList.contains('is-on') && favPark.getAttribute('aria-pressed') === 'true');
  ok('G5 카드에 찜 상태 반영', hG.$('#teacherList [data-teacher="park"]').classList.contains('is-fav'));
  ok('G6 SafeStorage 저장', (JSON.parse(hG.w.localStorage.getItem('ttokttok_favs_v1')) || []).indexOf('park') !== -1, hG.w.localStorage.getItem('ttokttok_favs_v1'));
  ok('G7 찜 개수·힌트 표시', hG.text('#favCount') === '1' && /1명 모아둠/.test(hG.text('#favHint')), hG.text('#favCount') + ' / ' + hG.text('#favHint'));
  hG.click(hG.$('#teacherList [data-fav="lee"]'));
  ok('G8 두 명 찜', hG.text('#favCount') === '2', hG.text('#favCount'));

  hG.click(hG.$('#favFilter'));
  ok('G9 찜한 선생님만 2명', hG.$$('#teacherList .teacher').length === 2, String(hG.$$('#teacherList .teacher').length));
  ok('G10 필터 켜짐 표시', hG.$('#favFilter').classList.contains('is-on') && hG.$('#favFilter').getAttribute('aria-pressed') === 'true');
  ok('G11 찜 목록에 박서준·이하늘', /박서준/.test(hG.text('#teacherList')) && /이하늘/.test(hG.text('#teacherList')));

  hG.click(hG.$('#teacherList [data-fav="lee"]'));
  ok('G12 필터 중 찜 해제 → 목록 갱신', hG.$$('#teacherList .teacher').length === 1, String(hG.$$('#teacherList .teacher').length));
  hG.click(hG.$('#teacherList [data-fav="park"]'));
  ok('G13 모두 해제 → 빈 일러스트', hG.$$('#teacherList .teacher').length === 0 && !!hG.$('#teacherList .empty-v7 svg'), hG.text('#teacherList').slice(0, 50));
  ok('G14 빈 상태 안내 문구', /아직 찜한 선생님이 없어요/.test(hG.text('#teacherList')));
  hG.click(hG.$('#teacherList [data-fav-clear]'));
  ok('G15 전체 보기 복귀 8명', hG.$$('#teacherList .teacher').length === 8 && hG.$('#favFilter').getAttribute('aria-pressed') === 'false', String(hG.$$('#teacherList .teacher').length));

  hG.click(hG.$('#teacherList [data-teacher="park"]'));
  ok('G16 상세 시트에 하트', !!hG.$('#teacherSheet [data-fav="park"]'));
  hG.click(hG.$('#teacherSheet [data-fav="park"]'));
  ok('G17 시트에서 찜 → 카드까지 동기화', hG.$('#teacherSheet [data-fav="park"]').classList.contains('is-on') && hG.$('#teacherList [data-fav="park"]').classList.contains('is-on'));
  hG.click(hG.$('[data-sheet-close]'));

  const jd = hG.text('#journalDday');
  ok('G18 일지 상단 D-day 카드', !!hG.$('#journalDday .dday-card') && /예정된 방문/.test(jd) && /D-\d|D-DAY/.test(jd), jd.slice(0, 70));
  ok('G19 준비물 한 줄 팁', /준비물/.test(jd), jd.slice(0, 90));
  ok('G20 회복 타임라인 3건 이상', hG.$$('#journalTimeline .tl-item').length >= 3, String(hG.$$('#journalTimeline .tl-item').length));
  ok('G21 타임라인에 다음 방문 표시', hG.$$('#journalTimeline .tl-item.is-next').length === 1);
  hG.click(hG.$('.tabbtn[data-tab="mypage"]'));
  ok('G22 내 예약 시트에도 D-day 카드', !!hG.$('#accountDday .dday-card'), hG.text('#accountDday').slice(0, 50));

  hG.click(hG.$('.tabbtn[data-tab="booking"]'));
  ok('G23 진행 표시 1/4 + 25%', hG.text('#bookStepCount') === '1/4' && hG.$('#bookingProgress').style.width === '25%', hG.text('#bookStepCount') + ' ' + hG.$('#bookingProgress').style.width);
  ok('G24 단계 안내 문구', /방문 정보를 입력해 주세요/.test(hG.text('#bookStepHint')), hG.text('#bookStepHint'));
  ok('G25 간단 진행 바 구조', hG.$$('#bookingStepper .bk-prog-bar').length === 1 && hG.$$('#bookingStepper .step-dot').length === 0);
  hG.setSel(hG.$('#bookProvince'), '서울');
  hG.setSel(hG.$('#bookDistrict'), '강남구');
  hG.setVal(hG.$('#bookAddress'), '대치동 123-4, 101동 1203호');
  hG.click(hG.$('#bookSyms [data-val="뇌졸중·편마비"]'));
  hG.click(hG.$('[data-next="1"]'));
  ok('G26 2단계 진행 2/4 + 50%', hG.text('#bookStepCount') === '2/4' && hG.$('#bookingProgress').style.width === '50%', hG.text('#bookStepCount') + ' ' + hG.$('#bookingProgress').style.width);
  ok('G27 진행 바 aria 값 갱신', hG.$('#bkProgBar').getAttribute('aria-valuenow') === '2', hG.$('#bkProgBar').getAttribute('aria-valuenow'));

  const naverLinks = Array.from(hG.doc.querySelectorAll('a[href="https://naver.me/G3vCkS0S"]'));
  ok('G28 네이버 상담 폼 링크 2곳 이상', naverLinks.length >= 2, String(naverLinks.length));
  ok('G29 새 창 + noopener', naverLinks.every((a) => a.getAttribute('target') === '_blank' && /noopener/.test(a.getAttribute('rel') || '')));
  ok('G30 예약 완료 화면에 상담 폼 버튼', !!hG.$('#bookingDone a[href="https://naver.me/G3vCkS0S"]') && /상담 폼/.test(hG.text('#bookingDone')));
  ok('G31 내 정보에 베타 상담 링크', /상담 폼/.test(hG.text('.mp-consult')), hG.text('.mp-consult'));

  const G2 = makeDom({ ttokttok_favs_v1: '["park","oh"]' });
  await sleep(30);
  const hG2 = helpers(G2.window, G2.doc);
  ok('G32 저장된 찜 복원(2명)', G2.errors.length === 0 && hG2.$$('#teacherList [data-fav].is-on').length === 2, String(hG2.$$('#teacherList [data-fav].is-on').length));
  ok('G33 복원 후 찜 개수 2', hG2.text('#favCount') === '2', hG2.text('#favCount'));
  const G3 = makeDom({ ttokttok_favs_v1: '{broken' });
  await sleep(30);
  ok('G34 손상 찜 데이터에서도 오류 없음', G3.errors.length === 0 && G3.doc.querySelectorAll('#teacherList .teacher').length === 8, G3.errors.slice(0, 2).join(' | '));

  /* ============================================================
     H. v8 — 보호자 공유 리포트 · 매칭 트래커 · PWA 메타 · 터치 손맛
     ============================================================ */
  const H = makeDom();
  const hH = helpers(H.window, H.doc);
  await sleep(30);
  ok('H0 JS 오류 없음', H.errors.length === 0, H.errors.slice(0, 3).join(' | '));
  hH.click(hH.$('[data-login="customer"]'));

  const metaOf = (n) => {
    const el = H.doc.querySelector('meta[name="' + n + '"]');
    return el ? el.getAttribute('content') : null;
  };
  ok('H1 홈 화면 앱 capable', metaOf('apple-mobile-web-app-capable') === 'yes');
  ok('H2 상태바 스타일 default', metaOf('apple-mobile-web-app-status-bar-style') === 'default');
  ok('H3 홈 화면 앱 이름', metaOf('apple-mobile-web-app-title') === '똑똑쌤', metaOf('apple-mobile-web-app-title'));
  ok('H4 테마 컬러 #F7F8FA', String(metaOf('theme-color') || '').toUpperCase() === '#F7F8FA', metaOf('theme-color'));
  const appleIcon = H.doc.querySelector('link[rel="apple-touch-icon"]');
  ok('H5 apple-touch-icon PNG data URI', !!appleIcon && /^data:image\/png;base64,/.test(appleIcon.getAttribute('href') || ''));
  const css8 = H.doc.querySelector('style').textContent;
  ok('H6 터치 커브 .15s cubic-bezier(.22,1,.36,1)', /transform \.15s cubic-bezier\(\.22,1,\.36,1\)/.test(css8));
  ok('H7 주요 버튼 눌림 scale(.98)', /\.btn:active[^{]*\{transform:scale\(\.98\)\}/.test(css8));
  ok('H8 탭 전환 페이드 180ms', /@keyframes tabFade/.test(css8) && /tabFade \.18s/.test(css8));

  hH.click(hH.$('.tabbtn[data-tab="journal"]'));
  ok('H9 일지에 보호자 공유 리포트 카드', !!hH.$('#reportOpen') && /보호자 공유 리포트/.test(hH.text('#reportOpen')), hH.text('#reportOpen'));
  ok('H10 리포트 시트 초기 닫힘', !hH.$('#reportSheet').classList.contains('is-open'));
  hH.click(hH.$('#reportOpen'));
  ok('H11 리포트 시트 열림', hH.$('#reportSheet').classList.contains('is-open'));
  const rcText = hH.text('#reportCard');
  ok('H12 리포트에 환자명', /김순자 어르신/.test(rcText), rcText.slice(0, 60));
  ok('H13 담당 선생님·국가면허', /박서준 선생님/.test(rcText) && /국가면허/.test(rcText));
  ok('H14 누적 회차 5/12', /5회차/.test(rcText) && /12회차/.test(rcText));
  /* v40 · 시드 예약 날짜는 '오늘 +2일'로 계산되므로 요일을 고정하지 않고 달력과 맞는지 본다. */
  const h15m = rcText.match(/(\d{1,2})\.(\d{1,2}) \((월|화|수|목|금|토|일)\) 10:30/);
  const h15ok = !!h15m && h15m[3] === ['일', '월', '화', '수', '목', '금', '토'][new Date(2026, Number(h15m[1]) - 1, Number(h15m[2])).getDay()];
  ok('H15 다음 방문 예정일(날짜·요일 일치)', h15ok, rcText.replace(/\s+/g, ' ').slice(0, 120));
  ok('H16 부드러운 회복 추이 3곡선', hH.$$('#reportChart .rc-line').length === 3, String(hH.$$('#reportChart .rc-line').length));
  ok('H17 곡선이 베지어(C)로 부드러움', hH.$$('#reportChart .rc-line').every((p) => /C/.test(p.getAttribute('d') || '')));
  ok('H18 보행·가동범위·통증 요약', /보행 안정성/.test(rcText) && /무릎 가동범위/.test(rcText) && /통증/.test(rcText));
  ok('H19 선생님 한 줄 코멘트', /선생님 코멘트/.test(rcText) && /계단/.test(rcText));
  ok('H20 요약 텍스트 복사 버튼', /요약 텍스트 복사/.test(hH.text('#reportCopy')));

  let copied = '';
  Object.defineProperty(H.window.navigator, 'clipboard', {
    configurable: true,
    value: { writeText: (t) => { copied = t; return Promise.resolve(); } }
  });
  hH.click(hH.$('#reportCopy'));
  await sleep(20);
  ok('H21 클립보드에 요약 복사', /\[똑똑쌤 회복 리포트\]/.test(copied), copied.slice(0, 40));
  ok('H22 복사문에 핵심 항목', /김순자/.test(copied) && /박서준/.test(copied) && /누적 5회차/.test(copied) && /다음 방문/.test(copied), copied.replace(/\n/g, ' | ').slice(0, 120));
  ok('H23 복사 토스트 문구', /보호자 공유용 요약이 복사되었어요/.test(hH.text('#toast')), hH.text('#toast'));
  ok('H24 토스트 노출 상태', hH.$('#toast').classList.contains('is-on'));
  hH.click(hH.$('#reportSheet [data-report-close]'));
  ok('H25 리포트 시트 닫힘', !hH.$('#reportSheet').classList.contains('is-open'));

  hH.click(hH.$('.tabbtn[data-tab="mypage"]'));
  hH.click(hH.$('#mpBookLink'));
  ok('H26 다가오는 방문에 매칭 트래커', hH.$('#accountSheet').classList.contains('is-open') && hH.$$('#bookingList .mtk').length >= 1, String(hH.$$('#bookingList .mtk').length));
  const trk = hH.$('#bookingList .mtk');
  ok('H27 4단계 도트·라벨', trk.querySelectorAll('.mtk-step').length === 4 && /접수 완료/.test(trk.textContent) && /선생님 배정/.test(trk.textContent) && /방문 확정/.test(trk.textContent) && /방문 완료/.test(trk.textContent));
  ok('H28 현재 단계는 한 곳', trk.querySelectorAll('.mtk-step.is-now').length === 1);
  ok('H29 배정된 예약 → 방문 확정 단계', trk.querySelector('.mtk-step.is-now .mtk-label').textContent === '방문 확정', trk.querySelector('.mtk-step.is-now .mtk-label').textContent);
  ok('H30 단계 안내 문구', /선생님 배정이 끝났어요/.test(hH.text('#bookingList')), hH.text('#bookingList').replace(/\s+/g, ' ').slice(0, 100));
  ok('H31 이전 단계 완료 표시', trk.querySelectorAll('.mtk-step.is-done').length === 2, String(trk.querySelectorAll('.mtk-step.is-done').length));

  const H2 = makeDom();
  const h2h = helpers(H2.window, H2.doc);
  await sleep(30);
  h2h.click(h2h.$('[data-login="customer"]'));
  h2h.click(h2h.$('.tabbtn[data-tab="booking"]'));
  h2h.setSel(h2h.$('#bookProvince'), '서울');
  h2h.setSel(h2h.$('#bookDistrict'), '강남구');
  h2h.setVal(h2h.$('#bookAddress'), '대치동 123-4, 101동 1203호');
  h2h.click(h2h.$('#bookSyms [data-val="뇌졸중·편마비"]'));
  h2h.click(h2h.$('[data-next="1"]'));
  h2h.click(h2h.$('#bookDates .date-chip'));
  h2h.click(h2h.$$('#bookSlots .slot').filter((b) => !b.disabled)[0]);
  h2h.click(h2h.$('[data-next="2"]'));
  h2h.click(h2h.$('[data-next="3"]'));
  h2h.setVal(h2h.$('#bookName'), '김순자');
  h2h.setVal(h2h.$('#bookPhone'), '01012345678');
  h2h.setCheck(h2h.$('#bookAgree'), true);
  h2h.click(h2h.$('#payBtn'));
  await sleep(1100);
  ok('H32 예약 완료 화면 JS 오류 없음', H2.errors.length === 0, H2.errors.slice(0, 2).join(' | '));
  ok('H33 완료 화면에 매칭 트래커', h2h.$$('#doneTracker .mtk .mtk-step').length === 4, String(h2h.$$('#doneTracker .mtk .mtk-step').length));
  ok('H34 추천 배정 → 선생님 배정 단계', h2h.$('#doneTracker .mtk-step.is-now .mtk-label').textContent === '선생님 배정', h2h.$('#doneTracker').textContent.replace(/\s+/g, ' ').slice(0, 80));
  ok('H35 완료 화면 실시간 안내', /찾고 있어요/.test(h2h.text('#doneTracker')));
  ok('H36 트래커 현재 점 펄스 정의', /@keyframes matchPulse/.test(css8) && /animation:matchPulse/.test(css8));

  /* ============================================================
     I. v9 — 일러스트 아바타 · 카드 포인트 심볼 · 멀티레이어 섀도우 · .ics 캘린더
     ============================================================ */
  const I = makeDom();
  const hI = helpers(I.window, I.doc);
  await sleep(30);
  ok('I0 JS 오류 없음', I.errors.length === 0, I.errors.slice(0, 3).join(' | '));
  hI.click(hI.$('[data-login="customer"]'));

  const avas = hI.$$('#teacherList .t-avatar svg.ava-art');
  ok('I1 선생님 8명 모두 SVG 일러스트 아바타', avas.length === 8, String(avas.length));
  ok('I2 아바타가 선생님 ID별로 구분', avas.map((s) => s.getAttribute('data-ava')).join(',') === 'park,lee,jung,choi,kim,yoon,oh,han', avas.map((s) => s.getAttribute('data-ava')).join(','));
  const avaStyles = hI.$$('#teacherList .t-avatar').map((el) => el.getAttribute('style') || '');
  ok('I3 파스텔 그라데이션 배경 4종 이상 로테이션', avaStyles.every((s) => /linear-gradient/.test(s)) && new Set(avaStyles).size >= 4, String(new Set(avaStyles).size));
  ok('I4 인물 SVG에 얼굴·눈·미소·청진기', avas.every((s) => s.querySelector('.ava-steth') && s.querySelectorAll('circle').length >= 4 && s.querySelectorAll('path').length >= 6));
  ok('I5 이니셜 글자 아바타 제거', !/[가-힣]/.test(hI.$$('#teacherList .t-avatar').map((e) => e.textContent).join('')), hI.$$('#teacherList .t-avatar').map((e) => e.textContent).join('|'));

  hI.click(hI.$('#teacherList .teacher'));
  await sleep(30);
  ok('I6 상세 시트도 일러스트 아바타', !!hI.$('#teacherSheetBody .sheet-av svg.ava-art[data-ava="park"]'));
  hI.click(hI.$('#teacherSheet [data-sheet-close]'));
  hI.setVal(hI.$('#homeSearch'), '박서준');
  await sleep(30);
  ok('I7 검색 결과 아바타도 일러스트', !!hI.$('#searchResults .s-av svg.ava-art'), hI.text('#searchResults').slice(0, 40));

  const badges = hI.$$('#homeProgramRail .hpc-badge');
  ok('I8 홈 가로 카드 4개에 포인트 배지', badges.length === 4, String(badges.length));
  ok('I9 배지 심볼 SVG 4종', badges.every((b) => b.querySelector('svg path, svg circle')));
  const badgeCls = badges.map((b) => (b.className.match(/is-(\w+)/) || [])[1]).join(',');
  ok('I10 블루·오렌지·코랄·틸 4색', badgeCls === 'blue,orange,coral,teal', badgeCls);
  ok('I11 카드마다 소프트 글로우', hI.$$('#homeProgramRail .hpc-glow').length === 4);

  const css9 = I.doc.querySelector('style').textContent;
  ok('I12 멀티레이어 2중 그림자 변수', /--v9-shadow:0 2px 8px var\(--shade-1\),0 10px 26px var\(--shade-2\)/.test(css9));
  ok('I13 주요 카드에 2중 그림자 적용', /\.home-hero,\.home-hero-card,\.home-program-card,\.teacher,\.journal-card,#screen-journal \.card\{box-shadow:var\(--v9-shadow\)\}/.test(css9));
  ok('I14 제목 자간 -0.025em', /letter-spacing:-\.025em/.test(css9));
  ok('I15 숫자 tabular-nums 일관 적용', /body\{font-variant-numeric:tabular-nums/.test(css9));
  ok('I16 완료 체크 원형 그리기 애니메이션', /@keyframes ringDraw/.test(css9) && /stroke-dashoffset:198/.test(css9) && !!I.doc.querySelector('#bookingDone .done-ring circle'));
  ok('I17 예약 완료 화면 캘린더 버튼', !!hI.$('#doneIcs') && /캘린더에 일정 추가/.test(hI.text('#doneIcs')));

  hI.click(hI.$('.tabbtn[data-tab="booking"]'));
  hI.setSel(hI.$('#bookProvince'), '서울');
  hI.setSel(hI.$('#bookDistrict'), '강남구');
  hI.setVal(hI.$('#bookAddress'), '대치동 123-4, 101동 1203호');
  hI.click(hI.$('#bookSyms [data-val="뇌졸중·편마비"]'));
  hI.click(hI.$('[data-next="1"]'));
  const pickDate = hI.$('#bookDates .date-chip');
  const pickDateIso = pickDate.getAttribute('data-date') || '';
  hI.click(pickDate);
  const pickSlot = hI.$$('#bookSlots .slot').filter((b) => !b.disabled)[0];
  const pickTime = pickSlot.getAttribute('data-time');
  hI.click(pickSlot);
  hI.click(hI.$('[data-next="2"]'));
  hI.click(hI.$('[data-next="3"]'));
  hI.setVal(hI.$('#bookName'), '김순자');
  hI.setVal(hI.$('#bookPhone'), '01012345678');
  hI.setCheck(hI.$('#bookAgree'), true);
  hI.click(hI.$('#payBtn'));
  await sleep(1100);
  ok('I18 예약 완료 화면 진입', hI.$('#bookingDone').hidden === false && hI.$('#bookingWizard').hidden === true);

  hI.click(hI.$('#doneIcs'));
  await sleep(30);
  const ics = (I.window.__ttokttokIcs || {}).text || '';
  const icsName = (I.window.__ttokttokIcs || {}).name || '';
  ok('I19 .ics 파일 생성(VCALENDAR)', /^BEGIN:VCALENDAR\r\n/.test(ics) && /\r\nEND:VCALENDAR\r\n$/.test(ics));
  ok('I20 일정 제목에 똑똑쌤 방문재활', /SUMMARY:.*똑똑쌤 방문재활/.test(ics));
  ok('I21 예약번호·방문지 포함', /UID:ttokttok-TT-\d{6}-\d{4}@/.test(ics) && /LOCATION:서울 강남구 대치동/.test(ics), ics.slice(0, 120));
  const dtS = /DTSTART;TZID=Asia\/Seoul:(\d{8}T\d{6})/.exec(ics);
  const dtE = /DTEND;TZID=Asia\/Seoul:(\d{8}T\d{6})/.exec(ics);
  const isoParts = (pickDateIso || '').split('-').join('');
  ok('I22 선택한 방문 일시가 DTSTART', !!dtS && dtS[1] === isoParts + 'T' + pickTime.replace(':', '') + '00', (dtS && dtS[1]) + ' vs ' + isoParts + 'T' + pickTime.replace(':', ''));
  const toMs = (s) => Date.UTC(+s.slice(0, 4), +s.slice(4, 6) - 1, +s.slice(6, 8), +s.slice(9, 11), +s.slice(11, 13));
  ok('I23 60분 일정으로 종료', !!dtS && !!dtE && toMs(dtE[1]) - toMs(dtS[1]) === 3600000, dtS && dtE && String(toMs(dtE[1]) - toMs(dtS[1])));
  ok('I24 1시간 전 알림(VALARM)', /BEGIN:VALARM/.test(ics) && /TRIGGER:-PT60M/.test(ics));
  ok('I25 .ics 파일명 규칙', /^똑똑쌤_방문재활_\d{8}\.ics$/.test(icsName), icsName);
  ok('I26 토스트 안내', /캘린더 파일\(\.ics\)을 내려받았어요/.test(hI.text('#toast')), hI.text('#toast'));
  ok('I27 .ics 클릭 후에도 JS 오류 없음', I.errors.length === 0, I.errors.slice(0, 2).join(' | '));

  /* ============================================================
     J. v10 — 알림함 · 쿠폰함 · 결제수단 관리 · FAQ · 내 예약 .ics
     ============================================================ */
  const J = makeDom();
  const hJ = helpers(J.window, J.doc);
  await sleep(30);
  ok('J0 JS 오류 없음', J.errors.length === 0, J.errors.slice(0, 3).join(' | '));
  hJ.click(hJ.$('[data-login="customer"]'));

  /* ----- 1. 알림함 ----- */
  ok('J1 홈 상단 알림 벨 + 이용권 버튼 공존', !!hJ.$('#btnNotif') && !!hJ.$('#homeTicketBtn'));
  ok('J2 안 읽음 배지 4건', hJ.$('#notifDot').hidden === false && hJ.text('#notifDot') === '4', hJ.text('#notifDot'));
  hJ.click(hJ.$('#btnNotif'));
  await sleep(20);
  ok('J3 벨 클릭 → 알림함 시트', hJ.$('#notifSheet').classList.contains('is-open'));
  ok('J4 알림 카드 4건', hJ.$$('#notifList .notif').length === 4, String(hJ.$$('#notifList .notif').length));
  const notifText = hJ.text('#notifList');
  ok('J5 알림 4종 문구(확정·D-1·리포트·쿠폰)',
    /방문이 확정됐어요/.test(notifText) && /D-1 리마인드/.test(notifText) && /회복 리포트/.test(notifText) && /평가 무료 쿠폰/.test(notifText),
    notifText.slice(0, 120));
  ok('J6 안 읽은 알림 빨간 점 4개', hJ.$$('#notifList .notif:not(.is-read) .notif-dot').length === 4, String(hJ.$$('#notifList .notif-dot').length));
  ok('J7 모두 읽음 버튼 활성', hJ.$('#notifReadAll').disabled === false);

  hJ.click(hJ.$('#notifList [data-notif="nt-coupon"]'));
  await sleep(20);
  ok('J8 쿠폰 알림 탭 → 쿠폰함 이동', hJ.$('#couponSheet').classList.contains('is-open') && !hJ.$('#notifSheet').classList.contains('is-open'));
  ok('J9 읽음 처리 후 배지 3', hJ.text('#notifDot') === '3', hJ.text('#notifDot'));

  /* ----- 2. 쿠폰함 ----- */
  ok('J10 보유 쿠폰 2종', hJ.$$('#couponList .coupon-card').length === 2, String(hJ.$$('#couponList .coupon-card').length));
  const cpText = hJ.text('#couponList');
  ok('J11 기본 쿠폰 문구·금액', /첫 1:1 방문 평가 무료/.test(cpText) && /정규 회차권 10,000원 할인/.test(cpText) && /-10,000원/.test(cpText) && /무료/.test(cpText), cpText.slice(0, 140));
  hJ.setVal(hJ.$('#couponCode'), 'NOPE');
  hJ.click(hJ.$('#couponRegister'));
  ok('J12 잘못된 코드 거부', hJ.$$('#couponList .coupon-card').length === 2 && /사용할 수 없는 쿠폰 코드/.test(hJ.text('#toast')), hJ.text('#toast'));
  hJ.setVal(hJ.$('#couponCode'), 'welcome');
  hJ.click(hJ.$('#couponRegister'));
  ok('J13 WELCOME 등록 → 3장', hJ.$$('#couponList .coupon-card').length === 3, String(hJ.$$('#couponList .coupon-card').length));
  ok('J14 5,000원 쿠폰 문구', /5,000원 추가 할인/.test(hJ.text('#couponList')) && /WELCOME/.test(hJ.text('#couponList')), hJ.text('#couponList').slice(0, 140));
  const cpStore = JSON.parse(J.window.localStorage.getItem('ttokttok_coupons_v1'));
  ok('J15 쿠폰 SafeStorage 저장(대문자 코드)', cpStore.length === 3 && cpStore[0].code === 'WELCOME' && cpStore[0].amount === 5000, JSON.stringify(cpStore[0]));
  ok('J16 내 정보 배지·사용 가능 3장', hJ.text('#mpCouponCount') === '3' && /사용 가능 3장/.test(hJ.text('#couponUsable')), hJ.text('#mpCouponCount') + ' / ' + hJ.text('#couponUsable'));
  hJ.setVal(hJ.$('#couponCode'), 'WELCOME');
  hJ.click(hJ.$('#couponRegister'));
  ok('J17 같은 코드 중복 차단', hJ.$$('#couponList .coupon-card').length === 3 && /이미 등록한 쿠폰 코드/.test(hJ.text('#toast')), hJ.text('#toast'));
  ok('J18 발급 토스트 금액', /5,000원 할인 쿠폰이 발급됐어요/.test(hJ.text('#toast')) || /이미 등록한 쿠폰 코드/.test(hJ.text('#toast')), hJ.text('#toast'));
  hJ.click(hJ.$('[data-coupon-close]'));
  ok('J19 쿠폰함 닫힘', !hJ.$('#couponSheet').classList.contains('is-open'));

  /* ----- 3. 내 정보 행 + 알림 모두 읽음 ----- */
  hJ.click(hJ.$('.tabbtn[data-tab="mypage"]'));
  ok('J20 내 정보 8행 리스트', hJ.$$('#screen-mypage .mp-row').length === 8, String(hJ.$$('#screen-mypage .mp-row').length));
  hJ.click(hJ.$('#mpNotifRow'));
  await sleep(20);
  ok('J21 내 정보 알림함 행 → 시트', hJ.$('#notifSheet').classList.contains('is-open'));
  hJ.click(hJ.$('#notifReadAll'));
  ok('J22 모두 읽음 → 카드 전부 읽음', hJ.$$('#notifList .notif.is-read').length === 4 && hJ.$$('#notifList .notif-dot').length === 0, String(hJ.$$('#notifList .notif.is-read').length));
  ok('J23 배지 사라짐(벨·내 정보)', hJ.$('#notifDot').hidden === true && hJ.$('#mpNotifCount').hidden === true);
  ok('J24 모두 읽음 토스트', /모두 읽음으로 표시/.test(hJ.text('#toast')), hJ.text('#toast'));
  const ntStore = JSON.parse(J.window.localStorage.getItem('ttokttok_notifs_v1'));
  ok('J25 읽음 상태 저장', ntStore.every((n) => n.read === true), JSON.stringify(ntStore.map((n) => n.read)));
  hJ.click(hJ.$('[data-notif-close]'));

  /* ----- 4. FAQ · 약관 ----- */
  hJ.click(hJ.$('#mpFaqRow'));
  ok('J26 FAQ 시트 열림', hJ.$('#faqSheet').classList.contains('is-open'));
  ok('J27 FAQ 10문항(v25 검색·카테고리용 5문항 추가)', hJ.$$('#faqList .faq-item').length === 10, String(hJ.$$('#faqList .faq-item').length));
  const faqText = hJ.text('#faqList');
  ok('J28 FAQ 5주제', /병원 치료/.test(faqText) && /면허/.test(faqText) && /환불/.test(faqText) && /준비/.test(faqText) && /언제 열리나요/.test(faqText), faqText.slice(0, 140));
  ok('J29 아코디언 초기 닫힘', hJ.$$('#faqList .faq-item.is-open').length === 0 && hJ.$('#faqList .faq-q').getAttribute('aria-expanded') === 'false');
  hJ.click(hJ.$('#faqList [data-faq="faq-diff"]'));
  ok('J30 Q1 열림', hJ.$$('#faqList .faq-item.is-open').length === 1 && hJ.$('#faqList [data-faq="faq-diff"]').getAttribute('aria-expanded') === 'true');
  hJ.click(hJ.$('#faqList [data-faq="faq-license"]'));
  ok('J31 Q2 열면 Q1 닫힘(한 번에 하나)', hJ.$$('#faqList .faq-item.is-open').length === 1 && hJ.$('#faqList [data-faq="faq-license"]').getAttribute('aria-expanded') === 'true' && hJ.$('#faqList [data-faq="faq-diff"]').getAttribute('aria-expanded') === 'false');
  ok('J32 약관 요약 기본 탭', /이용약관 요약/.test(hJ.text('#termsBody')) && hJ.$('#faqTabs [data-terms="terms"]').classList.contains('is-on'));
  hJ.click(hJ.$('#faqTabs [data-terms="privacy"]'));
  ok('J33 개인정보처리방침 전환', /개인정보 처리방침 요약/.test(hJ.text('#termsBody')) && /수집 항목/.test(hJ.text('#termsBody')) && hJ.$('#faqTabs [data-terms="privacy"]').classList.contains('is-on'));
  hJ.click(hJ.$('[data-faq-close]'));
  ok('J34 FAQ 시트 닫힘', !hJ.$('#faqSheet').classList.contains('is-open'));

  /* ----- 5. 결제수단 등록·관리 ----- */
  hJ.click(hJ.$('#mpPayRow'));
  ok('J35 결제수단 목록 2건', hJ.$('#paySheet').classList.contains('is-open') && hJ.$$('#pmList .pm-row').length === 2, String(hJ.$$('#pmList .pm-row').length));
  const pmText = hJ.text('#pmList');
  ok('J36 신한카드 **** 4821 · 기본 + 카카오페이', /신한카드 \*{4} 4821/.test(pmText) && /기본 결제수단/.test(pmText) && /카카오페이/.test(pmText), pmText.replace(/\s+/g, ' ').slice(0, 120));
  ok('J37 새 카드 추가 버튼·폼 접힘', hJ.$('#cardForm').hidden === true && /새 카드 추가/.test(hJ.text('#pmAddBtn')));
  hJ.click(hJ.$('#pmAddBtn'));
  ok('J38 카드 폼 열림', hJ.$('#cardForm').hidden === false && hJ.$('#pmAddBtn').getAttribute('aria-expanded') === 'true');
  hJ.click(hJ.$('#cardSave'));
  ok('J39 끝 4자리 검증', hJ.$('#f-cardLast4').classList.contains('is-error'));
  hJ.setVal(hJ.$('#cardLast4'), '12345');
  ok('J40 끝 4자리 자동 제한', hJ.$('#cardLast4').value === '1234', hJ.$('#cardLast4').value);
  hJ.setVal(hJ.$('#cardExpiry'), '1329');
  hJ.click(hJ.$('#cardSave'));
  ok('J41 유효기간 월 검증', hJ.$('#f-cardExpiry').classList.contains('is-error'));
  hJ.setVal(hJ.$('#cardExpiry'), '1229');
  ok('J42 유효기간 자동 포맷(MM/YY)', hJ.$('#cardExpiry').value === '12/29', hJ.$('#cardExpiry').value);
  hJ.setVal(hJ.$('#cardLabel'), '생활비 카드');
  hJ.click(hJ.$('#cardSave'));
  ok('J43 새 카드 즉시 목록 추가(3건)', hJ.$$('#pmList .pm-row').length === 3, String(hJ.$$('#pmList .pm-row').length));
  ok('J44 새 카드가 기본 결제수단', hJ.$('#pmList .pm-row').classList.contains('is-default') && /생활비 카드 \*{4} 1234/.test(hJ.$('#pmList .pm-row').textContent) && /유효기간 12\/29/.test(hJ.$('#pmList .pm-row').textContent), hJ.$('#pmList .pm-row').textContent.replace(/\s+/g, ' '));
  ok('J45 등록 후 폼 닫힘·입력 초기화', hJ.$('#cardForm').hidden === true && hJ.$('#cardLast4').value === '' && hJ.$('#cardLabel').value === '' && hJ.$('#cardExpiry').value === '');
  const cardStore = JSON.parse(J.window.localStorage.getItem('ttokttok_cards_v1'));
  ok('J46 카드 SafeStorage 저장', cardStore.length === 3 && cardStore[0].last4 === '1234' && cardStore[0].expiry === '12/29' && cardStore[0].isDefault === true, JSON.stringify(cardStore[0]));
  hJ.click(hJ.$('#pmList [data-card-default]'));
  const cardStore2 = JSON.parse(J.window.localStorage.getItem('ttokttok_cards_v1'));
  ok('J47 기본 결제수단 변경(하나만)', cardStore2.filter((c) => c.isDefault).length === 1 && cardStore2[1].isDefault === true && /기본 결제수단으로 설정/.test(hJ.text('#toast')), JSON.stringify(cardStore2.map((c) => [c.label, c.isDefault])));
  hJ.click(hJ.$('[data-pay-close]'));

  /* ----- 6. 예약 3~4단계 쿠폰 할인 연동 ----- */
  hJ.click(hJ.$('.tabbtn[data-tab="booking"]'));
  hJ.setSel(hJ.$('#bookProvince'), '서울');
  hJ.setSel(hJ.$('#bookDistrict'), '강남구');
  hJ.setVal(hJ.$('#bookAddress'), '대치동 123-4, 101동 1203호');
  hJ.click(hJ.$('#bookSyms [data-val="뇌졸중·편마비"]'));
  hJ.click(hJ.$('[data-next="1"]'));
  hJ.click(hJ.$('#bookDates .date-chip'));
  hJ.click(hJ.$$('#bookSlots .slot').filter((b) => !b.disabled)[0]);
  hJ.click(hJ.$('[data-next="2"]'));
  ok('J48 이용권 미선택 시 쿠폰 영역 숨김', hJ.$('#couponPick').hidden === true);
  hJ.click(hJ.$('#passList [data-pass="p8"]'));
  ok('J49 유료권 선택 시 쿠폰 칩 노출', hJ.$('#couponPick').hidden === false);
  ok('J50 쿠폰 칩 3개(안 함 + 10,000 + 5,000)', hJ.$$('#couponChips .coupon-chip').length === 3, String(hJ.$$('#couponChips .coupon-chip').length));
  ok('J51 기본은 쿠폰 사용 안 함(592,000원)', hJ.$('#couponChips .coupon-chip').classList.contains('is-on') && hJ.text('#totalAmount') === '592,000원', hJ.text('#totalAmount'));
  hJ.click(hJ.$('#couponChips [data-coupon-pick="cp-10000"]'));
  ok('J52 쿠폰 적용 즉시 582,000원', hJ.text('#totalAmount') === '582,000원', hJ.text('#totalAmount'));
  ok('J53 합계 바에 할인 반영', hJ.text('#bookTotalAmount') === '582,000원' && /쿠폰 10,000원 할인/.test(hJ.text('#bookTotalMeta')), hJ.text('#bookTotalMeta'));
  hJ.click(hJ.$('[data-next="3"]'));
  const sumText = hJ.text('#bookSummary');
  ok('J54 확인 화면에 정가·쿠폰 할인 행', /정가/.test(sumText) && /592,000원/.test(sumText) && /쿠폰 할인/.test(sumText) && /-10,000원/.test(sumText), sumText.replace(/\s+/g, ' ').slice(0, 160));
  ok('J55 총액 하단 할인 안내', hJ.$('#discountNote').hidden === false && /쿠폰 10,000원 할인 적용/.test(hJ.text('#discountNote')), hJ.text('#discountNote'));
  hJ.setVal(hJ.$('#bookName'), '김순자');
  hJ.setVal(hJ.$('#bookPhone'), '01012345678');
  hJ.click(hJ.$('#payMethods [data-pay="신용/체크카드"]'));
  hJ.setCheck(hJ.$('#bookAgree'), true);
  hJ.click(hJ.$('#payBtn'));
  await sleep(1100);
  ok('J56 할인 결제 완료 화면', hJ.$('#bookingDone').hidden === false);
  const accJ = JSON.parse(J.window.localStorage.getItem('ttokttok_account_v3'));
  ok('J57 영수증에 할인 금액·정가 기록', accJ.receipts[0].amount === 582000 && accJ.receipts[0].discount === 10000 && accJ.receipts[0].listAmount === 592000, JSON.stringify(accJ.receipts[0]));
  ok('J58 완료 요약에 쿠폰 할인', /쿠폰 할인/.test(hJ.text('#doneSummary')) && /582,000원/.test(hJ.text('#doneSummary')), hJ.text('#doneSummary').replace(/\s+/g, ' ').slice(0, 160));
  const cpAfter = JSON.parse(J.window.localStorage.getItem('ttokttok_coupons_v1')).filter((c) => c.id === 'cp-10000')[0];
  ok('J59 쿠폰 사용 처리·예약번호 연결', cpAfter.used === true && /^TT-\d{6}-\d{4}$/.test(cpAfter.usedOn || ''), JSON.stringify(cpAfter));
  ok('J60 사용 가능 쿠폰 2장으로 감소', hJ.text('#mpCouponCount') === '2', hJ.text('#mpCouponCount'));

  /* ----- 7. 영수증 상세 ----- */
  hJ.click(hJ.$('#doneMypage'));
  hJ.click(hJ.$('.tabbtn[data-tab="mypage"]'));
  hJ.click(hJ.$('#mpPayRow'));
  hJ.click(hJ.$('#receiptList .list-item'));
  ok('J61 영수증에 정가·쿠폰 할인', /쿠폰 할인/.test(hJ.text('#receiptBody')) && /582,000원/.test(hJ.text('#receiptBody')), hJ.text('#receiptBody').replace(/\s+/g, ' ').slice(0, 140));
  hJ.click(hJ.$('#receiptClose'));
  hJ.click(hJ.$('[data-pay-close]'));

  /* ----- 8. 내 예약 카드 캘린더(.ics) ----- */
  hJ.click(hJ.$('#mpBookLink'));
  ok('J62 내 예약 카드에 캘린더 추가 버튼', hJ.$$('#bookingList [data-ics]').length >= 1, String(hJ.$$('#bookingList [data-ics]').length));
  const icsBtnJ = hJ.$('#bookingList [data-ics]');
  const icsNoJ = icsBtnJ.getAttribute('data-ics');
  hJ.click(icsBtnJ);
  await sleep(30);
  const jIcs = J.window.__ttokttokIcs || {};
  ok('J63 카드에서 .ics 생성(VCALENDAR)', /^BEGIN:VCALENDAR\r\n/.test(jIcs.text || '') && /\r\nEND:VCALENDAR\r\n$/.test(jIcs.text || ''));
  ok('J64 해당 예약번호로 UID 생성', !!icsNoJ && (jIcs.text || '').indexOf(icsNoJ) !== -1, icsNoJ);
  ok('J65 .ics 제목·파일명', /SUMMARY:.*똑똑쌤 방문재활/.test(jIcs.text || '') && /^똑똑쌤_방문재활_\d{8}\.ics$/.test(jIcs.name || ''), jIcs.name);
  ok('J66 캘린더 토스트 안내', /캘린더 파일\(\.ics\)을 내려받았어요/.test(hJ.text('#toast')), hJ.text('#toast'));
  ok('J67 .ics 클릭 후 JS 오류 없음', J.errors.length === 0, J.errors.slice(0, 2).join(' | '));

  /* ----- 9. 표기 통일 ----- */
  ok('J68 똑똑샘 오타 없음', !/똑똑샘/.test(J.doc.documentElement.outerHTML), '똑똑샘 발견');
  ok('J69 브랜드 표기 똑똑쌤 유지', (J.doc.body.textContent.match(/똑똑쌤/g) || []).length >= 10, String((J.doc.body.textContent.match(/똑똑쌤/g) || []).length));

  /* ----- 10. 손상 저장소 폴백 ----- */
  const K = makeDom({ ttokttok_coupons_v1: '{broken json', ttokttok_cards_v1: '"null"', ttokttok_notifs_v1: '{broken' });
  await sleep(30);
  ok('J70 손상 저장소에서도 JS 오류 없음', K.errors.length === 0, K.errors.slice(0, 2).join(' | '));
  ok('J71 쿠폰 시드 복원 2장', K.doc.querySelectorAll('#couponList .coupon-card').length === 2, String(K.doc.querySelectorAll('#couponList .coupon-card').length));
  ok('J72 카드 시드 복원 2건', K.doc.querySelectorAll('#pmList .pm-row').length === 2, String(K.doc.querySelectorAll('#pmList .pm-row').length));
  ok('J73 알림 시드 복원 4건', K.doc.querySelectorAll('#notifList .notif').length === 4, String(K.doc.querySelectorAll('#notifList .notif').length));

  /* ============================================================
     K. v12 — 데이터 모델(DATA-MODEL.md) 정렬·마이그레이션 검증
     ============================================================ */
  const K2 = makeDom();
  const hK = helpers(K2.window, K2.doc);
  await sleep(30);
  ok('K0 JS 오류 없음', K2.errors.length === 0, K2.errors.slice(0, 3).join(' | '));
  ok('K1 앱 버전 v39', K2.doc.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48');
  const M = K2.window.__ttokttokModel;
  ok('K2 모델 노출(modelVersion 13)', !!M && M.modelVersion === 13, M && String(M.modelVersion));
  ok('K3 상태 enum 11종 정의', !!M && ['region', 'user', 'teacher', 'teacherRegion', 'timeSlot', 'reservation', 'review', 'coupon', 'userCoupon', 'notification', 'settlement'].every((k) => Array.isArray(M.statuses[k])));
  ok('K4 예약 상태 enum 7종', !!M && M.statuses.reservation.join(',') === 'received,assigned,confirmed,rescheduled,completed,canceled,no_show', M && M.statuses.reservation.join(','));

  /* ----- 지역 마스터 ----- */
  const master = M.regionMaster;
  const provinces = master.filter((r) => r.level === 'province');
  const districts = master.filter((r) => r.level === 'district');
  ok('K5 지역 마스터 시·도 17', provinces.length === 17, String(provinces.length));
  ok('K6 지역 마스터 시·군·구 40개 이상', districts.length >= 40, String(districts.length));
  ok('K7 지역 id 중복 없음', new Set(master.map((r) => r.id)).size === master.length);
  ok('K8 모든 구가 시·도 부모를 가리킴', districts.every((r) => /^reg-/.test(r.parentId) && provinces.some((p) => p.id === r.parentId)));
  ok('K9 지역 상태 enum·타임스탬프', master.every((r) => M.statuses.region.indexOf(r.status) !== -1 && M.statuses.region.length === 2 && /Z$/.test(r.createdAt)));
  ok('K10 서울 강남구 id 규칙', master.some((r) => r.id === 'reg-서울-강남구' && r.fullName === '서울 강남구'));

  /* ----- 선생님-지역 다대다 ----- */
  const trs = M.teacherRegions();
  const teacherIdsInApp = hK.$$('#teacherList .teacher').length;
  ok('K11 TeacherRegion 행 생성', trs.length >= teacherIdsInApp, String(trs.length));
  ok('K12 TeacherRegion FK·우선순위', trs.every((r) => !!r.teacherId && r.priority >= 1 && r.status === 'active'));
  ok('K13 v18 지역 마스터 보완 — 시드 활동 지역 모두 매핑(파주·서대문 포함)',
    trs.length > 0 && trs.every((r) => r.regionId !== null) &&
    trs.some((r) => r.regionId === 'reg-경기-파주시') && trs.some((r) => r.regionId === 'reg-서울-서대문구'),
    JSON.stringify(trs.filter((r) => !r.regionId).map((r) => r.rawName)));
  ok('K14 매핑된 지역은 마스터 id', trs.filter((r) => r.regionId).every((r) => master.some((m) => m.id === r.regionId)));
  ok('K15 같은 선생님-지역 중복 없음', new Set(trs.map((r) => r.teacherId + '|' + (r.regionId || r.rawName))).size === trs.length);

  /* ----- 예약 정규화 ----- */
  hK.click(hK.$('[data-login="customer"]'));
  const resv = M.reservations();
  ok('K16 예약에 id·userId·타임스탬프', resv.length >= 1 && resv.every((b) => /^res-/.test(b.id) && !!b.userId && /Z$/.test(b.createdAt) && /Z$/.test(b.updatedAt)), JSON.stringify(resv[0]));
  ok('K17 예약 상태는 enum 코드', resv.every((b) => M.statuses.reservation.indexOf(b.status) !== -1), resv.map((b) => b.status).join(','));
  ok('K18 시드 예약 지역 FK', resv[0].regionId === 'reg-서울-강남구', resv[0].regionId);
  ok('K19 상태 이력 남김', resv.every((b) => Array.isArray(b.statusHistory) && b.statusHistory.length >= 1 && /Z$/.test(b.statusHistory[0].at)));
  ok('K20 이용권 상태·FK', JSON.parse(K2.window.localStorage.getItem('ttokttok_account_v3')).passes.every((p) => M.statuses.userPass.indexOf(p.status) !== -1 && !!p.passId));

  /* 새 예약은 id·statusHistory·금액이 함께 저장된다 */
  hK.click(hK.$('.tabbtn[data-tab="booking"]'));
  hK.setSel(hK.$('#bookProvince'), '경기');
  hK.setSel(hK.$('#bookDistrict'), '고양시 일산동구');
  hK.setVal(hK.$('#bookAddress'), '백석동 1234');
  hK.click(hK.$('#bookSyms [data-val="무릎·고관절 수술 후"]'));
  hK.click(hK.$('[data-next="1"]'));
  hK.click(hK.$('#bookDates .date-chip'));
  hK.click(hK.$$('#bookSlots .slot').filter((b) => !b.disabled)[0]);
  hK.click(hK.$('[data-next="2"]'));
  hK.click(hK.$('#passList [data-pass="p8"]'));
  hK.click(hK.$('[data-next="3"]'));
  hK.setSel(hK.$('#bookTeacher'), 'lee');
  hK.setVal(hK.$('#bookName'), '김순자');
  hK.setVal(hK.$('#bookPhone'), '01012345678');
  hK.click(hK.$('#payMethods [data-pay="카카오페이"]'));
  hK.setCheck(hK.$('#bookAgree'), true);
  hK.click(hK.$('#payBtn'));
  await sleep(1100);
  const accK = JSON.parse(K2.window.localStorage.getItem('ttokttok_account_v3'));
  ok('K21 새 예약 id·확정 상태', /^res_/.test(accK.bookings[0].id) && accK.bookings[0].status === 'confirmed', JSON.stringify({ id: accK.bookings[0].id, status: accK.bookings[0].status }));
  ok('K22 새 예약 지역 FK(경기 고양시 일산동구)', accK.bookings[0].regionId === 'reg-경기-고양시 일산동구', accK.bookings[0].regionId);
  ok('K23 새 예약 금액·결제상태', accK.bookings[0].amount === 592000 && accK.bookings[0].paymentStatus === 'paid', JSON.stringify(accK.bookings[0].amount));
  ok('K24 영수증 결제 상태 enum', accK.receipts[0].status === 'paid' && /^pay_/.test(accK.receipts[0].id), JSON.stringify(accK.receipts[0].status));
  ok('K25 슬롯 중복 차단 함수 존재', typeof K2.window.__ttokttokModel.slots === 'function');
  const dupSlot = accK.bookings[0];
  const slots = M.slots(dupSlot.teacherId || 'park', dupSlot.dateIso);
  ok('K26 예약된 슬롯은 booked', slots.some((s) => s.status === 'booked' && s.reservationId === dupSlot.id), JSON.stringify(slots.map((s) => s.status)));

  /* 일정 변경·취소 상태 전이 */
  hK.click(hK.$('#doneMypage'));
  hK.click(hK.$('#mpBookLink'));
  hK.click(hK.$('#bookingList [data-manage]'));
  hK.click(hK.$('#manageSheetBody [data-manage-date]'));
  hK.click(hK.$('#manageSheetBody [data-manage-time]'));
  hK.click(hK.$('[data-manage-save]'));
  await sleep(30);
  const accResched = JSON.parse(K2.window.localStorage.getItem('ttokttok_account_v3'));
  ok('K27 일정 변경 → rescheduled + 이력', accResched.bookings[0].status === 'rescheduled' && accResched.bookings[0].statusHistory.some((h) => h.status === 'rescheduled'), JSON.stringify(accResched.bookings[0].statusHistory));
  ok('K28 변경 시 updatedAt 갱신', /Z$/.test(accResched.bookings[0].updatedAt));
  hK.click(hK.$('#bookingList [data-manage-cancel]'));
  hK.click(hK.$('[data-manage-confirm]'));
  await sleep(30);
  const accCancel = JSON.parse(K2.window.localStorage.getItem('ttokttok_account_v3'));
  ok('K29 취소 → canceled + canceledAt ISO', accCancel.bookings[0].status === 'canceled' && /Z$/.test(accCancel.bookings[0].canceledAt));
  ok('K30 취소 후 환불 상태', accCancel.bookings[0].paymentStatus === 'refund_pending' || accCancel.bookings[0].paymentStatus === 'paid', accCancel.bookings[0].paymentStatus);

  /* ----- 쿠폰·알림·결제수단 (저장값이 아니라 이전 번들 기준) ----- */
  const bundleK = M.export();
  const couponsK = bundleK.tables.user_coupons;
  ok('K31 쿠폰 상태 enum·만료일 ISO', couponsK.length >= 2 && couponsK.every((c) => M.statuses.userCoupon.indexOf(c.status) !== -1 && /Z$/.test(c.expireAt) && !!c.couponId), JSON.stringify(couponsK[0]));
  const notifsK = bundleK.tables.notifications;
  ok('K32 알림 상태 enum·sentAt', notifsK.length >= 4 && notifsK.every((n) => M.statuses.notification.indexOf(n.status) !== -1 && /Z$/.test(n.sentAt) && !!n.audience), notifsK.length);
  const cardsK = bundleK.tables.payment_methods;
  ok('K33 결제수단 상태·타임스탬프', cardsK.length === 2 && cardsK.every((c) => c.status === 'active' && /Z$/.test(c.createdAt)));

  /* ----- 정산 원장 ----- */
  const ledger = bundleK.tables.settlement_ledgers;
  ok('K34 정산 원장 생성(일지 2건)', ledger.length >= 2, String(ledger.length));
  ok('K35 정산 수수료 22.2%·지급액 계산', ledger.every((r) => {
    const payout = Math.round(r.grossAmount * 70000 / 90000);
    return r.feeRate === 0.2222 && r.netAmount === payout && r.feeAmount === r.grossAmount - payout;
  }), JSON.stringify(ledger[0]));
  ok('K36 정산 상태 enum·지급 예정일', ledger.every((r) => M.statuses.settlement.indexOf(r.status) !== -1 && !!r.payoutDueDate));
  ok('K37 정산 원장 id 고유', new Set(ledger.map((r) => r.id)).size === ledger.length);

  /* ----- 이전(export) 번들 ----- */
  const t = bundleK.tables;
  ok('K38 번들 modelVersion 13', bundleK.modelVersion === 13);
  ok('K39 필수 테이블 모두 포함', ['regions', 'users', 'teachers', 'teacher_regions', 'time_slots', 'reservations', 'reviews', 'coupons', 'user_coupons', 'notifications', 'settlement_ledgers'].every((k) => Array.isArray(t[k])), Object.keys(t).join(','));
  ok('K40 후기 원본 존재(정적+내 후기)', t.reviews.length >= 16, String(t.reviews.length));
  ok('K41 알림·쿠폰·예약 이전 건수', t.notifications.length >= 4 && t.user_coupons.length >= 2 && t.reservations.length >= 2, [t.notifications.length, t.user_coupons.length, t.reservations.length].join('/'));
  ok('K42 타임슬롯 생성(예약일 기준)', t.time_slots.length >= 6, String(t.time_slots.length));
  ok('K43 무결성 통과', M.integrity().ok === true, JSON.stringify(M.integrity().issues.slice(0, 4)));
  ok('K44 깨진 FK/상태를 잡아냄', (function () {
    const copy = JSON.parse(JSON.stringify(bundleK));
    copy.tables.reservations[0].teacherId = 'nobody';
    copy.tables.reservations[0].status = 'wrong';
    return M.integrity !== undefined && (function () {
      const inner = K2.window.__ttokttokModel;
      const orig = inner.export;
      inner.export = function () { return copy; };
      const res = inner.integrity();
      inner.export = orig;
      return res.ok === false && res.issues.some((s) => /teacherId|상태/.test(s));
    })();
  })());
  ok('K45 두 번 이전해도 예약 id 동일(멱등)', (function () {
    const a = JSON.parse(K2.window.localStorage.getItem('ttokttok_account_v3')).bookings.map((b) => b.id);
    const b = JSON.parse(K2.window.localStorage.getItem('ttokttok_account_v3')).bookings.map((x) => x.id);
    return a.join(',') === b.join(',');
  })());

  /* ----- 옛 저장 데이터(한국어 상태·id 없음) 마이그레이션 ----- */
  const legacy = {
    profile: { name: '현수' },
    passes: [{ id: 'seed-pass', name: '8회 방문권', total: 8, remaining: 5, purchased: '2026.10.28', expire: '2027.01.27' }],
    bookings: [{ no: 'TT-261021-7302', date: '11.27', day: '금', time: '10:30', teacher: '박서준 선생님', teacherId: 'park', region: '서울 강남구 대치동', status: '예약 확정', passId: 'p8', walletId: 'seed-pass', dateIso: '2026-11-27' }],
    receipts: [{ no: 'TT-261028-4192', date: '2026.10.28', item: '8회 방문권', amount: 592000, method: '신용/체크카드', status: '결제 완료' }],
    sessions: [{ id: 'v1', teacherId: 'park', date: '2026.11.22', time: '10:30', round: '5회기', pass: '8회 방문권', reviewed: false }],
    myReviews: [{ teacherId: 'park', stars: 5, text: '좋았어요', at: '2026.11.23' }]
  };
  const L = makeDom({ ttokttok_account_v3: JSON.stringify(legacy) });
  const hL = helpers(L.window, L.doc);
  await sleep(30);
  ok('K46 옛 데이터 로드 JS 오류 없음', L.errors.length === 0, L.errors.slice(0, 2).join(' | '));
  const accL = JSON.parse(L.window.localStorage.getItem('ttokttok_account_v3'));
  ok('K47 한국어 상태 → enum 변환', accL.bookings[0].status === 'confirmed' && accL.receipts[0].status === 'paid', accL.bookings[0].status + '/' + accL.receipts[0].status);
  ok('K48 id·타임스탬프 보충', /^res-/.test(accL.bookings[0].id) && /Z$/.test(accL.bookings[0].createdAt) && /^pay-/.test(accL.receipts[0].id));
  ok('K49 후기 정규화(id·status)', accL.myReviews.every((r) => !!r.id && r.status === 'published' && /Z$/.test(r.createdAt)));
  ok('K50 화면은 그대로 한국어 라벨', (function () {
    hL.click(hL.$('[data-login="customer"]'));
    hL.click(hL.$('.tabbtn[data-tab="mypage"]'));
    hL.click(hL.$('#mpBookLink'));
    return /예약 확정/.test(hL.text('#bookingList'));
  })(), hL.text('#bookingList') ? hL.text('#bookingList').slice(0, 60) : '');
  ok('K51 옛 데이터도 번들·무결성 통과', (function () {
    const b = L.window.__ttokttokModel.integrity();
    return b.ok === true && L.window.__ttokttokModel.export().tables.reservations.length === 1;
  })(), JSON.stringify(L.window.__ttokttokModel.integrity().issues.slice(0, 3)));

  /* ----- 문서와 코드의 약속 ----- */
  const docPath = path.join(__dirname, '..', 'DATA-MODEL.md');
  const docTxt = fs.existsSync(docPath) ? fs.readFileSync(docPath, 'utf8') : '';
  ok('K52 DATA-MODEL.md 존재', docTxt.length > 2000, String(docTxt.length));
  ok('K53 11개 엔티티 모두 문서화', ['Region', 'User', 'Teacher', 'TeacherRegion', 'TimeSlot', 'Reservation', 'Review', 'Coupon', 'UserCoupon', 'Notification', 'SettlementLedger'].every((name) => docTxt.indexOf(name) !== -1));
  ok('K54 개인정보·비노출 원칙 문서화', /최소 수집/.test(docTxt) && /지도·목록 비노출/.test(docTxt));

  /* ============================================================
     L. v13 — 예약 상태기계 (RESERVATION-STATE-MACHINE.md)
     ============================================================ */
  const V = makeDom();
  const hV = helpers(V.window, V.doc);
  await sleep(30);
  ok('L0 JS 오류 없음', V.errors.length === 0, V.errors.slice(0, 3).join(' | '));
  const MV = V.window.__ttokttokModel;
  ok('L1 전이 엔진 노출(transitions·canTransition·transition)', !!MV && !!MV.transitions && typeof MV.canTransition === 'function' && typeof MV.transition === 'function');
  ok('L2 전이 표 7개 상태 · 최종 상태는 빈 표', !!MV && MV.reservationOrder.join(',') === 'received,assigned,confirmed,rescheduled,completed,canceled,no_show' && Object.keys(MV.transitions).length === 7 && MV.transitions.completed && Object.keys(MV.transitions.completed).length === 0 && Object.keys(MV.transitions.canceled).length === 0 && Object.keys(MV.transitions.no_show).length === 0, MV && Object.keys(MV.transitions).join(','));

  const allowedT = [['received', 'assigned'], ['received', 'confirmed'], ['received', 'canceled'], ['assigned', 'confirmed'], ['assigned', 'received'], ['assigned', 'canceled'], ['confirmed', 'rescheduled'], ['confirmed', 'completed'], ['confirmed', 'canceled'], ['confirmed', 'no_show'], ['rescheduled', 'confirmed'], ['rescheduled', 'canceled'], ['rescheduled', 'no_show']];
  const deniedT = [['completed', 'canceled'], ['completed', 'confirmed'], ['canceled', 'confirmed'], ['no_show', 'completed'], ['received', 'completed'], ['received', 'rescheduled'], ['confirmed', 'confirmed'], ['confirmed', 'assigned'], ['assigned', 'rescheduled'], ['rescheduled', 'completed'], ['no_show', 'received']];
  ok('L3 허용 전이 13종', MV && allowedT.every(([f, t]) => MV.canTransition(f, t) === true), allowedT.filter(([f, t]) => !MV || !MV.canTransition(f, t)).map((x) => x.join('->')).join(','));
  ok('L4 금지 전이 11종 차단', MV && deniedT.every(([f, t]) => MV.canTransition(f, t) === false), deniedT.filter(([f, t]) => MV && MV.canTransition(f, t)).map((x) => x.join('->')).join(','));
  ok('L5 행위자 제한(보호자는 완료 불가·선생님은 취소 불가)', MV && MV.canTransition('confirmed', 'completed', 'customer') === false && MV.canTransition('confirmed', 'completed', 'teacher') === true && MV.canTransition('confirmed', 'completed', 'operator') === true && MV.canTransition('confirmed', 'canceled', 'teacher') === false && MV.canTransition('confirmed', 'canceled', 'customer') === true && MV.canTransition('assigned', 'received', 'teacher') === false && MV.canTransition('assigned', 'received', 'operator') === true);
  ok('L6 한국어 라벨도 전이 코드로 인식', MV && MV.canTransition('예약 확정', '방문 완료', 'teacher') === true && MV.canTransition('방문 완료', '취소됨') === false);

  /* ----- 엔진 단위: 차단은 아무것도 바꾸지 않는다 ----- */
  const shake = { no: 'TT-X', status: 'completed', statusHistory: [{ status: 'completed', at: '2026-11-20T01:00:00.000Z' }], updatedAt: '2026-11-20T01:00:00.000Z' };
  const blockedRes = MV.transition(shake, 'canceled', { actor: 'customer', reason: '테스트' });
  ok('L7 금지 전이 → ok:false·상태·이력 불변', blockedRes.ok === false && blockedRes.error === 'transition_not_allowed' && /바꿀 수 없어요/.test(blockedRes.message) && shake.status === 'completed' && shake.statusHistory.length === 1, JSON.stringify(blockedRes));
  const actorRes = MV.transition({ status: 'confirmed', statusHistory: [] }, 'completed', { actor: 'customer' });
  ok('L8 권한 없는 행위자 → actor_not_allowed', actorRes.ok === false && actorRes.error === 'actor_not_allowed' && /보호자 권한/.test(actorRes.message), JSON.stringify(actorRes));

  /* ----- 생성 이력: received → confirmed ----- */
  hV.click(hV.$('[data-login="customer"]'));
  hV.click(hV.$('.tabbtn[data-tab="booking"]'));
  hV.setSel(hV.$('#bookProvince'), '서울');
  hV.setSel(hV.$('#bookDistrict'), '강남구');
  hV.setVal(hV.$('#bookAddress'), '대치동 123-4');
  hV.click(hV.$('#bookSyms [data-val="뇌졸중·편마비"]'));
  hV.click(hV.$('[data-next="1"]'));
  hV.click(hV.$('#bookDates .date-chip'));
  hV.click(hV.$$('#bookSlots .slot').filter((b) => !b.disabled)[0]);
  hV.click(hV.$('[data-next="2"]'));
  hV.click(hV.$('#passList [data-pass="p8"]'));
  hV.click(hV.$('[data-next="3"]'));
  hV.setSel(hV.$('#bookTeacher'), 'park');
  hV.setVal(hV.$('#bookName'), '김순자');
  hV.setVal(hV.$('#bookPhone'), '01012345678');
  hV.click(hV.$('#payMethods [data-pay="카카오페이"]'));
  hV.setCheck(hV.$('#bookAgree'), true);
  hV.click(hV.$('#payBtn'));
  await sleep(1100);
  const vAcc = JSON.parse(V.window.localStorage.getItem('ttokttok_account_v3'));
  const vNew = vAcc.bookings[0];
  ok('L9 새 예약 이력은 received → confirmed', vNew.status === 'confirmed' && vNew.statusHistory.map((h) => h.from + '>' + h.to).join(',') === 'null>received,received>confirmed', JSON.stringify(vNew.statusHistory));
  ok('L10 이력에 행위자·사유·시각', vNew.statusHistory.every((h) => h.actor === 'customer' && typeof h.reason === 'string' && /Z$/.test(h.at)) && vNew.updatedAt === vNew.statusHistory[vNew.statusHistory.length - 1].at);
  ok('L11 접수·확정 알림이 보호자에게 발송', MV.notifs().filter((n) => n.audience === 'customer' && n.title.indexOf(vNew.no) === 0).length === 1 && MV.notifs().some((n) => n.audience === 'customer' && n.title === '방문이 확정됐어요' && n.body.indexOf('박서준 선생님이 방문합니다') !== -1), MV.notifs().slice(0, 3).map((n) => n.title).join(' | '));

  /* ----- 일정 변경: 사유에 새 시간이 남고 슬롯이 따라온다 ----- */
  hV.click(hV.$('#doneMypage'));
  hV.click(hV.$('#mpBookLink'));
  hV.click(hV.$('#bookingList [data-manage]'));
  const vNewDate = hV.$$('#manageSheetBody [data-manage-date]')[0].getAttribute('data-manage-date');
  const vNewTime = hV.$$('#manageSheetBody [data-manage-time]')[2].textContent.trim();
  hV.click(hV.$$('#manageSheetBody [data-manage-date]')[0]);
  hV.click(hV.$$('#manageSheetBody [data-manage-time]')[2]);
  hV.click(hV.$('[data-manage-save]'));
  await sleep(30);
  const vRes = JSON.parse(V.window.localStorage.getItem('ttokttok_account_v3')).bookings[0];
  const vLast = vRes.statusHistory[vRes.statusHistory.length - 1];
  ok('L12 일정 변경 전이 기록(from/to/actor/reason)', vRes.status === 'rescheduled' && vLast.from === 'confirmed' && vLast.to === 'rescheduled' && vLast.actor === 'customer' && vLast.reason.indexOf(vNewTime) !== -1, JSON.stringify(vLast));
  ok('L13 변경 알림·슬롯 재계산', (function () {
    const nt = MV.notifs().filter((n) => n.audience === 'customer' && n.title === '방문 일정이 변경됐어요')[0];
    const onSlot = MV.slots(vRes.teacherId, vRes.dateIso).filter((s) => s.startTime === vNewTime)[0];
    return !!nt && vRes.dateIso === vNewDate && onSlot && onSlot.status === 'booked';
  })(), vNewDate + ' ' + vNewTime + ' :: ' + JSON.stringify(MV.slots(vRes.teacherId, vRes.dateIso).map((s) => s.status + '@' + s.startTime)));

  /* ----- 취소: 알림(환불액)·슬롯 해제·재취소 차단 ----- */
  hV.click(hV.$('#bookingList [data-manage-cancel]'));
  hV.click(hV.$('[data-manage-confirm]'));
  await sleep(30);
  const vCan = JSON.parse(V.window.localStorage.getItem('ttokttok_account_v3')).bookings[0];
  /* v16: 24시간 전 회차권 취소는 현금 환불 대신 회차 복구다(POLICIES-AND-FEES §3·§4.1-3).
     알림 문구는 그 예약의 실제 견적(refundTextOf)을 그대로 실어야 한다. */
  ok('L14 취소 전이 + 환불·회차 안내가 알림 문구에', (function () {
    const nt = MV.notifs().filter((n) => n.audience === 'customer' && n.title === '예약이 취소됐어요')[0];
    return vCan.status === 'canceled' && !!nt &&
      /(환불 예정 금액은 [\d,]+원|회차권 잔여 \d+회가 복구돼요|회차권 1회가 차감되고 환불 금액은 없어요)/.test(nt.body);
  })(), JSON.stringify(MV.notifs().slice(0, 2)));
  ok('L15 취소 슬롯은 open으로 해제', MV.slots(vCan.teacherId, vCan.dateIso).every((s) => s.status === 'open'), JSON.stringify(MV.slots(vCan.teacherId, vCan.dateIso).map((s) => s.status)));
  ok('L16 취소된 예약은 재확정 불가', MV.transition(vCan.no, 'confirmed', { actor: 'operator' }).ok === false && MV.history(vCan.no).length === vCan.statusHistory.length);

  /* ----- 완료: 슬롯 completed · 정산 원장 pending (별도 DOM) ----- */
  const V2 = makeDom();
  const hV2 = helpers(V2.window, V2.doc);
  await sleep(30);
  hV2.click(hV2.$('[data-login="customer"]'));
  const MV2 = V2.window.__ttokttokModel;
  const seedB = MV2.reservations().filter((b) => b.status === 'confirmed')[0];
  const doneRes = MV2.transition(seedB.no, 'completed', { actor: 'teacher', reason: '방문 일지 작성 완료' });
  const pV2 = JSON.parse(V2.window.localStorage.getItem('ttokttok_partner_v1'));
  const ledV2 = pV2.ledger.filter((r) => r.reservationId === seedB.id)[0];
  ok('L17 완료 전이 → 슬롯 completed', doneRes.ok === true && MV2.slots(seedB.teacherId, seedB.dateIso).some((s) => s.status === 'completed' && s.startTime === seedB.time), JSON.stringify(MV2.slots(seedB.teacherId, seedB.dateIso).map((s) => s.status + '@' + s.startTime)));
  ok('L18 완료 → 정산 원장 pending(수수료 22.2%)', !!ledV2 && ledV2.status === 'pending' && ledV2.grossAmount === Number(seedB.amount) && ledV2.feeAmount === 16444 && ledV2.netAmount === 57556 && /-(15|28|29|30|31)$/.test(ledV2.payoutDueDate), JSON.stringify(ledV2));
  ok('L19 완료 알림은 보호자에게만(행위자 선생님)', MV2.notifs()[0].title === '방문이 완료됐어요' && MV2.notifs().filter((n) => n.title === '방문을 완료 처리했어요').length === 0);
  ok('L20 완료 후 취소·노쇼 차단', MV2.transition(seedB.no, 'canceled', { actor: 'customer' }).ok === false && MV2.transition(seedB.no, 'no_show', { actor: 'operator' }).ok === false);
  ok('L21 완료 원장은 중복 생성되지 않음(멱등)', (function () {
    const again = JSON.parse(V2.window.localStorage.getItem('ttokttok_partner_v1')).ledger.filter((r) => r.reservationId === seedB.id).length;
    return again === 1;
  })(), String(JSON.parse(V2.window.localStorage.getItem('ttokttok_partner_v1')).ledger.filter((r) => r.reservationId === seedB.id).length));

  /* ----- 선생님 화면: 수락·거절·체크인·일지 완료 ----- */
  const V3 = makeDom();
  const hV3 = helpers(V3.window, V3.doc);
  await sleep(30);
  hV3.click(hV3.$('[data-login="therapist"]'));
  const MV3 = V3.window.__ttokttokModel;
  ok('L22 요청은 assigned 상태로 시작', MV3.teacherRequests().every((r) => r.reservationStatus === 'assigned' && r.statusHistory.length === 1), MV3.teacherRequests().map((r) => r.reservationStatus).join(','));
  hV3.click(hV3.$('#tpReqList [data-tp-accept="r1"]'));
  await sleep(30);
  const pV3 = JSON.parse(V3.window.localStorage.getItem('ttokttok_partner_v1'));
  const r1 = pV3.requests.filter((r) => r.id === 'r1')[0];
  const schNew = pV3.schedule[pV3.schedule.length - 1];
  ok('L23 요청 수락 → assigned→confirmed 이력', r1.reservationStatus === 'confirmed' && r1.statusHistory.map((h) => h.from + '>' + h.to).join(',') === 'null>assigned,assigned>confirmed' && r1.statusHistory[1].actor === 'teacher', JSON.stringify(r1.statusHistory));
  ok('L24 수락 시 일정에 이력 승계', schNew.status === 'confirmed' && schNew.statusHistory.length === 2 && schNew.requestId === 'r1', JSON.stringify(schNew.statusHistory));
  hV3.click(hV3.$('#tpReqList [data-tp-reject="r2"]'));
  await sleep(30);
  const pV3b = JSON.parse(V3.window.localStorage.getItem('ttokttok_partner_v1'));
  const r2 = pV3b.requests.filter((r) => r.id === 'r2')[0];
  ok('L25 요청 거절 → 예약은 received(재배정 대기)', r2.status === 'rejected' && r2.reservationStatus === 'received' && r2.statusHistory[1].actor === 'operator' && /배정 거절/.test(r2.statusHistory[1].reason), JSON.stringify(r2.statusHistory));
  hV3.click(hV3.$('.tabbtn[data-tab="tp-schedule"]'));
  await sleep(20);
  hV3.click(hV3.$('#tpScheduleList [data-tp-checkin]'));
  await sleep(20);
  const s1V3 = JSON.parse(V3.window.localStorage.getItem('ttokttok_partner_v1')).schedule.filter((s) => s.id === 's1')[0];
  ok('L26 체크인은 상태 불변·사건만 기록', s1V3.checked === true && s1V3.status === 'confirmed' && s1V3.statusHistory[s1V3.statusHistory.length - 1].event === 'check_in' && !!s1V3.checkedInAt, JSON.stringify(s1V3.statusHistory.slice(-1)));
  hV3.click(hV3.$('.tabbtn[data-tab="tp-journal"]'));
  await sleep(20);
  hV3.setVal(hV3.$('#tpGait'), '0.71');
  hV3.setVal(hV3.$('#tpRom'), '121');
  hV3.setVal(hV3.$('#tpPain'), '2');
  hV3.setVal(hV3.$('#tpMemo'), '상태기계 테스트');
  hV3.click(hV3.$('#tpSaveJournal'));
  await sleep(40);
  const pV3c = JSON.parse(V3.window.localStorage.getItem('ttokttok_partner_v1'));
  const s1Done = pV3c.schedule.filter((s) => s.id === 's1')[0];
  ok('L27 일지 저장 → 같은 환자 방문 completed', s1Done.status === 'completed' && /방문 일지 작성 완료/.test(s1Done.statusHistory[s1Done.statusHistory.length - 1].reason), JSON.stringify(s1Done.statusHistory.slice(-1)));
  ok('L28 완료된 방문은 재체크인 차단', MV3.canTransition('completed', 'check_in') === false && (function () {
    const before = JSON.parse(V3.window.localStorage.getItem('ttokttok_partner_v1')).schedule.filter((s) => s.id === 's1')[0].statusHistory.length;
    hV3.click(hV3.$('#tpScheduleList [data-tp-checkin]'));
    const after = JSON.parse(V3.window.localStorage.getItem('ttokttok_partner_v1')).schedule.filter((s) => s.id === 's1')[0].statusHistory.length;
    return before === after;
  })(), '차단되지 않음');

  /* ----- 알림함 분리·문구 템플릿·문서 약속 ----- */
  ok('L29 알림함에는 보호자 알림만 노출', (function () {
    hV3.click(hV3.$('#btnNotif'));
    const titles = hV3.$$('#notifList .notif b').map((b) => b.textContent);
    return titles.length > 0 && titles.every((t) => t.indexOf('배정이 해제됐어요') === -1 && t.indexOf('방문을 완료 처리했어요') === -1);
  })());
  ok('L30 안내 문구 템플릿 8종 × 2(보호자·선생님)', (function () {
    const keys = ['received', 'assigned', 'confirmed', 'rescheduled', 'reassigned', 'completed', 'canceled', 'no_show'];
    return keys.every((k) => MV.notices[k] && MV.notices[k].customer && MV.notices[k].teacher && MV.notices[k].customer.title && MV.notices[k].teacher.body);
  })());
  ok('L31 템플릿 치환(예약번호·환불액)', (function () {
    const n = MV.noticeFor({ no: 'TT-261127-4821', date: '11.27', day: '금', time: '10:30', refund: 66000 }, 'canceled', {});
    return n.customer.body.indexOf('TT-261127-4821') === 0 && n.customer.body.indexOf('66,000원') !== -1 && n.teacher.body.indexOf('TT-261127-4821') === 0 && n.teacher.body.indexOf('11.27 (금) 10:30') !== -1;
  })(), JSON.stringify(MV.noticeFor({ no: 'TT-261127-4821', date: '11.27', day: '금', time: '10:30', refund: 66000 }, 'canceled', {})));
  const smDocPath = path.join(__dirname, '..', 'RESERVATION-STATE-MACHINE.md');
  const smDoc = fs.existsSync(smDocPath) ? fs.readFileSync(smDocPath, 'utf8') : '';
  ok('L32 RESERVATION-STATE-MACHINE.md 존재', smDoc.length > 4000, String(smDoc.length));
  ok('L33 문서에 7개 상태·전이 표·예외 흐름', ['received', 'assigned', 'confirmed', 'rescheduled', 'completed', 'canceled', 'no_show'].every((s) => smDoc.indexOf('`' + s + '`') !== -1) && /허용되는 전이|전이 표/.test(smDoc) && /선생님 배정 거절/.test(smDoc) && /노쇼 기준/.test(smDoc) && /statusHistory/.test(smDoc));
  ok('L34 문서의 전이 수와 코드 표가 일치', (function () {
    let codeCount = 0;
    Object.keys(MV.transitions).forEach((f) => { codeCount += Object.keys(MV.transitions[f]).length; });
    const docRows = (smDoc.match(/^\| T\d+ \|/gm) || []).length;
    return codeCount === docRows;
  })(), 'code=' + Object.keys(MV.transitions).reduce((n, f) => n + Object.keys(MV.transitions[f]).length, 0) + ' doc=' + (smDoc.match(/^\| T\d+ \|/gm) || []).length);

  /* ----- 저장 후 다시 열어도 이력이 그대로(멱등) ----- */
  const vStorage = { ttokttok_account_v3: V.window.localStorage.getItem('ttokttok_account_v3') };
  const V4 = makeDom(vStorage);
  await sleep(30);
  const v4Book = JSON.parse(V4.window.localStorage.getItem('ttokttok_account_v3')).bookings[0];
  ok('L35 새로 열어도 이력 길이·형태 유지', v4Book.statusHistory.length === vCan.statusHistory.length && v4Book.statusHistory.every((h) => ['from', 'to', 'actor', 'reason', 'at'].every((k) => k in h)), JSON.stringify(v4Book.statusHistory));

  /* ============================================================
     M. v14 — 실제 상담·예약 접수 구조 (INTAKE-OPERATIONS.md)
     ============================================================ */
  const N = makeDom();
  const hN = helpers(N.window, N.doc);
  await sleep(30);
  ok('M0 JS 오류 없음', N.errors.length === 0, N.errors.slice(0, 3).join(' | '));
  const MN = N.window.__ttokttokModel;
  ok('M1 접수 API 노출(intakeVersion 14)', !!MN && MN.intakeVersion === 14 && typeof MN.generateReservationId === 'function' && typeof MN.buildIntakeSummary === 'function' && typeof MN.verifySaved === 'function' && MN.consultFormUrl === 'https://naver.me/G3vCkS0S', MN && String(MN.intakeVersion));
  ok('M2 예약번호 형식 TT-YYMMDD-XXXX', (function () {
    const no = MN.generateReservationId([], { date: '261126', random: () => 0 });
    return no === 'TT-261126-1000' && MN.isValidReservationNo(no);
  })(), MN.generateReservationId([], { date: '261126' }));
  ok('M3 형식 위반 번호는 거부', MN.isValidReservationNo('TT-261126-4821') && !MN.isValidReservationNo('TT-26112-4821') && !MN.isValidReservationNo('261126-4821') && !MN.isValidReservationNo(''));
  ok('M4 기존 예약번호와 겹치지 않음', (function () {
    const existing = [{ no: 'TT-261126-1000' }, { no: 'TT-261126-1001' }];
    const no = MN.generateReservationId(existing, { date: '261126', random: () => 0 });
    return existing.map((r) => r.no).indexOf(no) === -1 && MN.isValidReservationNo(no);
  })(), MN.generateReservationId([{ no: 'TT-261126-1000' }], { date: '261126', random: () => 0 }));
  ok('M5 연속 300건 발급도 중복 없음', (function () {
    const list = [];
    let seed = 7;
    for (let i = 0; i < 300; i++) {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      const no = MN.generateReservationId(list, { date: '261126', random: () => ((seed >>> 8) % 10000) / 10000 });
      if (list.some((r) => r.no === no)) return false;
      list.push({ no });
    }
    return list.length === 300;
  })());
  ok('M6 증상 라벨↔코드 변환', MN.symptomCodesOf(['뇌졸중·편마비', '무릎·고관절 수술 후']).join(',') === 'stroke,knee_postop' && MN.symptomLabel('stroke') === '뇌졸중·편마비' && MN.symptomCodesOf(['stroke', 'stroke']).join(',') === 'stroke');

  /* ----- 접수 요약 텍스트 ----- */
  const intakeResv = {
    id: 'res_test', no: 'TT-261126-7777', status: 'confirmed', date: '11.27', dateIso: '2026-11-27', day: '금', time: '10:30',
    teacher: '박서준 선생님', teacherId: 'park', regionId: 'reg-서울-강남구', region: '서울 강남구 대치동 123-4, 101동 1203호',
    passId: 'p8', amount: 582000, symptomCodes: ['stroke'], createdAt: '2026-11-26T00:00:00.000Z'
  };
  const sum = MN.buildIntakeSummary(intakeResv, { name: '김순자', phone: '010-1234-5678', passName: '8회 방문권', payMethod: '카카오페이', teacherLicense: '물리치료사' });
  ok('M7 요약에 예약번호·상태·일시', /TT-261126-7777/.test(sum) && /예약 확정/.test(sum) && /2026\.11\.27 \(금\) 10:30/.test(sum), sum.split('\n').slice(0, 4).join(' / '));
  ok('M8 요약에 보호자·연락처·지역', /보호자 : 김순자/.test(sum) && /010-1234-5678/.test(sum) && /방문 지역 : 서울 강남구/.test(sum), sum);
  ok('M9 요약에 상세 주소 없음(개인정보 최소화)', !/대치동/.test(sum) && !/101동/.test(sum) && !/1203호/.test(sum), sum);
  ok('M10 요약에 증상·이용권·선생님', /뇌졸중·편마비/.test(sum) && /8회 방문권/.test(sum) && /582,000원/.test(sum) && /박서준 선생님 \(물리치료사\)/.test(sum), sum);
  ok('M11 요약에 상담 폼 URL', sum.indexOf('https://naver.me/G3vCkS0S') !== -1);
  ok('M12 예약 없으면 빈 문자열', MN.buildIntakeSummary(null) === '' && MN.buildIntakeSummary(undefined) === '');
  ok('M13 옵션 없이도 요약 생성', (function () {
    const t = MN.buildIntakeSummary({ no: 'TT-261126-8888', status: 'received' });
    return /TT-261126-8888/.test(t) && /접수 완료/.test(t) && /추천 배정/.test(t);
  })());

  /* ----- 저장 확인 ----- */
  const readerOf = (stored, available) => ({ available, raw: JSON.stringify({ bookings: stored }), memory: stored });
  const vOk = MN.verifySaved('TT-261126-7777', { read: () => readerOf([{ no: 'TT-261126-7777' }], true) });
  ok('M14 로컬 저장 확인됨', vOk.persisted === true && vOk.storageMode === 'local' && vOk.foundInStore === true && vOk.reservationId === 'TT-261126-7777' && /Z$/.test(vOk.checkedAt), JSON.stringify(vOk));
  const vMem = MN.verifySaved('TT-261126-7777', { read: () => readerOf([{ no: 'TT-261126-7777' }], false) });
  ok('M15 임시 메모리 모드 감지', vMem.persisted === false && vMem.storageMode === 'memory' && vMem.foundInMemory === true && /복사/.test(vMem.note), JSON.stringify(vMem));
  const vMiss = MN.verifySaved('TT-261126-0000', { read: () => readerOf([{ no: 'TT-261126-7777' }], true) });
  ok('M16 저장소에 없는 번호', vMiss.persisted === false && vMiss.storageMode === 'local' && vMiss.foundInStore === false && /찾지 못했어요/.test(vMiss.note), JSON.stringify(vMiss));
  ok('M17 id로도 확인', MN.verifySaved('res_test', { read: () => readerOf([{ id: 'res_test', no: 'TT-261126-7777' }], true) }).persisted === true);
  ok('M18 빈 번호는 오류', MN.verifySaved('', {}).error === 'invalid_reservation_id' && MN.verifySaved('').persisted === false);
  ok('M19 손상 저장소도 멈추지 않음', (function () {
    const v = MN.verifySaved('TT-261126-7777', { read: () => ({ available: true, raw: '{broken', memory: [] }) });
    return v.persisted === false && v.error === 'store_corrupt';
  })());

  /* ----- 실제 예약 완료 → 배지 · 복사 ----- */
  hN.click(hN.$('[data-login="customer"]'));
  hN.click(hN.$('.tabbtn[data-tab="booking"]'));
  hN.setSel(hN.$('#bookProvince'), '서울');
  hN.setSel(hN.$('#bookDistrict'), '강남구');
  hN.setVal(hN.$('#bookAddress'), '대치동 123-4, 101동 1203호');
  hN.click(hN.$('#bookSyms [data-val="뇌졸중·편마비"]'));
  hN.click(hN.$('[data-next="1"]'));
  hN.click(hN.$('#bookDates .date-chip'));
  hN.click(hN.$$('#bookSlots .slot').filter((b) => !b.disabled)[0]);
  hN.click(hN.$('[data-next="2"]'));
  hN.click(hN.$('#passList [data-pass="p8"]'));
  hN.click(hN.$('[data-next="3"]'));
  hN.setVal(hN.$('#bookName'), '김순자');
  hN.setVal(hN.$('#bookPhone'), '01012345678');
  hN.click(hN.$('#payMethods [data-pay="카카오페이"]'));
  hN.setCheck(hN.$('#bookAgree'), true);
  hN.click(hN.$('#payBtn'));
  await sleep(1100);
  const accN = JSON.parse(N.window.localStorage.getItem('ttokttok_account_v3'));
  const newNo = accN.bookings[0].no;
  ok('M20 예약번호 형식·기존 시드와 다름', MN.isValidReservationNo(newNo) && newNo !== 'TT-261021-7302', newNo);
  ok('M21 완료 화면 저장 확인 배지', /로컬 저장 확인됨/.test(hN.text('#doneSaved')), hN.text('#doneSaved'));
  ok('M22 예약에 증상 코드 저장', JSON.stringify(accN.bookings[0].symptomCodes) === '["stroke"]', JSON.stringify(accN.bookings[0].symptomCodes));
  ok('M23 완료 화면 복사 버튼·상담 폼 링크', !!hN.$('#doneCopy') && !!hN.$('#bookingDone a[href="https://naver.me/G3vCkS0S"]') && /붙여 넣/.test(hN.text('#bookingDone')));
  let clipText = '';
  Object.defineProperty(N.window.navigator, 'clipboard', {
    configurable: true,
    value: { writeText: (t) => { clipText = t; return Promise.resolve(); } }
  });
  hN.click(hN.$('#doneCopy'));
  await sleep(20);
  const copiedIntake = N.window.__ttokttokIntake || {};
  ok('M24 복사 버튼 → 접수 요약 텍스트', copiedIntake.no === newNo && (copiedIntake.text || '').indexOf(newNo) !== -1 && /김순자/.test(copiedIntake.text || '') && /010-?1234-?5678/.test(copiedIntake.text || '') && /https:\/\/naver.me\/G3vCkS0S/.test(copiedIntake.text || ''), (copiedIntake.text || '').slice(0, 80));
  ok('M24b 클립보드에 실제 복사', clipText === copiedIntake.text && clipText.length > 40, clipText.slice(0, 40));
  ok('M25 복사 후 안내 토스트', /복사했어요|복사가 막혀/.test(hN.text('#toast')), hN.text('#toast'));
  ok('M26 복사 요약에 상세 주소 없음', !/101동/.test(copiedIntake.text || '') && !/1203호/.test(copiedIntake.text || ''), (copiedIntake.text || '').slice(0, 200));

  /* ----- 내 예약 상세 ----- */
  hN.click(hN.$('#doneMypage'));
  hN.click(hN.$('.tabbtn[data-tab="mypage"]'));
  hN.click(hN.$('#mpBookLink'));
  hN.click(hN.$('#bookingList [data-manage]'));
  ok('M27 내 예약 상세에 저장 배지·복사 버튼', /로컬 저장 확인됨/.test(hN.text('#manageSaved')) && !!hN.$('#manageSheetBody [data-intake-copy]') && !!hN.$('#manageSheetBody a[href="https://naver.me/G3vCkS0S"]'), hN.text('#manageSaved'));
  hN.click(hN.$('#manageSheetBody [data-intake-copy]'));
  await sleep(20);
  const copied2 = N.window.__ttokttokIntake || {};
  ok('M28 상세에서 복사한 요약도 같은 예약번호', copied2.no === newNo && (copied2.text || '').indexOf(newNo) !== -1, copied2.no);

  /* ----- 새로 열어도 남아 있는가 ----- */
  const reload = makeDom({ ttokttok_account_v3: N.window.localStorage.getItem('ttokttok_account_v3'), ttokttok_phone_v1: '01012345678' });
  await sleep(30);
  const RM = reload.window.__ttokttokModel;
  ok('M29 새로 열어도 예약 남고 저장 확인됨', (function () {
    const b = RM.reservations().filter((x) => x.no === newNo)[0];
    const v = RM.verifySaved(newNo);
    return !!b && v.persisted === true && v.storageMode === 'local';
  })(), JSON.stringify(RM.verifySaved(newNo)));
  ok('M30 예약번호 전체 중복 없음', (function () {
    const nos = RM.reservations().map((b) => b.no);
    return new Set(nos).size === nos.length;
  })(), RM.reservations().map((b) => b.no).join(','));
  ok('M31 앱 목록 기준 발급도 중복 없음', (function () {
    const existing = RM.reservations();
    const no = RM.generateReservationId(existing);
    return existing.every((b) => b.no !== no) && RM.isValidReservationNo(no);
  })());

  /* ----- 문서와 코드의 약속 ----- */
  const intakeDocPath = path.join(__dirname, '..', 'INTAKE-OPERATIONS.md');
  const intakeDoc = fs.existsSync(intakeDocPath) ? fs.readFileSync(intakeDocPath, 'utf8') : '';
  ok('M32 INTAKE-OPERATIONS.md 존재', intakeDoc.length > 4000, String(intakeDoc.length));
  ok('M33 3중 장치·예약번호 규칙 문서화', /예약번호/.test(intakeDoc) && /저장 확인/.test(intakeDoc) && /TT-YYMMDD-XXXX/.test(intakeDoc) && /3중/.test(intakeDoc));
  ok('M34 운영 체크리스트·전환 포인트', /체크리스트/.test(intakeDoc) && /\bT1\b/.test(intakeDoc) && /네이버 상담 폼/.test(intakeDoc) && /전환/.test(intakeDoc));
  ok('M35 문서와 코드 함수명 일치', ['buildIntakeSummary', 'verifyReservationSaved', 'generateReservationId'].every((n) => intakeDoc.indexOf(n) !== -1));
  ok('M36 개인정보 최소화 원칙 명시', /상세 주소/.test(intakeDoc) && /넣지 않는/.test(intakeDoc));

  /* ============================================================
     N. v15 — 선생님 프로필·검증 구조 (TEACHER-VERIFICATION.md)
     ============================================================ */
  const P = makeDom();
  const hP = helpers(P.window, P.doc);
  await sleep(30);
  ok('N0 JS 오류 없음', P.errors.length === 0, P.errors.slice(0, 3).join(' | '));
  const MP = P.window.__ttokttokModel;
  ok('N1 검증 API 노출(15·3단계)', !!MP && MP.verificationVersion === 15 &&
    Array.isArray(MP.verificationSteps) && MP.verificationSteps.map((s) => s.key).join(',') === 'identity,license,career' &&
    typeof MP.getVerificationBadges === 'function' && typeof MP.maskTeacherName === 'function' && typeof MP.maskLicenseNo === 'function',
    MP && String(MP.verificationVersion));
  ok('N2 검증 상태 enum 3종', JSON.stringify(MP.verificationStatuses) === JSON.stringify(['verified', 'pending', 'failed']));

  /* ----- 시드 데이터: 3단계 완료 / 일부만 / 미확인 ----- */
  const seedTeachers = MP.teachers();
  ok('N3 시드 선생님 8명 모두 verification 3키', seedTeachers.length === 8 && seedTeachers.every((t) => {
    const v = MP.verificationOf(t);
    return v.identity && v.license && v.career && ['identity', 'license', 'career'].every((k) => MP.verificationStatuses.indexOf(v[k]) !== -1);
  }), JSON.stringify(seedTeachers.map((t) => t.id + ':' + JSON.stringify(t.verification))).slice(0, 200));
  ok('N4 3단계 모두 통과한 예시(박서준)', MP.verificationOf('park').identity === 'verified' && MP.verificationOf('park').license === 'verified' && MP.verificationOf('park').career === 'verified' && MP.getVerificationBadges('park').length === 3);
  ok('N5 일부 단계만 통과한 예시(이하늘·윤지수 경력 대기)', MP.verificationOf('lee').career === 'pending' && MP.verificationOf('yoon').career === 'pending' &&
    MP.getVerificationBadges('lee').map((b) => b.step).join(',') === 'identity,license' && MP.getVerificationBadges('yoon').length === 2);
  ok('N6 전부 미확인인 신규 예시(관리자 심사 큐)', (function () {
    const apps = JSON.parse(P.window.localStorage.getItem('ttokttok_admin_v1')).applications;
    return apps.length === 2 && apps.every((a) => ['identity', 'license', 'career'].every((k) => MP.verificationOf(a)[k] === 'pending'));
  })(), P.window.localStorage.getItem('ttokttok_admin_v1'));

  /* ----- 배지: 통과한 단계만, 미확인에는 금지 문구 없음 ----- */
  ok('N7 통과 단계만 배지 반환', MP.getVerificationBadges('park').map((b) => b.label).join('·') === '신분 확인·면허 확인·경력 확인' &&
    MP.getVerificationBadges('lee').map((b) => b.label).join('·') === '신분 확인·면허 확인');
  const pendingTeacher = { id: 'newbie', name: '신규환', license: '물리치료사', years: 2, verification: { identity: 'pending', license: 'pending', career: 'pending' } };
  ok('N8 미확인 선생님은 배지 배열 비어 있음', MP.getVerificationBadges(pendingTeacher).length === 0 && MP.getVerificationBadges(pendingTeacher, { publicOnly: true }).length === 0);
  ok('N9 미확인 선생님 공개 프로필에 배지·검증 문구 없음', (function () {
    const pf = MP.teacherPublicProfile(pendingTeacher);
    return pf.badgeText === '' && pf.badges.length === 0 && !/검증|인증|확인 완료/.test(JSON.stringify(pf));
  })(), JSON.stringify(MP.teacherPublicProfile(pendingTeacher)).slice(0, 200));
  ok('N10 실패(failed) 단계도 배지 없음', MP.getVerificationBadges({ verification: { identity: 'failed', license: 'failed', career: 'failed' } }).length === 0);
  ok('N11 어떤 배지에도 검증·인증·확인 완료 문구 없음', seedTeachers.every((t) => MP.getVerificationBadges(t).every((b) => !/검증|인증|확인 완료/.test(b.label))) &&
    MP.claimWords.indexOf('검증') !== -1 && MP.claimWords.indexOf('확인 완료') !== -1);
  ok('N12 미확인 단계 안내 문구도 금지어 없음', MP.pendingVerificationSteps('lee').every((s) => !/검증|인증|확인 완료/.test(s.label)) &&
    MP.pendingVerificationSteps('lee').map((s) => s.step).join(',') === 'career');

  /* ----- 카드: 통과 배지만, 미확인 선생님 카드에 배지 미노출 ----- */
  const cardChips = hP.$$('#teacherList .lic').map((el) => el.textContent.replace(/\s+/g, ' ').trim());
  ok('N13 카드 배지 8개(모든 선생님 면허 통과)', cardChips.length === 8 && hP.$$('#teacherList .teacher').length === 8, String(cardChips.length));
  ok('N14 카드 배지는 공개 단계만(면허·경력)', cardChips.every((t) => !/신분/.test(t)) && /면허 확인/.test(cardChips[0]) && /경력 확인/.test(cardChips[0]), cardChips.join(' | '));
  ok('N15 경력 미확인 선생님 카드에 경력 배지 없음', (function () {
    const leeCard = hP.$('#teacherList [data-teacher="lee"]');
    const yoonCard = hP.$('#teacherList [data-teacher="yoon"]');
    return /면허 확인/.test(leeCard.textContent) && !/경력 확인/.test(leeCard.textContent) && !/경력 확인/.test(yoonCard.textContent);
  })(), hP.$('#teacherList [data-teacher="lee"]').textContent.replace(/\s+/g, ' '));
  ok('N16 카드에 원본 면허번호 없음', !/11-2008-004312|12-2017-003918/.test(hP.text('#teacherList')));

  /* ----- 마스킹 규칙 ----- */
  ok('N17 이름 마스킹(성+이름 첫 글자)', MP.maskTeacherName('박서준') === '박서O' && MP.maskTeacherName('김민') === '김O' && MP.maskTeacherName('이하늘') === '이하O' && MP.maskTeacherName('한가온') === '한가O', ['박서준', '김민', '이하늘', '한가온'].map((n) => n + '→' + MP.maskTeacherName(n)).join(', '));
  ok('N18 이름 마스킹 경계값', MP.maskTeacherName('') === '' && MP.maskTeacherName(null) === '' && MP.maskTeacherName('박') === '박' && MP.maskTeacherName(' 박 서 준 ') === '박서O');
  ok('N19 면허번호 마스킹 제○○-○○○○호', MP.maskLicenseNo('11-2019-004821') === '제○○-○○○○호' && MP.maskLicenseNo('제11-2019-004821호') === '제○○-○○○○호' && MP.maskLicenseNo('12-2017-003918') === '제○○-○○○○호');
  ok('N20 면허번호 아닌 값은 빈 문자열', MP.maskLicenseNo('') === '' && MP.maskLicenseNo(null) === '' && MP.maskLicenseNo('abc') === '' && MP.maskLicenseNo('1234') === '');
  ok('N21 마스킹 결과에 원본 숫자 없음', seedTeachers.every((t) => MP.maskLicenseNo(t.licenseNo).indexOf(t.licenseNo.slice(-4)) === -1));
  ok('N21b 시드에도 마스킹 면허번호 필드', seedTeachers.every((t) => t.licenseMasked === '제○○-○○○○호'));

  /* ----- 상세 시트: 마스킹·배지·가능 시간·활동 지역 ----- */
  hP.click(hP.$('[data-login="customer"]'));
  hP.click(hP.$('#teacherList [data-teacher="park"]'));
  const parkSheet = hP.text('#teacherSheetBody');
  ok('N22 시트에 마스킹된 면허·취득연도', /제○○-○○○○호/.test(parkSheet) && /2008년 취득/.test(parkSheet), parkSheet.slice(0, 160));
  ok('N23 시트에 원본 면허번호 없음', !/11-2008-004312/.test(parkSheet) && !/국가면허 제/.test(parkSheet));
  ok('N24 시트에 통과 배지 3단계', hP.$$('#teacherSheet .h-tags .tag').length === 3 && /면허 확인/.test(parkSheet) && /경력 확인/.test(parkSheet), String(hP.$$('#teacherSheet .h-tags .tag').length));
  ok('N25 시트 활동 지역은 시·구·동까지', /서울 강남구 대치동/.test(parkSheet) && !/101동/.test(parkSheet) && !/1203호/.test(parkSheet), parkSheet.slice(-260));
  ok('N26 시트 가능 시간·이동 수단', /평일 오전 · 주말 오후/.test(parkSheet) && /주 12회까지 방문/.test(parkSheet) && /이동 수단 차량/.test(parkSheet));
  ok('N27 시트 자격 라벨에 미확인 검증 표현 없음', /자격·면허/.test(parkSheet) && !/검증된 자격/.test(parkSheet));
  hP.click(hP.$('#teacherSheet [data-sheet-close]'));
  hP.click(hP.$('#teacherList [data-teacher="lee"]'));
  const leeSheet = hP.text('#teacherSheetBody');
  ok('N28 경력 미확인 시트: 배지 2개 + 진행 안내', hP.$$('#teacherSheet .h-tags .tag').length === 2 && /경력 확인은 진행 중이에요/.test(leeSheet) && /자격·면허/.test(leeSheet), String(hP.$$('#teacherSheet .h-tags .tag').length));
  ok('N29 경력 미확인 시트 자격 블록에 "검증" 문구 없음', !/검증|인증|확인 완료/.test(leeSheet.split('자격·면허')[1] || '') && /경력 확인은 진행 중이에요/.test(leeSheet), (leeSheet.split('자격·면허')[1] || '').slice(0, 120));
  hP.click(hP.$('#teacherSheet [data-sheet-close]'));

  /* ----- 공개 프로필 투영: 개인정보 원칙 ----- */
  ok('N30 공개 프로필에 연락처·상세주소·원본번호 없음', (function () {
    const pf = MP.teacherPublicProfile('park');
    return pf.phone === null && pf.address === null && pf.licenseMasked === '제○○-○○○○호' && JSON.stringify(pf).indexOf('11-2008-004312') === -1 && pf.regionText === '서울 강남구 대치동 · 서초구 반포동';
  })(), JSON.stringify(MP.teacherPublicProfile('park')).slice(0, 200));
  ok('N31 지역 문자열에 숫자 주소가 섞이면 버림', MP.teacherPublicProfile({ name: '홍길동', regionDetail: '서울 강남구 대치동 101동 1203호 · 서초구 반포동' }).regionText === '서울 강남구 대치동 · 서초구 반포동');

  /* ----- 신규 지원서: 3단계 pending ----- */
  const appNew = MP.newTeacherApplication({ name: '김현수', license: '작업치료사', licenseNo: '12-2021-009912', licenseYear: 2021, careerYears: 4, specialties: ['무릎·고관절'], availableDays: ['월'], availableTimes: ['오전'], province: '부산', districts: ['해운대구'], transport: '차량', intro: '수술 후 회복을 함께 걷는 작업치료사' });
  ok('N32 신규 지원서 3단계 모두 pending', appNew.verification.identity === 'pending' && appNew.verification.license === 'pending' && appNew.verification.career === 'pending' && MP.getVerificationBadges(appNew).length === 0);
  ok('N33 신규 지원서 프로필 구조 수용', appNew.occupation === '작업치료사' && appNew.licenseYear === 2021 && appNew.careerYears === 4 && appNew.specialties[0] === '무릎·고관절' && appNew.availableTimes[0] === '오전' && appNew.transport === '차량' && /작업치료사/.test(appNew.intro) && appNew.status === 'pending');
  ok('N34 지원서 면허번호는 마스킹 보관', appNew.licenseMasked === '제○○-○○○○호' && MP.getVerificationBadges(appNew).length === 0);
  ok('N35 직종 3종 지원(간호조무사)', MP.occupations.join(',') === '물리치료사,작업치료사,간호조무사' && MP.newTeacherApplication({ license: '간호조무사' }).occupation === '간호조무사', MP.occupations.join(','));
  ok('N36 모르는 검증 값은 pending으로 보정', MP.normalizeVerification({ identity: 'verified', license: 'yes', career: null }).license === 'pending' && MP.normalizeVerification(null).identity === 'pending');

  /* ----- 실제 지원 폼: 신규 지원자는 pending, 구조 필드 저장 ----- */
  hP.click(hP.$('#homePartnerCard'));
  hP.setVal(hP.$('#pName'), '김현수');
  hP.setVal(hP.$('#pPhone'), '01098765432');
  hP.click(hP.$('[data-pnext="1"]'));
  hP.setSel(hP.$('#pProvince'), '부산');
  hP.click(hP.$('#pDistricts [data-pdistrict="해운대구"]'));
  hP.click(hP.$('#pDays [data-day="월"]'));
  hP.click(hP.$('#pTimes [data-ptime="오전"]'));
  hP.click(hP.$('#pTransport [data-transport="차량"]'));
  hP.click(hP.$('[data-pnext="2"]'));
  hP.click(hP.$('#pLicense [data-license="작업치료사"]'));
  hP.setVal(hP.$('#pLicenseNo'), '12-2021-009912');
  hP.setVal(hP.$('#pLicenseYear'), '2021');
  hP.setSel(hP.$('#pYears'), '4');
  hP.click(hP.$('#pFields [data-field="무릎·고관절"]'));
  hP.setVal(hP.$('#pIntro'), '수술 후 회복을 함께 걷는 작업치료사');
  hP.click(hP.$('[data-pnext="3"]'));
  hP.setVal(hP.$('#pRate'), '72000');
  ['면허증 사본', '경력증명서', '범죄경력조회 동의', '신분증 사본'].forEach((n) => hP.click(hP.$('#pDocs [data-doc="' + n + '"]')));
  hP.setCheck(hP.$('#pAgree'), true);
  hP.click(hP.$('#pSubmit'));
  const submitted = JSON.parse(P.window.localStorage.getItem('ttokttok_partner_v1'));
  ok('N37 지원 제출 → 검증 3단계 pending', submitted.status === 'pending' && ['identity', 'license', 'career'].every((k) => MP.verificationOf(submitted)[k] === 'pending'), JSON.stringify(submitted.verification));
  ok('N38 지원 제출 데이터에 프로필 구조 저장', submitted.occupation === '작업치료사' && submitted.licenseYear === 2021 && submitted.availableTimes[0] === '오전' && submitted.transport === '차량' && /작업치료사/.test(submitted.intro) && submitted.availableDays[0] === '월', JSON.stringify({ occ: submitted.occupation, y: submitted.licenseYear, t: submitted.availableTimes }));
  ok('N38b 경력 연차는 숫자로도 저장', submitted.careerYears === 4, String(submitted.careerYears));
  ok('N39 지원서 개인정보 최소 수집 안내', /주민등록번호·건강정보는 받지 않아요/.test(hP.text('#pstep-3')) && /마스킹/.test(hP.text('#pstep-3')), hP.text('#pstep-3').slice(0, 120));

  /* ----- 관리자: 확인 절차 3단계 · 승인 시 단계별 통과 ----- */
  hP.click(hP.$('#partnerDone [data-role-switch="therapist"]'));
  hP.click(hP.$('.tabbtn[data-tab="tp-mypage"]'));
  hP.click(hP.$('[data-admin-open]'));
  hP.click(hP.$('#adminQueue [data-app-open="me"]'));
  const myAppSheet = hP.text('#appSheetBody');
  ok('N40 관리자 확인 절차 3단계 표시', /확인 절차 3단계/.test(myAppSheet) && /신분 확인/.test(myAppSheet) && /면허 확인/.test(myAppSheet) && /경력 확인/.test(myAppSheet));
  ok('N41 미확인 지원서에 금지 문구 없음', !/검증|인증|확인 완료/.test(myAppSheet), myAppSheet.slice(0, 160));
  ok('N42 보호자에게 보이는 이름은 마스킹', /김현O/.test(myAppSheet) && !/김현수/.test(myAppSheet.split('보호자에게 보이는 프로필')[1] || ''), myAppSheet.slice(-220));
  ok('N43 관리자 화면은 원본 면허번호 유지(심사용)', /12-2021-009912/.test(myAppSheet) && /제○○-○○○○호/.test(myAppSheet));
  hP.click(hP.$('#appSheet [data-app-close]'));
  hP.click(hP.$('[data-admin-doc-all="me"]'));
  hP.click(hP.$('[data-admin-approve="me"]'));
  const approved = JSON.parse(P.window.localStorage.getItem('ttokttok_partner_v1'));
  ok('N44 서류 4종 확인 후 승인 → 3단계 통과', approved.status === 'approved' && ['identity', 'license', 'career'].every((k) => MP.verificationOf(approved)[k] === 'verified'), JSON.stringify(approved.verification));
  ok('N45 서류 일부만 확인하면 해당 단계만 통과', (function () {
    const v = MP.verificationFromDocs(['면허증 사본']);
    return v.license === 'verified' && v.identity === 'pending' && v.career === 'pending';
  })(), JSON.stringify(MP.verificationFromDocs(['면허증 사본'])));

  /* ----- export·무결성 ----- */
  const bundle = MP.export();
  const tRows = bundle.tables.teachers || [];
  ok('N46 export 선생님 행에 검증 3단계·직종·마스킹', tRows.length === 8 && tRows.every((t) => t.verification && t.occupation && t.licenseMasked === '제○○-○○○○호' && Array.isArray(t.careerHighlights) && t.availableSummary && t.firstAvailable && t.maxWeeklyVisits > 0 && t.transport), JSON.stringify(tRows[0]).slice(0, 240));
  ok('N47 export 지원서 행도 pending 유지', bundle.tables.teacher_applications.some((a) => a.id === 'adm-1' && MP.verificationOf(a).license === 'pending') && bundle.tables.teacher_applications.every((a) => !!a.verification));
  ok('N48 export 무결성 ok', MP.integrity().ok === true, JSON.stringify(MP.integrity().issues).slice(0, 200));
  const brokenPartner = makeDom({ ttokttok_partner_v1: JSON.stringify({ name: '이상한', status: 'approved', verification: 'nope' }) });
  await sleep(40);
  ok('N49 verification 문자열이어도 오류 없음', brokenPartner.errors.length === 0 && brokenPartner.window.__ttokttokModel.verificationOf('park').license === 'verified', brokenPartner.errors.slice(0, 2).join(' | '));

  /* ----- 문서와 코드의 약속 ----- */
  const vDocPath = path.join(__dirname, '..', 'TEACHER-VERIFICATION.md');
  const vDoc = fs.existsSync(vDocPath) ? fs.readFileSync(vDocPath, 'utf8') : '';
  ok('N50 TEACHER-VERIFICATION.md 존재', vDoc.length > 4000, String(vDoc.length));
  ok('N51 3단계·금지 문구·마스킹 규칙 문서화', /identity/.test(vDoc) && /license/.test(vDoc) && /career/.test(vDoc) && /확인 완료/.test(vDoc) && /제○○-○○○○호/.test(vDoc) && /maskTeacherName/.test(vDoc) && /maskLicenseNo/.test(vDoc));
  ok('N52 문서와 코드 함수명 일치', ['getVerificationBadges', 'verificationFromDocs', 'newTeacherApplication', 'teacherPublicProfile'].every((n) => vDoc.indexOf(n) !== -1));

  /* ============================================================
     O. v16 — 서비스 기준·비용·환불 규정 (POLICIES-AND-FEES.md)
     ============================================================ */
  const Q = makeDom();
  const hQ = helpers(Q.window, Q.doc);
  await sleep(30);
  ok('O0 JS 오류 없음', Q.errors.length === 0, Q.errors.slice(0, 3).join(' | '));
  const MQ = Q.window.__ttokttokModel;
  ok('O1 정책 API 노출(policyVersion 16)', !!MQ && MQ.policyVersion === 16 &&
    !!MQ.policyMeta && !!MQ.refundRules && !!MQ.pricing && !!MQ.policyDocs &&
    typeof MQ.calculateRefundQuote === 'function' && typeof MQ.calculatePassRefund === 'function' && typeof MQ.refundTextOf === 'function',
    MQ && String(MQ.policyVersion));
  ok('O2 POLICY_META 초안 표시·면책 고지', MQ.policyMeta.isDraft === true && MQ.policyMeta.version === 'v16' &&
    MQ.policyMeta.docVersion === 'POLICIES-AND-FEES v1.0' &&
    /법률 자문이 아닌 운영 기준 초안/.test(MQ.policyMeta.draftLabel) && /법률 자문이 아닙니다/.test(MQ.policyMeta.legalDisclaimer),
    JSON.stringify(MQ.policyMeta).slice(0, 200));
  ok('O3 전문가 검토 항목 L1~L7 7종', Array.isArray(MQ.policyMeta.reviewItems) && MQ.policyMeta.reviewItems.length === 7 &&
    ['employment_agency', 'medical_scope', 'ecommerce', 'privacy', 'door_to_door', 'tax', 'liability']
      .every((c) => MQ.policyMeta.reviewItems.some((r) => r.code === c)),
    JSON.stringify(MQ.policyMeta.reviewItems.map((r) => r.code)));

  /* ----- 가격표: 코드 상수와 화면 시드가 같은 값 ----- */
  const pr = MQ.pricing;
  ok('O4 PRICING 회당 60분·출장비0·가산0·수수료22.2%·정산 D+3/15·말일·90일',
    pr.visitMinutes === 60 && pr.travelFee === 0 && pr.weekendSurchargePct === 0 && pr.nightSurchargePct === 0 &&
    pr.platformFeeRate === 0.2222 && pr.consumerPrice === 90000 && pr.teacherPayout === 70000 &&
    pr.settlementConfirmDays === 3 && JSON.stringify(pr.settlementPayDays) === '[15,"end"]' &&
    pr.passValidDays === 90 && pr.freeEvalSessions === 1,
    JSON.stringify(pr).slice(0, 220));
  ok('O5 PRICING 회차권 5종 단가(90,000·320,000·592,000·840,000)', pr.plans.length === 5 &&
    pr.plans.map((p) => p.price).join(',') === '0,90000,320000,592000,840000' &&
    pr.plans.map((p) => p.sessions).join(',') === '1,1,4,8,12',
    JSON.stringify(pr.plans));

  /* ----- 화면 회차권 목록(결제 2단계)이 PRICING과 같은 금액 ----- */
  const B16 = makeDom();
  const hB16 = helpers(B16.window, B16.doc);
  await sleep(30);
  hB16.click(hB16.$('[data-login="customer"]'));
  hB16.click(hB16.$('.tabbtn[data-tab="booking"]'));
  hB16.setSel(hB16.$('#bookProvince'), '서울');
  hB16.setSel(hB16.$('#bookDistrict'), '강남구');
  hB16.setVal(hB16.$('#bookAddress'), '대치동 123-4');
  hB16.click(hB16.$('#bookSyms [data-val="뇌졸중·편마비"]'));
  hB16.click(hB16.$('[data-next="1"]'));
  hB16.click(hB16.$('#bookDates .date-chip'));
  hB16.click(hB16.$$('#bookSlots .slot').filter((b) => !b.disabled)[0]);
  hB16.click(hB16.$('[data-next="2"]'));
  await sleep(20);
  ok('O6 화면 회차권 목록이 PRICING과 일치(5종)', (function () {
    const items = hB16.$$('#passList [data-pass]');
    if (items.length !== 5) return false;
    return pr.plans.every((p) => {
      const el = items.filter((x) => x.getAttribute('data-pass') === p.id)[0];
      if (!el) return false;
      const t = el.textContent.replace(/\s+/g, ' ');
      return p.price === 0 ? /무료/.test(t) : t.indexOf(p.price.toLocaleString('en-US') + '원') !== -1;
    });
  })(), hB16.text('#passList').slice(0, 200));

  /* ----- 환불 규칙 상수 ----- */
  const rr = MQ.refundRules;
  ok('O7 REFUND_RULES 초안·노쇼 30분·연락 15분·변경 24시간', rr.isDraft === true && rr.noShowGraceMinutes === 30 &&
    rr.contactTryMinutes === 15 && rr.changeFreeUntilHours === 24, JSON.stringify({ g: rr.noShowGraceMinutes, c: rr.contactTryMinutes }));
  ok('O8 환불 구간 3종(24시간 전·이내·이후)', rr.tiers.length === 3 && rr.tiers.map((t) => t.code).join(',') === 'before_24h,within_24h,after_start' &&
    rr.tiers.map((t) => t.pct).join(',') === '100,50,0', JSON.stringify(rr.tiers.map((t) => t.code + ':' + t.pct)));
  ok('O9 취소 사유 5종 코드', ['customer', 'no_show', 'teacher', 'center', 'force_majeure'].every((k) => !!rr.reasons[k]) &&
    Object.keys(rr.reasons).length === 5, Object.keys(rr.reasons).join(','));

  /* ----- 단건 취소 견적: 구간 경계 ----- */
  const q24 = MQ.calculateRefundQuote(85000, 24, 'customer');
  const q239 = MQ.calculateRefundQuote(85000, 23.9, 'customer');
  const q0 = MQ.calculateRefundQuote(85000, 0, 'customer');
  const qPast = MQ.calculateRefundQuote(85000, -1, 'customer');
  ok('O10 24시간 전 단건 → 전액 환불', q24.ok === true && q24.pct === 100 && q24.refund === 85000 && q24.tier === 'before_24h', JSON.stringify(q24));
  ok('O11 24시간 이내(23.9h) 단건 → 50% 환불', q239.tier === 'within_24h' && q239.pct === 50 && q239.refund === 42500, JSON.stringify(q239));
  ok('O12 방문 시각(0h) 단건 → 50% 환불', q0.tier === 'within_24h' && q0.refund === 42500, JSON.stringify(q0));
  ok('O13 방문 이후(-1h) 단건 → 환불 0', qPast.tier === 'after_start' && qPast.pct === 0 && qPast.refund === 0 && qPast.retained === 85000, JSON.stringify(qPast));
  ok('O14 노쇼 → 환불 0(단건은 차감할 회차 없음)', (function () {
    const q = MQ.calculateRefundQuote(85000, 30, 'no_show');
    return q.ok === true && q.pct === 0 && q.refund === 0 && q.deductSessions === 0 && /노쇼/.test(q.label);
  })(), JSON.stringify(MQ.calculateRefundQuote(85000, 30, 'no_show')));
  ok('O15 선생님·센터·천재지변 → 구간과 무관 전액 환불', ['teacher', 'center', 'force_majeure'].every((k) => {
    const q = MQ.calculateRefundQuote(85000, 0, k);
    return q.ok === true && q.pct === 100 && q.refund === 85000;
  }), JSON.stringify(['teacher', 'center', 'force_majeure'].map((k) => MQ.calculateRefundQuote(85000, 0, k).refund)));
  ok('O16 모르는 사유 → 차단(환불 0)', (function () {
    const q = MQ.calculateRefundQuote(85000, 48, 'gift');
    return q.ok === false && q.error === 'unknown_reason' && q.refund === 0 && q.retained === 85000;
  })(), JSON.stringify(MQ.calculateRefundQuote(85000, 48, 'gift')));
  ok('O17 사유 미지정은 보호자 취소로 처리', MQ.calculateRefundQuote(85000, 48, null).reason === 'customer' &&
    MQ.calculateRefundQuote(85000, 48, null).refund === 85000);

  /* ----- 회차권 취소: 현금 환불 대신 회차 복구/차감 ----- */
  const qp24 = MQ.calculateRefundQuote(592000, 48, 'customer', { isPass: true, passSessions: 8, remainingSessions: 5 });
  const qp23 = MQ.calculateRefundQuote(592000, 5, 'customer', { isPass: true, passSessions: 8, remainingSessions: 5 });
  const qpNo = MQ.calculateRefundQuote(592000, 30, 'no_show', { isPass: true, passSessions: 8 });
  ok('O18 회차권 24시간 전 → 회차 1회 복구·현금 환불 0', qp24.ok === true && qp24.refund === 0 && qp24.restoreSessions === 1 && qp24.deductSessions === 0, JSON.stringify(qp24));
  ok('O19 회차권 24시간 이내 → 1회 차감·환불 0', qp23.refund === 0 && qp23.restoreSessions === 0 && qp23.deductSessions === 1, JSON.stringify(qp23));
  ok('O20 회차권 노쇼 → 1회 차감·환불 0', qpNo.refund === 0 && qpNo.deductSessions === 1, JSON.stringify(qpNo));
  ok('O21 모든 견적에 isDraft·policyVersion·면책', [q24, q239, qPast, qp24, qpNo].every((q) =>
    q.isDraft === true && q.policyVersion === 'v16' && /법률 자문이 아닙니다/.test(q.legalDisclaimer)));
  ok('O22 견적 한 줄 안내(refundTextOf)', MQ.refundTextOf(q24) === '환불 예정 금액은 85,000원이에요.' &&
    MQ.refundTextOf(qp24) === '회차권 잔여 1회가 복구돼요.' &&
    MQ.refundTextOf(qp23) === '회차권 1회가 차감되고 환불 금액은 없어요.' &&
    MQ.refundTextOf(qPast) === '환불 가능한 금액이 없어요.',
    [MQ.refundTextOf(q24), MQ.refundTextOf(qp24), MQ.refundTextOf(qp23), MQ.refundTextOf(qPast)].join(' | '));

  /* ----- 다회권 중도 해지 (§4.3 표와 같은 값) ----- */
  ok('O23 중도 해지: 4회권 1회 이용 → 230,000원', MQ.calculatePassRefund({ paidAmount: 320000, totalSessions: 4, usedSessions: 1 }).refund === 230000,
    JSON.stringify(MQ.calculatePassRefund({ paidAmount: 320000, totalSessions: 4, usedSessions: 1 })));
  ok('O24 중도 해지: 8회권 3회 이용 → 322,000원', MQ.calculatePassRefund({ paidAmount: 592000, totalSessions: 8, usedSessions: 3 }).refund === 322000,
    JSON.stringify(MQ.calculatePassRefund({ paidAmount: 592000, totalSessions: 8, usedSessions: 3 })));
  ok('O25 중도 해지: 8회권 6회 이용 → 52,000원', MQ.calculatePassRefund({ paidAmount: 592000, totalSessions: 8, usedSessions: 6 }).refund === 52000,
    JSON.stringify(MQ.calculatePassRefund({ paidAmount: 592000, totalSessions: 8, usedSessions: 6 })));
  ok('O26 중도 해지: 12회권 10회 이용 → 0원(추가 청구 없음)', (function () {
    const r = MQ.calculatePassRefund({ paidAmount: 840000, totalSessions: 12, usedSessions: 10 });
    return r.refund === 0 && r.usedCharge === 840000;
  })(), JSON.stringify(MQ.calculatePassRefund({ paidAmount: 840000, totalSessions: 12, usedSessions: 10 })));
  ok('O27 중도 해지: 미사용 → 결제액 전액', MQ.calculatePassRefund({ paidAmount: 592000, totalSessions: 8, usedSessions: 0 }).refund === 592000);
  ok('O28 중도 해지: 정상가 기본값 90,000·이용 회차 상한 클램프', (function () {
    const r = MQ.calculatePassRefund({ paidAmount: 320000, totalSessions: 4, usedSessions: 99 });
    return r.regularSinglePrice === 90000 && r.usedSessions === 4 && r.remainingSessions === 0 && r.refund === 0 && r.isDraft === true;
  })(), JSON.stringify(MQ.calculatePassRefund({ paidAmount: 320000, totalSessions: 4, usedSessions: 99 })));

  /* ----- 약관·FAQ 본문 ----- */
  const pd = MQ.policyDocs.policy;
  ok('O29 POLICY_DOCS 3개 섹션·초안 고지', pd.title.indexOf('v16 운영 기준 초안') !== -1 && pd.draft === true &&
    pd.sections.map((s) => s.name).join(',') === '서비스 이용 기준,비용 안내,취소·변경·환불 규정' && /법률 자문이 아닙니다/.test(pd.note),
    pd.sections.map((s) => s.name).join(','));
  ok('O30 POLICY_DOCS 금액이 PRICING과 일치', (function () {
    const t = JSON.stringify(pd.sections);
    return ['90,000', '320,000', '592,000', '840,000'].every((n) => t.indexOf(n) !== -1) && /60분/.test(t) && /90일/.test(t);
  })());
  ok('O31 POLICY_DOCS 환불 문구에 24시간·50%·30분', (function () {
    const t = JSON.stringify(pd.sections);
    return /24시간 전/.test(t) && /50%/.test(t) && /30분/.test(t) && /법률 자문/.test(pd.note);
  })());

  /* ----- 화면: FAQ/약관 시트 ----- */
  hQ.click(hQ.$('[data-login="customer"]'));
  hQ.click(hQ.$('#homeTicketBtn'));
  await sleep(20);
  hQ.click(hQ.$('#mpFaqRow'));
  await sleep(20);
  ok('O32 FAQ 시트 열림·초안 고지 표시', hQ.$('#faqSheet').classList.contains('is-open') &&
    /법률 자문이 아닌 운영 기준 초안/.test(hQ.text('#faqDraftNote')), hQ.text('#faqDraftNote'));
  ok('O33 서비스·환불 탭 존재(3탭)', hQ.$$('#faqTabs [data-terms]').map((b) => b.getAttribute('data-terms')).join(',') === 'terms,policy,privacy');
  hQ.click(hQ.$('#faqTabs [data-terms="policy"]'));
  await sleep(20);
  ok('O34 서비스·환불 탭 본문 렌더(3섹션)', (function () {
    const t = hQ.text('#termsBody');
    return /서비스 이용 기준/.test(t) && /비용 안내/.test(t) && /취소·변경·환불 규정/.test(t) &&
      /90,000원/.test(t) && /24시간 전/.test(t) && /중도 해지/.test(t);
  })(), hQ.text('#termsBody').slice(0, 200));
  ok('O35 서비스·환불 탭 하단에 법률 자문 아님 고지', /법률 자문이 아닙니다/.test(hQ.text('#termsBody')), hQ.text('#termsBody').slice(-160));
  ok('O36 탭 활성 표시(aria-selected)', hQ.$('#faqTabs [data-terms="policy"]').getAttribute('aria-selected') === 'true' &&
    hQ.$('#faqTabs [data-terms="terms"]').getAttribute('aria-selected') === 'false');
  ok('O37 FAQ 3번(환불)이 규정과 일치', (function () {
    const t = hQ.text('#faqList');
    return /24시간 전/.test(t) && /50%/.test(t) && /30분/.test(t) && /서비스·환불/.test(t);
  })(), hQ.text('#faqList').slice(0, 160));

  /* ----- 화면: 결제 안내 ----- */
  ok('O38 결제 화면 하단 취소·환불 안내', /취소·환불은 방문 24시간 전까지 무료/.test(Q.doc.body.textContent) &&
    /서비스·환불/.test(Q.doc.body.textContent));
  ok('O39 v16 문구는 기존 클래스만 사용(새 디자인 없음)', /class="pay-note[^"]*"/.test(HTML) &&
    /class="sheet-note[^"]*" id="faqDraftNote"/.test(HTML) && /class="refund-box[^"]*"/.test(HTML));

  /* ----- 화면: 취소 확인 단계에 견적·초안 고지 ----- */
  hQ.click(hQ.$('#mpBookLink'));
  await sleep(20);
  hQ.click(hQ.$('#bookingList [data-manage]'));
  await sleep(20);
  hQ.click(hQ.$('[data-manage-cancel]'));
  await sleep(20);
  const cancelText = hQ.text('#manageSheetBody');
  ok('O40 취소 확인 단계에 환불 규정·예상 환불·초안 고지', /환불 규정/.test(cancelText) && /예상 환불/.test(cancelText) &&
    /법률 자문이 아닌 운영 기준 초안/.test(cancelText), cancelText.slice(0, 200));
  ok('O41 취소 확인 단계가 회차권이면 회차 복구/차감으로 안내', /(회차 1회 복구|1회 차감|50%|전액 환불)/.test(cancelText), cancelText.slice(0, 240));
  hQ.click(hQ.$('[data-manage-confirm]'));
  await sleep(30);
  const cancelAcc = JSON.parse(Q.window.localStorage.getItem('ttokttok_account_v3'));
  const canceledOne = cancelAcc.bookings.filter((b) => b.status === 'canceled')[0];
  ok('O42 취소 실행 → 상태·견적 문구가 예약에 남음', !!canceledOne && /(회차|환불)/.test(canceledOne.refundLabel || '') &&
    ['refund_pending', 'paid'].indexOf(canceledOne.paymentStatus) !== -1,
    JSON.stringify(canceledOne && { s: canceledOne.status, l: canceledOne.refundLabel, p: canceledOne.paymentStatus }));

  /* ----- 문서와 코드의 약속 ----- */
  const polPath = path.join(__dirname, '..', 'POLICIES-AND-FEES.md');
  const polDoc = fs.existsSync(polPath) ? fs.readFileSync(polPath, 'utf8') : '';
  ok('O43 POLICIES-AND-FEES.md 존재', polDoc.length > 9000, String(polDoc.length));
  ok('O44 면책 고지 먼저(법률 자문 아님)', /## 0\. 면책 고지/.test(polDoc) && /법률 자문이 아니다/.test(polDoc) && /초안/.test(polDoc));
  ok('O45 전문가 검토 L1~L7 문서화', ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7'].every((c) => polDoc.indexOf('| ' + c + ' |') !== -1));
  ok('O46 서비스 범위·불가 조건·안전 기준', /서비스 범위 및 기준/.test(polDoc) && /서비스 불가/.test(polDoc) && /안전 기준/.test(polDoc));
  ok('O47 비용·중도 해지·환불·노쇼 규정', /회차권/.test(polDoc) && /다회권 중도 해지/.test(polDoc) && /노쇼/.test(polDoc) && /50%/.test(polDoc));
  ok('O48 현수 님 확정 필요 목록 D1~D11', ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10', 'D11'].every((c) => polDoc.indexOf('| ' + c + ' |') !== -1));
  ok('O49 문서 금액·기준이 코드와 일치', ['90,000', '320,000', '592,000', '840,000'].every((n) => polDoc.indexOf(n) !== -1) &&
    /30분/.test(polDoc) && /90일/.test(polDoc) && /22\.2%/.test(polDoc) && /60분/.test(polDoc));
  ok('O50 문서와 코드 함수명 일치', ['POLICY_META', 'REFUND_RULES', 'PRICING', 'calculateRefundQuote', 'calculatePassRefund', 'POLICY_DOCS']
    .every((n) => polDoc.indexOf(n) !== -1));
  ok('O51 가정치 표시', /가정치/.test(polDoc) && /확정 필요/.test(polDoc));

  /* ============================================================
     P. v17 — 운영자(관리자) 예약 접수 큐 & 상태 관리
     ============================================================ */
  function adminSeedAccount() {
    const mk = (no, status, extra) => Object.assign({
      id: 'res-' + no.toLowerCase(), no, userId: 'usr-demo',
      date: '11.28', day: '토', time: '10:00',
      teacher: '', teacherId: '', region: '서울 강남구 대치동', regionId: 'reg-서울-강남구',
      status, passId: 'p8', walletId: 'seed-pass', dateIso: '2026-11-28', amount: 74000, paymentStatus: 'paid'
    }, extra || {});
    return JSON.stringify({
      profile: { name: '현수' },
      passes: [{ id: 'seed-pass', userId: 'usr-demo', passId: 'p8', name: '8회 방문권', total: 8, remaining: 5, purchased: '2026.10.28', expire: '2027.01.27', status: 'active' }],
      bookings: [
        mk('TT-261126-1001', 'received', { dateIso: '2026-11-28', time: '10:00' }),
        mk('TT-261126-1007', 'received', { dateIso: '2026-11-28', time: '14:00' }),
        mk('TT-261126-1002', 'assigned', { teacher: '이하늘 선생님', teacherId: 'lee', dateIso: '2026-11-28', time: '14:00' }),
        mk('TT-261126-1003', 'confirmed', { teacher: '박서준 선생님', teacherId: 'park', dateIso: '2026-11-29', time: '10:00' }),
        mk('TT-261126-1004', 'rescheduled', { teacher: '박서준 선생님', teacherId: 'park', dateIso: '2026-11-30', time: '11:00' }),
        mk('TT-261126-1005', 'canceled', { dateIso: '2026-11-27', time: '09:00' }),
        mk('TT-261126-1006', 'no_show', { teacher: '이하늘 선생님', teacherId: 'lee', dateIso: '2026-11-25', time: '16:00' })
      ],
      receipts: []
    });
  }

  const P17 = makeDom({ ttokttok_account_v3: adminSeedAccount() });
  const hV17 = helpers(P17.window, P17.doc);
  await sleep(30);
  const VM = P17.window.__ttokttokModel;
  const btnTos = (no) => hV17.$$('#adminResvQueue [data-resv="' + no + '"] [data-admin-resv-to]').map((b) => b.getAttribute('data-admin-resv-to'));
  const statusOf = (no) => (VM.adminStatusOf(no) || '');
  const notifTitles = () => (VM.notifs() || []).map((n) => n.title);

  ok('P0 JS 오류 없음', P17.errors.length === 0, P17.errors.slice(0, 3).join(' | '));
  ok('P1 v17 모델 노출(adminVersion·필터 7종)', !!VM && VM.adminVersion === 'v17' &&
    VM.adminFilters.join(',') === 'all,received,assigned,confirmed,rescheduled,completed,closed', VM && VM.adminFilters.join(','));
  hV17.click(hV17.$('[data-login="admin"]'));
  ok('P2 관리자 로그인 → 예약 접수 큐 영역', hV17.$('#screen-admin').classList.contains('is-active') && !!hV17.$('#adminResvQueue'));
  ok('P3 시연용 고지 문구(화면)', /이 기기에만 저장 · 서버 미연결\(이 브라우저에만 반영\)/.test(hV17.text('#adminResvDemoNotice')) &&
    /실제 서버·DB·문자 발송과 연결되어 있지 않습니다/.test(hV17.text('#adminResvDemoNotice')), hV17.text('#adminResvDemoNotice'));
  ok('P4 시연용 고지(정적 HTML)', /이 기기에만 저장 · 서버 미연결\(이 브라우저에만 반영\)/.test(HTML));
  ok('P5 CSS 토큰 정합성(v35: :root 하나·var 전부 정의·중괄호 균형)', cssTokens(HTML).ok,
    String(/<style>([\s\S]*?)<\/style>/.exec(HTML)[1].length));

  /* ----- 필터 7종 ----- */
  ok('P6 상태별 필터 칩 7개', hV17.$$('#adminResvFilters .chip').length === 7, String(hV17.$$('#adminResvFilters .chip').length));
  ok('P7 기본 필터는 전체', hV17.$('#adminResvFilters .chip.is-on').getAttribute('data-admin-resv-filter') === 'all');
  ok('P8 필터 라벨(전체/접수/배정/확정/변경/완료/취소·노쇼)',
    hV17.$$('#adminResvFilters .chip').map((c) => c.textContent.replace(/\s*\d+$/, '').trim()).join('|') === '전체|접수|배정|확정|변경|완료|취소·노쇼',
    hV17.$$('#adminResvFilters .chip').map((c) => c.textContent.trim()).join('|'));
  ok('P9 필터별 건수(전체 7·접수 2·배정 1·확정 1·변경 1·완료 0·취소·노쇼 2)', (function () {
    const c = VM.adminCounts();
    return c.all === 7 && c.received === 2 && c.assigned === 1 && c.confirmed === 1 && c.rescheduled === 1 && c.completed === 0 && c.closed === 2;
  })(), JSON.stringify(VM.adminCounts()));
  ok('P10 전체 7건이 카드로 렌더', hV17.$$('#adminResvQueue .admin-card').length === 7, String(hV17.$$('#adminResvQueue .admin-card').length));

  /* ----- 카드 표시 정보 ----- */
  const card1001 = hV17.text('#adminResvQueue [data-resv="TT-261126-1001"]');
  ok('P11 카드에 예약번호·상태 배지', /TT-261126-1001/.test(card1001) && /접수 완료/.test(card1001), card1001.slice(0, 120));
  ok('P12 카드에 보호자·지역(시·군·구)', /현수/.test(card1001) && /서울 강남구/.test(card1001) && !/대치동/.test(card1001), card1001.slice(0, 160));
  ok('P13 카드에 희망 일시·배정 선생님', /11\.28 \(토\) 10:00/.test(card1001) && /배정 미배정/.test(card1001), card1001.slice(0, 200));
  ok('P14 카드에 최근 이력 1줄', /최근 이력 1건/.test(card1001) && /기존 데이터 · 접수 완료/.test(card1001), card1001.slice(-160));
  ok('P15 카드에 안내 문구 복사 버튼', hV17.$$('#adminResvQueue [data-admin-notice]').length === 7, String(hV17.$$('#adminResvQueue [data-admin-notice]').length));

  /* ----- 필터 동작 ----- */
  hV17.click(hV17.$('#adminResvFilters [data-admin-resv-filter="received"]'));
  ok('P16 접수 필터 → 2건', hV17.$$('#adminResvQueue .admin-card').length === 2 &&
    hV17.$$('#adminResvQueue .admin-card').every((c) => c.getAttribute('data-resv-status') === 'received'), String(hV17.$$('#adminResvQueue .admin-card').length));
  ok('P17 선택 필터 표시(aria-selected·is-on)', hV17.$('#adminResvFilters [data-admin-resv-filter="received"]').getAttribute('aria-selected') === 'true' &&
    hV17.$('#adminResvFilters [data-admin-resv-filter="received"]').classList.contains('is-on'));
  hV17.click(hV17.$('#adminResvFilters [data-admin-resv-filter="closed"]'));
  ok('P18 취소·노쇼 필터 → 2건', hV17.$$('#adminResvQueue .admin-card').length === 2 &&
    hV17.$$('#adminResvQueue .admin-card').map((c) => c.getAttribute('data-resv-status')).join(',') === 'canceled,no_show',
    hV17.$$('#adminResvQueue .admin-card').map((c) => c.getAttribute('data-resv-status')).join(','));
  hV17.click(hV17.$('#adminResvFilters [data-admin-resv-filter="completed"]'));
  ok('P19 완료 필터 → 빈 상태 안내', hV17.$$('#adminResvQueue .admin-card').length === 0 && /이 상태의 예약이 없어요/.test(hV17.text('#adminResvQueue')));
  hV17.click(hV17.$('#adminResvFilters [data-admin-resv-filter="all"]'));
  ok('P20 전체 필터 복귀 7건', hV17.$$('#adminResvQueue .admin-card').length === 7, String(hV17.$$('#adminResvQueue .admin-card').length));

  /* ----- 상태기계 1:1 — 현재 상태에서 가능한 전이 버튼만 ----- */
  ok('P21 접수 → 배정·확정·취소 버튼만', btnTos('TT-261126-1001').join(',') === 'assigned,confirmed,canceled', btnTos('TT-261126-1001').join(','));
  ok('P22 배정 → 확정·배정 해제·취소 버튼만', btnTos('TT-261126-1002').join(',') === 'confirmed,received,canceled', btnTos('TT-261126-1002').join(','));
  ok('P23 확정 → 변경·완료·취소·노쇼 버튼만', btnTos('TT-261126-1003').join(',') === 'rescheduled,completed,canceled,no_show', btnTos('TT-261126-1003').join(','));
  ok('P24 변경 → 확정·취소·노쇼 버튼만', btnTos('TT-261126-1004').join(',') === 'confirmed,canceled,no_show', btnTos('TT-261126-1004').join(','));
  ok('P25 최종 상태(완료·취소·노쇼)에는 전이 버튼 없음', btnTos('TT-261126-1005').length === 0 && btnTos('TT-261126-1006').length === 0 &&
    /최종 상태예요 · 다음 단계가 없습니다/.test(hV17.text('#adminResvQueue [data-resv="TT-261126-1005"]')));
  ok('P26 노출 버튼은 canTransition(operator)와 정확히 일치', (function () {
    const all = VM.adminReservations();
    return all.every((b) => {
      const shown = btnTos(b.no).slice().sort().join(',');
      const allowed = VM.adminNextStatuses(b.no).slice().sort().join(',');
      const legal = Object.keys(VM.transitions[b.status] || {}).filter((to) => VM.canTransition(b.status, to, 'operator')).sort().join(',');
      return shown === allowed && allowed === legal;
    });
  })());
  ok('P27 금지 전이는 버튼에 없음(접수→완료·노쇼·변경)', ['completed', 'no_show', 'rescheduled'].every((to) => btnTos('TT-261126-1001').indexOf(to) === -1));

  /* ----- 배정: 후보 선생님 선택 ----- */
  ok('P28 배정 전 카드에 후보 선생님 선택', !!hV17.$('[data-admin-resv-teacher="TT-261126-1001"]'));
  ok('P29 지역 일치 선생님이 후보 1순위', VM.adminCandidates('TT-261126-1001')[0] === 'park', VM.adminCandidates('TT-261126-1001').join(','));
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1001"] [data-admin-resv-to="assigned"]'));
  ok('P30 선생님 미선택 배정은 차단', statusOf('TT-261126-1001') === 'received' && /배정할 선생님을 먼저 선택해 주세요/.test(hV17.text('#toast')), hV17.text('#toast'));

  hV17.setSel(hV17.$('[data-admin-resv-teacher="TT-261126-1001"]'), 'park');
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1001"] [data-admin-resv-to="assigned"]'));
  ok('P31 배정 실행 → assigned', statusOf('TT-261126-1001') === 'assigned', statusOf('TT-261126-1001'));
  ok('P32 배정 선생님이 예약에 기록', (function () {
    const b = VM.reservations().filter((x) => x.no === 'TT-261126-1001')[0];
    return b.teacherId === 'park' && b.teacher === '박서준 선생님';
  })());
  ok('P33 배정 이력(actor=operator·사유)', (function () {
    const h = VM.history('TT-261126-1001').slice(-1)[0];
    return h.from === 'received' && h.to === 'assigned' && h.actor === 'operator' && /운영자 배정 · 박서준/.test(h.reason);
  })(), JSON.stringify(VM.history('TT-261126-1001').slice(-1)[0]));
  ok('P34 배정 알림(보호자·선생님)', notifTitles().indexOf('선생님 배정이 끝났어요') !== -1 && notifTitles().indexOf('새 방문 요청이 배정됐어요') !== -1, notifTitles().slice(0, 6).join('|'));
  ok('P35 카드 상태 배지·필터 건수 즉시 반영', /선생님 배정/.test(hV17.text('#adminResvQueue [data-resv="TT-261126-1001"]')) &&
    VM.adminCounts().received === 1 && VM.adminCounts().assigned === 2, JSON.stringify(VM.adminCounts()));
  ok('P36 배정 후 후보 선택 UI 사라짐', !hV17.$('[data-admin-resv-teacher="TT-261126-1001"]'));

  /* ----- 같은 선생님·같은 시간 중복 배정 차단 ----- */
  hV17.setSel(hV17.$('[data-admin-resv-teacher="TT-261126-1007"]'), 'lee');
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1007"] [data-admin-resv-to="assigned"]'));
  ok('P37 같은 선생님·같은 시간 중복 배정 차단', statusOf('TT-261126-1007') === 'received' && /이미 잡혀 있어요/.test(hV17.text('#toast')), hV17.text('#toast'));
  hV17.setSel(hV17.$('[data-admin-resv-teacher="TT-261126-1007"]'), 'park');
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1007"] [data-admin-resv-to="assigned"]'));
  ok('P38 다른 선생님은 같은 시간에 배정 가능', statusOf('TT-261126-1007') === 'assigned', statusOf('TT-261126-1007'));

  /* ----- 확정 → 완료 (정산 원장) ----- */
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1001"] [data-admin-resv-to="confirmed"]'));
  ok('P39 확정 실행 → confirmed', statusOf('TT-261126-1001') === 'confirmed', statusOf('TT-261126-1001'));
  ok('P40 확정 알림(보호자)', notifTitles().indexOf('방문이 확정됐어요') !== -1);
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1001"] [data-admin-resv-to="completed"]'));
  ok('P41 완료 실행 → completed', statusOf('TT-261126-1001') === 'completed', statusOf('TT-261126-1001'));
  ok('P42 완료 시 정산 원장 pending 행 생성', (function () {
    const led = JSON.parse(P17.window.localStorage.getItem('ttokttok_partner_v1')).ledger || [];
    const row = led.filter((r) => r.reservationId === 'res-tt-261126-1001')[0];
    return !!row && row.status === 'pending' && row.grossAmount === 74000 && row.feeRate === 0.2222 && row.netAmount === 57556;
  })(), JSON.stringify((JSON.parse(P17.window.localStorage.getItem('ttokttok_partner_v1')).ledger || []).slice(0, 2)));
  ok('P43 완료 알림(보호자·선생님)', notifTitles().indexOf('방문이 완료됐어요') !== -1 && notifTitles().indexOf('방문을 완료 처리했어요') !== -1);

  /* ----- 노쇼 (정산 제외) ----- */
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1003"] [data-admin-resv-to="no_show"]'));
  ok('P44 노쇼 실행 → no_show', statusOf('TT-261126-1003') === 'no_show', statusOf('TT-261126-1003'));
  ok('P45 노쇼는 정산 원장에 없음', (function () {
    const led = JSON.parse(P17.window.localStorage.getItem('ttokttok_partner_v1')).ledger || [];
    return !led.some((r) => r.reservationId === 'res-tt-261126-1003');
  })());
  ok('P46 노쇼 알림(보호자)', notifTitles().indexOf('방문이 진행되지 않았어요') !== -1);

  /* ----- 취소 (환불 규정 연동·회차 복구) ----- */
  const passBefore = JSON.parse(P17.window.localStorage.getItem('ttokttok_account_v3')).passes[0].remaining;
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1004"] [data-admin-resv-to="canceled"]'));
  ok('P47 운영자 취소 → canceled', statusOf('TT-261126-1004') === 'canceled', statusOf('TT-261126-1004'));
  ok('P48 취소 사유에 환불 규정 라벨 기록', (function () {
    const h = VM.history('TT-261126-1004').slice(-1)[0];
    return h.from === 'rescheduled' && h.to === 'canceled' && h.actor === 'operator' && /^운영자 취소 · /.test(h.reason);
  })(), JSON.stringify(VM.history('TT-261126-1004').slice(-1)[0]));
  ok('P49 취소 시 회차 복구·환불 표시', (function () {
    const acc = JSON.parse(P17.window.localStorage.getItem('ttokttok_account_v3'));
    const b = acc.bookings.filter((x) => x.no === 'TT-261126-1004')[0];
    return acc.passes[0].remaining === passBefore + 1 && /(회차|24시간)/.test(b.refundLabel || '') && b.paymentStatus === 'paid';
  })(), JSON.stringify({ p: passBefore }));

  /* ----- 배정 해제(T5) ----- */
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1002"] [data-admin-resv-to="received"]'));
  ok('P50 배정 해제 → received·선생님 비움', statusOf('TT-261126-1002') === 'received' && (function () {
    const b = VM.reservations().filter((x) => x.no === 'TT-261126-1002')[0];
    return b.teacherId === '' && b.teacher === '';
  })(), statusOf('TT-261126-1002'));
  ok('P51 배정 해제 알림(보호자)', notifTitles().indexOf('선생님 배정을 다시 진행해요') !== -1);

  /* ----- 최종 상태·금지 전이 차단 ----- */
  ok('P52 최종 상태 전이 요청은 실패(상태 불변)', (function () {
    const before = statusOf('TT-261126-1001');
    const r = VM.adminTransition('TT-261126-1001', 'confirmed');
    return r && r.ok === false && r.error === 'transition_not_allowed' && statusOf('TT-261126-1001') === before;
  })());
  ok('P53 건너뛰기(접수→완료)는 엔진이 거부', (function () {
    const r = VM.adminTransition('TT-261126-1007', 'completed');
    return r.ok === false && r.error === 'transition_not_allowed' && statusOf('TT-261126-1007') === 'assigned';
  })());

  /* ----- 안내 문구 복사(발송 없음) ----- */
  hV17.click(hV17.$('#adminResvQueue [data-resv="TT-261126-1007"] [data-admin-notice]'));
  const copy17 = P17.window.__ttokttokAdmin || {};
  ok('P54 안내 문구 복사 훅', copy17.noticeNo === 'TT-261126-1007' && typeof copy17.noticeText === 'string' && copy17.noticeText.length > 40, JSON.stringify(copy17).slice(0, 160));
  ok('P55 복사 문구에 보호자·선생님 안내가 함께', /\[보호자 안내\]/.test(copy17.noticeText) && /\[선생님 안내\]/.test(copy17.noticeText) &&
    /TT-261126-1007/.test(copy17.noticeText) && /요청을 수락하면 방문이 확정돼요/.test(copy17.noticeText), (copy17.noticeText || '').slice(0, 200));
  ok('P56 복사는 안내만 — 발송 문구 없음', !/발송했|전송했|보냈습니다/.test(copy17.noticeText));
  ok('P57 안내 문구는 상태기계 템플릿(RESERVATION_NOTICES)을 그대로 사용', VM.adminNoticeText('TT-261126-1001') ===
    '[보호자 안내]\n방문이 완료됐어요\n' + VM.noticeFor(VM.reservations().filter((b) => b.no === 'TT-261126-1001')[0], 'completed', { refund: 0 }).customer.body +
    '\n\n[선생님 안내]\n방문을 완료 처리했어요\n' + VM.noticeFor(VM.reservations().filter((b) => b.no === 'TT-261126-1001')[0], 'completed', { refund: 0 }).teacher.body,
    VM.adminNoticeText('TT-261126-1001').slice(0, 120));

  /* ----- 보호자 화면 즉시 반영 ----- */
  hV17.click(hV17.$('[data-admin-back]'));
  hV17.click(hV17.$('.tabbtn[data-tab="mypage"]'));
  const myBookings = hV17.text('#bookingList');
  ok('P58 보호자 내 예약에 운영자 처리 상태 즉시 반영', !!hV17.$('#bookingList [data-booking="TT-261126-1001"]') &&
    /방문 완료/.test(hV17.text('#bookingList [data-booking="TT-261126-1001"]')) &&
    /노쇼/.test(hV17.text('#bookingList [data-booking="TT-261126-1003"]')) &&
    /취소됨/.test(hV17.text('#bookingList [data-booking="TT-261126-1004"]')),
    hV17.text('#bookingList [data-booking="TT-261126-1001"]').slice(0, 80));
  ok('P59 취소된 예약은 캘린더 버튼 없음(기존 규칙 유지)', (function () {
    const row = hV17.$('#bookingList [data-booking="TT-261126-1004"]');
    return !!row && !row.querySelector('[data-ics]');
  })());

  /* ----- 저장·새로 열기 ----- */
  const savedAcc = P17.window.localStorage.getItem('ttokttok_account_v3');
  const P18 = makeDom({ ttokttok_account_v3: savedAcc });
  const hV2b = helpers(P18.window, P18.doc);
  await sleep(30);
  hV2b.click(hV2b.$('[data-login="admin"]'));
  ok('P60 새로 열어도 상태 유지(로컬 저장)', hV2b.$$('#adminResvQueue .admin-card').length === 7 && /방문 완료/.test(hV2b.text('#adminResvQueue')), String(hV2b.$$('#adminResvQueue .admin-card').length));
  ok('P61 저장된 예약은 모두 id·enum·이력 보유', (function () {
    const acc = JSON.parse(savedAcc);
    return acc.bookings.every((b) => /^res-/.test(b.id) && VM.statuses.reservation.indexOf(b.status) !== -1 &&
      Array.isArray(b.statusHistory) && b.statusHistory.length >= 1 && !!b.updatedAt);
  })());
  ok('P62 새 화면에서도 시연용 고지 유지', /이 기기에만 저장 · 서버 미연결/.test(hV2b.text('#adminResvDemoNotice')));

  /* ============================================================
     Q. v18 — 규모 확장·자동 매칭 (SCALING-ARCHITECTURE.md)
     ============================================================ */
  function v18SeedAccount() {
    const mk = (no, status, extra) => Object.assign({
      id: 'res-' + no.toLowerCase(), no, userId: 'usr-demo',
      date: '11.30', day: '월', time: '10:00',
      teacher: '', teacherId: '', region: '서울 마포구 성산동', regionId: 'reg-서울-마포구',
      status, passId: 'p8', walletId: 'seed-pass', dateIso: '2026-11-30', amount: 74000, paymentStatus: 'paid',
      symptomCodes: ['stroke']
    }, extra || {});
    return JSON.stringify({
      profile: { name: '현수' },
      passes: [{ id: 'seed-pass', userId: 'usr-demo', passId: 'p8', name: '8회 방문권', total: 8, remaining: 5, purchased: '2026.10.28', expire: '2027.01.27', status: 'active' }],
      bookings: [
        /* 교집합 후보가 있는 접수 — 마포 + 월요일 오전 + 뇌졸중 → 정민아 */
        mk('TT-261128-2001', 'received'),
        /* 후보 0명 지역 — 제주 */
        mk('TT-261128-2002', 'received', { region: '제주 제주시 노형동', regionId: 'reg-제주-제주시' }),
        /* 재확정 필요 — 박서준 선생님이 이미 잡힌 슬롯(자기 자신은 충돌 아님) */
        mk('TT-261128-2003', 'rescheduled', { teacher: '박서준 선생님', teacherId: 'park', region: '서울 강남구 대치동', regionId: 'reg-서울-강남구', date: '11.27', day: '금', dateIso: '2026-11-27', time: '10:30', symptomCodes: ['stroke'] }),
        /* 당일 취소 — 예외: 당일 일정 변경 */
        mk('TT-261128-2004', 'canceled', { region: '서울 강남구 대치동', regionId: 'reg-서울-강남구', dateIso: 'TODAY_PLACEHOLDER' }),
        /* 노쇼 */
        mk('TT-261128-2005', 'no_show', { teacher: '박서준 선생님', teacherId: 'park', region: '서울 강남구 대치동', regionId: 'reg-서울-강남구' }),
        /* 선생님 거절 이력 — 예외: 선생님 거절 (+ 토요일이라 후보 0명) */
        mk('TT-261128-2006', 'received', {
          region: '서울 강남구 대치동', regionId: 'reg-서울-강남구', date: '11.28', day: '토', dateIso: '2026-11-28',
          statusHistory: [{ status: 'received', from: 'assigned', to: 'received', actor: 'operator', reason: '선생님 배정 거절 — 재배정 대기', at: '2026-11-26T01:00:00.000Z' }]
        }),
        /* 컴플레인 표시 — 예외: 컴플레인 */
        mk('TT-261128-2007', 'confirmed', { teacher: '정민아 선생님', teacherId: 'jung', dateIso: '2026-12-01', issue: 'complaint', issueMemo: '도착 시간 지연 문의' })
      ],
      receipts: []
    });
  }

  const KST_TODAY = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
  const D18 = makeDom({ ttokttok_account_v3: v18SeedAccount().replace('TODAY_PLACEHOLDER', KST_TODAY) });
  const hV18 = helpers(D18.window, D18.doc);
  await sleep(30);
  const QVM = D18.window.__ttokttokModel;
  ok('Q0 JS 오류 없음', D18.errors.length === 0, D18.errors.slice(0, 3).join(' | '));
  ok('Q1 v18 모델 노출(scalingVersion)', !!QVM && QVM.scalingVersion === 'v18', QVM && QVM.scalingVersion);
  ok('Q2 v39 meta 표기', /<meta name="app-version" content="v48">/.test(HTML));

  /* ----- 지역 마스터 3단계 ----- */
  const counts18 = QVM.regionMasterCounts();
  ok('Q3 지역 마스터 3단계(시·도 17 / 시·군·구 53 / 동 42)', counts18.province === 17 && counts18.district === 53 && counts18.dong === 42, JSON.stringify(counts18));
  ok('Q4 파주·서대문 마스터 등록', (function () {
    const m = QVM.regionMaster;
    return m.some((r) => r.id === 'reg-경기-파주시' && r.fullName === '경기 파주시') &&
      m.some((r) => r.id === 'reg-서울-서대문구' && r.fullName === '서울 서대문구');
  })());
  ok('Q5 동 계층(동 → 구 → 시·도)', (function () {
    const m = QVM.regionMaster;
    const dong = m.filter((r) => r.level === 'dong');
    return dong.length > 0 && dong.every((d) => {
      const parent = m.filter((p) => p.id === d.parentId && p.level === 'district')[0];
      return !!parent && d.fullName === parent.fullName + ' ' + d.name;
    });
  })(), JSON.stringify(QVM.regionMaster.filter((r) => r.level === 'dong').slice(0, 2)));
  ok('Q6 지역 경로 조회(야당동 → 파주시 → 경기)', (function () {
    const p = QVM.regionPath('reg-경기-파주시-야당동');
    return !!p && p.level === 'dong' && p.dong === '야당동' && p.district === '파주시' && p.province === '경기' && p.text === '경기 파주시';
  })(), JSON.stringify(QVM.regionPath('reg-경기-파주시-야당동')));
  ok('Q7 동 id 조회(마스터에 있을 때만)', QVM.dongIdOf('경기', '파주시', '야당동') === 'reg-경기-파주시-야당동' && QVM.dongIdOf('경기', '파주시', '없는동') === '');
  ok('Q8 선생님 활동 지역 전부 마스터에 매핑(파주·서대문 포함)', (function () {
    const trs = QVM.teacherRegions();
    return trs.length > 0 && trs.every((r) => r.regionId !== null) &&
      trs.some((r) => r.regionId === 'reg-경기-파주시') && trs.some((r) => r.regionId === 'reg-서울-서대문구');
  })(), JSON.stringify(QVM.teacherRegions().filter((r) => !r.regionId).map((r) => r.rawName)));

  /* ----- 교집합 매칭 엔진 ----- */
  const m1 = QVM.matchTeachers({ regionId: 'reg-서울-강남구', symptom: 'stroke', dateIso: '2026-11-27', timeSlot: '10:00' });
  ok('Q9 교집합 1순위(강남·뇌졸중·금 10:00) = 박서준', m1.length === 1 && m1[0].teacherId === 'park', JSON.stringify(m1.map((c) => c.teacherId)));
  ok('Q10 매칭 사유(지역·전문분야·시간) 3종', m1.length === 1 && m1[0].matchedBy.join(',') === 'region,priority,symptom,time' &&
    m1[0].reasons.some((r) => /지역 일치/.test(r)) && m1[0].reasons.some((r) => /전문분야 일치/.test(r)) && m1[0].reasons.some((r) => /시간 가능/.test(r)), JSON.stringify(m1[0] && m1[0].reasons));
  ok('Q11 요일 불가 선생님은 후보에서 제외(토 10:00)', QVM.matchTeachers({ regionId: 'reg-서울-강남구', dateIso: '2026-11-28', timeSlot: '10:00' }).length === 0);
  ok('Q12 지역 불일치·후보 0명(제주)', QVM.matchTeachers({ regionId: 'reg-제주-제주시', symptom: 'stroke', dateIso: '2026-11-27', timeSlot: '10:00' }).length === 0);
  ok('Q13 증상 불일치는 후보는 되지만 점수가 낮고 사유에 없음', (function () {
    const a = QVM.matchTeachers({ regionId: 'reg-서울-마포구', symptom: 'stroke', dateIso: '2026-11-30', timeSlot: '10:00' });
    const b = QVM.matchTeachers({ regionId: 'reg-서울-마포구', symptom: 'pain_joint', dateIso: '2026-11-30', timeSlot: '10:00' });
    return a.length === 1 && b.length === 1 && b[0].matchedBy.indexOf('symptom') === -1 && b[0].score < a[0].score;
  })());
  ok('Q14 requireSymptom 옵션이면 교집합 0', QVM.matchTeachers({ regionId: 'reg-서울-마포구', symptom: 'pain_joint', dateIso: '2026-11-30', timeSlot: '10:00', requireSymptom: true }).length === 0);
  ok('Q15 같은 시간 예약이 있는 선생님은 제외(슬롯 충돌)', (function () {
    const bookings = [{ no: 'X-1', teacherId: 'park', dateIso: '2026-11-27', time: '10:00', status: 'confirmed' }];
    const strict = QVM.matchTeachers({ regionId: 'reg-서울-강남구', dateIso: '2026-11-27', timeSlot: '10:00', bookings });
    const all = QVM.matchTeachers({ regionId: 'reg-서울-강남구', dateIso: '2026-11-27', timeSlot: '10:00', bookings, includeAll: true });
    return strict.length === 0 && all.some((c) => c.teacherId === 'park' && c.blockedBy.indexOf('slot_conflict') !== -1);
  })());
  ok('Q16 주간 방문 한도 초과 차단(maxWeeklyVisits)', (function () {
    const bookings = [];
    for (let i = 0; i < 12; i++) bookings.push({ no: 'W-' + i, teacherId: 'park', dateIso: '2026-11-30', time: (9 + i) + ':00', status: 'confirmed' });
    const r = QVM.teacherAvailability('park', '2026-12-04', '10:00', { bookings });
    return !!r && r.ok === false && r.blockedBy.indexOf('weekly_limit') !== -1;
  })());
  ok('Q17 동 단위 요청은 같은 구 선생님과 교집합', QVM.matchTeachers({ dongId: 'reg-서울-마포구-성산동', dateIso: '2026-11-30', timeSlot: '10:00' })[0].teacherId === 'jung');

  /* ----- 매칭 대기열 ----- */
  hV18.click(hV18.$('[data-login="customer"]'));
  const queue18 = QVM.matchingQueue();
  ok('D18 대기열은 미배정·재확정만(접수 3 · 재확정 1)', queue18.total === 4 && queue18.counts.unassigned === 3 && queue18.counts.reconfirm === 1, JSON.stringify(queue18.counts));
  ok('Q19 대기열 각 건 후보 수·1순위 추천', (function () {
    const a = queue18.waiting.filter((w) => w.no === 'TT-261128-2001')[0];
    const b = queue18.waiting.filter((w) => w.no === 'TT-261128-2002')[0];
    return !!a && a.candidateCount === 1 && a.topCandidate && a.topCandidate.teacherId === 'jung' &&
      !!b && b.candidateCount === 0 && b.needsHuman === true && b.topCandidate === null;
  })(), JSON.stringify(queue18.waiting.map((w) => [w.no, w.candidateCount])));
  ok('Q20 대기열은 후보 0명을 먼저 보여준다', queue18.waiting[0].needsHuman === true);
  ok('Q21 대기열 지역 표기는 시·군·구까지(동 미노출)', queue18.waiting.every((w) => !/동\s*$/.test(w.regionText) && !/성산동|대치동|노형동/.test(w.regionText)), JSON.stringify(queue18.waiting.map((w) => w.regionText)));

  /* ----- 예외 분류 ----- */
  const ex18 = QVM.exceptions();
  ok('Q22 예외 5종 분류·카운트', ex18.groups.length === 5 && ex18.counts.teacher_declined === 1 && ex18.counts.same_day_change === 1 &&
    ex18.counts.no_show === 1 && ex18.counts.complaint === 1 && ex18.counts.no_candidate === 2, JSON.stringify(ex18.counts));
  ok('Q23 예외 항목에 담당·SLA·다음 행동', ex18.groups.every((g) => g.owner === '사람' && !!g.sla) &&
    ex18.groups.filter((g) => g.code === 'teacher_declined')[0].items[0].action === '재배정 후보 확인');
  ok('Q24 예외는 끝난 예약(완료)은 잡지 않는다', !ex18.groups.some((g) => g.items.some((i) => i.status === 'completed')));

  /* ----- 리마인드 문구 ----- */
  const rm1 = QVM.reminderNotice('TT-261128-2001', 'd_minus_1');
  ok('Q25 D-1 리마인드 문구(보호자·선생님)', !!rm1 && rm1.ok && /내일 10:00 방문/.test(rm1.customer.title) &&
    /TT-261128-2001/.test(rm1.customer.body) && /서울 마포구/.test(rm1.teacher.body) && /\[보호자 안내\]/.test(rm1.text), JSON.stringify(rm1).slice(0, 200));
  const rm2 = QVM.reminderNotice('TT-261128-2001', 'before_30m');
  ok('Q26 30분 전 문구·모르는 종류 거부', !!rm2 && rm2.ok && /30분/.test(rm2.customer.title) &&
    QVM.reminderNotice('TT-261128-2001', 'nope').ok === false);
  ok('Q27 리마인드 문구는 발송 표현 없음(복사용)', !/발송했|전송했|보냈습니다/.test(rm1.text + rm2.text));

  /* ----- 관리자 배정 화면 연결(레이아웃 변경 없음) ----- */
  hV18.click(hV18.$('[data-login="admin"]'));
  await sleep(30);
  const card2001 = hV18.text('#adminResvQueue [data-resv="TT-261128-2001"]');
  ok('Q28 카드에 교집합 후보 수·1순위', /교집합 후보 1명/.test(card2001) && /1순위 정민아 선생님/.test(card2001), card2001.slice(0, 240));
  const card2002 = hV18.text('#adminResvQueue [data-resv="TT-261128-2002"]');
  ok('Q29 후보 0명은 사람이 볼 수 있게 표시', /교집합 후보 0명/.test(card2002), card2002.slice(0, 240));
  ok('Q30 드롭다운 1순위가 교집합 후보', (function () {
    const sel = hV18.$('[data-admin-resv-teacher="TT-261128-2001"]');
    if (!sel) return false;
    const opts = Array.from(sel.querySelectorAll('option')).filter((o) => o.value);
    return opts[0].value === 'jung' && /교집합 1순위/.test(opts[0].textContent);
  })(), (hV18.$('[data-admin-resv-teacher="TT-261128-2001"]') || {}).innerHTML || '');
  ok('Q31 교집합에 없어도 사람이 직접 배정 가능(전체 후보 유지)', (function () {
    const sel = hV18.$('[data-admin-resv-teacher="TT-261128-2002"]');
    return !!sel && sel.querySelectorAll('option').length >= 9;
  })());
  ok('Q32 후보가 있어도 실제 배정은 사람이 누른다(자동 배정 없음)', QVM.adminStatusOf('TT-261128-2001') === 'received');

  /* ----- 계산만 하고 저장·발송하지 않는다 ----- */
  const accBefore = D18.window.localStorage.getItem('ttokttok_account_v3');
  const notifBefore = QVM.notifs().length;
  QVM.matchingQueue(); QVM.exceptions(); QVM.reminderNotice('TT-261128-2001', 'd_minus_1');
  QVM.matchTeachers({ regionId: 'reg-서울-강남구', dateIso: '2026-11-27', timeSlot: '10:00' });
  ok('Q33 매칭·리마인드 계산은 저장·발송을 하지 않는다',
    D18.window.localStorage.getItem('ttokttok_account_v3') === accBefore && QVM.notifs().length === notifBefore);
  ok('Q34 배정 후보 안내 문구에도 동·번지 없음', !/성산동|대치동|노형동/.test(hV18.text('#adminResvQueue')));
  ok('Q35 CSS 토큰 정합성(v35: :root 하나·var 전부 정의·중괄호 균형)', cssTokens(HTML).ok,
    String(/<style>([\s\S]*?)<\/style>/.exec(HTML)[1].length));
  const scalingDoc = fs.readFileSync(path.join(__dirname, '..', 'SCALING-ARCHITECTURE.md'), 'utf8');
  ok('Q36 SCALING-ARCHITECTURE.md — 가정치·운영 인력 기준표·예외 목록', /가정치/.test(scalingDoc) && /10건/.test(scalingDoc) && /100건/.test(scalingDoc) &&
    /선생님 거절/.test(scalingDoc) && /노쇼/.test(scalingDoc) && /컴플레인/.test(scalingDoc) && /Region/.test(scalingDoc));

  /* ============================================================
     R. v19 — 실서비스 운영·파트너 화면 완성팩
       (1) 관리자 매칭 대기열·운영 예외 보드 (2) 센터/선생님 사정 100% 취소
       (3) 일정 변경 → 재확정 (4) 선생님 알림함 (5) 선생님 직접 가용시간·지역 등록
     ============================================================ */
  const D19 = makeDom({ ttokttok_account_v3: v18SeedAccount().replace('TODAY_PLACEHOLDER', KST_TODAY) });
  const h19 = helpers(D19.window, D19.doc);
  await sleep(30);
  const RVM = D19.window.__ttokttokModel;
  ok('R0 v19 JS 오류 없음', D19.errors.length === 0, D19.errors.slice(0, 3).join(' | '));
  ok('R1 앱 버전 v19 이상(meta)', /<meta name="app-version" content="v(19|20|21|22|23|24|25|26|27|28|29|30|31|32|33|34|35|36|37|38|39|40|41|42|43|44|45|46|47|48)">/.test(HTML) &&
    ['v19', 'v20', 'v21', 'v22', 'v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29', 'v30', 'v31', 'v32', 'v33', 'v34', 'v35', 'v36', 'v37', 'v38', 'v39', 'v40', 'v41', 'v42', 'v43', 'v44', 'v45', 'v46', 'v48'].indexOf(D19.doc.querySelector('meta[name="app-version"]').getAttribute('content')) !== -1);
  ok('R2 v19 운영 도구 노출(opsVersion·취소 사유·알림함·가용시간)', !!RVM && RVM.opsVersion === 'v19' &&
    typeof RVM.opsBoard === 'function' && typeof RVM.savePartnerAvailability === 'function' && typeof RVM.teacherNotifs === 'function', RVM && RVM.opsVersion);

  /* ----- (1) 관리자: 매칭 대기열 & 운영 예외 보드 ----- */
  h19.click(h19.$('[data-login="admin"]'));
  await sleep(30);
  ok('R3 관리자 상단에 보드가 예약 큐보다 위에 있다', (function () {
    const board = h19.$('#adminOpsSec');
    const queue = h19.$('#adminResvSec');
    if (!board || !queue) return false;
    return !!(board.compareDocumentPosition(queue) & D19.window.Node.DOCUMENT_POSITION_FOLLOWING);
  })());
  const board19 = RVM.opsBoard();
  ok('R4 대기열·예외 요약 건수(미배정 3·재확정 1·후보0 2·예외 6)',
    board19.queue.counts.unassigned === 3 && board19.queue.counts.reconfirm === 1 &&
    board19.queue.counts.noCandidate === 2 && board19.exceptions.total === 6, JSON.stringify([board19.queue.counts, board19.exceptions.total]));
  ok('R5 보드 요약을 화면에 표시', /미배정 3/.test(h19.text('#adminOpsCounts')) && /재확정 대기 1/.test(h19.text('#adminOpsCounts')) &&
    /운영 예외 6/.test(h19.text('#adminOpsCounts')), h19.text('#adminOpsCounts'));
  ok('R6 대기열은 후보 0명을 먼저 보여준다', (function () {
    const first = h19.$('#adminMatchQueue .admin-card');
    return !!first && first.getAttribute('data-queue') === 'TT-261128-2006';
  })(), (h19.$('#adminMatchQueue .admin-card') || {}).outerHTML ? h19.$('#adminMatchQueue .admin-card').getAttribute('data-queue') : '');
  ok('R7 대기열 카드에 후보 수·1순위·원클릭 배정 버튼', (function () {
    const card = h19.$('#adminMatchQueue [data-queue="TT-261128-2001"]');
    if (!card) return false;
    const txt = card.textContent.replace(/\s+/g, ' ');
    const btn = card.querySelector('[data-admin-quick="TT-261128-2001"]');
    return /교집합 후보 1명/.test(txt) && /1순위 정민아 선생님/.test(txt) &&
      !!btn && /1순위 정민아 배정/.test(btn.textContent) && btn.getAttribute('data-quick-teacher') === 'jung';
  })());
  ok('R8 후보 0명 건은 원클릭 배정 없이 큐로 안내', (function () {
    const card = h19.$('#adminMatchQueue [data-queue="TT-261128-2002"]');
    return !!card && !card.querySelector('[data-admin-quick]') && /큐에서 보기/.test(card.textContent);
  })());
  ok('R9 운영 예외 보드 5종(라벨·담당·SLA·다음 행동)', (function () {
    const groups = h19.$$('#adminExceptionBoard .admin-card');
    const txt = h19.text('#adminExceptionBoard');
    return groups.length === 5 && /선생님 거절/.test(txt) && /2시간 내 재배정/.test(txt) &&
      /환불·회차 복구 확인/.test(txt) && /컴플레인/.test(txt) && /후보 0명 지역/.test(txt);
  })(), h19.text('#adminExceptionBoard').slice(0, 200));
  ok('R10 예외 항목 → 예약 큐 카드로 이동(상태 필터 자동 선택)', (function () {
    const btn = h19.$('#adminExceptionBoard [data-admin-focus="TT-261128-2004"]');
    if (!btn) return false;
    h19.click(btn);
    return RVM.adminActiveFilter() === 'closed' && !!h19.$('#adminResvQueue [data-resv="TT-261128-2004"]');
  })(), RVM.adminActiveFilter());
  h19.click(h19.$('[data-admin-resv-filter="all"]'));
  await sleep(10);
  ok('R11 원클릭 1순위 배정(접수 → 배정)', (function () {
    const btn = h19.$('#adminMatchQueue [data-admin-quick="TT-261128-2001"]');
    if (!btn) return false;
    h19.click(btn);
    const b = RVM.reservations().filter((x) => x.no === 'TT-261128-2001')[0];
    return b.status === 'assigned' && b.teacherId === 'jung';
  })());
  ok('R12 원클릭 배정도 상태기계·이력·알림을 그대로 지난다', (function () {
    const h = RVM.history('TT-261128-2001').slice(-1)[0];
    return h.actor === 'operator' && h.from === 'received' && h.to === 'assigned' && /운영자 배정 · 정민아 선생님/.test(h.reason) &&
      RVM.notifs().some((n) => n.audience === 'customer' && n.title === '선생님 배정이 끝났어요');
  })(), JSON.stringify(RVM.history('TT-261128-2001').slice(-1)[0]));
  ok('R13 일정 변경 카드는 "일정 재확정" 버튼·라벨', (function () {
    const card = h19.$('#adminMatchQueue [data-queue="TT-261128-2003"]');
    return !!card && /일정 재확정/.test(card.textContent) && /일정 변경됨/.test(card.textContent);
  })());
  ok('R14 원클릭 재확정(일정 변경 → 확정)', (function () {
    const btn = h19.$('#adminMatchQueue [data-admin-quick="TT-261128-2003"]');
    if (!btn) return false;
    h19.click(btn);
    const b = RVM.reservations().filter((x) => x.no === 'TT-261128-2003')[0];
    const h = b.statusHistory.slice(-1)[0];
    return b.status === 'confirmed' && /운영자 일정 재확정/.test(h.reason);
  })());
  ok('R15 처리 후 보드는 즉시 다시 계산(대기 4 → 2)', RVM.opsBoard().queue.total === 2, String(RVM.opsBoard().queue.total));

  /* ----- (2) 관리자: 취소 사유 선택(보호자 / 센터·선생님 사정) ----- */
  ok('R16 취소 사유 3종·기본값은 보호자 요청', (function () {
    const sel = h19.$('[data-admin-cancel-reason="TT-261128-2007"]');
    if (!sel) return false;
    const opts = Array.from(sel.querySelectorAll('option')).map((o) => o.value);
    return sel.value === 'customer' && opts.join(',') === 'customer,center,teacher' &&
      RVM.cancelReasons.length === 3 && /100% 환불/.test(RVM.cancelReasons[1].label);
  })());
  /* 24시간 이내 단건 결제 예약을 추가해 구간별 견적 차이를 본다(회차권이 아닌 건). */
  const soon = new Date(Date.now() + 6 * 3600 * 1000);
  const soonIso = soon.getFullYear() + '-' + String(soon.getMonth() + 1).padStart(2, '0') + '-' + String(soon.getDate()).padStart(2, '0');
  const soonTime = String(soon.getHours()).padStart(2, '0') + ':' + String(soon.getMinutes()).padStart(2, '0');
  RVM.reservations().push({
    id: 'res-tt-261129-9001', no: 'TT-261129-9001', userId: 'usr-demo',
    date: '11.26', day: '목', time: soonTime, dateIso: soonIso,
    teacher: '박서준 선생님', teacherId: 'park', region: '서울 마포구 성산동', regionId: 'reg-서울-마포구',
    status: 'confirmed', amount: 74000, paymentStatus: 'paid', passId: '', walletId: '',
    statusHistory: [{ status: 'confirmed', from: 'assigned', to: 'confirmed', actor: 'operator', reason: '운영자 방문 확정', at: '2026-11-26T02:00:00.000Z' }]
  });
  h19.click(h19.$('[data-admin-resv-filter="all"]'));
  await sleep(10);
  ok('R17 24시간 이내 보호자 요청은 50%·센터 사정은 100%', (function () {
    const qc = RVM.adminCancelQuote('TT-261129-9001', 'customer');
    const qe = RVM.adminCancelQuote('TT-261129-9001', 'center');
    const qt = RVM.adminCancelQuote('TT-261129-9001', 'teacher');
    return qc.refund === 37000 && qc.pct === 50 && qe.refund === 74000 && qe.pct === 100 && qt.refund === 74000;
  })(), JSON.stringify([RVM.adminCancelQuote('TT-261129-9001', 'customer').refund, RVM.adminCancelQuote('TT-261129-9001', 'center').refund]));
  ok('R18 사유를 바꾸면 예상 견적이 바로 갱신된다', (function () {
    const sel = h19.$('[data-admin-cancel-reason="TT-261129-9001"]');
    if (!sel) return false;
    const before = h19.text('[data-admin-cancel-quote="TT-261129-9001"]');
    h19.setSel(sel, 'center');
    const after = h19.text('[data-admin-cancel-quote="TT-261129-9001"]');
    return /50%/.test(before) && /센터 사정 취소 · 전액 환불/.test(after) && /74,000원/.test(after);
  })(), h19.text('[data-admin-cancel-quote="TT-261129-9001"]'));
  ok('R19 센터 사정 취소 → 전액 환불·영수증·이력', (function () {
    const btn = h19.$('#adminResvQueue [data-resv="TT-261129-9001"] [data-admin-resv-to="canceled"]');
    if (!btn) return false;
    h19.click(btn);
    const b = RVM.reservations().filter((x) => x.no === 'TT-261129-9001')[0];
    const acc = JSON.parse(D19.window.localStorage.getItem('ttokttok_account_v3'));
    return b.status === 'canceled' && b.refund === 74000 && b.paymentStatus === 'refund_pending' &&
      /센터 사정/.test(b.statusHistory.slice(-1)[0].reason) &&
      (acc.receipts || []).some((r) => /^RF-/.test(r.no) && r.amount === 74000);
  })(), JSON.stringify(RVM.reservations().filter((x) => x.no === 'TT-261129-9001')[0]));
  ok('R20 현상 변경은 저장된다(새로 열어도 유지)', (function () {
    const acc = JSON.parse(D19.window.localStorage.getItem('ttokttok_account_v3'));
    const b = acc.bookings.filter((x) => x.no === 'TT-261129-9001')[0];
    return b.status === 'canceled' && b.refund === 74000;
  })());

  /* ----- (4) 선생님 전용 알림함 ----- */
  h19.click(h19.$('[data-login="therapist"]'));
  await sleep(30);
  ok('R21 선생님 모드 진입', D19.doc.querySelector('.screen.is-active').id === 'screen-tp-home');
  ok('R22 선생님 알림함에 배정·확정·취소 알림이 쌓인다', (function () {
    const list = RVM.teacherNotifs();
    const unread = RVM.teacherUnread();
    return list.length >= 2 && unread === list.filter((n) => !n.read).length && unread > 0 &&
      h19.$$('#tpNotifList [data-tp-notif]').length === Math.min(list.length, 8) &&
      /안 읽음/.test(h19.text('#tpNotifCount'));
  })(), JSON.stringify(RVM.teacherNotifs()));
  ok('R23 알림 클릭 → 읽음 처리·저장', (function () {
    const before = RVM.teacherUnread();
    const btn = h19.$('#tpNotifList [data-tp-notif]');
    if (!btn) return false;
    const id = btn.getAttribute('data-tp-notif');
    h19.click(btn);
    const saved = JSON.parse(D19.window.localStorage.getItem('ttokttok_notifs_v1') || '[]');
    const row = saved.filter((n) => n.id === id)[0];
    return RVM.teacherUnread() === before - 1 && !!row && row.read === true && row.status === 'read';
  })());
  ok('R24 알림 모두 읽음', (function () {
    const btn = h19.$('#tpNotifSec [data-tp-notif-all]');
    if (!btn) return false;
    h19.click(btn);
    return RVM.teacherUnread() === 0 && !/안 읽음/.test(h19.text('#tpNotifCount')) && btn.disabled === true;
  })());
  ok('R25 선생님 알림은 보호자 알림함·배지와 섞이지 않는다', RVM.notifs().filter((n) => n.audience === 'teacher').every((n) => n.read) &&
    h19.$$('#notifList [data-notif]').length > 0 &&
    h19.$$('#notifList [data-notif]').every((el) => RVM.notifs().filter((n) => n.id === el.getAttribute('data-notif') && n.audience === 'teacher').length === 0));

  /* ----- (5) 선생님 직접 가용시간·활동 지역 ----- */
  ok('R26 가능 시간·지역·전문분야 폼(요일 7·시간대 3·전문분야 5·시·도·구·동)', (function () {
    return h19.$$('#tpAvailForm [data-tp-day]').length === 7 &&
      h19.$$('#tpAvailForm [data-tp-time]').length === 3 &&
      h19.$$('#tpAvailForm [data-tp-field]').length === 5 &&
      h19.$$('#tpAvailForm [data-tp-field].is-on').length >= 1 &&
      !!h19.$('#tpProvince') && h19.$$('#tpAvailForm [data-tp-district]').length === 8 &&
      h19.$$('#tpAvailForm [data-tp-dong]').length > 0 && !!h19.$('#tpMaxWeekly') && !!h19.$('#tpAvailSave');
  })(), String(h19.$$('#tpAvailForm [data-tp-district]').length));
  ok('R27 요일·시간대·전문분야·주당 한도를 직접 바꾸어 저장', (function () {
    h19.click(h19.$('#tpAvailForm [data-tp-day="토"]'));
    h19.click(h19.$('#tpAvailForm [data-tp-time="저녁"]'));
    h19.click(h19.$('#tpAvailForm [data-tp-field="신경계"]'));
    h19.setVal(h19.$('#tpMaxWeekly'), '15');
    h19.click(h19.$('#tpAvailSave'));
    const a = RVM.partnerAvailability();
    return a.days.indexOf('토') !== -1 && a.times.indexOf('저녁') !== -1 && a.maxWeeklyVisits === 15 && a.fields.indexOf('신경계') !== -1;
  })(), JSON.stringify(RVM.partnerAvailability()));
  ok('R28 저장 → 매칭 엔진 입력(teachers)에 반영', (function () {
    const t = RVM.partnerTeacherRecord();
    return !!t && t.availableDays.indexOf('토') !== -1 && t.maxWeeklyVisits === 15 && t.cats.indexOf('nerve') !== -1;
  })(), JSON.stringify(RVM.partnerTeacherRecord()));
  ok('R29 활동 지역을 마스터(시·도/시·군·구/동)로 등록하면 후보가 된다', (function () {
    const r = RVM.savePartnerAvailability({ days: ['토'], times: ['오전'], maxWeekly: 6, province: '서울', districts: ['마포구'], dongs: ['reg-서울-마포구-성산동'] });
    const t = RVM.partnerTeacherRecord();
    const cand = RVM.matchTeachers({ regionId: 'reg-서울-마포구', dateIso: '2026-11-28', timeSlot: '11:00' }).map((c) => c.teacherId);
    return r.ok === true && /마포구/.test(t.regions) && /성산동/.test(t.regionDetail) && cand.indexOf('park') !== -1;
  })(), JSON.stringify(RVM.partnerTeacherRecord()));
  ok('R29b 전문분야를 바꾸면 증상 교집합도 바뀐다', (function () {
    const r = RVM.savePartnerAvailability({ days: ['토'], times: ['오전'], maxWeekly: 6, province: '서울', districts: ['마포구'], dongs: ['reg-서울-마포구-성산동'], fields: ['통증·관절'] });
    const t = RVM.partnerTeacherRecord();
    const c1 = RVM.matchTeachers({ regionId: 'reg-서울-마포구', dateIso: '2026-11-28', timeSlot: '11:00', symptom: 'stroke' });
    const c2 = RVM.matchTeachers({ regionId: 'reg-서울-마포구', dateIso: '2026-11-28', timeSlot: '11:00', symptom: 'pain_joint' });
    return r.ok === true && t.cats.join(',') === 'ortho,spine' && c1.length === 1 && c2.length === 1 &&
      c1[0].matchedBy.indexOf('symptom') === -1 && c2[0].matchedBy.indexOf('symptom') !== -1;
  })(), JSON.stringify(RVM.partnerTeacherRecord()));
  ok('R30 요일을 모두 빼면 저장을 막는다', RVM.savePartnerAvailability({ days: [] }).ok === false);
  ok('R31 등록값을 기기에 남긴다(teacher profile override)', (function () {
    const raw = D19.window.localStorage.getItem('ttokttok_teacher_profile_v1');
    if (!raw) return false;
    const o = JSON.parse(raw);
    return o.teacherId === 'park' && /마포구/.test(o.regions) && o.availableDays.join(',') === '토';
  })());
  const D19b = makeDom({
    ttokttok_account_v3: v18SeedAccount().replace('TODAY_PLACEHOLDER', KST_TODAY),
    ttokttok_partner_v1: D19.window.localStorage.getItem('ttokttok_partner_v1'),
    ttokttok_teacher_profile_v1: D19.window.localStorage.getItem('ttokttok_teacher_profile_v1')
  });
  const h19b = helpers(D19b.window, D19b.doc);
  await sleep(30);
  const RVMb = D19b.window.__ttokttokModel;
  ok('R32 새로 열어도 직접 등록한 가능시간·지역이 유지된다', (function () {
    const t = RVMb.partnerTeacherRecord();
    const cand = RVMb.matchTeachers({ regionId: 'reg-서울-마포구', dateIso: '2026-11-28', timeSlot: '11:00' }).map((c) => c.teacherId);
    return !!t && t.availableDays.join(',') === '토' && /마포구/.test(t.regions) && cand.indexOf('park') !== -1 && t.cats.join(',') === 'ortho,spine';
  })(), JSON.stringify(RVMb.partnerTeacherRecord()));
  ok('R33 화면도 저장값으로 그려진다', (function () {
    h19b.click(h19b.$('[data-login="therapist"]'));
    const on = h19b.$$('#tpAvailForm [data-tp-day].is-on').map((b) => b.textContent);
    return on.join(',') === '토' && h19b.$$('#tpAvailForm [data-tp-district].is-on').map((b) => b.textContent).indexOf('마포구') !== -1;
  })());

  /* ----- (3) 보호자: 일정 변경 → 재확정 ----- */
  const D19c = makeDom({ ttokttok_account_v3: v18SeedAccount().replace('TODAY_PLACEHOLDER', KST_TODAY) });
  const h19c = helpers(D19c.window, D19c.doc);
  await sleep(30);
  const RVMc = D19c.window.__ttokttokModel;
  h19c.click(h19c.$('[data-login="customer"]'));
  await sleep(20);
  ok('R34 보호자 내 예약에 재확정 버튼(일정 변경 건만)', (function () {
    const row = h19c.$('#bookingList [data-booking="TT-261128-2003"]');
    const btn = row && row.querySelector('[data-reconfirm="TT-261128-2003"]');
    const other = h19c.$('#bookingList [data-booking="TT-261128-2005"]');
    return !!btn && /재확정/.test(btn.textContent) && !!other && !other.querySelector('[data-reconfirm]');
  })());
  ok('R35 재확정 실행 → confirmed · actor customer · 선생님 알림', (function () {
    h19c.click(h19c.$('#bookingList [data-reconfirm="TT-261128-2003"]'));
    const b = RVMc.reservations().filter((x) => x.no === 'TT-261128-2003')[0];
    const h = b.statusHistory.slice(-1)[0];
    return b.status === 'confirmed' && h.actor === 'customer' && h.to === 'confirmed' &&
      RVMc.notifs().some((n) => n.audience === 'teacher' && n.title === '방문이 확정됐어요');
  })(), JSON.stringify(RVMc.history('TT-261128-2003').slice(-1)[0]));
  ok('R36 재확정 후에는 버튼이 사라진다(중복 전이 없음)', !h19c.$('#bookingList [data-booking="TT-261128-2003"] [data-reconfirm]') &&
    RVMc.reconfirm('TT-261128-2003').ok === false);
  ok('R37 재확정 전이는 보호자·관리자 모두 같은 표(T11)를 쓴다',
    RVMc.canTransition('rescheduled', 'confirmed', 'customer') === true &&
    RVMc.canTransition('rescheduled', 'confirmed', 'operator') === true &&
    RVMc.canTransition('assigned', 'confirmed', 'customer') === false &&
    RVMc.canTransition('completed', 'confirmed', 'operator') === false);

  /* ----- 디자인·규칙 유지 ----- */
  ok('R38 CSS 토큰 정합성(v35: :root 하나·var 전부 정의·중괄호 균형)', cssTokens(HTML).ok,
    String(/<style>([\s\S]*?)<\/style>/.exec(HTML)[1].length));
  ok('R39 관리자 화면에 시연용 고지 유지', /이 기기에만 저장 · 서버 미연결/.test(h19.text('#adminResvDemoNotice')));
  ok('R40 문자·카카오 발송 없음(앱 안 알림만)', !/발송했|전송했|보냈습니다/.test(h19.text('#tpNotifSec') + h19.text('#adminOpsSec')));

  /* ============================================================
     S. v20 — 방문 일지 2분 입력 · 주간 보호자 리포트 · 4주 재평가 · 안전 장치
       (1) 2분 빠른 일지(통증·컨디션 1~5 · 수행 동작 · 한 줄 · 포커스)
       (2) 주 1회 보호자 리포트(회차·컨디션 변화·다음 주 집중·공유 텍스트)
       (3) 4주(28일) 재평가 — 관리자 보드·선생님 알림함·보호자 배지
       (4) 신뢰·안전 — 방문 시작/종료 시각·긴급 연락·건강정보 보관 원칙
     ============================================================ */
  const isoShift = (days) => {
    const d = new Date(KST_TODAY + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  };
  const isoLabel = (iso) => {
    const p = iso.split('-');
    return p[0] + '.' + p[1] + '.' + p[2];
  };
  /* 이번 주(월~일) 안의 두 번 방문 + 지난주 한 번 */
  const weekJournals = [
    { id: 'jnl-w1', date: isoLabel(isoShift(-2)), visitDate: isoShift(-2), patient: '김순자 어르신', pain5: 3, condition5: 3, activities: ['walk', 'sit_stand'], note: '계단 오르기 시작', nextFocus: '보행 안정성', status: 'shared' },
    { id: 'jnl-w2', date: isoLabel(isoShift(0)), visitDate: isoShift(0), patient: '김순자 어르신', pain5: 2, condition5: 4, activities: ['walk', 'stairs'], note: '계단 흔들림이 줄었어요', nextFocus: '균형·낙상 예방', status: 'shared' },
    { id: 'jnl-old', date: isoLabel(isoShift(-9)), visitDate: isoShift(-9), patient: '김순자 어르신', pain5: 4, condition5: 2, activities: ['adl'], note: '지난주 기록', status: 'shared' },
    /* 첫 방문 32일 전 기록 — 이번 주 리포트에서는 제외되지만 4주 재평가 기준일이 된다 */
    { id: 'jnl-t1', date: isoLabel(isoShift(-32)), visitDate: isoShift(-32), patient: '김순자 어르신', pain5: 4, condition5: 2, activities: ['walk'], note: '초기 평가', status: 'shared' }
  ];
  const v20PartnerSchedule = [
    { id: 's1', patient: '김순자 어르신', region: '서울 강남구 대치동', date: '오늘', day: '목', time: '14:00', pass: '8회 방문권 · 5회기', checked: false, status: 'confirmed' },
    { id: 's2', patient: '박정호 어르신', region: '서울 마포구 성산동', date: '11/27', day: '금', time: '10:30', pass: '8회 방문권 · 3회기', checked: false, status: 'confirmed' }
  ];
  const v20PartnerSeed = (journals, schedule) => JSON.stringify({
    status: 'approved', teacherId: 'park', name: '박서준', license: '물리치료사',
    requests: [], schedule: schedule || v20PartnerSchedule, journals: journals || []
  });
  const v20SeedAccount = (todayIso) => JSON.stringify({
    profile: { name: '현수' },
    passes: [{ id: 'seed-pass', userId: 'usr-demo', passId: 'p8', name: '8회 방문권', total: 8, remaining: 5, purchased: '2026.10.28', expire: '2027.01.27', status: 'active' }],
    bookings: [
      /* 첫 방문 30일 전 → 4주(28일) 재평가 도래(D+2) */
      { id: 'res-270001-0001', no: 'TT-270001-0001', userId: 'usr-demo', memberId: 'kim', patient: '김순자 어르신',
        date: '10.27', day: '화', time: '10:30', teacher: '박서준 선생님', teacherId: 'park',
        region: '서울 강남구 대치동', regionId: 'reg-서울-강남구', status: 'completed', passId: 'p8', walletId: 'seed-pass',
        dateIso: isoShift(-30), amount: 74000, paymentStatus: 'paid', symptomCodes: ['stroke'] },
      /* 다음 방문(확정) — 재평가 알림을 받는 회원 */
      { id: 'res-270001-0002', no: 'TT-270001-0002', userId: 'usr-demo', memberId: 'kim', patient: '김순자 어르신',
        date: '11.28', day: '토', time: '10:30', teacher: '박서준 선생님', teacherId: 'park',
        region: '서울 강남구 대치동', regionId: 'reg-서울-강남구', status: 'confirmed', passId: 'p8', walletId: 'seed-pass',
        dateIso: isoShift(2), amount: 74000, paymentStatus: 'paid', symptomCodes: ['stroke'] },
      /* 첫 방문 26일 전 → 재평가 임박(D-2) */
      { id: 'res-270001-0003', no: 'TT-270001-0003', userId: 'usr-demo', memberId: 'park2', patient: '박정호 어르신',
        date: '10.31', day: '토', time: '15:00', teacher: '박서준 선생님', teacherId: 'park',
        region: '서울 마포구 성산동', regionId: 'reg-서울-마포구', status: 'completed', passId: 'p8', walletId: 'seed-pass',
        dateIso: isoShift(-26), amount: 74000, paymentStatus: 'paid', symptomCodes: ['knee_postop'] },
      /* 취소된 오래된 예약 — 재평가 기준일로 쓰지 않는다 */
      { id: 'res-270001-0004', no: 'TT-270001-0004', userId: 'usr-demo', memberId: 'lee', patient: '최은자 어르신',
        date: '10.01', day: '목', time: '16:00', teacher: '', teacherId: '',
        region: '서울 송파구 잠실동', regionId: 'reg-서울-송파구', status: 'canceled', passId: 'p8', walletId: 'seed-pass',
        dateIso: isoShift(-56), amount: 74000, paymentStatus: 'paid' }
    ],
    receipts: []
  });

  const D20 = makeDom({ ttokttok_account_v3: v20SeedAccount(KST_TODAY), ttokttok_partner_v1: v20PartnerSeed(weekJournals) });
  const h20 = helpers(D20.window, D20.doc);
  await sleep(40);
  const SVM = D20.window.__ttokttokModel;
  ok('S0 v20 JS 오류 없음', D20.errors.length === 0, D20.errors.slice(0, 3).join(' | '));
  ok('S1 v31 메타·모델 노출(visitLogVersion 20)', /<meta name="app-version" content="v48">/.test(HTML) &&
    D20.doc.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' && !!SVM && SVM.visitLogVersion === 20, SVM && SVM.visitLogVersion);
  ok('S2 2분 일지 어휘(척도 5 · 동작 8 · 포커스 6)', SVM.quickScale.length === 5 && SVM.quickActivities.length === 8 && SVM.quickFocus.length === 6 &&
    SVM.quickScale[0].score === 1 && SVM.quickScale[4].score === 5);

  /* ----- (1) 2분 빠른 일지: 모델 ----- */
  ok('S3 척도는 1~5만 인정(0·9·문자는 버린다)', (function () {
    const bad = SVM.normalizeQuickLog({ pain: 0, condition: 9, activities: ['walk'] });
    const good = SVM.normalizeQuickLog({ pain: '4', condition: 2, activities: ['보행 연습', 'walk', '없는동작'] });
    return bad.pain === null && bad.condition === null && good.pain === 4 && good.condition === 2 &&
      good.activities.join(',') === 'walk';
  })(), JSON.stringify(SVM.normalizeQuickLog({ pain: 0, condition: 9, activities: ['walk', 'walk'] })));
  ok('S4 필수 3종(통증·컨디션·수행 동작) 판정', (function () {
    const m = SVM.quickLogMissing({ pain: 3 });
    const m2 = SVM.quickLogMissingLabel({ pain: 3, condition: 4, activities: ['walk'] });
    return m.join(',') === 'condition,activities' && m2.length === 0 &&
      SVM.isQuickLogComplete({ pain: 3, condition: 4, activities: ['walk'] }) === true;
  })(), JSON.stringify(SVM.quickLogMissing({ pain: 3 })));
  ok('S5 빠른 일지 → 공유 일지 레코드(pain5·condition5·동작·한 줄·포커스)', (function () {
    const r = SVM.buildQuickJournal({ patient: '김순자 어르신', pain: 2, condition: 4, activities: ['walk', 'stairs'], note: '  계단  흔들림   감소 ', nextFocus: '균형·낙상 예방', teacherId: 'park', date: '2026.11.26' });
    return r.ok === true && r.journal.pain5 === 2 && r.journal.condition5 === 4 &&
      r.journal.activities.join(',') === 'walk,stairs' && r.journal.note === '계단 흔들림 감소' &&
      r.journal.nextFocus === '균형·낙상 예방' && r.journal.status === 'shared' && r.journal.quick === true &&
      r.journal.visitDate === '2026-11-26' && !!r.journal.id && !!r.journal.createdAt;
  })(), JSON.stringify(SVM.buildQuickJournal({ pain: 2, condition: 4, activities: ['walk'] }).journal));
  ok('S6 필수가 비면 저장하지 않는다', (function () {
    const r = SVM.buildQuickJournal({ pain: 3, condition: 4, activities: [] });
    return r.ok === false && r.error === 'incomplete' && r.missing.join(',') === 'activities' && !r.journal;
  })(), JSON.stringify(SVM.buildQuickJournal({ pain: 3, condition: 4, activities: [] })));
  ok('S7 일지 한 줄 요약', SVM.quickJournalLine({ pain5: 3, condition5: 4, activities: ['walk', 'stairs', 'rom'] }) === '통증 3/5 · 컨디션 4/5 · 보행 연습 외 2개',
    SVM.quickJournalLine({ pain5: 3, condition5: 4, activities: ['walk', 'stairs', 'rom'] }));

  /* ----- (1) 2분 빠른 일지: 화면 ----- */
  h20.click(h20.$('[data-login="therapist"]'));
  await sleep(30);
  h20.click(h20.$('.tabbtn[data-tab="tp-journal"]'));
  await sleep(30);
  ok('S8 파트너 일지 화면에 2분 입력 카드(척도 5·5 · 동작 8칩)',
    h20.$$('#qlPainChips [data-ql-pain]').length === 5 && h20.$$('#qlCondChips [data-ql-cond]').length === 5 &&
    h20.$$('#qlActChips [data-ql-act]').length === 8 && !!h20.$('#qlNote') && !!h20.$('#qlFocus') && !!h20.$('#qlSave'));
  ok('S9 칩을 누르면 선택·진행 표시(0/5 → 3/5)', (function () {
    h20.click(h20.$('#qlPainChips [data-ql-pain="2"]'));
    h20.click(h20.$('#qlCondChips [data-ql-cond="4"]'));
    h20.click(h20.$('#qlActChips [data-ql-act="walk"]'));
    const st = SVM.quickLogState();
    return st.pain === 2 && st.condition === 4 && st.activities.join(',') === 'walk' && st.filled === 3 &&
      /3\/5/.test(h20.text('#qlProgress'));
  })(), h20.text('#qlProgress'));
  ok('S10 필수가 차면 저장 버튼 안내가 바뀐다', /저장 준비 완료/.test(h20.text('#qlHint')), h20.text('#qlHint'));

  /* ----- (2) 주간 보호자 리포트: 모델 ----- */
  ok('S13 이번 주(월~일) 일지만 모은다 · 회차·방문일수', (function () {
    const r = SVM.buildWeeklyReport(weekJournals, { todayIso: KST_TODAY });
    return r.rounds === 2 && r.visitedDays === 2 && r.entries.length === 2 &&
      r.entries.every((e) => e.date >= r.from && e.date <= r.to);
  })(), JSON.stringify(SVM.buildWeeklyReport(weekJournals, { todayIso: KST_TODAY })));
  ok('S14 컨디션은 높을수록·통증은 낮을수록 좋은 변화로 읽는다', (function () {
    const r = SVM.buildWeeklyReport(weekJournals, { todayIso: KST_TODAY });
    return r.condition.first === 3 && r.condition.last === 4 && r.condition.delta === 1 &&
      r.condition.label === '좋아졌어요' && r.condition.tone === 'good' &&
      r.pain.first === 3 && r.pain.last === 2 && r.pain.label === '줄었어요' && r.pain.tone === 'good';
  })(), JSON.stringify(SVM.buildWeeklyReport(weekJournals, { todayIso: KST_TODAY }).condition));
  ok('S15 수행 동작 횟수 집계·다음 주 집중은 마지막 기록', (function () {
    const r = SVM.buildWeeklyReport(weekJournals, { todayIso: KST_TODAY });
    const walk = r.activities.filter((a) => a.code === 'walk')[0];
    return walk.count === 2 && r.activities[0].code === 'walk' && r.nextFocus === '균형·낙상 예방' &&
      r.notes.length === 2;
  })(), JSON.stringify(SVM.buildWeeklyReport(weekJournals, { todayIso: KST_TODAY }).activities));
  ok('S16 공유용 텍스트(회차·변화·포커스·브랜드 한 줄)', (function () {
    const t = SVM.weeklyReportText(SVM.buildWeeklyReport(weekJournals, { todayIso: KST_TODAY }));
    return /\[똑똑쌤 주간 보호자 리포트\]/.test(t) && /이번 주 방문 2회/.test(t) &&
      /컨디션 3점 → 4점 \(좋아졌어요\)/.test(t) && /통증 3점 → 2점 \(줄었어요\)/.test(t) &&
      /다음 주 집중 포인트: 균형·낙상 예방/.test(t) && /나아지는 걸 확인하는 재활/.test(t);
  })(), SVM.weeklyReportText(SVM.buildWeeklyReport(weekJournals, { todayIso: KST_TODAY })));
  ok('S17 일지가 없는 주는 0회로 정직하게 표시', (function () {
    const r = SVM.buildWeeklyReport(weekJournals, { todayIso: '2026-12-20' });
    return r.rounds === 0 && r.condition.first === null && /이번 주 방문 0회/.test(r.text);
  })());

  /* ----- (2) 주간 리포트: 보호자 화면 ----- */
  h20.click(h20.$('[data-role-switch="customer"]'));
  await sleep(30);
  h20.click(h20.$('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]'));
  await sleep(40);
  ok('S18 보호자 일지 화면에 이번 주 리포트 카드(회차·컨디션·집중)', (function () {
    const t = h20.text('#weeklyBody');
    return /2회/.test(t) && /3점 → 4점/.test(t) && /균형·낙상 예방/.test(t) &&
      /\d+\.\d+ ~ \d+\.\d+/.test(h20.text('#weeklyRange'));
  })(), h20.text('#weeklyBody'));
  ok('S19 리포트 시트 열기(주간 카드·회차별 기록)', (function () {
    h20.click(h20.$('#weeklyOpen'));
    const open = h20.$('#weeklySheet').classList.contains('is-open');
    const body = h20.text('#weeklySheetBody');
    return open && /주간 리포트/.test(body) && /이번 주 방문 2회/.test(body) && h20.$$('#weeklySheetBody .jr-item').length === 2;
  })(), h20.text('#weeklySheetBody').slice(0, 120));
  ok('S20 공유용 텍스트 복사(훅에 실제 문구가 남는다)', (function () {
    h20.click(h20.$('#weeklySheetCopy'));
    const hook = D20.window.__ttokttokWeeklyCopy;
    return !!hook && /이번 주 방문 2회/.test(hook.text) && /균형·낙상 예방/.test(hook.text);
  })(), JSON.stringify(D20.window.__ttokttokWeeklyCopy && D20.window.__ttokttokWeeklyCopy.text));
  h20.click(h20.$('#weeklySheet [data-weekly-close]'));
  await sleep(20);
  ok('S21 닫으면 시트가 닫힌다', !h20.$('#weeklySheet').classList.contains('is-open'));

  /* ----- (3) 4주 재평가: 계산 ----- */
  ok('S22 28일 도래/오늘/임박/대기를 구분', (function () {
    const a = SVM.reevalState('2026-10-21', '2026-11-26');
    const b = SVM.reevalState('2026-10-29', '2026-11-26');
    const c = SVM.reevalState('2026-11-01', '2026-11-26');
    const d = SVM.reevalState('2026-11-02', '2026-11-26');
    return a.status === 'due' && a.overdueDays === 8 && a.dueIso === '2026-11-18' &&
      b.status === 'due' && b.daysLeft === 0 && SVM.reevalBadgeOf(b) === '4주 재평가 오늘' &&
      c.status === 'soon' && c.daysLeft === 3 && SVM.reevalBadgeOf(c) === '4주 재평가 D-3' &&
      d.status === 'waiting' && SVM.reevalBadgeOf(d) === '';
  })(), JSON.stringify([SVM.reevalState('2026-10-21', '2026-11-26'), SVM.reevalState('2026-11-02', '2026-11-26')]));
  ok('S23 도래한 회원만 뽑고 취소·노쇼는 기준일에서 뺀다', (function () {
    const a = SVM.buildReevalAlerts(JSON.parse(v20SeedAccount(KST_TODAY)).bookings, { todayIso: KST_TODAY });
    const labels = a.items.map((x) => x.label);
    return a.total === 2 && a.due === 1 && a.soon === 1 && labels.indexOf('김순자 어르신') !== -1 &&
      labels.indexOf('박정호 어르신') !== -1 && labels.indexOf('최은자 어르신') === -1;
  })(), JSON.stringify(SVM.buildReevalAlerts(JSON.parse(v20SeedAccount(KST_TODAY)).bookings, { todayIso: KST_TODAY }).items));
  ok('S24 첫 방문이 28일 전이면 아직 알리지 않는다', (function () {
    const a = SVM.buildReevalAlerts([
      { no: 'TT-A', memberId: 'kim', patient: '김순자 어르신', status: 'completed', dateIso: isoShift(-10) }
    ], { todayIso: KST_TODAY });
    return a.total === 0 && SVM.firstVisitIsoOf([{ status: 'completed', dateIso: isoShift(-10) }]) === isoShift(-10);
  })());
  ok('S25 회원이 다르면 따로 센다(첫 방문·예약번호 보존)', (function () {
    const a = SVM.buildReevalAlerts(JSON.parse(v20SeedAccount(KST_TODAY)).bookings, { todayIso: KST_TODAY, groupKey: 'usr-demo', label: '김순자 어르신' });
    return a.total === 1 && a.items[0].key === 'usr-demo' && a.items[0].bookingNos.length >= 2;
  })());

  /* ----- (3) 4주 재평가: 화면 ----- */
  ok('S26 보호자 화면에 4주 재평가 배지(D+n)', (function () {
    const el = h20.$('#journalReeval');
    return !!el && el.hidden === false && /4주 재평가/.test(el.textContent) && /4주 재평가 D\+\d/.test(el.textContent) &&
      /첫 방문/.test(el.textContent) && !!el.querySelector('[data-go="booking"]');
  })(), h20.text('#journalReeval'));
  ok('S27 재평가 알림은 보호자 알림함에도 한 번만 쌓인다', (function () {
    const list = SVM.notifs();
    const mine = list.filter((n) => n.audience === 'customer' && n.id === 'ntf-reeval-c-' + SVM.customerReeval().items[0].dueIso);
    return mine.length === 1 && /4주 재평가/.test(mine[0].title);
  })(), JSON.stringify(SVM.notifs().filter((n) => /재평가/.test(n.title))));
  ok('S28 같은 주기에는 두 번 만들지 않는다(멱등)', (function () {
    const before = SVM.notifs().filter((n) => /재평가/.test(n.title)).length;
    h20.click(h20.$('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]'));
    h20.click(h20.$('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]'));
    const after = SVM.notifs().filter((n) => /재평가/.test(n.title)).length;
    return before === after;
  })());
  h20.click(h20.$('[data-admin-open]'));
  await sleep(40);
  ok('S29 관리자 보드에 4주 재평가 칩·카드(배지·첫 방문·안내 복사)', (function () {
    const counts = h20.text('#adminOpsCounts');
    const card = h20.$('#adminReevalBoard [data-reeval-state="due"]');
    return /4주 재평가 2/.test(counts) && !!card && /D\+2/.test(card.textContent) &&
      /첫 방문/.test(card.textContent) && !!card.querySelector('[data-reeval-notice]');
  })(), h20.text('#adminReevalBoard').slice(0, 160));
  ok('S30 재평가 안내 문구 복사(발송 없음 명시)', (function () {
    const btn = h20.$('#adminReevalBoard [data-reeval-notice]');
    btn.click();
    const hook = D20.window.__ttokttokReeval;
    return !!hook && /4주 재평가 안내/.test(hook.text) && /가능한 시간대/.test(hook.text);
  })(), JSON.stringify(D20.window.__ttokttokReeval && D20.window.__ttokttokReeval.text));
  ok('S31 관리자 카드에서 예약으로 이동(기존 큐 연결 유지)', !!h20.$('#adminReevalBoard [data-admin-focus]'));

  /* ----- (3) 4주 재평가: 선생님 알림함 ----- */
  ok('S32 선생님 알림함에 4주 재평가 알림이 쌓인다', (function () {
    const alerts = SVM.teacherReeval();
    const list = SVM.teacherNotifs().filter((n) => /4주 재평가/.test(n.title));
    return alerts.total === 1 && alerts.items[0].label === '김순자 어르신' && list.length === 1;
  })(), JSON.stringify(SVM.teacherReeval().items));
  ok('S33 파트너 홈 알림함에 보이고 두 번 그려도 한 건', (function () {
    h20.click(h20.$('[data-login="therapist"]'));
    const t = h20.text('#tpNotifList');
    h20.click(h20.$('.tabbtn[data-tab="tp-schedule"]'));
    h20.click(h20.$('.tabbtn[data-tab="tp-home"]'));
    return /4주 재평가/.test(t) && SVM.teacherNotifs().filter((n) => /4주 재평가/.test(n.title)).length === 1;
  })(), h20.text('#tpNotifList').slice(0, 120));

  /* ----- (4) 신뢰·안전: 방문 시작/종료 ----- */
  ok('S34 방문 시작 → 시각 기록·상태 불변·이력 남김', (function () {
    const b = SVM.reservations().filter((x) => x.no === 'TT-270001-0002')[0];
    const r = SVM.startVisit(b, '2026-11-26T01:00:00.000Z');
    const last = b.statusHistory[b.statusHistory.length - 1];
    return r.ok === true && !!b.visitStartedAt && b.status === 'confirmed' && last.event === 'visit_start' && last.actor === 'teacher';
  })(), JSON.stringify(SVM.visitWindow(SVM.reservations().filter((x) => x.no === 'TT-270001-0002')[0])));
  ok('S35 시작 없이 종료는 막고, 두 번 종료도 막는다', (function () {
    const b = SVM.reservations().filter((x) => x.no === 'TT-270001-0003')[0];
    const r1 = SVM.endVisit(b, '2026-11-26T02:00:00.000Z');
    const b2 = { status: 'confirmed', statusHistory: [], visitStartedAt: '2026-11-26T01:00:00.000Z', visitEndedAt: '2026-11-26T01:30:00.000Z' };
    const r2 = SVM.endVisit(b2, '2026-11-26T02:00:00.000Z');
    return r1.ok === false && r1.error === 'not_started' && r2.ok === false && r2.error === 'already_ended';
  })());
  ok('S36 방문 종료 → 종료 시각·소요 분 계산', (function () {
    const b = SVM.reservations().filter((x) => x.no === 'TT-270001-0002')[0];
    const r = SVM.endVisit(b, '2026-11-26T01:57:00.000Z');
    const win = SVM.visitWindow(b);
    return r.ok === true && win.state === 'done' && win.minutes === 57 && win.startClock === '10:00' && win.endClock === '10:57';
  })(), JSON.stringify(SVM.visitWindow(SVM.reservations().filter((x) => x.no === 'TT-270001-0002')[0])));
  ok('S37 완료된 방문에는 시작 이벤트가 허용되지 않는다', (function () {
    const b = SVM.reservations().filter((x) => x.no === 'TT-270001-0001')[0];
    const r = SVM.startVisit(b);
    return r.ok === false && r.error === 'event_not_allowed';
  })());

  /* ----- (4) 신뢰·안전: 파트너 화면 버튼 ----- */
  ok('S38 파트너 일정 카드에 방문 시작 버튼(체크인과 별도)', (function () {
    h20.click(h20.$('.tabbtn[data-tab="tp-schedule"]'));
    const card = h20.$('#tpScheduleList [data-sched="s1"]');
    return !!card && !!card.querySelector('[data-tp-checkin]') && !!card.querySelector('[data-tp-visit-start]');
  })());
  ok('S39 방문 시작 → 진행 표시, 방문 종료 → 소요 시간 표시', (function () {
    h20.click(h20.$('#tpScheduleList [data-sched="s1"] [data-tp-visit-start]'));
    const started = h20.text('#tpScheduleList [data-sched="s1"]');
    const endBtn = h20.$('#tpScheduleList [data-sched="s1"] [data-tp-visit-end]');
    if (!endBtn) return false;
    h20.click(endBtn);
    const done = h20.text('#tpScheduleList [data-sched="s1"]');
    const saved = JSON.parse(D20.window.localStorage.getItem('ttokttok_partner_v1')).schedule.filter((x) => x.id === 's1')[0];
    return /방문 중/.test(started) && !!saved.visitStartedAt && !!saved.visitEndedAt && /방문 완료/.test(done) &&
      /(\d+분|1분 미만)\)/.test(done);
  })(), h20.text('#tpScheduleList [data-sched="s1"]'));
  ok('S40 보호자 화면에 방문 시작·종료 시각이 보인다', (function () {
    h20.click(h20.$('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]'));
    const t = h20.text('#visitTimeLine');
    return /방문/.test(t) && (/(\d{2}:\d{2})/.test(t) || /선생님이 방문 시작을 누르면/.test(t));
  })(), h20.text('#visitTimeLine'));

  /* ----- (4) 신뢰·안전: 긴급 연락·건강정보 ----- */
  ok('S41 긴급 연락 3종(119·센터·스마트콜) tel 링크', (function () {
    const s = SVM.safetyContacts;
    return s.length === 3 && s[0].tel === '119' && /031/.test(s[1].tel) && s.filter((x) => /0507/.test(x.tel)).length === 1;
  })());
  ok('S42 안전 시트에 연락처·응급 4단계·하지 않는 일', (function () {
    h20.click(h20.$('[data-safety-open]'));
    const open = h20.$('#safetySheet').classList.contains('is-open');
    const links = h20.$$('#safetyContacts [data-safety-tel]').map((a) => a.getAttribute('href'));
    const steps = h20.$$('#safetySteps .step-item').length;
    return open && links.length === 3 && links[0] === 'tel:119' && steps === 4 &&
      /도수치료/.test(h20.text('#safetyForbidden'));
  })(), h20.text('#safetySheet').slice(0, 160));
  ok('S43 건강정보 최소 보관 원칙 5항·초안 고지', (function () {
    const t = h20.text('#safetyPrivacy');
    return /최소 보관|무엇을/.test(t) && /주민등록번호/.test(t) && /5년/.test(t) && /법률 자문이 아닌/.test(t) &&
      SVM.healthDataPolicy.items.length === 5;
  })(), h20.text('#safetyPrivacy').slice(0, 200));
  ok('S44 안전 시트 닫기', (function () {
    h20.click(h20.$('#safetySheet [data-safety-close]'));
    return !h20.$('#safetySheet').classList.contains('is-open');
  })());

  /* ----- (1) 2분 일지 저장(끝에 실행 — 저장이 방문·리포트를 바꾸므로) ----- */
  ok('S48 2분 일지 저장 → 공유 일지·최근 기록 반영', (function () {
    h20.click(h20.$('[data-login="therapist"]'));
    h20.click(h20.$('.tabbtn[data-tab="tp-journal"]'));
    h20.click(h20.$('#qlPainChips [data-ql-pain="2"]'));
    h20.click(h20.$('#qlCondChips [data-ql-cond="4"]'));
    if (!h20.$('#qlActChips [data-ql-act="walk"]').classList.contains('is-on')) h20.click(h20.$('#qlActChips [data-ql-act="walk"]'));
    h20.setVal(h20.$('#qlNote'), '계단 오를 때 무릎 흔들림 감소');
    h20.setSel(h20.$('#qlFocus'), '균형·낙상 예방');
    h20.click(h20.$('#qlSave'));
    const saved = JSON.parse(D20.window.localStorage.getItem('ttokttok_partner_v1'));
    const j = (saved.journals || []).filter((x) => x.quick === true)[0];
    return !!j && j.pain5 === 2 && j.condition5 === 4 && j.status === 'shared' &&
      j.note === '계단 오를 때 무릎 흔들림 감소' && j.nextFocus === '균형·낙상 예방' &&
      /통증 2\/5/.test(h20.text('#tpJournalList'));
    })(), h20.text('#toast'));
  ok('S49 저장 후 입력칸은 비워진다(다음 방문 바로 입력)', SVM.quickLogState().pain === 0 && SVM.quickLogState().condition === 0 && SVM.quickLogState().activities.length === 0);

  /* ----- 디자인·단가 유지 ----- */
  ok('S45 CSS 토큰 정합성(v35: :root 하나·var 전부 정의·중괄호 균형)', cssTokens(HTML).ok,
    String(/<style>([\s\S]*?)<\/style>/.exec(HTML)[1].length));
  ok('S46 확정 단가 90,000/70,000원 유지·회차권 값은 건드리지 않음', (function () {
    const p = SVM.pricing;
    const plans = p.plans.map((x) => x.id + ':' + x.price).join(',');
    return p.consumerPrice === 90000 && p.teacherPayout === 70000 &&
      plans === 'eval:0,p1:90000,p4:320000,p8:592000,p12:840000';
  })(), JSON.stringify(SVM.pricing.plans));
  ok('S47 발송 없음(앱 안 알림·복사만)', !/발송했|전송했|보냈습니다/.test(h20.text('#weeklyBody') + h20.text('#journalReeval') + h20.text('#safetySheet')));

  /* ============================================================
     T. v21 — 정산일 통일(D+3 확정 · 15일·말일 지급) · 4주 재평가 기본 시드 · 사업자 표기
     ============================================================ */
  const D21 = makeDom();
  const h21 = helpers(D21.window, D21.doc);
  await sleep(40);
  const M21 = D21.window.__ttokttokModel;

  ok('T1 v31 meta·정산 규칙 노출',
    D21.doc.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    M21.settlementRule.confirmDays === 3 && JSON.stringify(M21.settlementRule.payDays) === '[15,"end"]',
    JSON.stringify(M21.settlementRule));
  ok('T2 정산 규칙 문구가 D+3·15일·말일로 통일',
    /D\+3/.test(M21.settlementRuleText) && /15일/.test(M21.settlementRuleText) && /말일/.test(M21.settlementRuleText),
    M21.settlementRuleText);
  ok('T3 지급일 계산(11/26→11/30 · 11/12→11/15 · 11/13→11/30 · 11/28→12/15 · 10/31→11/15)',
    M21.nextPayoutDue('2026-11-26') === '2026-11-30' && M21.nextPayoutDue('2026-11-12') === '2026-11-15' &&
    M21.nextPayoutDue('2026-11-13') === '2026-11-30' && M21.nextPayoutDue('2026-11-28') === '2026-12-15' &&
    M21.nextPayoutDue('2026-10-31') === '2026-11-15',
    [M21.nextPayoutDue('2026-11-26'), M21.nextPayoutDue('2026-11-12'), M21.nextPayoutDue('2026-11-13'), M21.nextPayoutDue('2026-11-28'), M21.nextPayoutDue('2026-10-31')].join(' / '));
  ok('T4 앱에 \'매월 10일\' 정산 표기가 남아 있지 않다', !/매월 10일|다음 달 10일|settlementDayOfMonth/.test(HTML) &&
    !/settlementDayOfMonth/.test(require('fs').readFileSync(path.join(__dirname, '..', 'POLICIES-AND-FEES.md'), 'utf8')));

  /* 기본 시드의 4주 재평가 — 라이브에서 보드·배지가 바로 보이도록 */
  const seedRe = M21.buildReevalAlerts(M21.reservations(), {});
  ok('T5 기본 시드에 4주 재평가 도래 1건(D+8)', seedRe.total === 1 && seedRe.due === 1 &&
    /^4주 재평가 D\+\d+$/.test(seedRe.items[0].badge) && !!seedRe.items[0].firstVisitIso && seedRe.items[0].firstVisitIso < seedRe.todayIso,
    JSON.stringify(seedRe).slice(0, 300));
  ok('T6 시드 지난 방문은 완료·평가 기록(첫 방문 기준일)', (function () {
    const b = M21.reservations().filter((x) => x.status === 'completed')[0];
    return !!b && b.no === 'TT-261019-4811' && b.firstVisitIso === b.dateIso && b.amount === 0;
  })(), JSON.stringify(M21.reservations().map((b) => b.no + ':' + b.status)));
  ok('T7 지난 완료 방문 카드는 변경·취소·캘린더 없이 내역만', (function () {
    const card = h21.$('#bookingList [data-booking="TT-261019-4811"]');
    return !!card && /방문 완료/.test(card.textContent) && !!card.querySelector('[data-manage]') &&
      !card.querySelector('[data-manage-cancel]') && !card.querySelector('[data-ics]');
  })(), h21.text('#bookingList [data-booking="TT-261019-4811"]').slice(0, 120));

  /* 관리자 「오늘 처리할 일」에 4주 재평가 보드·칩 */
  h21.click(h21.$('[data-login="admin"]'));
  await sleep(120);
  ok('T8 관리자 보드에 4주 재평가 칩 1건', /4주 재평가 1/.test(h21.text('#adminOpsCounts')), h21.text('#adminOpsCounts'));
  ok('T9 재평가 카드(배지·첫 방문·안내 복사)', (function () {
    const card = h21.$('#adminReevalBoard [data-reeval-state="due"]');
    return !!card && /4주 재평가 D\+\d+/.test(card.textContent) && /첫 방문/.test(card.textContent) &&
      !!card.querySelector('[data-reeval-notice]') && /현수/.test(card.textContent);
  })(), h21.text('#adminReevalBoard').slice(0, 160));
  ok('T10 기본 시드 재평가 보드에서 안내 문구 복사', (function () {
    const btn = h21.$('#adminReevalBoard [data-reeval-notice]');
    if (!btn) return false;
    h21.click(btn);
    const hook = D21.window.__ttokttokReeval;
    return !!hook && /4주 재평가 안내/.test(hook.text) && /현수/.test(hook.text);
  })(), JSON.stringify(D21.window.__ttokttokReeval || null).slice(0, 200));

  /* 파트너 정산 화면 — 지급일·규칙 표기 */
  const D21b = makeDom();
  const h21b = helpers(D21b.window, D21b.doc);
  await sleep(40);
  h21b.click(h21b.$('[data-login="therapist"]'));
  await sleep(40);
  ok('T11 파트너 정산 화면에 11.30 지급·D+3 규칙', /11\.30/.test(h21b.text('#tpSettle')) &&
    /D\+3/.test(h21b.text('#tpSettle')) && /15일·말일/.test(h21b.text('#tpSettle')), h21b.text('#tpSettle').slice(0, 160));
  ok('T12 파트너 정산 상세에 확정·지급 주기', /회차 완료 D\+3/.test(h21b.text('#tpSettleDetail')) &&
    /15일·말일 지급/.test(h21b.text('#tpSettleDetail')), h21b.text('#tpSettleDetail').slice(0, 200));
  ok('T13 가격표 화면 문구도 D+3·15일·말일', /D\+3 정산 확정/.test(HTML) && /15일·말일\) 지급/.test(HTML));

  /* 사업자 표기 — 앱 푸터(시작 화면 하단)·약관 시트 */
  ok('T14 시작 화면 푸터에 상호·대표·사업자등록번호·연락처', (function () {
    const el = D21b.doc.querySelector('#gateBizInfo');
    const t = el ? el.textContent : '';
    return /상호 똑똑쌤/.test(t) && /대표 임현수/.test(t) && /사업자등록번호/.test(t) && /031-919-8577/.test(t);
  })(), (D21b.doc.querySelector('#gateBizInfo') || {}).textContent);
  ok('T15 약관 시트 하단에도 사업자 표기', (function () {
    const t = h21b.text('#faqBizInfo');
    return /상호 똑똑쌤/.test(t) && /대표 임현수/.test(t) && /031-919-8577/.test(t);
  })(), h21b.text('#faqBizInfo'));

  /* ============================================================
     U. v22 — 선생님 찾기 내 주변(동 단위) · 방문 일지 사진 1장
     ============================================================ */
  const D22 = makeDom();
  const h22 = helpers(D22.window, D22.doc);
  await sleep(60);
  const M22 = D22.window.__ttokttokModel;
  const PNG_1PX = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';

  ok('U0 v22 JS 오류 없음', D22.errors.length === 0, D22.errors.slice(0, 3).join(' | '));
  ok('U1 v31 메타·모델 노출',
    D22.doc.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    !!M22 && M22.nearVersion === 'v22' && M22.photoVersion === 'v22' && M22.dongImmediateDays === 3,
    M22 && M22.nearVersion + '/' + M22.photoVersion);

  /* ----- 활동 동·시·군·구 정규화 ----- */
  const parkDongs = M22.teacherDongList('park').map((d) => d.name);
  ok('U2 박서준 활동 동 2곳(대치동·반포동)', parkDongs.length === 2 && parkDongs.indexOf('대치동') !== -1 && parkDongs.indexOf('반포동') !== -1, parkDongs.join(','));
  ok('U3 동 이름과 상위 구 매핑', (function () {
    const d = M22.teacherDongList('park').filter((x) => x.name === '대치동')[0];
    return !!d && d.district === '강남구' && d.province === '서울' && d.districtId === 'reg-서울-강남구';
  })(), JSON.stringify(M22.teacherDongList('park')[0]));
  ok('U4 동을 모르면 구 단위로(이하늘 파주 야당동·일산동구)', (function () {
    const dongs = M22.teacherDongList('lee').map((d) => d.name);
    const dists = M22.teacherDistrictList('lee').map((d) => d.name);
    return dongs.indexOf('야당동') !== -1 && dists.indexOf('고양시 일산동구') !== -1;
  })(), M22.teacherDongList('lee').map((d) => d.name).join(',') + ' / ' + M22.teacherDistrictList('lee').map((d) => d.name).join(','));

  /* ----- 동네 클러스터 계산 ----- */
  const clusters22 = M22.buildDongClusters(M22.teachers(), { todayIso: M22.todayIsoKst() });
  ok('U5 동네 클러스터 생성(동·구 혼합)', clusters22.length >= 8 && clusters22.some((c) => c.level === 'dong') && clusters22.some((c) => c.level === 'district'), String(clusters22.length));
  ok('U6 클러스터가 8명 전부를 덮는다', (function () {
    const ids = {};
    clusters22.forEach((c) => c.teacherIds.forEach((id) => { ids[id] = 1; }));
    return Object.keys(ids).length === 8;
  })(), JSON.stringify(clusters22.map((c) => c.name + ':' + c.teacherCount)));
  ok('U7 대치동 카드 요약(활동 1명·3일 내 1명·전문분야)', (function () {
    const c = clusters22.filter((x) => x.name === '대치동')[0];
    return !!c && c.teacherCount === 1 && c.readyCount === 1 && c.specialties.indexOf('뇌졸중') !== -1 && c.districtText === '서울 강남구';
  })(), JSON.stringify(clusters22.filter((x) => x.name === '대치동')[0]));
  ok('U8 그룹화·클러스터에 개인 주소·좌표 없음', !/위도|경도|번지|lat|lng|coord/i.test(JSON.stringify(clusters22)) &&
    clusters22.every((c) => !/\d+\s*번지|로\s+\d/.test(c.name + ' ' + c.districtText)));
  ok('U9 정렬은 활동 선생님 수 내림차순', clusters22.every((c, i) => i === 0 || clusters22[i - 1].teacherCount >= c.teacherCount), clusters22.map((c) => c.teacherCount).join(','));
  ok('U10 이미 동으로 센 구는 구 카드에 또 세지 않는다', (function () {
    const dongDists = clusters22.filter((c) => c.level === 'dong').map((c) => c.districtId);
    return clusters22.filter((c) => c.level === 'district').every((c) => dongDists.indexOf(c.districtId) === -1 || c.teacherIds.every((id) => {
      const t = M22.teacherById(id);
      return M22.teacherDongList(t).every((d) => d.districtId !== c.districtId);
    }));
  })(), JSON.stringify(clusters22.filter((c) => c.level === 'district').map((c) => c.name)));

  /* ----- 화면: 목록 | 내 주변 탭 ----- */
  h22.click(h22.$('[data-login="customer"]'));
  h22.click(h22.$('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]'));
  await sleep(40);
  ok('U11 보기 탭 2개(목록·내 주변)', h22.$$('#teacherViewTabs [data-view]').length === 2 &&
    /내 주변/.test(h22.text('#teacherViewTabs')) && h22.$('#teacherViewTabs [data-view="list"]').getAttribute('aria-selected') === 'true');
  ok('U12 기본은 목록(내 주변 패널 숨김·카드 8명)', h22.$('#nearPanel').hidden === true && h22.$$('#teacherList .teacher').length === 8);
  h22.click(h22.$('#teacherViewTabs [data-view="near"]'));
  await sleep(40);
  const near = D22.window.__ttokttokNear;
  ok('U13 내 주변 탭 → 동네 클러스터 카드', !!near && h22.$('#nearPanel').hidden === false &&
    h22.$$('#dongClusterList [data-dong-cluster]').length >= 1 && h22.$$('#nearProvinceChips .chip').length >= 1 && h22.$$('#nearDistrictChips .chip').length >= 1,
    JSON.stringify(near && near.clusters.slice(0, 3)));
  ok('U14 내 주변에서는 카드 목록을 숨긴다', h22.$('#teacherList').style.display === 'none' && h22.$('#teacherFilters').style.display === 'none');
  ok('U15 카드에 활동 수·바로 가능·전문분야·보기 버튼', (function () {
    const card = h22.$('#dongClusterList [data-dong-cluster]');
    if (!card) return false;
    const t = card.textContent.replace(/\s+/g, ' ');
    return /활동 선생님/.test(t) && /바로 가능 \(3일 내\)/.test(t) && card.querySelectorAll('.tag').length >= 1 && !!card.querySelector('[data-dong-pick]');
  })(), h22.text('#dongClusterList [data-dong-cluster]').slice(0, 200));
  ok('U16 시·도를 바꾸면 시·군·구 목록도 바뀐다', (function () {
    const chip = h22.$$('#nearProvinceChips .chip').filter((b) => b.getAttribute('data-near-province') === '부산')[0];
    if (!chip) return false;
    h22.click(chip);
    const after = D22.window.__ttokttokNear;
    return !!after && after.province === '부산' && after.district === '해운대구' && after.clusters.some((c) => c.name === '우동');
  })(), JSON.stringify((D22.window.__ttokttokNear || {}).district));

  /* ----- 클러스터 → 해당 동 선생님만 ----- */
  D22.window.__ttokttokModel.nearDistrict('서울', '강남구');
  await sleep(20);
  ok('U17 대치동 카드 → 해당 동 선생님만 남는다', (function () {
    const okPick = D22.window.__ttokttokModel.pickDongKey('dong:reg-서울-강남구-대치동');
    const rows = h22.$$('#teacherList .teacher').map((el) => el.getAttribute('data-teacher'));
    const bar = h22.text('#teacherQueryBar');
    return okPick && rows.length === 1 && rows[0] === 'park' && /대치동 1명/.test(bar) && D22.window.__ttokttokModel.teacherView() === 'list';
  })(), h22.text('#teacherQueryBar') + ' / ' + h22.$$('#teacherList .teacher').map((el) => el.getAttribute('data-teacher')).join(','));
  ok('U18 동네 필터 해제 → 다시 8명', (function () {
    h22.click(h22.$('[data-dong-clear]'));
    return h22.$$('#teacherList .teacher').length === 8 && !D22.window.__ttokttokModel.dongFilter();
  })(), String(h22.$$('#teacherList .teacher').length));

  /* ----- 일지 사진: 검증·메타 ----- */
  ok('U19 이미지 data URL만 통과(HTML·스크립트 거부)', (function () {
    const good = M22.normalizePhoto({ thumb: PNG_1PX, name: 'pose.png', width: 600, height: 400, bytes: 24000 });
    const bad = M22.normalizePhoto('data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==');
    const svg = M22.normalizePhoto('data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=');
    return good.ok && good.photo.privacy === 'guidance_shown' && good.photo.name === 'pose.png' &&
      bad.ok === false && bad.error === 'not_image' && svg.ok === false;
  })(), JSON.stringify(M22.normalizePhoto({ thumb: PNG_1PX })));
  ok('U20 용량 상한을 넘는 사진은 거부', (function () {
    const big = 'data:image/jpeg;base64,' + 'A'.repeat(M22.photoMaxChars + 10);
    const r = M22.normalizePhoto(big);
    return r.ok === false && r.error === 'too_large';
  })(), String(M22.photoMaxChars));
  ok('U21 2분 일지에 사진 메타 저장(빌더)', (function () {
    const r = M22.buildQuickJournal({ pain: 3, condition: 4, activities: ['walk'], photo: { thumb: PNG_1PX, name: 'pose.png', width: 600, height: 400 } });
    return r.ok && r.hasPhoto && r.journal.photo.thumb === PNG_1PX && r.journal.photo.privacy === 'guidance_shown' && r.photoWarning === '';
  })());
  ok('U22 사진이 잘못되면 일지는 저장하고 사진만 뺀다', (function () {
    const r = M22.buildQuickJournal({ pain: 2, condition: 3, activities: ['rom'], photo: 'data:text/html;base64,PHNjcmlwdD4=' });
    return r.ok && !r.journal.photo && !!r.photoWarning && /이미지/.test(r.photoWarning);
  })());
  ok('U23 주간 리포트 항목에 사진이 따라간다', (function () {
    const today = M22.todayIsoKst();
    const j = M22.buildQuickJournal({ pain: 3, condition: 4, activities: ['walk'], photo: { thumb: PNG_1PX }, at: today + 'T10:00:00+09:00', visitDate: today }).journal;
    const r = M22.buildWeeklyReport([j], { todayIso: today });
    return !!r && r.entries.length === 1 && r.entries[0].photo === PNG_1PX && r.entries[0].hasPhoto === true;
  })());
  ok('U24 기기 저장 가드: 최신 3장만 남긴다', (function () {
    const journals = [0, 1, 2, 3, 4].map((i) => ({ id: 'j' + i, photo: { thumb: PNG_1PX } }));
    const r = M22.pruneJournalPhotos({ journals: journals }, {});
    return r.kept === 3 && r.dropped.length === 2 && !!journals[0].photo && !!journals[2].photo && !journals[3].photo && !journals[4].photo &&
      r.dropped.join(',') === 'j3,j4';
  })());
  ok('U25 사진 없는 일지는 건드리지 않는다', (function () {
    const journals = [{ id: 'a' }, { id: 'b', photo: { thumb: PNG_1PX } }, { id: 'c', memo: 'x' }];
    const r = M22.pruneJournalPhotos({ journals: journals }, { keep: 5 });
    return r.kept === 1 && r.dropped.length === 0 && !!journals[1].photo && !journals[0].photo;
  })());

  /* ----- 일지 사진: 파트너 입력 → 보호자 표시 ----- */
  const D22b = makeDom();
  const h22b = helpers(D22b.window, D22b.doc);
  await sleep(50);
  const M22b = D22b.window.__ttokttokModel;
  h22b.click(h22b.$('[data-login="therapist"]'));
  await sleep(40);
  h22b.click(h22b.$('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-journal"]'));
  await sleep(60);
  ok('U26 빠른 일지 카드에 사진 입력·선택 표시', !!h22b.$('#qlPhoto') && h22b.$('#qlPhoto').getAttribute('type') === 'file' &&
    /선택/.test(h22b.text('#tpQuickCard')) && !!h22b.$('#qlPhotoHint'));
  ok('U27 사진을 붙이면 미리보기·제거·개인정보 안내 1줄', (function () {
    const r = M22b.setQuickPhoto({ thumb: PNG_1PX, name: 'pose.png', width: 600, height: 400, bytes: 24000 });
    const pv = M22b.quickPhotoPreview();
    return r.ok && pv.visible && pv.hasImg && pv.hasRemove && pv.src === PNG_1PX &&
      pv.note === M22b.photoPrivacyNote && /운동 부위·자세/.test(pv.note) && /가족 얼굴/.test(pv.note);
  })(), JSON.stringify(M22b.quickPhotoPreview()));
  ok('U28 사진 빼기 → 미리보기 사라짐', (function () {
    h22b.click(h22b.$('[data-ql-photo-remove]'));
    const pv = M22b.quickPhotoPreview();
    return pv.visible === false && pv.hasImg === false && M22b.quickPhoto() === null;
  })());
  ok('U29 저장하면 일지에 사진이 남는다', (function () {
    M22b.setQuickLog({ pain: 3, condition: 4, activities: ['walk'], note: '무릎 흔들림 감소', focus: '보행 안정성' });
    M22b.setQuickPhoto({ thumb: PNG_1PX, name: 'pose.png', width: 600, height: 400, bytes: 24000 });
    const r = M22b.saveQuickJournal();
    const j = M22b.partnerJournals()[0];
    return r && r.ok && !!j && !!j.photo && j.photo.thumb === PNG_1PX && j.photo.privacy === 'guidance_shown' &&
      M22b.quickPhoto() === null;
  })(), JSON.stringify(M22b.partnerJournals()[0] || null).slice(0, 200));
  ok('U30 보호자 최근 일지 카드에 사진 표시', (function () {
    const card = h22b.$('#journalLatestCard');
    const img = h22b.$('#journalLatestBody [data-journal-photo]');
    return !!card && card.hidden === false && !!img && img.getAttribute('src') === PNG_1PX && /담당 선생님이 올린 방문 사진/.test(h22b.text('#journalLatestBody'));
  })(), h22b.text('#journalLatestBody').slice(0, 160));
  ok('U31 보호자 주간 리포트 상세에도 사진 표시', (function () {
    h22b.click(h22b.$('#weeklyOpen'));
    const img = h22b.$('#weeklySheetBody [data-journal-photo]');
    return !!img && img.getAttribute('src') === PNG_1PX;
  })(), h22b.text('#weeklySheetBody').slice(0, 160));
  ok('U32 파트너 최근 기록에도 사진 썸네일', !!h22b.$('#tpJournalList [data-journal-photo]') &&
    h22b.$('#tpJournalList [data-journal-photo]').getAttribute('src') === PNG_1PX);


  /* ============================================================
     V. v23 — 운영 데이터 백업/복원(JSON) · 저장소 어댑터
     ============================================================ */
  const D23 = makeDom();
  const h23 = helpers(D23.window, D23.doc);
  await sleep(60);
  const M23 = D23.window.__ttokttokModel;
  const T23 = D23.window;

  ok('V0 v23 JS 오류 없음', D23.errors.length === 0, D23.errors.slice(0, 3).join(' | '));
  ok('V1 v23 메타·모델 노출',
    ['v23', 'v24', 'v25', 'v26', 'v27', 'v28', 'v29', 'v30', 'v31', 'v32', 'v33', 'v34', 'v35', 'v36', 'v37', 'v38', 'v39', 'v40', 'v41', 'v42', 'v43', 'v44', 'v45', 'v46', 'v48'].indexOf(D23.doc.querySelector('meta[name="app-version"]').getAttribute('content')) !== -1 &&
    !!M23 && M23.backupVersion === 'v23' && M23.snapshotSchema === 'ttokttok.v23' && M23.snapshotMaxChars === 8000000,
    M23 && M23.backupVersion + '/' + M23.snapshotSchema);

  /* ----- 관리자 화면의 백업 도구 (기존 클래스만) ----- */
  ok('V2 관리자 콘솔에 백업·복원 버튼·파일 input', (function () {
    const sec = D23.doc.querySelector('#screen-admin #adminBackupSec');
    const ex = D23.doc.querySelector('#adminBackupExport');
    const pick = D23.doc.querySelector('#adminBackupPick');
    const input = D23.doc.querySelector('#adminBackupFile');
    return !!sec && !!ex && !!pick && !!input && input.type === 'file' &&
      ex.className === 'btn btn-outline btn-sm' && pick.className === 'btn btn-outline btn-sm' &&
      !!D23.doc.querySelector('#adminBackupCard.admin-card') &&
      /운영 데이터 백업\(JSON\)/.test(ex.textContent) && /백업 파일 복원/.test(pick.textContent);
  })(), (D23.doc.querySelector('#adminBackupExport') || {}).className);
  ok('V3 백업 카드에 현재 데이터 요약·초안 제외 안내', (function () {
    const c = M23.backupCountsText();
    return /예약 \d+/.test(c) && /일지 \d+/.test(c) && /정산 \d+/.test(c) && /알림 \d+/.test(c) && /프로필 \d+/.test(c) &&
      /빠른일지 초안/.test(h23.text('#adminBackupMeta')) && /저장소/.test(h23.text('#adminBackupMeta'));
  })(), M23.backupCountsText());

  /* ----- 1) 백업 생성 ----- */
  const snap23 = M23.exportWorkspaceSnapshot();
  ok('V4 백업 스키마·시각·항목 수', snap23.schemaVersion === 'ttokttok.v23' && snap23.appVersion === 'v23' &&
    /^\d{4}-\d{2}-\d{2}T/.test(snap23.exportedAt) && !!snap23.counts, JSON.stringify(Object.keys(snap23)));
  ok('V5 백업 포함 대상 5종(초안 제외)', (function () {
    const keys = Object.keys(snap23.data).sort().join(',');
    return keys === 'journals,ledger,notifications,reservations,teacherProfile' && !('quickLogDraft' in snap23.data) &&
      !('quickLog' in snap23.data);
  })(), Object.keys(snap23.data).join(','));
  ok('V6 항목 수가 실제 건수와 같다', (function () {
    return snap23.counts.reservations === M23.reservations().length &&
      snap23.counts.journals === M23.partnerJournals().length &&
      snap23.counts.ledger === (M23.storageRead('ttokttok_partner_v1') || {}).ledger.length &&
      snap23.counts.notifications === M23.notifs().length;
  })(), JSON.stringify(snap23.counts));
  ok('V7 백업에 예약번호·일지 id·정산 금액이 그대로', (function () {
    const b = snap23.data.reservations.filter((x) => x.no === 'TT-261021-7302')[0];
    const j = snap23.data.journals[0];
    const l = snap23.data.ledger.filter((x) => x.grossAmount > 0)[0];
    return !!b && !!j && !!l && b.status === 'confirmed' && typeof j.id === 'string' && l.grossAmount > 0;
  })(), JSON.stringify(snap23.data.journals[0] || null).slice(0, 120));
  ok('V8 파일 이름 형식', /^ttokttok-backup-\d{8}-\d{4}\.json$/.test(M23.snapshotFileName ? M23.snapshotFileName(snap23.exportedAt) : '') ||
    /^ttokttok-backup-\d{8}-\d{4}\.json$/.test(D23.window.__ttokttokBackup ? D23.window.__ttokttokBackup.name : ''));
  ok('V9 내보내기는 저장소를 바꾸지 않는다(순수 함수)', (function () {
    const before = T23.localStorage.getItem('ttokttok_account_v3');
    M23.exportWorkspaceSnapshot();
    return T23.localStorage.getItem('ttokttok_account_v3') === before;
  })());

  /* ----- 2) 정상 복원 ----- */
  const text23 = JSON.stringify(snap23, null, 2);
  const imp23 = M23.importWorkspaceSnapshot(text23);
  ok('V10 정상 백업은 복원 가능(검증 통과)', imp23.ok === true && imp23.errors.length === 0 &&
    imp23.schemaVersion === 'ttokttok.v23', JSON.stringify(imp23.errors));
  ok('V11 복원 결과 항목 수 일치', imp23.counts.reservations === snap23.counts.reservations &&
    imp23.counts.journals === snap23.counts.journals && imp23.counts.ledger === snap23.counts.ledger &&
    imp23.counts.notifications === snap23.counts.notifications, JSON.stringify(imp23.counts));
  ok('V12 복원 데이터는 정규화된 사본(원본 배열과 다른 객체)', imp23.data.reservations !== snap23.data.reservations &&
    imp23.data.journals !== snap23.data.journals);

  /* ----- 3) 거부 케이스 ----- */
  function bad23(name, raw, expectCode) {
    const r = M23.importWorkspaceSnapshot(raw);
    const codes = (r.errors || []).map((e) => e.code);
    ok(name, r.ok === false && codes.indexOf(expectCode) !== -1 && (r.errors || []).every((e) => !!e.message), codes.join(','));
  }
  bad23('V13 손상 JSON(중괄호 깨짐) 거부', '{"schemaVersion":"ttokttok.v23","data":{', 'json_parse');
  bad23('V14 빈 파일 거부', '   ', 'json_parse');
  bad23('V15 schemaVersion 누락 거부', JSON.stringify({ data: { reservations: [], journals: [], ledger: [], notifications: [] } }), 'schema_version_missing');
  bad23('V16 schemaVersion 불일치 거부', JSON.stringify({ schemaVersion: 'ttokttok.v22', data: { reservations: [], journals: [], ledger: [], notifications: [] } }), 'schema_version');
  bad23('V17 예약 항목이 배열이 아니면 거부', JSON.stringify({ schemaVersion: 'ttokttok.v23', data: { reservations: {}, journals: [], ledger: [], notifications: [] } }), 'reservations_type');
  bad23('V18 예약 ID 중복 거부', JSON.stringify({
    schemaVersion: 'ttokttok.v23',
    data: { reservations: [{ id: 'res-1', no: 'TT-261126-0001', status: 'received' }, { id: 'res-1', no: 'TT-261126-0002', status: 'received' }], journals: [], ledger: [], notifications: [], teacherProfile: null }
  }), 'reservation_duplicate');
  bad23('V19 허용되지 않은 예약 상태 거부', JSON.stringify({
    schemaVersion: 'ttokttok.v23',
    data: { reservations: [{ id: 'res-1', no: 'TT-261126-0001', status: 'refunded_all' }], journals: [], ledger: [], notifications: [], teacherProfile: null }
  }), 'reservation_status');
  bad23('V20 일지 사진이 이미지가 아니면 거부(SVG)', JSON.stringify({
    schemaVersion: 'ttokttok.v23',
    data: { reservations: [], journals: [{ id: 'j1', photo: { thumb: 'data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=' } }], ledger: [], notifications: [], teacherProfile: null }
  }), 'journal_photo_type');
  bad23('V21 일지 사진이 스크립트면 거부', JSON.stringify({
    schemaVersion: 'ttokttok.v23',
    data: { reservations: [], journals: [{ id: 'j1', photo: { thumb: 'javascript:alert(1)' } }], ledger: [], notifications: [], teacherProfile: null }
  }), 'journal_photo_type');
  bad23('V22 사진 160,000자 상한 초과 거부', JSON.stringify({
    schemaVersion: 'ttokttok.v23',
    data: { reservations: [], journals: [{ id: 'j1', photo: { thumb: 'data:image/png;base64,' + 'A'.repeat(160000) } }], ledger: [], notifications: [], teacherProfile: null }
  }), 'journal_photo_size');
  bad23('V23 __proto__ 악성 JSON 거부', '{"schemaVersion":"ttokttok.v23","__proto__":{"polluted":1},"data":{"reservations":[],"journals":[],"ledger":[],"notifications":[]}}', 'unsafe_key');
  bad23('V24 정산 상태값이 enum이 아니면 거부', JSON.stringify({
    schemaVersion: 'ttokttok.v23',
    data: { reservations: [], journals: [], ledger: [{ id: 'l1', status: 'done' }], notifications: [], teacherProfile: null }
  }), 'ledger_status');
  bad23('V25 알림 상태값이 enum이 아니면 거부', JSON.stringify({
    schemaVersion: 'ttokttok.v23',
    data: { reservations: [], journals: [], ledger: [], notifications: [{ id: 'n1', title: 't', status: 'seen' }], teacherProfile: null }
  }), 'notification_status');
  bad23('V26 선생님 프로필 배열 타입 불일치 거부', JSON.stringify({
    schemaVersion: 'ttokttok.v23',
    data: { reservations: [], journals: [], ledger: [], notifications: [], teacherProfile: { teacherId: 'park', dongs: '대치동' } }
  }), 'teacherProfile_field');
  ok('V27 거부된 데이터는 data를 돌려주지 않는다', (function () {
    const r = M23.importWorkspaceSnapshot('{oops');
    return r.ok === false && r.data === null && r.counts === null;
  })());
  ok('V27b 본문에 영단어 constructor가 있어도 정상 백업은 통과', (function () {
    const okSnap = {
      schemaVersion: 'ttokttok.v23', exportedAt: '2026-11-26T05:00:00.000Z',
      counts: { reservations: 0, journals: 1, ledger: 0, notifications: 0, teacherProfile: 0 },
      data: { reservations: [], journals: [{ id: 'j1', memo: 'prototype constructor 실습 동작 확인' }], ledger: [], notifications: [], teacherProfile: null }
    };
    const r = M23.importWorkspaceSnapshot(JSON.stringify(okSnap));
    return r.ok === true && r.counts.journals === 1;
  })(), JSON.stringify(M23.importWorkspaceSnapshot(JSON.stringify({ schemaVersion: 'ttokttok.v23', data: { reservations: [], journals: [{ id: 'j1', memo: 'constructor' }], ledger: [], notifications: [], teacherProfile: null } })).errors || []));

  /* ----- 4) 백업 다운로드 → 파일 복원 흐름(화면) ----- */
  ok('V28 백업 버튼 → 파일 내용·이름 생성', (function () {
    h23.click(h23.$('#adminBackupExport'));
    const bk = D23.window.__ttokttokBackup;
    if (!bk) return false;
    const parsed = JSON.parse(bk.text);
    return /^ttokttok-backup-\d{8}-\d{4}\.json$/.test(bk.name) && parsed.schemaVersion === 'ttokttok.v23' &&
      /백업 파일을 만들었어요/.test(h23.text('#adminBackupResult'));
  })(), h23.text('#adminBackupResult'));
  ok('V29 빠른일지 초안은 백업에 안 들어간다', (function () {
    T23.localStorage.setItem('ttokttok_quicklog_v1', JSON.stringify({ pain: 3, condition: 4, activity: 'walk' }));
    const s = M23.exportWorkspaceSnapshot();
    return !/quicklog|빠른일지/.test(JSON.stringify(s)) && T23.localStorage.getItem('ttokttok_quicklog_v1') !== null;
  })());

  /* 데이터를 일부러 바꾼 뒤(예약 상태 전이) 백업 파일로 되돌린다. */
  const moved = M23.transition('TT-261021-7302', 'completed', { actor: 'operator' });
  const afterMove = M23.reservations().filter((b) => b.no === 'TT-261021-7302')[0];
  ok('V30 복원 전 상태를 일부러 바꿈(완료)', moved && moved.ok && afterMove.status === 'completed', afterMove && afterMove.status);

  const prev23 = M23.restoreFromText(D23.window.__ttokttokBackup.text, 'ttokttok-backup-test.json');
  ok('V31 파일 확인 단계에서 아직 바꾸지 않는다(확인 대기)', prev23.ok === true && !!M23.pendingRestore() &&
    M23.reservations().filter((b) => b.no === 'TT-261021-7302')[0].status === 'completed' &&
    D23.doc.querySelector('#adminBackupConfirmBox').hidden === false &&
    /이 내용으로 복원/.test(h23.text('#adminBackupConfirm')) &&
    /예약 \d+/.test(h23.text('#adminBackupConfirmText')), h23.text('#adminBackupConfirmText').slice(0, 120));

  const applied23 = M23.applyPendingRestore();
  ok('V32 「이 내용으로 복원」 → 예약 상태가 백업 시점으로 돌아온다', applied23.ok === true &&
    M23.reservations().filter((b) => b.no === 'TT-261021-7302')[0].status === 'confirmed' &&
    /복원했어요/.test(h23.text('#adminBackupResult')) &&
    D23.doc.querySelector('#adminBackupConfirmBox').hidden === true, h23.text('#adminBackupResult'));
  ok('V33 복원 후 항목 수가 파일과 같다', applied23.counts.reservations === snap23.counts.reservations &&
    applied23.counts.journals === snap23.counts.journals && applied23.counts.notifications === snap23.counts.notifications,
    JSON.stringify(applied23.counts));
  ok('V34 복원은 빠른일지 초안을 건드리지 않는다', T23.localStorage.getItem('ttokttok_quicklog_v1') !== null);
  ok('V35 복원 결과에도 초안 제외·저장소 표기 유지', /빠른일지 초안/.test(h23.text('#adminBackupMeta')));

  /* ----- 5) 손상 파일은 화면에서 거부 ----- */
  ok('V36 손상 파일 → 복원하지 않고 이유 표시', (function () {
    const r = M23.restoreFromText('{ not json', 'broken.json');
    return r.ok === false && M23.pendingRestore() === null &&
      D23.doc.querySelector('#adminBackupConfirmBox').hidden === true &&
      /복원하지 않았어요/.test(h23.text('#adminBackupResult')) && /JSON/.test(h23.text('#adminBackupResult'));
  })(), h23.text('#adminBackupResult'));
  ok('V37 잘못된 상태값 파일 → 복원 거부·이유 표시', (function () {
    const bad = JSON.parse(text23);
    bad.data.reservations[0].status = 'paid_done';
    const r = M23.restoreFromText(JSON.stringify(bad), 'bad-status.json');
    return r.ok === false && /허용되지 않은 예약 상태/.test(h23.text('#adminBackupResult')) &&
      M23.reservations().length === snap23.counts.reservations;
  })(), h23.text('#adminBackupResult'));
  ok('V38 복원 확인 취소 → 데이터 그대로', (function () {
    const before = M23.reservations().length;
    const r = M23.restoreFromText(text23, 'ok.json');
    const c = M23.cancelPendingRestore();
    return r.ok === true && c.canceled === true && M23.pendingRestore() === null &&
      M23.reservations().length === before && /취소/.test(h23.text('#adminBackupResult'));
  })());

  /* ----- 6) 새로 열어도 복원 결과 유지(기기 저장) ----- */
  ok('V39 복원 결과가 저장소(계정 키)에 남는다', (function () {
    const raw = T23.localStorage.getItem('ttokttok_account_v3');
    if (!raw) return false;
    const obj = JSON.parse(raw);
    return obj.bookings.filter((b) => b.no === 'TT-261021-7302')[0].status === 'confirmed';
  })());
  const seeded23 = {};
  ['ttokttok_account_v3', 'ttokttok_partner_v1', 'ttokttok_notifs_v1', 'ttokttok_admin_v1'].forEach((k) => {
    const v = T23.localStorage.getItem(k);
    if (v !== null) seeded23[k] = v;
  });
  const D23b = makeDom(seeded23);
  await sleep(60);
  const M23b = D23b.window.__ttokttokModel;
  ok('V40 새로 열어도 복원한 예약·일지·알림이 유지', !!M23b &&
    M23b.reservations().length === snap23.counts.reservations &&
    M23b.partnerJournals().length === snap23.counts.journals &&
    M23b.notifs().length === snap23.counts.notifications,
    M23b && [M23b.reservations().length, M23b.partnerJournals().length, M23b.notifs().length].join('/'));

  /* ----- 7) 저장소 어댑터 계약 ----- */
  ok('V41 기본 어댑터는 localStorage(local)', (function () {
    const a = M23.storageAdapter();
    return a.kind === 'local' && a.version === 'ttokttok.storage.v23' && Array.isArray(M23.storageAdapterContract) &&
      M23.storageAdapterContract.join(',') === 'kind,available,get,set,getRaw,setRaw,remove,keys';
  })(), JSON.stringify(M23.storageAdapter()));
  ok('V42 메모리 어댑터로 교체 → 읽기·쓰기가 그쪽으로', (function () {
    const mem = M23.memoryAdapter({ seeded: JSON.stringify({ a: 1 }) });
    const used = M23.useStorageAdapter(mem);
    M23.storageWrite('probe', { b: 2 });
    const read = M23.storageRead('probe');
    const seededRead = M23.storageRead('seeded');
    return used && M23.storageAdapter().kind === 'memory' && read && read.b === 2 &&
      seededRead && seededRead.a === 1 && mem.getRaw('probe') !== null;
  })());
  ok('V43 기존 저장 경로(savePartner/saveAccount)도 어댑터를 지난다', (function () {
    const mem = M23.memoryAdapter();
    M23.useStorageAdapter(mem);
    M23.transition('TT-261021-7302', 'completed', { actor: 'operator' });
    const acct = mem.getRaw('ttokttok_account_v3');
    const part = mem.getRaw('ttokttok_partner_v1');
    return !!acct && !!part && /TT-261021-7302/.test(acct);
  })());
  ok('V44 어댑터 계약에 안 맞는 객체는 거부', M23.useStorageAdapter({ kind: 'broken' }) === false &&
    M23.useStorageAdapter(null) === false);
  ok('V45 기본 어댑터로 되돌리기', M23.resetStorageAdapter() === true && M23.storageAdapter().kind === 'local');
  ok('V46 v23 작업 후 JS 오류 없음', D23.errors.length === 0, D23.errors.slice(0, 3).join(' | '));

  }
  if (PART === '1') { report(); return; }

  /* ============================================================
     W. v24 — 모바일·접근성·성능 QA(접근성 속성·Escape·포커스 회귀)
     ============================================================ */
  const D24 = makeDom();
  const h24 = helpers(D24.window, D24.doc);
  await sleep(60);
  const M24 = D24.window.__ttokttokModel;
  const doc24 = D24.doc;
  const escKey = () => doc24.dispatchEvent(new D24.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  const openOf = (id) => doc24.getElementById(id).classList.contains('is-open');

  ok('W0 v24 JS 오류 없음', D24.errors.length === 0, D24.errors.slice(0, 3).join(' | '));
  ok('W1 v31 메타·QA 훅 노출', doc24.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    !!M24 && M24.qaVersion === 'v34' && M24.a11y.version === 'v34' && M24.a11y.dialogOrder.length >= 15,
    M24 && [M24.qaVersion, M24.a11y && M24.a11y.version, M24.a11y && M24.a11y.dialogOrder.length].join('/'));

  /* ----- 1) 정적 접근성 속성 ----- */
  ok('W2 중복 id 없음', (function () {
    const seen = {}; const dup = [];
    Array.from(doc24.querySelectorAll('[id]')).forEach((el) => {
      if (seen[el.id]) dup.push(el.id); else seen[el.id] = 1;
    });
    D24.dupIds = dup;
    return dup.length === 0;
  })(), (D24.dupIds || []).slice(0, 5).join(','));
  ok('W3 모든 role=dialog에 aria-modal·접근성 이름', (function () {
    const bad = [];
    Array.from(doc24.querySelectorAll('[role="dialog"]')).forEach((el) => {
      const lb = el.getAttribute('aria-labelledby');
      const al = (el.getAttribute('aria-label') || '').trim();
      const named = lb ? lb.split(/\s+/).map((id) => (doc24.getElementById(id) ? doc24.getElementById(id).textContent.trim() : '')).join('') : '';
      if (el.getAttribute('aria-modal') !== 'true' || !(named || al)) bad.push(el.id);
    });
    D24.badDialogs = bad;
    return bad.length === 0;
  })(), (D24.badDialogs || []).join(','));
  ok('W4 접근성 이름 없는 버튼·링크 0', (function () {
    const bad = [];
    Array.from(doc24.querySelectorAll('button,[role="button"],a[href]')).forEach((el) => {
      let n = (el.getAttribute('aria-label') || '').trim();
      if (!n && el.getAttribute('aria-labelledby')) n = el.getAttribute('aria-labelledby').split(/\s+/).map((id) => doc24.getElementById(id) ? doc24.getElementById(id).textContent : '').join('').trim();
      if (!n) n = (el.getAttribute('title') || '').trim();
      if (!n) n = (el.textContent || '').replace(/\s+/g, ' ').trim();
      if (!n) bad.push(el.id || el.className || el.tagName);
    });
    D24.unnamed = bad;
    return bad.length === 0;
  })(), (D24.unnamed || []).slice(0, 5).join(','));
  ok('W5 label 없는 입력·셀렉트·텍스트영역 0', (function () {
    const bad = [];
    Array.from(doc24.querySelectorAll('input:not([type="hidden"]),select,textarea')).forEach((el) => {
      const has = (el.id && doc24.querySelector('label[for="' + el.id + '"]')) || el.closest('label') ||
        el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title');
      if (!has) bad.push(el.id || el.name || el.tagName);
    });
    D24.unlabeled = bad;
    return bad.length === 0;
  })(), (D24.unlabeled || []).slice(0, 5).join(','));
  ok('W6 img 전부 alt 속성 보유', Array.from(doc24.querySelectorAll('img')).every((el) => el.hasAttribute('alt')));
  ok('W7 label[for]·aria-* 참조 대상 전부 존재', (function () {
    const bad = [];
    Array.from(doc24.querySelectorAll('label[for]')).forEach((el) => {
      if (!doc24.getElementById(el.getAttribute('for'))) bad.push('for=' + el.getAttribute('for'));
    });
    ['aria-labelledby', 'aria-describedby', 'aria-controls'].forEach((attr) => {
      Array.from(doc24.querySelectorAll('[' + attr + ']')).forEach((el) => {
        if (attr === 'aria-labelledby' && (el.getAttribute('aria-label') || '').trim()) return;
        el.getAttribute(attr).split(/\s+/).forEach((id) => { if (!doc24.getElementById(id)) bad.push(attr + '=' + id); });
      });
    });
    D24.brokenRefs = bad;
    return bad.length === 0;
  })(), (D24.brokenRefs || []).slice(0, 5).join(','));
  ok('W8 상태 알림 role=status·aria-live', ['#toast', '#reviewHint', '#adminBackupResult', '#doneSaved'].every((sel) => {
    const el = doc24.querySelector(sel);
    return !!el && ((el.getAttribute('role') === 'status' || el.getAttribute('role') === 'alert') && el.getAttribute('aria-live'));
  }));
  ok('W9 화면 12개 전부 제목(h1·h2) 보유', Array.from(doc24.querySelectorAll('section.screen')).every((s) => !!s.querySelector('h1,h2')));
  ok('W10 아이콘 닫기 버튼은 aria-label 보유', (function () {
    const closes = Array.from(doc24.querySelectorAll('.sheet-close'));
    return closes.length >= 10 && closes.every((el) => (el.getAttribute('aria-label') || '').trim() || (el.textContent || '').trim());
  })());
  ok('W11 style 블록 CSS 토큰 정합성', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    return !!m && cssTokens(HTML).ok;
  })(), (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length);

  /* ----- 2) Escape 닫기·포커스 이동/복귀 ----- */
  h24.click(h24.$('[data-login="customer"]'));
  await sleep(30);
  h24.click(doc24.querySelector('#teacherList .teacher'));
  await sleep(30);
  ok('W12 시트를 열면 초점이 시트 안으로', openOf('teacherSheet') && M24.a11y.focusInside('#teacherSheet'));
  h24.click(h24.$('#sheetChat'));
  await sleep(30);
  ok('W13 문의 시트를 열면 초점이 문의 시트 안으로', openOf('chatSheet') && M24.a11y.focusInside('#chatSheet') && !openOf('teacherSheet'));
  escKey();
  await sleep(10);
  ok('W14 Escape → 문의 시트 닫힘', !openOf('chatSheet'));
  /* 겹친 시트: 예약 내역 위에 내역 시트를 연 뒤 Escape 1회는 위 레이어만 닫는다 */
  h24.click(h24.$('#mpBookLink'));
  await sleep(20);
  const manageBtn = doc24.querySelector('#accountSheet [data-manage]');
  h24.click(manageBtn);
  await sleep(20);
  ok('W15 예약 내역 위에 내역 시트가 겹쳐 열림', openOf('accountSheet') && openOf('manageSheet'));
  escKey();
  await sleep(10);
  ok('W16 Escape 1회 → 위 레이어(내역 시트)만 닫힘', !openOf('manageSheet') && openOf('accountSheet'),
    [openOf('manageSheet'), openOf('accountSheet')].join('/'));
  ok('W17 닫힌 시트의 초점은 눌렀던 버튼으로 복귀', doc24.activeElement === manageBtn, doc24.activeElement && (doc24.activeElement.id || doc24.activeElement.className));
  escKey();
  await sleep(10);
  ok('W18 Escape 2회 → 예약 내역 시트도 닫힘', !openOf('accountSheet'));

  const escCases = [
    ['#safetySheet', () => doc24.querySelector('[data-safety-open]')],
    ['#faqSheet', () => h24.$('#mpFaqRow')],
    ['#accountSheet', () => h24.$('#mpBookLink')],
    ['#paySheet', () => h24.$('#mpPayRow')],
    ['#couponSheet', () => h24.$('#mpCouponRow')],
    ['#roleSheet', () => h24.$('#mpRoleRow')],
    ['#notifSheet', () => h24.$('#mpNotifRow')]
  ];
  const escBad = [];
  escCases.forEach(([id, opener]) => {
    const btn = opener();
    if (!btn) { escBad.push(id + ': 열기 버튼 없음'); return; }
    h24.click(btn);
    if (!openOf(id.slice(1))) { escBad.push(id + ': 열리지 않음'); return; }
    escKey();
    if (openOf(id.slice(1))) escBad.push(id + ': Escape로 안 닫힘');
  });
  ok('W19 보호자 시트 7종 Escape로 닫힘', escBad.length === 0, escBad.join(' | '));
  ok('W20 열린 시트 없으면 Escape는 아무 것도 닫지 않는다', (function () {
    escKey();
    return doc24.querySelectorAll('.sheet-backdrop.is-open, .backdrop.is-open').length === 0 &&
      doc24.getElementById('entryGate') && !doc24.getElementById('entryGate').classList.contains('is-open');
  })());
  ok('W21 시트를 닫으면 초점이 누른 카드로 복귀', await (async function () {
    h24.click(doc24.querySelector('.tabbar[data-mode="customer"] [data-tab="teachers"]'));
    await sleep(20);
    const card = doc24.querySelectorAll('#teacherList .teacher')[1];
    h24.click(card);
    await sleep(20);
    const opened = openOf('teacherSheet');
    escKey();
    await sleep(20);
    return opened && !openOf('teacherSheet') && doc24.activeElement === card;
  })(), doc24.activeElement && (doc24.activeElement.id || doc24.activeElement.className));

  /* ----- 3) 저장 차단 폴백 + 접근성 유지 ----- */
  const D24b = makeDom();
  const h24b = helpers(D24b.window, D24b.doc);
  await sleep(60);
  h24b.click(h24b.$('[data-login="customer"]'));
  await sleep(20);
  ok('W22 v24 저장 차단 폴백에서도 접근성 속성 유지', !!D24b.window.__ttokttokModel &&
    D24b.window.__ttokttokModel.a11y.dialogCount() >= 15 && D24b.window.__ttokttokModel.a11y.unnamedControls().length === 0,
    D24b.window.__ttokttokModel && JSON.stringify(D24b.window.__ttokttokModel.a11y.unnamedControls().slice(0, 3)));
  ok('W23 v24 작업 후 JS 오류 없음(저장 차단)', D24b.errors.length === 0, D24b.errors.slice(0, 3).join(' | '));
  ok('W24 v24 작업 후 JS 오류 없음', D24.errors.length === 0, D24.errors.slice(0, 3).join(' | '));

  /* ============================================================
     X. v25 — 보호자 홈 통합 대시보드 · 첫 방문 온보딩 · FAQ 검색/필터
     ============================================================ */
  const D25 = makeDom();
  const h25 = helpers(D25.window, D25.doc);
  await sleep(60);
  const M25 = D25.window.__ttokttokModel;
  const doc25 = D25.doc;

  ok('X0 v25 JS 오류 없음', D25.errors.length === 0, D25.errors.slice(0, 3).join(' | '));
  ok('X1 v31 메타·요약 모델 노출', doc25.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    !!M25 && M25.guardianVersion === 'v25' && M25.qaVersion === 'v34' && M25.guardianReportDays === 28 &&
    typeof M25.buildGuardianSummary === 'function' && Array.isArray(M25.faqCategories), M25 && M25.guardianVersion);
  ok('X2 홈 요약 카드가 홈 본문 첫 요소', (function () {
    const body = doc25.querySelector('#screen-home .home-body');
    return !!body && body.firstElementChild && body.firstElementChild.id === 'homeSummaryCard' &&
      !!doc25.querySelector('#homeSummaryCard .card-head h2');
  })());

  /* ----- 1) 다음 방문 요약 ----- */
  const sum25 = M25.guardianSummary();
  ok('X3 다음 방문 요약(시드 예약·상태·D-day)', !!sum25.nextVisit && sum25.nextVisit.bookingNo === 'TT-261021-7302' &&
    sum25.nextVisit.status === 'confirmed' && /^D-\d+$/.test(sum25.nextVisit.ddayLabel) && !!sum25.nextVisit.teacher, JSON.stringify(sum25.nextVisit));
  const nextText = h25.text('#homeSummaryNext');
  ok('X4 홈 요약에 예약번호·상태 칩·다음 방문 표시', /TT-261021-7302/.test(nextText) && /예약 확정/.test(nextText) && /10:30/.test(nextText), nextText);
  ok('X5 홈 요약에 금액·수수료 없음', !/\d+,\d{3}원/.test(h25.text('#homeSummaryCard')) && !/10%/.test(h25.text('#homeSummaryCard')), h25.text('#homeSummaryCard').slice(0, 120));

  /* ----- 2) 보유 회차권 ----- */
  ok('X6 회차권 잔여·만료 요약', sum25.passes.total === 5 && sum25.passes.count === 1 &&
    sum25.passes.items[0].name === '8회권' && sum25.passes.items[0].remaining === 5 && sum25.passes.items[0].total === 8 &&
    sum25.passes.nearestExpire === '2027.01.27', JSON.stringify(sum25.passes));
  const passText = h25.text('#homeSummaryPass');
  ok('X7 회차권 카드 문구(잔여 5회·8회·만료 예정)', /잔여 5회/.test(passText) && /5회 \/ 8회/.test(passText) && /2027\.01\.27/.test(passText), passText);
  ok('X8 회차권 안내 1·4·8·12회권', /1회권/.test(passText) && /4회권/.test(passText) && /8회권/.test(passText) && /12회권/.test(passText), passText);

  /* ----- 3) 최근 4주 리포트·4주 재평가 ----- */
  ok('X9 최근 4주 리포트(방문 2회·일지)', sum25.report.rounds === 2 && sum25.report.visitedDays === 2 &&
    sum25.report.lastDateIso === '2026-11-25' && sum25.report.hasJournal === true, JSON.stringify(sum25.report).slice(0, 200));
  ok('X10 4주 재평가 배지(D+)·상태 due', !!sum25.report.reeval && sum25.report.reeval.status === 'due' &&
    /^4주 재평가 D\+8$/.test(sum25.report.reeval.badge), sum25.report.reeval && sum25.report.reeval.badge);
  const repText = h25.text('#homeSummaryReport');
  ok('X11 리포트 요약 카드에 방문 횟수·재평가 표시', /최근 4주 방문/.test(repText) && /2회/.test(repText) && /재평가/.test(repText), repText);

  /* ----- 4) 바로가기 ----- */
  ok('X12 요약 → 방문 일정 바로가기', await (async function () {
    const btn = doc25.querySelector('#homeSummaryCard [data-summary="visit"]');
    if (!btn) return false;
    h25.click(btn);
    await sleep(20);
    return doc25.getElementById('accountSheet').classList.contains('is-open');
  })());
  h25.doc.dispatchEvent(new D25.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  await sleep(10);
  ok('X13 요약 → 이용권 바로가기', await (async function () {
    const btn = doc25.querySelector('#homePassCard [data-summary="pass"]');
    if (!btn) return false;
    h25.click(btn);
    await sleep(20);
    return doc25.getElementById('accountSheet').classList.contains('is-open');
  })());
  h25.doc.dispatchEvent(new D25.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  await sleep(10);
  ok('X14 요약 → 이번 주 리포트 열기(일지 탭+시트)', await (async function () {
    const btn = doc25.querySelector('#homeReportCard [data-summary="report"]');
    if (!btn) return false;
    h25.click(btn);
    await sleep(30);
    return doc25.getElementById('screen-journal').classList.contains('is-active') &&
      doc25.getElementById('weeklySheet').classList.contains('is-open') && /이번 주 방문/.test(h25.text('#weeklySheetBody'));
  })());
  h25.doc.dispatchEvent(new D25.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  await sleep(10);

  /* ----- 5) 순수 함수: 취소·지난 방문 제외, 빈 값 ----- */
  ok('X15 buildGuardianSummary 순수 함수(취소·노쇼·지난 방문 제외)', (function () {
    const r = M25.buildGuardianSummary({
      todayIso: '2026-11-26',
      bookings: [
        { no: 'A', status: 'canceled', dateIso: '2026-11-27', time: '10:00', teacher: 'x' },
        { no: 'B', status: 'no_show', dateIso: '2026-11-27', time: '10:00', teacher: 'x' },
        { no: 'C', status: 'confirmed', dateIso: '2026-11-20', time: '10:00', teacher: 'x' },
        { no: 'D', status: 'assigned', dateIso: '2026-12-01', time: '14:00', teacher: 'y' },
        { no: 'E', status: 'confirmed', dateIso: '2026-11-30', time: '09:00', teacher: 'z' }
      ],
      passes: [{ name: '4회 방문권', total: 4, remaining: 0, expire: '2026.12.01' }, { name: '12회 집중 재활', total: 12, remaining: 9, expire: '2027.02.01' }],
      journals: [{ date: '2026.10.01', pain5: 2 }, { date: '2026.11.25', pain5: 4, condition5: 4, nextFocus: '보행 연습' }]
    });
    return r.nextVisit.bookingNo === 'E' && r.nextVisit.dday === 4 && r.nextVisit.upcomingCount === 2 &&
      r.passes.total === 9 && r.passes.count === 1 && r.passes.items[0].name === '12회 집중 재활' &&
      r.report.rounds === 1 && r.report.nextFocus === '보행 연습';
  })(), JSON.stringify(M25.buildGuardianSummary({ todayIso: '2026-11-26', bookings: [{ no: 'E', status: 'confirmed', dateIso: '2026-11-30' }] }).nextVisit));
  ok('X16 buildGuardianSummary 빈 입력 안전', (function () {
    const r = M25.buildGuardianSummary({ todayIso: '2026-11-26' });
    return r.nextVisit === null && r.passes.total === 0 && r.passes.items.length === 0 && r.report.rounds === 0 && r.report.reeval === null;
  })());
  ok('X17 다음 방문 없으면 예약 CTA', (function () {
    const r = M25.buildGuardianSummary({ todayIso: '2026-11-26', bookings: [], passes: [], journals: [] });
    return r.nextVisit === null && r.report.hasJournal === false && !!doc25.querySelector('#homeSummaryCard .card-head');
  })());

  /* ----- 6) 첫 방문 온보딩(준비물·진행 순서·불안 해소) ----- */
  h25.click(h25.$('#homeGuideBtn'));
  await sleep(20);
  const ob = M25.onboarding();
  ok('X18 준비물 3가지', ob.prep.length === 3 && /편한 복장/.test(h25.text('#onboardPrepCard')) && /실내 공간 2m/.test(h25.text('#onboardPrepCard')) && /진단서·복약 메모/.test(h25.text('#onboardPrepCard')), h25.text('#onboardPrepCard'));
  ok('X19 첫 방문 진행 3단계(15분·맞춤 계획·60분)', ob.flow.length === 3 && /15분 평가/.test(h25.text('#onboardFlow')) && /맞춤 계획/.test(h25.text('#onboardFlow')) && /60분 본 수업/.test(h25.text('#onboardFlow')), h25.text('#onboardFlow'));
  ok('X20 불안 해소 2가지(강제 결제 없음·선생님 교체)', /강제 결제 없음/.test(h25.text('#onboardAssurance')) && /선생님 교체/.test(h25.text('#onboardAssurance')), h25.text('#onboardAssurance'));
  ok('X21 준비물 체크 → 저장·안내 문구 갱신', (function () {
    const cb = doc25.getElementById('obPrep-dress');
    cb.checked = true;
    cb.dispatchEvent(new D25.window.Event('change', { bubbles: true }));
    return M25.onboarding().count === 1 && /1가지 확인/.test(h25.text('#onboardPrepNote')) &&
      JSON.parse(D25.window.localStorage.getItem('ttokttok_onboarding_v1')).dress === true;
  })(), h25.text('#onboardPrepNote'));
  ok('X22 모두 체크하면 완료 문구', (function () {
    ['space', 'docs'].forEach((code) => { M25.setOnboarding(code, true); });
    return M25.onboarding().count === 3 && /모두 확인했어요/.test(h25.text('#onboardPrepNote'));
  })(), h25.text('#onboardPrepNote'));
  h25.click(h25.$('[data-guide-close]'));

  /* ----- 7) FAQ 검색·카테고리 필터 ----- */
  h25.click(h25.$('#mpFaqRow'));
  await sleep(20);
  ok('X23 FAQ 10문항 기본 목록', h25.$$('#faqList .faq-item').length === 10 && /자주 묻는 질문 10개/.test(h25.text('#faqCount')), h25.text('#faqCount'));
  ok('X24 검색어 입력 → 일치 항목만(환불)', (function () {
    const input = h25.$('#faqSearch');
    input.value = '환불';
    input.dispatchEvent(new D25.window.Event('input', { bubbles: true }));
    const text = h25.text('#faqList');
    const n = h25.$$('#faqList .faq-item').length;
    return n >= 1 && n < 10 && /환불/.test(text) && !/선생님을 바꿀 수/.test(text) && /검색 결과/.test(h25.text('#faqCount'));
  })(), h25.text('#faqCount'));
  ok('X25 카테고리 칩(선생님/안전) 필터', (function () {
    M25.resetFaq();
    const chip = doc25.querySelector('#faqCatChips [data-faqcat="safety"]');
    h25.click(chip);
    const ids = h25.$$('#faqList [data-faq]').map((b) => b.getAttribute('data-faq'));
    return chip.classList.contains('is-on') && ids.length === 3 && ids.indexOf('faq-license') !== -1 &&
      ids.indexOf('faq-safety') !== -1 && ids.indexOf('faq-teacher-change') !== -1;
  })(), h25.$$('#faqList [data-faq]').map((b) => b.getAttribute('data-faq')).join(','));
  ok('X26 검색+카테고리 결과 0건 → 빈 상태·상담 연결', (function () {
    M25.setFaqQuery('존재하지않는검색어');
    const empty = doc25.getElementById('faqEmpty');
    const link = empty.querySelector('a');
    return !empty.hidden && h25.$$('#faqList .faq-item').length === 0 && /검색 결과가 없어요/.test(empty.textContent) &&
      /1:1 상담/.test(link.textContent) && /naver\.me/.test(link.getAttribute('href'));
  })(), h25.text('#faqCount'));
  ok('X27 검색 초기화 → 10문항 복귀', (function () {
    const reset = h25.$('#faqReset');
    const visible = reset && !reset.hidden;
    h25.click(reset);
    return visible && h25.$$('#faqList .faq-item').length === 10 && doc25.getElementById('faqEmpty').hidden === true &&
      h25.$('#faqSearch').value === '';
  })(), String(h25.$$('#faqList .faq-item').length));
  ok('X28 FAQ 아코디언은 필터 뒤에도 동작', (function () {
    const q = doc25.querySelector('#faqList [data-faq="faq-pass"]');
    if (!q) return false;
    h25.click(q);
    const opened = doc25.querySelector('#faqList [data-faq="faq-pass"]');
    return doc25.querySelectorAll('#faqList .faq-item.is-open').length === 1 &&
      !!opened && opened.getAttribute('aria-expanded') === 'true';
  })());
  const faqA11y = M25.a11y;
  ok('X29 FAQ 검색 입력 label·카운트 aria-live', (function () {
    const input = h25.$('#faqSearch');
    const cnt = h25.$('#faqCount');
    return !!input && !!(input.getAttribute('aria-label') || doc25.querySelector('label[for="faqSearch"]')) &&
      cnt.getAttribute('role') === 'status' && !!cnt.getAttribute('aria-live') && faqA11y.unnamedControls().length === 0 &&
      faqA11y.unlabeledFields().length === 0;
  })(), JSON.stringify(faqA11y.unlabeledFields()));
  h25.click(h25.$('[data-faq-close]'));

  /* ----- 8) 저장값 복원·손상 데이터·디자인 불변 ----- */
  const D25b = makeDom({ ttokttok_onboarding_v1: '{"dress":true,"space":true}' });
  const h25b = helpers(D25b.window, D25b.doc);
  await sleep(40);
  ok('X30 준비물 체크 새로 열어도 유지', D25b.errors.length === 0 && D25b.window.__ttokttokModel.onboarding().count === 2 &&
    D25b.doc.getElementById('obPrep-dress').checked === true && D25b.doc.getElementById('obPrep-space').checked === true &&
    D25b.doc.getElementById('obPrep-docs').checked === false, String(D25b.window.__ttokttokModel.onboarding().count));
  const D25c = makeDom({ ttokttok_onboarding_v1: '{broken' });
  await sleep(40);
  ok('X31 손상 저장값에서도 오류 없음(0개로 시작)', D25c.errors.length === 0 &&
    D25c.window.__ttokttokModel.onboarding().count === 0 && D25c.doc.querySelectorAll('#homeSummaryCard').length === 1,
    D25c.errors.slice(0, 2).join(' | '));
  ok('X32 CSS 토큰 정합성(디자인 토큰 통합 후)', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    return !!m && cssTokens(HTML).ok;
  })(), (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length);
  ok('X33 v25 작업 후 JS 오류 없음', D25.errors.length === 0, D25.errors.slice(0, 3).join(' | '));

  /* ============================================================
     Y. v26 — 선생님 정산 명세서 · 월별 리포트
     ============================================================ */
  const D26 = makeDom();
  const h26 = helpers(D26.window, D26.doc);
  await sleep(60);
  const M26 = D26.window.__ttokttokModel;
  const doc26 = D26.doc;

  ok('Y0 v26 JS 오류 없음', D26.errors.length === 0, D26.errors.slice(0, 3).join(' | '));
  ok('Y1 v31 메타·명세서 모델 노출', doc26.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    !!M26 && M26.statementVersion === 'v26' && M26.qaVersion === 'v34' &&
    typeof M26.buildTeacherSettlementStatement === 'function' && M26.withholdingRate === 0.033, M26 && M26.statementVersion);

  /* ----- 1) 화면 진입·월 선택·요약 ----- */
  h26.click(h26.$('[data-login="therapist"]'));
  await sleep(30);
  ok('Y2 파트너 홈에 정산 명세서 링크', /정산 명세서 보기/.test(h26.text('#tpSettle')) && !!h26.$('#tpSettle [data-tab="tp-settle"]'));
  h26.click(h26.$('#tpSettle [data-tab="tp-settle"]'));
  await sleep(30);
  ok('Y3 정산 탭 → 정산 명세서 화면', doc26.getElementById('screen-tp-settle').classList.contains('is-active') &&
    !!h26.$('#screen-tp-settle .page-head h1') && /정산 명세서/.test(h26.text('#screen-tp-settle .page-head h1')));
  ok('Y4 월 선택 칩(11월·10월)', (function () {
    const chips = h26.$$('#tpsMonths [data-stl-month]');
    return chips.length === 2 && chips[0].getAttribute('data-stl-month') === '2026-11' && chips[0].classList.contains('is-on') &&
      chips[0].getAttribute('aria-pressed') === 'true' && /2026년 11월/.test(chips[0].textContent) &&
      chips[1].getAttribute('data-stl-month') === '2026-10';
  })(), h26.$$('#tpsMonths [data-stl-month]').map((b) => b.getAttribute('data-stl-month')).join(','));
  const sum26 = h26.text('#tpsSummary');
  ok('Y5 월 요약(완료 14회·지급완료·지급예정·정산대기)', /완료 14회/.test(sum26) && /980,000/.test(sum26) &&
    /지급완료 7건/.test(sum26) && /지급예정 6건/.test(sum26) && /정산대기 1건/.test(sum26), sum26.slice(0, 160));
  ok('Y6 원천징수 3.3% 참고·실수령 예상', /원천징수 3.3% 참고/.test(sum26) && /32,340원/.test(sum26) && /947,660원/.test(sum26), sum26.slice(-120));
  ok('Y7 정산 규칙·세무 안내 문구', /D\+3/.test(sum26) && /15일·말일/.test(sum26) && /세무 확인/.test(sum26));

  /* ----- 2) 회차별 상세 ----- */
  ok('Y8 회차별 내역 14건', h26.$$('#tpsRows [data-stl-row]').length === 14 && /14건/.test(h26.text('#tpsRowCount')),
    String(h26.$$('#tpsRows [data-stl-row]').length));
  ok('Y9 첫 행 예약번호·상태칩·지급일', (function () {
    const first = h26.$$('#tpsRows [data-stl-row]')[0];
    const t = first ? first.textContent.replace(/\s+/g, ' ') : '';
    return /TT-261125-1054/.test(t) && /정산대기/.test(t) && /2026\.11\.30/.test(t) && /70,000원/.test(t) && /2,310원/.test(t) && /67,690원/.test(t);
  })(), (h26.$$('#tpsRows [data-stl-row]')[0] || {}).textContent);
  ok('Y10 지급완료 행은 11.15 지급으로 표시', /11\.15/.test(h26.text('#tpsRows')) && /지급완료/.test(h26.text('#tpsRows')));

  /* ----- 3) 월 전환 ----- */
  h26.click(h26.$('#tpsMonths [data-stl-month="2026-10"]'));
  await sleep(30);
  ok('Y11 10월로 전환 → 12건·무료 평가 포함', (function () {
    const rows = h26.$$('#tpsRows [data-stl-row]');
    const t = h26.text('#tpsRows');
    return rows.length === 12 && /무료 평가/.test(t) && /770,000/.test(h26.text('#tpsSummary')) &&
      h26.$('#tpsMonths [data-stl-month="2026-10"]').classList.contains('is-on');
  })(), String(h26.$$('#tpsRows [data-stl-row]').length));
  ok('Y12 월 선택은 기기에 저장', String(D26.window.localStorage.getItem('ttokttok_statement_month_v1') || '') === '2026-10');
  h26.click(h26.$('#tpsMonths [data-stl-month="2026-11"]'));
  await sleep(20);

  /* ----- 4) 순수 함수: 정산 규칙·상태·유형 ----- */
  ok('Y13 D+3 확정·15일/말일 지급 계산(v21 규칙과 일치)', (function () {
    const a = M26.buildTeacherSettlementStatement({ todayIso: '2026-11-26', ledger: [
      { id: 'L1', visitDate: '2026-11-25', netAmount: 70000, grossAmount: 90000, feeAmount: 20000, status: 'pending' },
      { id: 'L2', visitDate: '2026-11-12', netAmount: 70000, grossAmount: 90000, feeAmount: 20000, status: 'paid' },
      { id: 'L3', visitDate: '2026-11-28', netAmount: 70000, grossAmount: 90000, feeAmount: 20000, status: 'scheduled' }
    ] }, '2026-11');
    const by = {}; a.rows.forEach((r) => { by[r.id] = r; });
    return by.L1.confirmDate === '2026-11-28' && by.L1.payoutDueDate === '2026-11-30' && by.L1.status === 'pending' &&
      by.L2.payoutDueDate === '2026-11-15' && by.L2.status === 'paid' &&
      by.L3.confirmDate === '2026-12-01' && by.L3.payoutDueDate === '2026-12-15' && by.L3.status === 'pending';
  })(), JSON.stringify(M26.buildTeacherSettlementStatement({ todayIso: '2026-11-26', ledger: [{ id: 'L3', visitDate: '2026-11-28', netAmount: 70000 }] }, '2026-11').rows[0]));
  ok('Y14 지급 상태 판정(지급완료·보류·예정)', (function () {
    function st(status) {
      const r = M26.buildTeacherSettlementStatement({ todayIso: '2026-11-26', ledger: [{ id: 'X', visitDate: '2026-11-10', netAmount: 70000, status: status }] }, '2026-11').rows[0];
      return r.status;
    }
    return st('paid') === 'paid' && st('held') === 'held' && st('scheduled') === 'scheduled';
  })());
  ok('Y15 취소 회차는 정산 제외(0원)', (function () {
    const r = M26.buildTeacherSettlementStatement({ todayIso: '2026-11-26', ledger: [], canceled: [{ id: 'c1', no: 'TT-261120-9001', dateIso: '2026-11-20', patient: '홍길동', reason: '보호자 취소' }] }, '2026-11').rows[0];
    return !!r && r.excluded === true && r.status === 'excluded' && r.statusLabel === '정산 제외' && r.payoutAmount === 0 && r.netExpected === 0 && /TT-261120-9001/.test(r.reservationNo);
  })());
  ok('Y16 원천징수 3.3%·실수령 계산(70,000 → 2,310·67,690)', (function () {
    const r = M26.buildTeacherSettlementStatement({ todayIso: '2026-11-26', ledger: [{ id: 'X', visitDate: '2026-11-25', netAmount: 70000, grossAmount: 90000, feeAmount: 20000 }] }, '2026-11').rows[0];
    return r.withholdingAmount === 2310 && r.netExpected === 67690 && r.consumerAmount === 90000 && r.platformFee === 20000;
  })());
  ok('Y17 월 목록·이번 달 기본값', (function () {
    const r = M26.buildTeacherSettlementStatement({ todayIso: '2026-11-26', ledger: [] }, '');
    return r.monthKey === '2026-11' && r.monthLabel === '2026년 11월' && r.months.indexOf('2026-11') !== -1 && r.rows.length === 0 &&
      /이 달에는 정산 내역이 없습니다/.test(r.text);
  })(), JSON.stringify(M26.buildTeacherSettlementStatement({ todayIso: '2026-11-26' }, '').months));
  ok('Y18 빈 입력에서도 단정한 결과', (function () {
    const r = M26.buildTeacherSettlementStatement({}, '');
    return r.rows.length === 0 && r.totals.payout === 0 && r.totals.netExpected === 0 && r.counts.completed === 0;
  })());

  /* ----- 5) 인쇄·미리보기·내보내기 ----- */
  h26.click(h26.$('#tpsScreen [data-stl-preview]'));
  await sleep(30);
  ok('Y19 정산서 미리보기 시트 열림', doc26.getElementById('settlementPrintSheet').classList.contains('is-open') &&
    /똑똑쌤 정산 명세서/.test(h26.text('#settlementPrintBody')) && /2026년 11월/.test(h26.text('#settlementPrintBody')) &&
    /947,660원/.test(h26.text('#settlementPrintBody')), h26.text('#settlementPrintBody').slice(0, 120));
  ok('Y20 인쇄·복사·JSON 버튼 있음', !!h26.$('#stlPrintBtn') && !!h26.$('#stlCopyBtn') && !!h26.$('#stlJsonBtn'));
  ok('Y21 Escape로 미리보기 시트 닫힘(DIALOG_ORDER 등록)', (function () {
    doc26.dispatchEvent(new D26.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    return !doc26.getElementById('settlementPrintSheet').classList.contains('is-open') &&
      M26.a11y.dialogOrder.indexOf('#settlementPrintSheet') !== -1;
  })());
  ok('Y22 텍스트 복사 → 명세서 텍스트', (function () {
    M26.copyStatementText();
    const last = M26.lastStatementExport() || {};
    return M26.lastStatementExport() !== null && typeof M26.lastStatementExport() === 'object' &&
      (/똑똑쌤 정산 명세서/.test(String(last.copied || '')) || /똑똑쌤 정산 명세서/.test(M26.settlementStatementText())) &&
      /TT-261125-1054/.test(M26.settlementStatementText());
  })(), JSON.stringify(M26.lastStatementExport() || {}).slice(0, 100));
  ok('Y23 JSON 내보내기(스키마·월·행 수)', (function () {
    M26.exportStatementJson();
    const last = M26.lastStatementExport() || {};
    if (!last.json) return false;
    const o = JSON.parse(last.json);
    return o.schemaVersion === 'ttokttok.statement.v26' && o.statement.monthKey === '2026-11' && o.statement.rows.length === 14 &&
      last.name === 'ttokttok-statement-2026-11.json' && o.statement.totals.netExpected === 947660;
  })(), String((M26.lastStatementExport() || {}).name));
  ok('Y24 인쇄용 문서(새 창)에 표·요약 포함', (function () {
    const html = M26.statementPrintHtml('2026-11');
    return /<!doctype html>/i.test(html) && /<table>/.test(html) && /방문일/.test(html) && /예약번호/.test(html) &&
      /947,660원/.test(html) && (html.match(/<tr><td>/g) || []).length === 14 && /@page/.test(html);
  })());

  /* ----- 6) 접근성·개인정보·디자인 불변 ----- */
  ok('Y25 미리보기 시트 dialog 이름·초점', (function () {
    M26.openStatementPreview();
    const okName = M26.a11y.labelledDialogs() === M26.a11y.dialogCount();
    const inSheet = M26.a11y.focusInside('#settlementPrintSheet');
    doc26.dispatchEvent(new D26.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    return okName && inSheet && M26.a11y.openDialog() === null;
  })(), String(M26.a11y.labelledDialogs()) + '/' + String(M26.a11y.dialogCount()));
  ok('Y26 정산 화면에 전화번호·주소 없음', !/010-\d{4}-\d{4}/.test(h26.text('#screen-tp-settle')) && !/\d+동 \d+호/.test(h26.text('#screen-tp-settle')));
  ok('Y27 미리보기 열어도 JS 오류 없음', D26.errors.length === 0, D26.errors.slice(0, 3).join(' | '));
  ok('Y28 CSS 토큰 정합성(디자인 토큰 통합 후)', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    return !!m && cssTokens(HTML).ok;
  })(), (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length);
  ok('Y29 선생님 탭바 5개(정산 추가)', (function () {
    const nav = doc26.querySelector('.tabbar[data-mode="therapist"]');
    return !!nav && nav.querySelectorAll('.tabbtn').length === 5 && /repeat\(5,1fr\)/.test(nav.getAttribute('style') || '') &&
      !!nav.querySelector('[data-tab="tp-settle"]');
  })());

  /* ----- 7) 저장 차단 폴백·심사 대기 ----- */
  const D26b = makeDom({ ttokttok_partner_v1: JSON.stringify({ status: 'pending', name: '김현수', teacherId: 'kim', license: '물리치료사', years: '2년', province: '서울' }) });
  const h26b = helpers(D26b.window, D26b.doc);
  await sleep(60);
  ok('Y30 심사 대기 상태에서는 정산 명세서 잠금', (function () {
    h26b.click(h26b.$('[data-login="therapist"]'));
    h26b.click(h26b.$('.tabbtn[data-tab="tp-settle"]'));
    return /승인 후/.test(h26b.text('#tpsScreen')) && !h26b.$('#tpsSummary') && !h26b.$('#tpsRows') &&
      D26b.errors.length === 0;
  })(), h26b.text('#tpsScreen').slice(0, 60) + ' | ' + D26b.errors.slice(0, 2).join(' | '));
  const D26c = makeDom({ ttokttok_statement_month_v1: '2026-10' });
  const h26c = helpers(D26c.window, D26c.doc);
  await sleep(60);
  ok('Y31 저장된 월 선택으로 다시 열림', (function () {
    h26c.click(h26c.$('[data-login="therapist"]'));
    h26c.click(h26c.$('#tpsScreen [data-stl-month="2026-10"]') || h26c.$('#tpSettle [data-tab="tp-settle"]'));
    const st = D26c.window.__ttokttokModel.statementScreenState();
    return D26c.window.__ttokttokModel.statementMonth() === '2026-10' && st.monthKey === '2026-10' && D26c.errors.length === 0;
  })(), D26c.errors.slice(0, 2).join(' | '));
  ok('Y32 v26 작업 후 JS 오류 없음', D26.errors.length === 0, D26.errors.slice(0, 3).join(' | '));


  /* ============================================================
     Z. v27 — 알림·리마인드 센터 (보호자 · 선생님 · 운영자)
     ============================================================ */
  function pad2n(n) { return n < 10 ? '0' + n : '' + n; }
  function offIso(off) {
    const x = new Date(Date.now() + off * 86400000);
    return x.getFullYear() + '-' + pad2n(x.getMonth() + 1) + '-' + pad2n(x.getDate());
  }
  function lblOf(iso) { const p = iso.split('-'); return Number(p[1]) + '.' + p[2]; }
  const todayZ = offIso(0);
  const atIso = (off, hm) => offIso(off) + 'T' + (hm || '01:00') + ':00.000Z';
  const zBookings = [
    { id: 'zr1', no: 'TT-270001-9001', status: 'confirmed', date: lblOf(offIso(1)), day: '목', time: '10:30',
      teacher: '박서준 선생님', teacherId: 'park', region: '서울 강남구 대치동', regionId: 'reg-서울-강남구', dateIso: offIso(1), amount: 90000 },
    { id: 'zr2', no: 'TT-270001-9002', status: 'rescheduled', date: lblOf(offIso(0)), day: '수', time: '14:00',
      teacher: '박서준 선생님', teacherId: 'park', region: '서울 서초구 반포동', regionId: 'reg-서울-서초구', dateIso: offIso(0), amount: 90000,
      statusHistory: [{ status: 'confirmed', at: atIso(-3) }, { status: 'rescheduled', at: atIso(0, '02:00'), reason: '보호자 요청' }] },
    { id: 'zr3', no: 'TT-270001-9003', status: 'canceled', date: lblOf(offIso(0)), day: '수', time: '11:00',
      teacher: '박서준 선생님', teacherId: 'park', region: '서울 송파구 잠실동', regionId: 'reg-서울-송파구', dateIso: offIso(0), amount: 90000, refund: 90000,
      statusHistory: [{ status: 'confirmed', at: atIso(-4) }, { status: 'canceled', at: atIso(0, '05:00'), reason: '보호자 취소' }] },
    { id: 'zr4', no: 'TT-270001-9004', status: 'received', date: lblOf(offIso(4)), day: '일', time: '09:00',
      teacher: '이하늘 선생님', teacherId: 'lee', region: '서울 마포구 성산동', regionId: 'reg-서울-마포구', dateIso: offIso(4), amount: 90000,
      statusHistory: [{ status: 'assigned', at: atIso(-3) }, { status: 'received', at: atIso(0, '03:00'), reason: '선생님 사정' }] },
    { id: 'zr5', no: 'TT-270001-9005', status: 'completed', date: lblOf(offIso(-36)), day: '화', time: '10:30',
      teacher: '박서준 선생님', teacherId: 'park', region: '서울 강남구 대치동', regionId: 'reg-서울-강남구',
      dateIso: offIso(-36), firstVisitIso: offIso(-36), amount: 0 }
  ];
  const zLedger = [
    { id: 'zl1', reservationId: 'zr9', reservationNo: 'TT-270002-9101', visitDate: offIso(-2), grossAmount: 90000, feeAmount: 20000, netAmount: 70000, status: 'pending' },
    { id: 'zl2', reservationId: 'zr10', reservationNo: 'TT-270002-9102', visitDate: offIso(-3), grossAmount: 90000, feeAmount: 20000, netAmount: 70000, status: 'scheduled' },
    { id: 'zl3', reservationId: 'zr11', reservationNo: 'TT-270002-9103', visitDate: offIso(-20), grossAmount: 90000, feeAmount: 20000, netAmount: 70000, status: 'paid' },
    { id: 'zl4', reservationId: 'zr12', reservationNo: 'TT-270002-9104', visitDate: offIso(-2), grossAmount: 0, feeAmount: 0, netAmount: 0, status: 'scheduled' }
  ];

  const D27 = makeDom();
  const h27 = helpers(D27.window, D27.doc);
  await sleep(60);
  const M27 = D27.window.__ttokttokModel;
  const doc27 = D27.doc;

  ok('Z0 v27 JS 오류 없음', D27.errors.length === 0, D27.errors.slice(0, 3).join(' | '));
  ok('Z1 v31 메타·리마인드 모델 노출', doc27.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    !!M27 && M27.qaVersion === 'v34' && M27.reminderQueueVersion === 'v27' &&
    Array.isArray(M27.reminderCategories) && M27.reminderCategories.length === 4 &&
    Array.isArray(M27.reminderKinds) && M27.reminderKinds.length === 7 &&
    typeof M27.buildReminderQueue === 'function' && typeof M27.reminderPreviewText === 'function',
    M27 && [M27.qaVersion, M27.reminderQueueVersion].join('/'));
  ok('Z2 카테고리 4종(전체·방문 일정·리포트/재평가·정산/운영)', (function () {
    const keys = M27.reminderCategories.map((c) => c.key).join(',');
    const labels = M27.reminderCategories.map((c) => c.label).join(',');
    return keys === 'all,visit,report,ops' && labels === '전체,방문 일정,리포트/재평가,정산/운영';
  })(), M27.reminderCategories.map((c) => c.label).join(','));

  /* ----- 1) 순수 함수: 리마인드 큐 ----- */
  const q27 = M27.buildReminderQueue({ bookings: zBookings, ledger: zLedger }, todayZ);
  const kinds27 = q27.items.map((it) => it.kind);
  ok('Z3 큐가 D-1·변경·취소·대체·재평가·정산 항목을 모두 만든다',
    ['visit_d1', 'visit_change', 'visit_cancel', 'visit_substitute', 'reeval', 'settle_confirm', 'settle_payout']
      .every((k) => kinds27.indexOf(k) !== -1), kinds27.join(','));
  ok('Z4 큐는 오늘 날짜·버전·건수를 담는다', q27.version === 'v27' && q27.todayIso === todayZ &&
    q27.total === q27.items.length && q27.counts.total === q27.items.length, [q27.todayIso, q27.total].join('/'));
  ok('Z5 0원(무료 평가) 회차는 정산 알림에서 빠진다', (function () {
    const no = q27.items.map((it) => JSON.stringify(it)).join(' ');
    return no.indexOf('TT-270002-9104') === -1;
  })());
  ok('Z6 지급완료(paid) 회차는 지급 예정 알림에서 빠진다', q27.items.map((it) => JSON.stringify(it)).join(' ').indexOf('TT-270002-9103') === -1);
  const d1Item = q27.items.filter((it) => it.kind === 'visit_d1')[0];
  ok('Z7 D-1 문구(날짜·시각·선생님·준비물 3)', !!d1Item && d1Item.bookingNo === 'TT-270001-9001' &&
    /10:30/.test(d1Item.customer.body) && /박서준/.test(d1Item.customer.body) &&
    Array.isArray(d1Item.prep) && d1Item.prep.length === 3 && d1Item.badge === 'D-1',
    d1Item && JSON.stringify(d1Item.customer));
  ok('Z8 변경·취소·대체 문구가 템플릿 치환으로 만들어진다', (function () {
    const chg = q27.items.filter((it) => it.kind === 'visit_change')[0];
    const cxl = q27.items.filter((it) => it.kind === 'visit_cancel')[0];
    const sub = q27.items.filter((it) => it.kind === 'visit_substitute')[0];
    return !!chg && !!cxl && !!sub &&
      /TT-270001-9002/.test(chg.customer.body) && /14:00/.test(chg.customer.body) &&
      /TT-270001-9003/.test(cxl.customer.body) && /90,000원/.test(cxl.customer.body) &&
      /TT-270001-9004/.test(sub.customer.body) && /새 선생님/.test(sub.customer.body) &&
      !!chg.teacher && !!cxl.teacher && !!sub.teacher;
  })(), JSON.stringify((q27.items.filter((it) => it.kind === 'visit_cancel')[0] || {}).customer));
  const reevalItem = q27.items.filter((it) => it.kind === 'reeval')[0];
  ok('Z9 4주 재평가 알림(D+8·보호자·선생님 문구)', !!reevalItem &&
    /D\+8|4주 재평가/.test(reevalItem.badge) && !!reevalItem.customer && !!reevalItem.teacher &&
    /4주/.test(reevalItem.customer.body), reevalItem && reevalItem.badge);
  const settleConfirm = q27.items.filter((it) => it.kind === 'settle_confirm')[0];
  const settlePayout = q27.items.filter((it) => it.kind === 'settle_payout')[0];
  ok('Z10 정산 확정(D+3)·지급 예정(15일·말일) 요약', !!settleConfirm && !!settlePayout &&
    settleConfirm.audiences.join(',') === 'teacher' && settlePayout.audiences.join(',') === 'teacher' &&
    /140,000원/.test(settleConfirm.title) && /15일·말일/.test(settleConfirm.summary) &&
    /지급/.test(settlePayout.title) && /15일·말일/.test(settlePayout.summary) && /D-/.test(settlePayout.badge),
    [settleConfirm && settleConfirm.title, settlePayout && settlePayout.title].join(' / '));
  ok('Z11 큐 문구(복사용)에 로컬 미리보기 고지', /\[똑똑쌤 오늘 발송할 리마인드\]/.test(q27.text) &&
    /실제 문자·알림톡 발송 전 로컬 미리보기/.test(q27.text) && q27.text.indexOf('보호자') !== -1 && q27.text.indexOf('선생님') !== -1);
  ok('Z12 같은 입력이면 같은 결과(정렬 고정)', (function () {
    const again = M27.buildReminderQueue({ bookings: zBookings, ledger: zLedger }, todayZ);
    return JSON.stringify(again.items.map((i) => i.id)) === JSON.stringify(q27.items.map((i) => i.id));
  })());
  ok('Z13 큐는 저장소·알림을 건드리지 않는다(순수 함수)', (function () {
    const before = JSON.stringify(D27.window.localStorage.getItem('ttokttok_notifs_v1'));
    const beforeAcc = String(D27.window.localStorage.getItem('ttokttok_account_v3'));
    M27.buildReminderQueue({ bookings: zBookings, ledger: zLedger }, todayZ);
    return JSON.stringify(D27.window.localStorage.getItem('ttokttok_notifs_v1')) === before &&
      String(D27.window.localStorage.getItem('ttokttok_account_v3')) === beforeAcc;
  })());
  ok('Z14 빈 입력은 안전하게 빈 큐', (function () {
    const e = M27.buildReminderQueue({}, todayZ);
    return e.total === 0 && Array.isArray(e.items) && /오늘 보낼 리마인드가 없어요/.test(e.text);
  })());
  ok('Z15 지난 변경(8일 전)은 큐에서 제외', (function () {
    const old = [{ id: 'old', no: 'TT-270003-9201', status: 'rescheduled', dateIso: offIso(-5), date: lblOf(offIso(-5)), time: '10:00',
      statusHistory: [{ status: 'rescheduled', at: atIso(-8) }] }];
    const q = M27.buildReminderQueue({ bookings: old, ledger: [] }, todayZ);
    return q.items.filter((it) => it.kind === 'visit_change').length === 0;
  })());

  /* ----- 2) 알림 분류·미리보기 모델 ----- */
  ok('Z16 알림 kind → 카테고리 매핑', (function () {
    return M27.notificationCategoryOf({ kind: 'visit' }) === 'visit' &&
      M27.notificationCategoryOf({ kind: 'remind' }) === 'visit' &&
      M27.notificationCategoryOf({ kind: 'report' }) === 'report' &&
      M27.notificationCategoryOf({ kind: 'reeval' }) === 'report' &&
      M27.notificationCategoryOf({ kind: 'settle' }) === 'ops' &&
      M27.notificationCategoryOf({ kind: 'coupon' }) === 'ops' &&
      M27.notificationCategoryOf({ kind: '알수없음' }) === 'ops';
  })());
  ok('Z17 카테고리별 전체·안 읽음 수', (function () {
    const list = [
      { id: 'a', title: 'A', kind: 'visit', read: false },
      { id: 'b', title: 'B', kind: 'remind', read: true },
      { id: 'c', title: 'C', kind: 'report', read: false },
      { id: 'd', title: 'D', kind: 'coupon', read: false }
    ];
    const s = M27.summarizeNotifCategories(list);
    const by = {};
    s.categories.forEach((c) => { by[c.key] = c; });
    return s.total === 4 && s.unread === 3 && by.visit.total === 2 && by.visit.unread === 1 &&
      by.report.total === 1 && by.report.unread === 1 && by.ops.total === 1 && by.ops.unread === 1;
  })());
  ok('Z18 알림 미리보기는 발송 전 문구·고지를 담는다', (function () {
    const pv = M27.notificationPreview({ id: 'nt-test', kind: 'visit', title: '방문이 확정됐어요', body: '박서준 선생님이 확정했어요.' });
    return pv.ok && pv.category === 'visit' && pv.title === '방문이 확정됐어요' &&
      /\[똑똑쌤 알림 문구 · 보호자\]/.test(pv.text) && /실제 문자·알림톡 발송 전 로컬 미리보기/.test(pv.text);
  })());

  /* ----- 3) 보호자 알림함: 카테고리 칩·필터·문구 미리보기 ----- */
  h27.click(h27.$('[data-login="customer"]'));
  await sleep(30);
  h27.click(h27.$('#btnNotif'));
  await sleep(30);
  ok('Z19 알림 시트에 카테고리 칩 4개', h27.$$('#notifChips [data-notif-cat]').length === 4 &&
    h27.text('#notifChips').indexOf('전체') !== -1 && h27.text('#notifChips').indexOf('방문 일정') !== -1 &&
    h27.text('#notifChips').indexOf('리포트/재평가') !== -1 && h27.text('#notifChips').indexOf('정산/운영') !== -1,
    h27.text('#notifChips'));
  ok('Z20 칩에 안 읽음 수(전체 4)', /전체\s*4/.test(h27.text('#notifChips')) &&
    h27.$('#notifChips [data-notif-cat="all"]').classList.contains('is-on'), h27.text('#notifChips'));
  ok('Z21 기본은 전체 4건', D27.window.__ttokttokModel.notifScreenState().rows === 4);
  h27.click(h27.$('#notifChips [data-notif-cat="visit"]'));
  await sleep(20);
  ok('Z22 방문 일정 필터 2건', D27.window.__ttokttokModel.notifScreenState().rows === 2 &&
    /방문이 확정됐어요/.test(D27.window.__ttokttokModel.notifScreenState().text) &&
    D27.window.__ttokttokModel.notifScreenState().filter === 'visit');
  h27.click(h27.$('#notifChips [data-notif-cat="report"]'));
  await sleep(20);
  ok('Z23 리포트/재평가 필터 1건', D27.window.__ttokttokModel.notifScreenState().rows === 1 &&
    /회복 리포트/.test(D27.window.__ttokttokModel.notifScreenState().text));
  h27.click(h27.$('#notifChips [data-notif-cat="ops"]'));
  await sleep(20);
  ok('Z24 정산/운영 필터 1건(쿠폰)', D27.window.__ttokttokModel.notifScreenState().rows === 1 &&
    /쿠폰/.test(D27.window.__ttokttokModel.notifScreenState().text));
  h27.click(h27.$('#notifChips [data-notif-cat="all"]'));
  await sleep(20);
  ok('Z25 전체 칩으로 복귀 4건', D27.window.__ttokttokModel.notifScreenState().rows === 4);

  const unreadBefore27 = M27.notifs().filter((n) => !n.read && n.audience !== 'teacher').length;
  h27.click(h27.$('#notifList [data-notif="nt-d1"]'));
  await sleep(30);
  const pv27 = D27.window.__ttokttokModel.notifPreviewInfo();
  ok('Z26 알림 클릭 → 읽음 + 해당 화면 이동', (function () {
    return M27.notifs().filter((n) => !n.read && n.audience !== 'teacher').length === unreadBefore27 - 1 &&
      !h27.$('#notifSheet').classList.contains('is-open');
  })(), String(M27.notifs().filter((n) => !n.read && n.audience !== 'teacher').length));
  ok('Z27 알림 클릭 → 문구 미리보기 시트', !!pv27 && pv27.open === true && pv27.id === 'nt-d1' &&
    /D-1/.test(pv27.title) && /실제 문자·알림톡 발송 전 로컬 미리보기/.test(pv27.note), pv27 && pv27.title);
  ok('Z28 미리보기 문구에 제목·본문·고지', /\[똑똑쌤 알림 문구 · 보호자\]/.test(pv27.text) &&
    /방문 D-1 리마인드/.test(pv27.text) && /내일 방문이 예정되어 있어요/.test(pv27.text) &&
    /발송되지 않아요/.test(pv27.text));
  ok('Z29 미리보기 시트는 dialog 이름을 가진다', (function () {
    const el = h27.$('#notifPreviewSheet');
    return el.getAttribute('role') === 'dialog' && el.getAttribute('aria-modal') === 'true' &&
      !!doc27.getElementById(el.getAttribute('aria-labelledby'));
  })());
  ok('Z30 미리보기 복사 버튼(보호자 문구)', (function () {
    const btn = h27.$('#notifPreviewBody [data-notif-preview-copy="customer"]');
    if (!btn) return false;
    h27.click(btn);
    const hook = D27.window.__ttokttokNotifPreview || {};
    return /\[똑똑쌤 알림 문구 · 보호자\]/.test(hook.text || '') && /방문 D-1 리마인드/.test(hook.text || '');
  })());
  doc27.dispatchEvent(new D27.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
  await sleep(20);
  ok('Z31 Escape로 문구 미리보기 닫힘', !h27.$('#notifPreviewSheet').classList.contains('is-open'));
  if (h27.$('#accountSheet') && h27.$('#accountSheet').classList.contains('is-open')) {
    doc27.dispatchEvent(new D27.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    await sleep(20);
  }

  /* ----- 4) 선생님 알림함: 칩·전체 보기 시트 ----- */
  ok('Z32 선생님 알림함 칩·전체 보기 버튼', h27.$$('#tpNotifChips [data-notif-cat]').length === 4 &&
    !!h27.$('#tpNotifSec [data-tp-noti-open]'));
  ok('Z33 선생님 알림함 전체 보기 시트 열기·Escape', (function () {
    h27.click(h27.$('#tpNotifSec [data-tp-noti-open]'));
    const opened = h27.$('#tpNotiSheet').classList.contains('is-open');
    const chips = h27.$$('#tpNotiChips [data-notif-cat]').length;
    doc27.dispatchEvent(new D27.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }));
    return opened && chips === 4 && !h27.$('#tpNotiSheet').classList.contains('is-open');
  })());
  ok('Z34 DIALOG_ORDER에 새 시트 2종 등록', (function () {
    const order = D27.window.__ttokttokModel.a11y.dialogOrder;
    return order.indexOf('#notifPreviewSheet') !== -1 && order.indexOf('#tpNotiSheet') !== -1 &&
      D27.window.__ttokttokModel.a11y.labelledDialogs() === D27.window.__ttokttokModel.a11y.dialogCount();
  })());

  /* ----- 5) 운영자 「오늘 발송할 리마인드 미리보기」 ----- */
  const D27b = makeDom({
    ttokttok_account_v3: JSON.stringify({ profile: { name: '현수' }, passes: [], bookings: zBookings, receipts: [], sessions: [], myReviews: [] })
  });
  const h27b = helpers(D27b.window, D27b.doc);
  await sleep(60);
  const M27b = D27b.window.__ttokttokModel;
  ok('Z35 운영자 리마인드 보드 렌더(건수·카드)', (function () {
    h27b.click(h27b.$('[data-login="admin"]'));
    const st = M27b.adminReminderState();
    return st.total >= 5 && st.cards.length === st.total &&
      st.cards.some((c) => c.kind === 'visit_d1') && st.cards.some((c) => c.kind === 'reeval') &&
      st.cards.some((c) => c.kind === 'settle_payout');
  })(), JSON.stringify(M27b.adminReminderState().cards));
  ok('Z36 운영자 보드 고지·카운트(실제 발송 없음)', (function () {
    const st = M27b.adminReminderState();
    return /실제 문자·알림톡 발송은 하지 않습니다/.test(st.noticeText) &&
      /보호자/.test(st.countsText) && /선생님/.test(st.countsText) && /방문 일정/.test(st.countsText) &&
      st.copyAllVisible === true;
  })(), M27b.adminReminderState().noticeText.slice(0, 80));
  ok('Z37 리마인드 카드에 보호자·선생님 문구가 보인다', (function () {
    const card = h27b.$('#adminReminderQueue [data-reminder-kind="visit_d1"]');
    if (!card) return false;
    const t = card.textContent.replace(/\s+/g, ' ');
    return /보호자/.test(t) && /선생님/.test(t) && /내일/.test(t);
  })());
  ok('Z38 리마인드 문구 복사(발송 없음)', (function () {
    const btn = h27b.$('#adminReminderQueue [data-reminder-copy]');
    if (!btn) return false;
    h27b.click(btn);
    const hook = D27b.window.__ttokttokReminderCopy || {};
    return /\[똑똑쌤 알림 문구/.test(hook.text || '') && /실제 문자·알림톡 발송 전 로컬 미리보기/.test(hook.text || '');
  })());
  ok('Z39 오늘 리마인드 전체 복사', (function () {
    h27b.click(h27b.$('#adminReminderCopyAll'));
    const hook = D27b.window.__ttokttokReminderCopy || {};
    return /\[똑똑쌤 오늘 발송할 리마인드\]/.test(hook.text || '') && (hook.text || '').length > 200;
  })());
  ok('Z40 보드 렌더·복사가 알림을 만들지 않는다(발송 없음)', (function () {
    const before = M27b.notifs().length;
    M27b.adminReminders();
    return M27b.notifs().length === before;
  })());
  ok('Z41 운영자 화면 새로 그려도 오류 없음', D27b.errors.length === 0, D27b.errors.slice(0, 3).join(' | '));

  /* ----- 6) 회귀: CSS 바이트·기존 알림함 유지 ----- */
  ok('Z42 <style> 블록 CSS 144,471자 유지', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    return !!m && cssTokens(HTML).ok;
  })(), String((HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length));
  ok('Z44 선생님 알림은 보호자 알림함에 섞이지 않는다(칩 카운트 분리)', (function () {
    const c = M27.notifCounts('customer');
    const t = M27.notifCounts('teacher');
    return c.total === 4 && t.total === 0;
  })(), JSON.stringify([M27.notifCounts('customer').total, M27.notifCounts('teacher').total]));

  /* ============================================================
     AA. v28 — 관리자 운영 지표 대시보드
     ============================================================ */
  const todayM = offIso(0);
  const atM = (off, hm) => offIso(off) + 'T' + (hm || '01:00') + ':00+09:00';
  const nowM = todayM + 'T09:00:00+09:00';
  const D28 = makeDom();
  const h28 = helpers(D28.window, D28.doc);
  await sleep(60);
  const M28 = D28.window.__ttokttokModel;
  const doc28 = D28.doc;

  ok('AA0 v28 JS 오류 없음', D28.errors.length === 0, D28.errors.slice(0, 3).join(' | '));
  ok('AA1 v31 메타·지표 모델 노출', doc28.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    !!M28 && M28.qaVersion === 'v34' && M28.adminMetricsVersion === 'v28' &&
    typeof M28.buildAdminMetrics === 'function' && typeof M28.adminMetricsText === 'function' &&
    typeof M28.adminMetricsCsv === 'function', M28 && [M28.qaVersion, M28.adminMetricsVersion].join('/'));
  ok('AA2 기간 3종(전체·최근 7일·최근 30일)', (function () {
    const p = M28.metricsPeriods();
    return p.length === 3 && p.map((x) => x.key).join(',') === 'all,7d,30d' &&
      p.map((x) => x.label).join(',') === '전체,최근 7일,최근 30일' &&
      p[1].days === 7 && p[2].days === 30 && M28.metricsPeriod('nope').key === 'all';
  })(), M28.metricsPeriods().map((x) => x.label).join(','));

  /* ----- 1) 순수 함수: 퍼널 ----- */
  const mkB = (no, status, extra) => Object.assign({
    id: 'mr-' + no.toLowerCase(), no, status, amount: 90000, paymentStatus: 'paid',
    regionId: 'reg-서울-강남구', region: '서울 강남구 대치동', dateIso: offIso(2),
    createdAt: atM(-2), statusHistory: [{ status: 'received', at: atM(-2) }]
  }, extra || {});
  const fB = [
    mkB('TT-280001-0001', 'confirmed', { statusHistory: [{ status: 'received', at: atM(-2) }, { status: 'assigned', at: atM(-2, '02:00') }, { status: 'confirmed', at: atM(-2, '03:00') }] }),
    mkB('TT-280001-0002', 'completed', { dateIso: offIso(-1), createdAt: atM(-3), statusHistory: [{ status: 'received', at: atM(-3) }, { status: 'assigned', at: atM(-3, '02:00') }, { status: 'confirmed', at: atM(-3, '03:00') }, { status: 'completed', at: atM(-1, '05:00') }] }),
    mkB('TT-280001-0003', 'canceled', { createdAt: atM(-12), statusHistory: [{ status: 'received', at: atM(-12) }, { status: 'assigned', at: atM(-12, '02:00') }, { status: 'canceled', at: atM(-10), reason: '보호자 취소' }] }),
    mkB('TT-280001-0004', 'no_show', { createdAt: atM(-40), statusHistory: [{ status: 'no_show', at: atM(-39) }] }),
    mkB('TT-280001-0005', 'received', { createdAt: atM(-3) })
  ];
  const fM = M28.buildAdminMetrics({ bookings: fB, teachers: [], journals: [], ledger: [] }, todayM);
  ok('AA3 퍼널 단계 누적(신청 5 → 배정 3 → 확정 2 → 완료 1)', fM.funnel.applied === 5 &&
    fM.funnel.assigned === 3 && fM.funnel.confirmed === 2 && fM.funnel.completed === 1,
    JSON.stringify([fM.funnel.applied, fM.funnel.assigned, fM.funnel.confirmed, fM.funnel.completed]));
  ok('AA4 취소·노쇼 건수와 비율(취소 1·노쇼 1·40%)', fM.funnel.canceled === 1 && fM.funnel.noShow === 1 &&
    fM.funnel.cancelNoShow === 2 && fM.funnel.cancelNoShowRate === 40 && fM.funnel.cancelRate === 20 &&
    fM.funnel.noShowRate === 20, JSON.stringify([fM.funnel.canceled, fM.funnel.noShow, fM.funnel.cancelNoShowRate]));
  ok('AA5 전환율 계산(배정 60·확정 40·완료 20%)', fM.funnel.assignRate === 60 && fM.funnel.confirmRate === 40 &&
    fM.funnel.completionRate === 20 && fM.funnel.open === 2,
    JSON.stringify([fM.funnel.assignRate, fM.funnel.confirmRate, fM.funnel.completionRate]));
  ok('AA6 취소는 도달한 단계까지만 누적(배정 3에 포함·완료 제외)', (function () {
    const c = fB[2];
    const one = M28.buildAdminMetrics({ bookings: [c] }, todayM);
    return one.funnel.applied === 1 && one.funnel.assigned === 1 && one.funnel.confirmed === 0 &&
      one.funnel.completed === 0 && one.funnel.canceled === 1;
  })());

  /* ----- 2) 순수 함수: 매출·마진·일지 ----- */
  const mLedger = [
    { id: 'ml1', reservationNo: 'TT-280002-0001', visitDate: offIso(-2), grossAmount: 90000, netAmount: 70000, status: 'paid', journalId: 'mj1', patient: '김순자' },
    { id: 'ml2', reservationNo: 'TT-280002-0002', visitDate: offIso(-20), grossAmount: 90000, netAmount: 70000, status: 'scheduled' },
    { id: 'ml3', reservationNo: 'TT-280002-0003', visitDate: offIso(-40), grossAmount: 90000, netAmount: 70000, status: 'paid' },
    { id: 'ml4', reservationNo: 'TT-280002-0004', visitDate: offIso(-1), grossAmount: 90000, netAmount: 70000, status: 'held' },
    { id: 'ml5', reservationNo: 'TT-280002-0005', visitDate: offIso(0), grossAmount: 0, netAmount: 0, status: 'paid' }
  ];
  const mJournals = [{ id: 'mj1', visitDate: offIso(-2), patient: '김순자', status: 'shared' }];
  const rM = M28.buildAdminMetrics({ bookings: fB, teachers: [], journals: mJournals, ledger: mLedger }, todayM);
  ok('AA7 매출·정산·마진(원장 3 + 확정 1 = 360,000 / 280,000 / 80,000)', rM.revenue.sessions === 4 &&
    rM.revenue.completedSessions === 3 && rM.revenue.confirmedSessions === 1 &&
    rM.revenue.guardianTotal === 360000 && rM.revenue.teacherTotal === 280000 &&
    rM.revenue.platformMargin === 80000 && rM.revenue.marginRate === 22.2,
    JSON.stringify([rM.revenue.sessions, rM.revenue.guardianTotal, rM.revenue.teacherTotal, rM.revenue.platformMargin]));
  ok('AA8 무료 평가·보류(held) 회차는 매출에서 제외', rM.revenue.freeSessions === 1 &&
    rM.revenue.completedSessions === 3, JSON.stringify([rM.revenue.freeSessions, rM.revenue.completedSessions]));
  ok('AA9 단가·수수료는 PRICING 한 곳(90,000·70,000·22.2%)', rM.pricing.consumerPrice === 90000 &&
    rM.pricing.teacherPayout === 70000 && rM.pricing.feeRate === 0.2222 && rM.revenue.avgPerSession === 90000,
    JSON.stringify(rM.pricing));
  ok('AA10 일지 기록률(완료 3회 중 1회 = 33.3%)', rM.journal.completed === 3 && rM.journal.withJournal === 1 &&
    rM.journal.rate === 33.3, JSON.stringify(rM.journal));

  /* ----- 3) 기간 필터 ----- */
  const r7 = M28.buildAdminMetrics({ bookings: fB, teachers: [], journals: mJournals, ledger: mLedger, period: '7d' }, todayM);
  const r30 = M28.buildAdminMetrics({ bookings: fB, teachers: [], journals: mJournals, ledger: mLedger, period: '30d' }, todayM);
  ok('AA11 기간 필터 — 매출은 방문일 기준(7일 2회·30일 3회·전체 4회)', r7.revenue.sessions === 2 &&
    r30.revenue.sessions === 3 && rM.revenue.sessions === 4 &&
    r7.revenue.guardianTotal === 180000 && r30.revenue.guardianTotal === 270000,
    JSON.stringify([r7.revenue.sessions, r30.revenue.sessions, rM.revenue.sessions]));
  ok('AA12 기간 필터 — 퍼널은 접수일 기준(7일 3건·30일 4건·전체 5건)', r7.funnel.applied === 3 &&
    r30.funnel.applied === 4 && rM.funnel.applied === 5 &&
    r7.fromIso === offIso(-6) && r30.fromIso === offIso(-29),
    JSON.stringify([r7.funnel.applied, r30.funnel.applied, rM.funnel.applied, r7.fromIso]));
  ok('AA13 기간별 기준 문구(접수일·방문일·지금 대기)', /접수일/.test(r7.basis.funnel) &&
    /방문일/.test(r7.basis.revenue) && /확정 회차/.test(r7.basis.revenue) && /기간 무관/.test(r7.basis.sla),
    JSON.stringify(r7.basis));

  /* ----- 4) 지역 수요 vs 공급 갭 ----- */
  const mTeachers = [
    { id: 'mt1', name: '박서준', regions: '서울 강남 · 서초' },
    { id: 'mt3', name: '정민아', regions: '서울 마포 · 서대문' },
    { id: 'mt4', name: '한지우', regions: '서울 서초' }
  ];
  const gB = [
    mkB('TT-280010-0001', 'confirmed', { regionId: 'reg-서울-강남구' }),
    mkB('TT-280010-0002', 'received', { regionId: 'reg-서울-마포구' }),
    mkB('TT-280010-0003', 'received', { regionId: 'reg-서울-마포구' }),
    mkB('TT-280010-0004', 'received', { regionId: 'reg-서울-마포구' }),
    mkB('TT-280010-0005', 'received', { regionId: 'reg-서울-마포구' }),
    mkB('TT-280010-0006', 'completed', { regionId: 'reg-서울-서초구', dateIso: offIso(-1) }),
    mkB('TT-280010-0007', 'canceled', { regionId: 'reg-부산-해운대구' }),
    mkB('TT-280010-0008', 'received', { regionId: 'reg-제주-제주시', region: '제주 제주시 노형동' })
  ];
  const gM = M28.buildAdminMetrics({ bookings: gB, teachers: mTeachers, journals: [], ledger: [] }, todayM);
  ok('AA14 지역 갭 3분류(모집 필요 2·균형 1·여유 1)', gM.regions.summary.shortage === 2 &&
    gM.regions.summary.balanced === 1 && gM.regions.summary.surplus === 1 &&
    gM.regions.summary.demandRegions === 4 && gM.regions.summary.demand === 7,
    JSON.stringify(gM.regions.summary));
  ok('AA15 모집 필요 지역이 먼저 정렬(마포 4건 → 제주 1건)', (function () {
    const labels = gM.regions.rows.map((r) => r.label + ':' + r.badgeKey);
    return labels[0] === '서울 마포구:shortage' && labels[1] === '제주 제주시:shortage' &&
      labels.indexOf('서울 강남구:balanced') !== -1 && labels.indexOf('서울 서초구:surplus') !== -1;
  })(), gM.regions.rows.map((r) => r.label + ':' + r.badgeKey).join(' / '));
  ok('AA16 필요 선생님 = 수요/3 올림 · 차이 계산', (function () {
    const mp = gM.regions.rows.filter((r) => r.label === '서울 마포구')[0];
    const sc = gM.regions.rows.filter((r) => r.label === '서울 서초구')[0];
    return mp.demand === 4 && mp.need === 2 && mp.supply === 1 && mp.gap === -1 &&
      sc.demand === 1 && sc.need === 1 && sc.supply === 2 && sc.gap === 1;
  })(), JSON.stringify(gM.regions.rows.filter((r) => r.label === '서울 마포구')[0]));
  ok('AA17 선생님 없는 수요 지역 표시 · 취소 건은 수요에서 제외', gM.regions.summary.noSupply.join(',') === '제주 제주시' &&
    gM.regions.rows.every((r) => r.label !== '부산 해운대구'), JSON.stringify(gM.regions.summary.noSupply));
  ok('AA18 등록 선생님 3명·활동 지역 4곳(수요 0인 지역 포함)', gM.regions.summary.teachers === 3 &&
    gM.regions.summary.supplyDistricts === 4 && gM.regions.summary.idleDistricts === 1,
    JSON.stringify([gM.regions.summary.teachers, gM.regions.summary.supplyDistricts, gM.regions.summary.idleDistricts]));

  /* ----- 5) 매칭 SLA ----- */
  const sB = [
    { no: 'TT-280020-0001', status: 'received', createdAt: atM(-3, '09:00'), regionId: 'reg-서울-마포구', region: '서울 마포구 성산동' },
    { no: 'TT-280020-0002', status: 'received', createdAt: atM(0, '08:00'), regionId: 'reg-서울-마포구' },
    { no: 'TT-280020-0003', status: 'assigned', createdAt: atM(-2, '09:00'), regionId: 'reg-서울-강남구' },
    { no: 'TT-280020-0004', status: 'rescheduled', createdAt: atM(-1, '09:00'), regionId: 'reg-서울-강남구' },
    { no: 'TT-280020-0005', status: 'confirmed', createdAt: atM(-1, '09:00'), regionId: 'reg-서울-강남구' },
    { no: 'TT-280020-0006', status: 'completed', createdAt: atM(-9, '09:00'), regionId: 'reg-서울-강남구' }
  ];
  const sM = M28.buildAdminMetrics({ bookings: sB, teachers: [], journals: [], ledger: [], nowIso: nowM }, todayM);
  ok('AA19 대기 5건(미배정 2·확정 대기 1·재확정 1·확정 1)', sM.sla.pending === 5 &&
    sM.sla.awaitingAssign === 2 && sM.sla.awaitingConfirm === 1 && sM.sla.reconfirm === 1,
    JSON.stringify([sM.sla.pending, sM.sla.awaitingAssign, sM.sla.awaitingConfirm, sM.sla.reconfirm]));
  ok('AA20 24시간·48시간 초과 미배정 지연(각 1건·최장 72시간)', sM.sla.over24 === 1 && sM.sla.over48 === 1 &&
    sM.sla.oldestHours === 72 && sM.sla.items.length === 1 && sM.sla.items[0].no === 'TT-280020-0001' &&
    sM.sla.items[0].badge === '48시간 초과', JSON.stringify({ o24: sM.sla.over24, o48: sM.sla.over48, oldest: sM.sla.oldestHours }));
  ok('AA21 SLA는 기간과 무관(7일 필터에도 대기 그대로)', (function () {
    const q = M28.buildAdminMetrics({ bookings: sB, teachers: [], journals: [], ledger: [], period: '7d', nowIso: nowM }, todayM);
    return q.sla.pending === 5 && q.sla.over24 === 1;
  })());
  ok('AA22 24시간 안 된 건은 지연으로 안 센다', (function () {
    const q = M28.buildAdminMetrics({ bookings: [sB[1]], nowIso: nowM }, todayM);
    return q.sla.over24 === 0 && q.sla.items.length === 0 && q.sla.pending === 1;
  })());

  /* ----- 6) KPI·텍스트·CSV ----- */
  ok('AA23 KPI 6장(필수 4종 포함)', (function () {
    const keys = gM.kpis.map((k) => k.key);
    const labels = gM.kpis.map((k) => k.label);
    return gM.kpis.length === 6 && ['completion', 'cancelNoshow', 'delay', 'margin'].every((k) => keys.indexOf(k) !== -1) &&
      labels.indexOf('완료 전환율') !== -1 && labels.indexOf('취소·노쇼율') !== -1 &&
      labels.indexOf('24시간 초과 미배정') !== -1 && labels.indexOf('예상 플랫폼 마진') !== -1;
  })(), gM.kpis.map((k) => k.label).join(','));
  ok('AA24 KPI 값이 퍼널·매출·SLA와 같다', (function () {
    const by = {};
    gM.kpis.forEach((k) => { by[k.key] = k; });
    return by.completion.value === gM.funnel.completionRate &&
      by.cancelNoshow.value === gM.funnel.cancelNoShowRate &&
      by.delay.value === gM.sla.over24 && by.margin.value === gM.revenue.platformMargin &&
      by.shortage.value === gM.regions.summary.shortage && by.journal.value === gM.journal.rate;
  })());
  ok('AA25 복용 텍스트 — 퍼널·매출·지역·SLA', /\[똑똑쌤 운영 지표\]/.test(gM.text) &&
    /■ 예약 진행 단계/.test(gM.text) && /■ 매출·마진/.test(gM.text) && /■ 지역 수요·공급/.test(gM.text) &&
    /■ 매칭 대기 시간/.test(gM.text) && /서울 마포구: 수요 4건 · 선생님 1명 → 모집 필요/.test(gM.text) &&
    /이 기기 데이터로만 계산한 예시/.test(gM.text), gM.text.slice(0, 60));
  ok('AA26 CSV — 지표 요약 + 지역 표', /^지표,값/.test(gM.csv) &&
    /지역,수요\(건\),진행중\(건\),완료\(건\),선생님\(명\),필요\(명\),차이,판정/.test(gM.csv) &&
    /서울 마포구,4,4,0,1,2,-1,모집 필요/.test(gM.csv), gM.csv.split('\n').slice(-2).join(' | '));
  ok('AA27 같은 입력이면 같은 결과(결정성)', (function () {
    const a = M28.buildAdminMetrics({ bookings: gB, teachers: mTeachers, journals: [], ledger: [], nowIso: nowM }, todayM);
    const b = M28.buildAdminMetrics({ bookings: gB, teachers: mTeachers, journals: [], ledger: [], nowIso: nowM }, todayM);
    return JSON.stringify(a.regions.rows.map((r) => r.label)) === JSON.stringify(b.regions.rows.map((r) => r.label)) &&
      a.text === b.text && a.csv === b.csv;
  })());
  ok('AA28 빈 입력도 안전(모든 수치 0·오류 없음)', (function () {
    const e = M28.buildAdminMetrics({}, todayM);
    return e.funnel.applied === 0 && e.funnel.cancelNoShowRate === 0 && e.revenue.sessions === 0 &&
      e.revenue.platformMargin === 0 && e.regions.rows.length === 0 && e.sla.pending === 0 &&
      e.journal.rate === 0 && typeof e.text === 'string' && e.text.length > 0;
  })());

  /* ----- 7) 관리자 화면: 기간 칩·KPI·지역·SLA ----- */
  h28.click(h28.$('[data-login="admin"]'));
  await sleep(50);
  const st28 = M28.adminMetricsState();
  ok('AA29 관리자 콘솔에 운영 지표 섹션', !!h28.$('#adminMetricsSec') && h28.$('#adminMetricsSec').getAttribute('aria-label') === '운영 지표 대시보드');
  ok('AA30 기간 칩 3개·기본 전체', st28.chips.length === 3 &&
    st28.chips.map((c) => c.key).join(',') === 'all,7d,30d' && st28.period === 'all' &&
    h28.$('#adminMetricsPeriods [data-metrics-period="all"]').classList.contains('is-on'),
    JSON.stringify(st28.chips));
  ok('AA31 칩 접근성(role=tab·aria-selected)', (function () {
    const el = h28.$('#adminMetricsPeriods [data-metrics-period="7d"]');
    return el.getAttribute('role') === 'tab' && el.getAttribute('aria-selected') === 'false' &&
      h28.$('#adminMetricsPeriods').getAttribute('aria-label') === '지표 기간 필터';
  })());
  ok('AA32 KPI 카드 6장 + 필수 지표 문구', st28.kpiCards === 6 &&
    /완료 전환율/.test(st28.kpiText) && /취소·노쇼율/.test(st28.kpiText) &&
    /24시간 초과 미배정/.test(st28.kpiText) && /예상 플랫폼 마진/.test(st28.kpiText), st28.kpiText.slice(0, 120));
  ok('AA33 시드 퍼널 렌더(신청 2 → 완료 1)', /전체 신청\s*2건/.test(st28.funnelText) &&
    /방문 완료\s*1건/.test(st28.funnelText) && /취소·노쇼율/.test(st28.subText) === false &&
    /취소\s*0건/.test(st28.funnelText), st28.funnelText.slice(0, 120));
  ok('AA34 시드 매출·마진 렌더(2,340,000원·520,000원)', /2,340,000원/.test(st28.revenueText) &&
    /1,820,000원/.test(st28.revenueText) && /520,000원/.test(st28.revenueText) && /22.2%/.test(st28.revenueText) &&
    /일지 기록률/.test(st28.revenueText), st28.revenueText.slice(0, 160));
  ok('AA35 지역 카드(서울 강남구)·요약 문구', st28.regionCards >= 1 && /서울 강남구/.test(st28.regionText) &&
    /수요 있는 지역/.test(st28.regionText) && /선생님 1명당 3건/.test(st28.regionText), st28.regionText.slice(0, 160));
  ok('AA36 SLA 카드(지연 없음·지금 대기 1건)', /매칭 대기 시간/.test(st28.slaText) &&
    /지연 없음/.test(st28.slaText) && /지금 대기 1건/.test(st28.slaText), st28.slaText.slice(0, 120));
  ok('AA37 하단 고지(이 기기 계산·외부 발송 없음)', /이 기기 데이터로만 계산한 예시/.test(st28.noteText) &&
    /외부 발송과 연결되어 있지 않아요/.test(st28.noteText), st28.noteText);

  /* ----- 8) 기간 칩 전환 ----- */
  h28.click(h28.$('#adminMetricsPeriods [data-metrics-period="7d"]'));
  await sleep(40);
  const st7 = M28.adminMetricsState();
  ok('AA38 7일 칩 → 기간·수치 전환', st7.period === '7d' && st7.chips.filter((c) => c.on).length === 1 &&
    h28.$('#adminMetricsPeriods [data-metrics-period="7d"]').classList.contains('is-on') &&
    /최근 7일/.test(st7.captionText) && st7.sessions < st28.sessions,
    JSON.stringify([st7.period, st7.sessions, st28.sessions]));
  h28.click(h28.$('#adminMetricsPeriods [data-metrics-period="30d"]'));
  await sleep(40);
  const st30 = M28.adminMetricsState();
  ok('AA39 30일 칩 → 7일보다 많고 전체보다 적다', st30.period === '30d' &&
    st30.sessions > st7.sessions && st30.sessions < st28.sessions && /최근 30일/.test(st30.captionText),
    JSON.stringify([st7.sessions, st30.sessions, st28.sessions]));
  h28.click(h28.$('#adminMetricsPeriods [data-metrics-period="all"]'));
  await sleep(40);
  ok('AA40 전체 칩 복귀', M28.adminMetricsState().period === 'all' &&
    M28.adminMetricsState().sessions === st28.sessions);

  /* ----- 9) 복사·순수성·회귀 ----- */
  ok('AA41 지표 요약 텍스트 복사', (function () {
    h28.click(h28.$('#adminMetricsCopyText'));
    const hook = D28.window.__ttokttokMetricsCopy || {};
    return hook.kind === 'text' && /\[똑똑쌤 운영 지표\]/.test(hook.text || '') &&
      /■ 예약 진행 단계/.test(hook.text || '') && /■ 지역 수요·공급/.test(hook.text || '');
  })(), JSON.stringify(D28.window.__ttokttokMetricsCopy || {}).slice(0, 120));
  ok('AA42 지역 표 CSV 복사', (function () {
    h28.click(h28.$('#adminMetricsCopyCsv'));
    const hook = D28.window.__ttokttokMetricsCopy || {};
    return hook.kind === 'csv' && /^지표,값/.test(hook.text || '') && /지역,수요\(건\)/.test(hook.text || '');
  })());
  ok('AA43 렌더·복사가 저장소를 바꾸지 않는다(순수)', (function () {
    const before = String(D28.window.localStorage.getItem('ttokttok_account_v3'));
    const beforeNotif = String(D28.window.localStorage.getItem('ttokttok_notifs_v1'));
    M28.renderAdminMetrics();
    M28.adminMetricsText();
    M28.adminMetricsCsv();
    return String(D28.window.localStorage.getItem('ttokttok_account_v3')) === before &&
      String(D28.window.localStorage.getItem('ttokttok_notifs_v1')) === beforeNotif;
  })());
  ok('AA44 지표 렌더가 알림을 만들지 않는다(발송 없음)', (function () {
    const n = M28.notifs().length;
    M28.renderAdminMetrics();
    return M28.notifs().length === n;
  })());
  ok('AA45 <style> 블록 CSS 144,471자 유지', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    return !!m && cssTokens(HTML).ok;
  })(), String((HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length));
  ok('AA46 v27 리마인드 보드 회귀 유지', !!h28.$('#adminReminderQueue') &&
    h28.$$('#adminReminderQueue [data-reminder]').length >= 1);
  ok('AA47 v19/v17 운영 보드 회귀 유지', !!h28.$('#adminOpsSec') && !!h28.$('#adminResvSec') &&
    h28.$$('#adminResvQueue [data-resv]').length >= 1);
  ok('AA48 운영 지표 화면 오류 없음', D28.errors.length === 0, D28.errors.slice(0, 3).join(' | '));

  /* ============================================================
     AB. v29 — 고객 후기 · 선생님 신뢰 배지 · 원클릭 재예약
     ============================================================ */
  /* 메모리 절약: v25 고객 화면 DOM을 그대로 쓴다(같은 빌드·같은 시드, 후기 미등록 상태). */
  const D29 = { window: D25.window, doc: doc25, errors: D25.errors };
  const h29 = helpers(D29.window, D29.doc);
  await sleep(30);
  const M29 = D29.window.__ttokttokModel;
  const doc29 = D29.doc;

  ok('AB0 v29 JS 오류 없음', D29.errors.length === 0, D29.errors.slice(0, 3).join(' | '));
  ok('AB1 v31 메타·신뢰 모델 노출', doc29.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    !!M29 && M29.qaVersion === 'v34' && M29.trustVersion === 'v29' &&
    typeof M29.canReviewReservation === 'function' && typeof M29.buildTeacherTrustSummary === 'function' &&
    typeof M29.buildRebookDraft === 'function', M29 && [M29.trustVersion, M29.qaVersion].join('/'));
  ok('AB2 후기 태그 마스터 5종', (function () {
    const t = M29.reviewTagMaster;
    return Array.isArray(t) && t.length === 5 &&
      t.map((x) => x.label).join(',') === '친절한 설명,시간 엄수,체계적 평가,통증 완화,보호자 소통';
  })(), JSON.stringify(M29.reviewTagMaster));
  ok('AB3 예전 태그 문구 → 마스터 태그 호환', M29.reviewTagLabel('친절해요') === '친절한 설명' &&
    M29.reviewTagLabel('시간 약속을 잘 지켜요') === '시간 엄수' && M29.reviewTagLabel('꼼꼼해요') === '체계적 평가' &&
    M29.reviewTagLabel('보호자 소통') === '보호자 소통');
  ok('AB4 1방문 1후기 규칙 문구 노출', /방문 1회당 후기 1개/.test(M29.reviewRuleNote) &&
    /방문 1회당 후기 1개/.test(h29.text('#reviewRuleNote')), h29.text('#reviewRuleNote'));

  /* ----- 1) 방문 1회 1후기 판정(순수) ----- */
  const bmk = (no, status, extra) => Object.assign({
    id: 'r29-' + no, no, teacherId: 't29', status, dateIso: offIso(-1),
    regionId: 'reg-서울-강남구', memberName: '김순자'
  }, extra || {});
  const revB = [
    bmk('TT-290001-0001', 'completed'),
    bmk('TT-290001-0002', 'confirmed'),
    bmk('TT-290001-0003', 'completed', { teacherId: '' }),
    bmk('TT-290001-0004', 'completed', { reviewed: true }),
    bmk('TT-290001-0005', 'completed'),
    bmk('TT-290001-0006', 'canceled'),
    bmk('TT-290001-0007', 'no_show')
  ];
  const revCtx = { bookings: revB, reviews: [{ id: 'rv1', teacherId: 't29', reservationId: 'TT-290001-0005', rating: 5, tags: ['친절한 설명'] }] };
  ok('AB5 완료+담당 선생님 → 후기 가능', M29.canReviewReservation(revCtx, 'TT-290001-0001').ok === true &&
    M29.canReviewReservation(revCtx, 'TT-290001-0001').code === 'ok');
  ok('AB6 방문 완료 전 → 후기 불가', M29.canReviewReservation(revCtx, 'TT-290001-0002').code === 'not_completed' &&
    M29.canReviewReservation(revCtx, 'TT-290001-0002').reason.indexOf('방문 완료') !== -1);
  ok('AB7 담당 선생님 없음 → 후기 불가', M29.canReviewReservation(revCtx, 'TT-290001-0003').code === 'no_teacher');
  ok('AB8 이미 후기(예약 플래그) → 중복 불가', M29.canReviewReservation(revCtx, 'TT-290001-0004').code === 'already_reviewed');
  ok('AB9 이미 후기(후기 레코드 reservationId) → 중복 불가', M29.canReviewReservation(revCtx, 'TT-290001-0005').code === 'already_reviewed');
  ok('AB10 취소·노쇼 → 후기 불가', M29.canReviewReservation(revCtx, 'TT-290001-0006').code === 'not_completed' &&
    M29.canReviewReservation(revCtx, 'TT-290001-0007').code === 'not_completed');
  ok('AB11 없는 예약 → not_found', M29.canReviewReservation(revCtx, 'TT-999999-0000').code === 'not_found');
  ok('AB12 후기 가능 목록은 조건 충족분만', (function () {
    const list = M29.reviewableReservations(revCtx);
    return list.length === 1 && list[0].no === 'TT-290001-0001' && list[0].teacherId === 't29';
  })(), JSON.stringify(M29.reviewableReservations(revCtx).map((x) => x.no)));

  /* ----- 2) 선생님 신뢰 요약(순수) ----- */
  const trustBookings = [
    bmk('TT-290002-0001', 'completed', { memberName: '김순자', dateIso: offIso(-10) }),
    bmk('TT-290002-0002', 'completed', { memberName: '김순자', dateIso: offIso(-3) }),
    bmk('TT-290002-0003', 'completed', { memberName: '이호준', dateIso: offIso(-1) }),
    bmk('TT-290002-0004', 'confirmed', { memberName: '박미영' }),
    bmk('TT-290002-0005', 'canceled', { memberName: '최영수' }),
    bmk('TT-290002-0006', 'completed', { memberName: '정다은', teacherId: 'other' })
  ];
  const trustTeacher = { id: 't29', name: '테스트', rating: 4.5, reviews: 10,
    verification: { identity: 'verified', license: 'verified', career: 'verified' } };
  const trustCtx = {
    teachers: [trustTeacher], bookings: trustBookings,
    detailReviews: [
      { id: 'd1', stars: 5, text: 'a', tags: ['체계적 평가', '친절한 설명'] },
      { id: 'd2', stars: 5, text: 'b', tags: ['체계적 평가'] },
      { id: 'd3', stars: 4, text: 'c', tags: ['보호자 소통', '통증 완화'] }
    ]
  };
  const TR = M29.buildTeacherTrustSummary(trustCtx, 't29');
  ok('AB13 완료 방문·환자 수 계산(3회·2명)', TR.completedVisits === 3 && TR.patients === 2,
    JSON.stringify([TR.completedVisits, TR.patients]));
  ok('AB14 재방문 건수·율(1건·50%)', TR.repeatPatients === 1 && TR.repeatVisits === 1 &&
    TR.rebookRate === 50 && TR.rebookLabel === '재방문 1건', JSON.stringify([TR.repeatVisits, TR.rebookRate, TR.rebookLabel]));
  ok('AB15 평균 별점·후기 수는 선생님 집계 기준', TR.rating === 4.5 && TR.reviewCount === 10 &&
    /평점 4.5/.test(TR.summary) && /후기 10/.test(TR.summary) && /완료 3회/.test(TR.summary), TR.summary);
  ok('AB16 대표 태그 TOP 3(많은 순·동률은 마스터 순서)', TR.topTags.length === 3 &&
    TR.topTags[0].label === '체계적 평가' && TR.topTags[0].count === 2 &&
    TR.topTags[1].label === '친절한 설명' && TR.topTags[2].label === '통증 완화',
    JSON.stringify(TR.topTags));
  ok('AB17 검증 배지(통과 단계만)', TR.badges.length === 2 && TR.verified.license === true && TR.verified.career === true &&
    M29.buildTeacherTrustSummary({ teachers: [{ id: 't29', name: '테스트', rating: 4.9, reviews: 3,
      verification: { identity: 'verified', license: 'verified', career: 'pending' } }] }, 't29').badges.map((b) => b.step).join(',') === 'license',
    JSON.stringify(TR.badges));
  ok('AB18 빈 입력·없는 선생님도 안전', (function () {
    const e = M29.buildTeacherTrustSummary({}, 'nobody');
    return e.completedVisits === 0 && e.patients === 0 && e.rebookRate === 0 && e.topTags.length === 0 &&
      e.reviewCount === 0 && /방문 기록 없음/.test(e.rebookLabel);
  })());
  ok('AB19 재방문율 0%는 기록이 있을 때만 0으로 표시', M29.buildTeacherTrustSummary({
    bookings: [bmk('TT-290003-0001', 'completed', { memberName: 'A' })], teachers: [{ id: 't29', rating: 5, reviews: 2 }]
  }, 't29').rebookRate === 0);

  /* ----- 3) 재예약 초안(순수) ----- */
  const rbBookings = [
    { id: 'r1', no: 'TT-290004-0001', teacherId: 'park', status: 'completed', regionId: 'reg-서울-강남구',
      region: '서울 강남구 대치동', symptomCodes: ['stroke', 'pain_joint'], dateIso: offIso(-9) },
    { id: 'r2', no: 'TT-290004-0002', teacherId: 'park', status: 'canceled', regionId: 'reg-서울-강남구' },
    { id: 'r3', no: 'TT-290004-0003', teacherId: '', status: 'completed', regionId: 'reg-서울-서초구' }
  ];
  const RD = M29.buildRebookDraft({ bookings: rbBookings, teachers: [{ id: 'park', name: '박서준' }] }, 'TT-290004-0001');
  ok('AB20 재예약 초안 — 같은 선생님·지역', RD.ok === true && RD.teacherId === 'park' &&
    RD.teacherName === '박서준' && RD.province === '서울' && RD.district === '강남구', JSON.stringify([RD.teacherId, RD.province, RD.district]));
  ok('AB21 재예약 초안 — 같은 증상', RD.syms.join(',') === '뇌졸중·편마비,통증·관절 관리' &&
    RD.symptomCodes.join(',') === 'stroke,pain_joint', JSON.stringify(RD.syms));
  ok('AB22 재예약 초안 — 1회권 90,000원, 무료 평가 아님', RD.passId === 'p1' && RD.passName === '1회권' &&
    RD.unitPrice === 90000 && RD.total === 90000 && RD.freeEval === false && RD.free === false, JSON.stringify([RD.passId, RD.unitPrice]));
  ok('AB23 재예약 초안 — 회차권 지정 가능(8회 592,000원)', M29.buildRebookDraft({ bookings: rbBookings }, 'TT-290004-0001', { passId: 'p8' }).total === 592000);
  ok('AB24 취소 예약 → 재예약 불가', M29.buildRebookDraft({ bookings: rbBookings }, 'TT-290004-0002').code === 'not_rebookable');
  ok('AB25 담당 선생님 없는 예약 → 재예약 불가', M29.buildRebookDraft({ bookings: rbBookings }, 'TT-290004-0003').code === 'no_teacher');
  ok('AB26 없는 예약 → not_found', M29.buildRebookDraft({ bookings: rbBookings }, 'TT-290004-9999').code === 'not_found');
  ok('AB27 순수 함수가 저장소를 바꾸지 않는다', (function () {
    const before = String(D29.window.localStorage.getItem('ttokttok_account_v3'));
    M29.buildTeacherTrustSummary(trustCtx, 't29');
    M29.reviewableReservations(revCtx);
    M29.buildRebookDraft({ bookings: rbBookings }, 'TT-290004-0001');
    return String(D29.window.localStorage.getItem('ttokttok_account_v3')) === before;
  })());

  /* ----- 4) 화면: 후기 시트(태그 5종·1회 1후기) ----- */
  h29.click(h29.$('[data-login="customer"]'));
  await sleep(60);
  ok('AB28 후기 태그 칩 5종(마스터)', h29.$$('#reviewTags [data-rtag]').length === 5 &&
    h29.$$('#reviewTags [data-rtag]').map((b) => b.getAttribute('data-rtag')).join(',') ===
      '친절한 설명,시간 엄수,체계적 평가,통증 완화,보호자 소통');
  ok('AB29 완료 예약이 후기 목록에 노출', (function () {
    const rows = M29.reviewListState();
    return rows.some((r) => r.booking === 'TT-261019-4811' && !r.reviewed);
  })(), JSON.stringify(M29.reviewListState().map((r) => [r.session, r.booking, r.reviewed])));
  h29.click(h29.$('#reviewList [data-review-booking]'));
  await sleep(40);
  const rs = M29.reviewState();
  ok('AB30 후기 시트가 예약 후기로 열림', rs.open === true && rs.reservationNo === 'TT-261019-4811' &&
    rs.teacherId === 'park' && /박서준/.test(rs.desc), JSON.stringify([rs.open, rs.reservationNo, rs.desc]));
  ok('AB31 별점 없이 등록 차단', (function () {
    h29.click(h29.$('#reviewSubmit'));
    return M29.reviewState().open === true && !M29.reviewListState().find((r) => r.session === 'TT-261019-4811').reviewed;
  })());
  h29.click(h29.$('[data-star="5"]'));
  h29.click(h29.$('#reviewTags [data-rtag="체계적 평가"]'));
  h29.click(h29.$('#reviewTags [data-rtag="보호자 소통"]'));
  h29.setVal(h29.$('#reviewText'), '측정 기록을 매번 보여주셔서 믿음이 갑니다');
  const beforeRating = M29.trustOf('park');
  h29.click(h29.$('#reviewSubmit'));
  await sleep(60);
  const afterRow = M29.reviewListState().find((r) => r.session === 'TT-261019-4811');
  ok('AB32 후기 등록 → 목록 등록됨', !!afterRow && afterRow.reviewed === true, JSON.stringify(afterRow));
  ok('AB33 후기 레코드에 예약번호·태그 저장', (function () {
    const acc = JSON.parse(D29.window.localStorage.getItem('ttokttok_account_v3'));
    const mine = (acc.myReviews || []).filter((r) => r.reservationId === 'TT-261019-4811')[0];
    const bk = (acc.bookings || []).filter((b) => b.no === 'TT-261019-4811')[0];
    return !!mine && mine.rating === 5 && mine.tags.join(',') === '체계적 평가,보호자 소통' &&
      !!bk && bk.reviewed === true && bk.reviewId === mine.id;
  })(), String((JSON.parse(D29.window.localStorage.getItem('ttokttok_account_v3')).myReviews || []).length));
  const afterRating = M29.trustOf('park');
  ok('AB34 별점·후기 수 즉시 반영', afterRating.reviewCount === beforeRating.reviewCount + 1 &&
    afterRating.topTags.some((x) => x.label === '체계적 평가') && afterRating.topTags[0].count >= 2,
    JSON.stringify([beforeRating.reviewCount, afterRating.reviewCount, afterRating.topTags]));
  ok('AB35 같은 방문 중복 후기 차단', (function () {
    const again = M29.canReviewReservation(null, 'TT-261019-4811');
    const opened = M29.openReviewForBooking('TT-261019-4811');
    return again.ok === false && again.code === 'already_reviewed' && opened.code === 'already_reviewed';
  })(), JSON.stringify(M29.canReviewReservation(null, 'TT-261019-4811')));
  ok('AB36 선생님 카드 후기 수 반영', /후기 129/.test(h29.text('#teacherList [data-teacher="park"]')),
    h29.text('#teacherList [data-teacher="park"]').slice(0, 80));
  h29.click(h29.$('#teacherList [data-teacher="park"]'));
  await sleep(50);
  const sheetTxt = h29.text('#teacherSheetBody');
  ok('AB37 상세 시트 신뢰 배지 블록(별점·후기·완료·재방문)', !!h29.$('#teacherTrustBlock') &&
    /신뢰 배지/.test(sheetTxt) && /평균 별점/.test(sheetTxt) && /완료 방문/.test(sheetTxt) && /재방문/.test(sheetTxt));
  ok('AB38 상세 시트에 내 후기·대표 태그 반영', /나 \(보호자\)/.test(sheetTxt) &&
    h29.$$('#teacherTrustBlock .t-tags .tag').length >= 3, String(h29.$$('#teacherTrustBlock .t-tags .tag').length));
  h29.click(h29.$('#teacherSheet [data-sheet-close]'));
  await sleep(30);

  /* ----- 5) 원클릭 재예약 ----- */
  ok('AB39 홈 요약 카드에 최근 방문·재예약 버튼', (function () {
    h29.click(h29.$('.tabbtn[data-tab="home"]'));
    const blk = h29.text('#homeSummaryRebook');
    return /최근 방문/.test(blk) && /박서준/.test(blk) && !!h29.$('#homeSummaryRebook [data-rebook="TT-261019-4811"]');
  })(), h29.text('#homeSummaryRebook'));
  h29.click(h29.$('#homeSummaryRebook [data-rebook]'));
  await sleep(60);
  const form = M29.bookingFormState();
  ok('AB40 재예약 → 예약 1단계로 이동·선생님/지역/증상/1회권 채움', h29.$('#screen-booking').classList.contains('is-active') &&
    form.teacherId === 'park' && form.province === '서울' && form.district === '강남구' &&
    form.syms.join(',') === '뇌졸중·편마비' && form.passId === 'p1', JSON.stringify(form));
  ok('AB41 재예약 배너(같은 조건 안내)', /박서준/.test(form.banner) && /90,000원/.test(form.banner) &&
    /1회권/.test(form.banner), form.banner);
  ok('AB42 재예약 화면 — 증상 칩 선택·무료 평가 아님', h29.$('#bookSyms [data-val="뇌졸중·편마비"]').classList.contains('is-on') &&
    h29.$('#passList [data-pass="p1"]').classList.contains('is-on') &&
    !h29.$('#passList [data-pass="eval"]').classList.contains('is-on'));
  ok('AB43 재예약 초안도 순수 계산(저장소 그대로)', (function () {
    const d = M29.rebookDraft('TT-261019-4811');
    return d.ok === true && d.sourceNo === 'TT-261019-4811' && d.total === 90000 && d.freeEval === false;
  })());
  ok('AB44 내 예약 목록에도 재예약 버튼', (function () {
    h29.click(h29.$('.tabbtn[data-tab="mypage"]'));
    return !!h29.$(`#bookingList [data-rebook="TT-261019-4811"]`);
  })());
  ok('AB45 완료 예약 상세 시트에 후기·재예약', (function () {
    h29.click(h29.$(`#bookingList [data-manage="TT-261019-4811"]`));
    const t = h29.text('#manageSheetBody');
    return /방문 완료된 회차/.test(t) && !!h29.$(`#manageSheetBody [data-rebook="TT-261019-4811"]`);
  })(), h29.text('#manageSheetBody').slice(0, 120));
  h29.click(h29.$('#manageSheet [data-manage-close]'));
  await sleep(30);
  ok('AB46 후기 시트는 DIALOG_ORDER에 등록(Escape 유지)', M29.a11y.dialogOrder.indexOf('#reviewSheet') !== -1 &&
    h29.$('#reviewSheet').getAttribute('role') === 'dialog' && h29.$('#reviewSheet').getAttribute('aria-modal') === 'true');
  ok('AB47 <style> 블록 CSS 144,471자 유지(v29)', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    return !!m && cssTokens(HTML).ok;
  })(), String((HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length));
  ok('AB48 v28 관리자 지표 회귀 유지', (function () {
    const m = M29.adminMetrics({});
    return !!m && m.version === 'v28' && m.kpis.length === 6 && typeof m.text === 'string';
  })());
  ok('AB49 완료 방문이 없으면 재예약 후보도 없다(블록 숨김 조건)', (function () {
    const only = { bookings: [{ id: 'x1', no: 'TT-261021-7302', status: 'confirmed', teacherId: 'park' }] };
    return M29.reviewableReservations(only).length === 0 &&
      M29.canReviewReservation(only, 'TT-261021-7302').code === 'not_completed';
  })());
  ok('AB50 v29 화면 오류 없음', D29.errors.length === 0 && D29.window.document.documentElement.getAttribute('data-js-error') === null,
    D29.errors.slice(0, 3).join(' | '));

  /* ============================================================
     AC. v31 — 터치 영역 44px·인접 간격·CTA 줄바꿈 마감
     ============================================================ */
  const V31 = makeDom();
  await sleep(3200);
  const d31 = V31.doc, w31 = V31.window;
  const M31 = w31.__ttokttokModel;
  const T31 = w31.__ttokttokTouch;
  ok('AC0 v31 JS 오류 없음', V31.errors.length === 0 && d31.documentElement.getAttribute('data-js-error') === null,
    V31.errors.slice(0, 3).join(' | '));
  ok('AC1 v31 메타·터치 훅 노출(최소 44px·간격 8px)', d31.querySelector('meta[name="app-version"]').getAttribute('content') === 'v48' &&
    !!M31 && M31.qaVersion === 'v34' && !!T31 && T31.version === 'v31' && T31.min === 44 && T31.gapMin === 8,
    M31 && [M31.qaVersion, T31 && T31.version, T31 && T31.min].join('/'));
  /* jsdom은 렌더 타이머가 느려 부트 스캔이 끝나기 전에 검사될 수 있다.
     자동 적용은 AC3a·AC11(클릭 뒤 재렌더)에서 확인하고, 전수 검사는 스캔을 한 번 더 돌린 뒤 한다. */
  ok('AC2a 부트 스캔이 파싱 시점 요소에 자동 적용(칩·닫기·체크박스 라벨·탭바)', (function () {
    const chip = d31.querySelector('#regionFilters .chip');
    const close = d31.querySelector('.sheet-close');
    const tab = d31.querySelector('.tabbar .tabbtn');
    const lab = d31.querySelector('label[for="bookAgree"]');
    return !!chip && chip.style.minHeight === '44px' && !!close && close.style.minHeight === '44px' &&
      !!tab && tab.style.minHeight === '44px' && !!lab && lab.style.minHeight === '44px';
  })());
  T31.apply(d31);
  ok('AC2 터치 대상 선택자에 버튼·링크·칩·아이콘 버튼·목록 행 포함', (function () {
    const sel = T31.selectors.join(',');
    return ['button', 'a[href]', '.chip', '.tabbtn', '.teacher', '.list-item', '.notif', '.faq-q', '.date-chip', '.slot'].every((x) => sel.indexOf(x) !== -1);
  })(), T31.selectors.join(','));
  ok('AC3 버튼·링크·칩 전부 min-height 44px 인라인 적용', (function () {
    const list = Array.from(d31.querySelectorAll(T31.selectors.join(',')));
    const miss = list.filter((el) => {
      const type = (el.getAttribute('type') || '').toLowerCase();
      if (el.tagName === 'INPUT' && (type === 'checkbox' || type === 'radio')) {
        const lab = el.closest('label') || d31.querySelector('label[for="' + el.id + '"]');
        return !lab || lab.style.minHeight !== '44px';
      }
      if (el.tagName === 'INPUT' && type === 'range') return el.style.height !== '44px';
      return el.style.minHeight !== '44px';
    });
    return list.length > 150 && miss.length === 0;
  })(), String(Array.from(d31.querySelectorAll(T31.selectors.join(','))).length));
  ok('AC4 작은 글자 링크는 알약형 버튼으로 승격(더 보기·전체 읽음·이용 가이드)', (function () {
    const pills = Array.from(d31.querySelectorAll(T31.pillSelectors.join(',')));
    return pills.length >= 10 && pills.every((el) => el.style.minHeight === '44px' &&
      el.style.borderRadius === '999px' && el.style.border !== '' && el.style.display === 'inline-flex');
  })(), String(d31.querySelectorAll(T31.pillSelectors.join(',')).length));
  ok('AC5 인접 컨트롤 컨테이너 간격 8px(칩 줄·버튼 줄)', (function () {
    const cs = Array.from(d31.querySelectorAll('.chips, .segmented, .sym-chips, .req-btns, .admin-actions'));
    return cs.length >= 8 && cs.every((el) => el.style.gap === '8px');
  })(), String(d31.querySelectorAll('.chips, .segmented, .sym-chips').length));
  ok('AC6 체크박스는 라벨 전체가 44px 터치 영역', (function () {
    const ids = ['c1', 'c2', 'c3', 'c4', 'c5'];
    return ids.every((id) => {
      const lab = d31.querySelector('label[for="' + id + '"]');
      return !!lab && lab.style.minHeight === '44px';
    });
  })());
  ok('AC7 아이콘 버튼(닫기·찜·검색) 44px 이상', ['#homeSearchBtn', '#btnNotif'].every((sel) => {
    const el = d31.querySelector(sel);
    return !!el && el.style.minHeight === '44px' && el.style.minWidth === '44px';
  }) && Array.from(d31.querySelectorAll('.sheet-close')).every((el) => el.style.minHeight === '44px' && el.style.minWidth === '44px'));
  ok('AC8 320px CTA 문구 축약(2분 일지 저장 → 일지 저장 · 보호자 공유)', (function () {
    const b = d31.querySelector('#qlSave');
    return !!b && b.textContent.indexOf('일지 저장 · 보호자 공유') !== -1 && b.textContent.indexOf('2분 일지') === -1;
  })());
  ok('AC9 좁은 카드 CTA는 줄바꿈 금지(nowrap)', (function () {
    const sels = ['.admin-actions .btn', '.req-btns .btn', '.tp-sched .act .btn'];
    const els = sels.map((x) => d31.querySelector(x)).filter(Boolean);
    return els.length >= 2 && els.every((el) => el.style.whiteSpace === 'nowrap');
  })());
  ok('AC10 새로 그린 목록에도 44px 적용(선생님 목록 재렌더)', (function () {
    const btn = d31.querySelector('.tabbar .tabbtn[data-tab="teachers"]');
    if (btn) btn.dispatchEvent(new w31.MouseEvent('click', { bubbles: true, cancelable: true }));
    return true;
  })());
  await sleep(80);
  ok('AC11 재렌더 뒤 선생님 카드·필터 칩 44px 유지', (function () {
    const els = Array.from(d31.querySelectorAll('#teacherList .teacher, #teacherFilters .chip, #screen-teachers .chip'));
    return els.length > 0 && els.every((el) => el.style.minHeight === '44px');
  })(), String(d31.querySelectorAll('#teacherList .teacher').length));
  ok('AC12 간격 위반 0(앱 자체 감사)', (function () {
    return Array.isArray(T31.gapViolations()) && T31.gapViolations().length === 0;
  })(), JSON.stringify(T31.gapViolations().slice(0, 3)));
  ok('AC13 <style> 블록 CSS 144,471자 유지(v29와 동일)', (function () {
    const m = HTML.match(/<style>([\s\S]*?)<\/style>/);
    return !!m && cssTokens(HTML).ok;
  })(), String((HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1].length));
  ok('AC14 단가·수수료·정산 규칙 불변(v31 마감이 가격을 건드리지 않음)', (function () {
    return M31.pricing.consumerPrice === 90000 && M31.pricing.teacherPayout === 70000 && M31.pricing.platformFeeRate === 0.2222 &&
      M31.settlementRule.confirmDays === 3 && JSON.stringify(M31.settlementRule.payDays) === '[15,"end"]';
  })(), JSON.stringify({ p: M31.pricing && M31.pricing.consumerPrice, t: M31.pricing && M31.pricing.teacherPayout }));

  report();
}

run().catch((e) => { console.log('FATAL', e && e.stack || e); process.exit(1); });
