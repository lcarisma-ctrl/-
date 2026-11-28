/*
 * 똑똑쌤 v37 — 입력 UX(숫자 포맷 · 자리수 완료 시 다음 칸 · 즉시 검증 · 자동 포커스 · 키보드 회피) 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v37.test.js
 * ─ 실제 픽셀·키보드 동작은 Chromium(E2E v37 · qa_v24)에서 보고,
 *   여기서는 규칙(순수 함수)·마크업 계약·aria 연결·초점 이동·키보드 상태를 본다.
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
      const RealDate = window.Date;
      function FixedDate(...args) { return args.length ? new RealDate(...args) : new RealDate(FIXED_NOW); }
      FixedDate.prototype = RealDate.prototype;
      FixedDate.now = () => FIXED_NOW;
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
     CA. v37 — 입력 UX
     ============================================================ */

  /* ── 1) CSS(키보드 회피·오류 표시) ──────────────────────────── */
  ok('CA1 :root는 한 블록 그대로(v35 구조 유지)', (STYLE.match(/:root\{/g) || []).length === 1);
  ok('CA2 CSS 중괄호 균형·var() 정의', (function () {
    const defs = new Set((STYLE.match(/--[a-zA-Z0-9-]+\s*:/g) || []).map((x) => x.replace(/\s*:$/, '')));
    const uses = (STYLE.match(/var\((--[a-zA-Z0-9-]+)/g) || []).map((x) => x.slice(4));
    return (STYLE.match(/\{/g) || []).length === (STYLE.match(/\}/g) || []).length && [...new Set(uses)].every((u) => defs.has(u));
  })());
  ok('CA3 키보드가 올라오면 시트를 그만큼 올린다(--kb-inset)', /body\.is-keyboard \.sheet-backdrop\.is-open \.sheet\{bottom:var\(--kb-inset,0px\)/.test(STYLE));
  ok('CA4 시트 내용은 패딩으로 밀지 않고, 스크롤 여유만(작게) 둔다', /body\.is-keyboard \.sheet-scroll\{scroll-padding-bottom:12px;scroll-padding-top:12px\}/.test(STYLE) &&
    !/body\.is-keyboard \.sheet-scroll\{padding-bottom/.test(STYLE), 'scroll-padding only');
  ok('CA5 예약·지원 화면은 제출 버튼까지 스크롤(아래 여백 + 하단 합계바 숨김)', /body\.is-keyboard #screen-booking \.wstep\.is-active/.test(STYLE) &&
    /body\.is-keyboard #screen-partner \.wstep\.is-active/.test(STYLE) && /body\.is-keyboard #bookTotalBar\{display:none\}/.test(STYLE));
  ok('CA6 오류 입력란은 aria-invalid로도 같은 표시를 준다', /\[aria-invalid="true"\]\{border-color:var\(--line-tint-rose-2\)/.test(STYLE));
  ok('CA7 게이트(로그인) 번호 오류 문구 규칙', /\.gate-phone \.err\{display:none/.test(STYLE) && /\.gate-phone\.is-error \.err\{display:block\}/.test(STYLE));
  ok('CA8 v35 규칙 유지 — 글자 크기 리터럴 0(320 시작 화면 1줄 예외)', (STYLE.match(/font-size:\s*[\d.]+px/g) || []).length <= 1);
  ok('CA9 index.html 1.45MB 이하', Buffer.byteLength(HTML, 'utf8') <= 1450 * 1024, String(Buffer.byteLength(HTML, 'utf8')));

  /* ── 2) 마크업 계약(정적) ───────────────────────────────────── */
  ok('CA10 휴대폰·생년월일류 숫자 입력란은 inputmode가 있다', (function () {
    const tel = HTML.match(/<input[^>]*type="tel"[^>]*>/g) || [];
    return tel.length >= 4 && tel.every((t) => /inputmode="numeric"/.test(t));
  })(), String((HTML.match(/<input[^>]*type="tel"[^>]*>/g) || []).filter((t) => !/inputmode="numeric"/.test(t)).join(' | ')));
  ok('CA11 type=number 입력란은 inputmode·autocomplete를 갖춘다', (function () {
    const nums = HTML.match(/<input[^>]*type="number"[^>]*>/g) || [];
    return nums.length >= 4 && nums.every((t) => /inputmode="/.test(t) && /autocomplete="/.test(t));
  })());
  ok('CA12 자동 포커스는 입력하러 여는 시트 2곳(게이트 번호·쿠폰 코드)뿐', (function () {
    const all = HTML.match(/<input[^>]*data-autofocus[^>]*>/g) || [];
    return all.length === 2 && all.some((t) => /id="gatePhone"/.test(t)) && all.some((t) => /id="couponCode"/.test(t));
  })(), String((HTML.match(/<[^>]*data-autofocus[^>]*>/g) || []).length));
  ok('CA13 자리수 완료 시 이동(data-next)은 결정적인 칸에만', (function () {
    const map = {};
    (HTML.match(/<input[^>]*data-next="[^"]*"[^>]*>/g) || []).forEach((t) => {
      const id = (t.match(/id="([^"]+)"/) || [])[1];
      map[id] = (t.match(/data-next="([^"]+)"/) || [])[1];
    });
    return map.pPhone === '#pEmail' && map.cardLast4 === '#cardExpiry' &&
      map.cardExpiry === '#cardSave' && map.pLicenseYear === '#pYears' && !map.bookPhone;
  })());
  ok('CA14 규칙 입력란마다 enterkeyhint가 있다', (function () {
    const rules = HTML.match(/<input[^>]*data-tt-rule="[^"]*"[^>]*>/g) || [];
    return rules.length >= 9 && rules.every((t) => /enterkeyhint="/.test(t));
  })(), String((HTML.match(/<input[^>]*data-tt-rule="[^"]*"[^>]*>/g) || []).filter((t) => !/enterkeyhint="/.test(t)).length));
  ok('CA15 카드 유효기간은 autocomplete="cc-exp"', /id="cardExpiry"[^>]*autocomplete="cc-exp"/.test(HTML.replace(/\n/g, ' ')) || /autocomplete="cc-exp"[^>]*id="cardExpiry"/.test(HTML.replace(/\n/g, ' ')));

  /* ── 3) 순수 함수(모델) ─────────────────────────────────────── */
  const A = makeDom();
  await sleep(520);
  const dA = A.doc, WA = A.window, M = WA.__ttokttokModel, I = WA.__ttokttokInput;
  ok('CA16 부트·훅 노출(meta v37, qaVersion v34 유지)', dA.querySelector('meta[name=app-version]').content === 'v50' &&
    !!I && I.version === 'v37' && M.qaVersion === 'v34' && M.a11y.version === 'v34' && M.inputVersion === 'v37');
  ok('CA17 부트 JS 오류 0', A.errors.length === 0, A.errors.slice(0, 3).join(' | '));
  ok('CA18 규칙 입력란 11개가 바인딩됨', M.inputState().bound === 11 && M.inputState().fields === 11, JSON.stringify(M.inputState()));

  ok('CA19 휴대폰 포맷 — 010 3-4-4', M.formatInput('phone', '01012345678') === '010-1234-5678', M.formatInput('phone', '01012345678'));
  ok('CA20 휴대폰 포맷 — 011 3-3-4', M.formatInput('phone', '0111234567') === '011-123-4567', M.formatInput('phone', '0111234567'));
  ok('CA21 휴대폰 포맷 — 서울 02 2-4-4·2-3-4', M.formatInput('phone', '0212345678') === '02-1234-5678' &&
    M.formatInput('phone', '021234567') === '02-123-4567', M.formatInput('phone', '0212345678') + '/' + M.formatInput('phone', '021234567'));
  ok('CA22 휴대폰 포맷 — 지역번호·부분 입력·11자리 상한', M.formatInput('phone', '0311234567') === '031-123-4567' &&
    M.formatInput('phone', '01012') === '010-12' && M.formatInput('phone', '010123456789999') === '010-1234-5678',
    M.formatInput('phone', '0311234567') + '/' + M.formatInput('phone', '01012'));
  ok('CA23 자리수 완료 판정(휴대폰)', M.isInputComplete('phone', '010-1234-5678') === true &&
    M.isInputComplete('phone', '010-1234-567') === false && M.isInputComplete('phone', '02-1234-5678') === true &&
    M.isInputComplete('phone', '011-123-4567') === true);
  ok('CA24 유효기간 포맷·완료·월 검증', M.formatInput('expiry', '1229') === '12/29' && M.isInputComplete('expiry', '12/29') === true &&
    M.validateInput('expiry', '13/29').ok === false && M.validateInput('expiry', '00/29').ok === false);
  ok('CA25 끝 4자리는 숫자 4자리만', M.formatInput('card4', '12-34-56') === '1234' && M.validateInput('card4', '123').ok === false &&
    M.validateInput('card4', '1234').ok === true);

  ok('CA26 이름 검증 문구(빈 값·1자·정상)', (function () {
    const a = M.validateInput('name', ''), b = M.validateInput('name', '김'), c = M.validateInput('name', '김순자');
    return !a.ok && /이름을 입력해/.test(a.message) && !b.ok && /2자 이상/.test(b.message) && c.ok;
  })());
  ok('CA27 휴대폰 검증(010은 11자리, 서울 02는 9~10자리)', M.validateInput('phone', '010-1234-567').ok === false &&
    M.validateInput('phone', '010-1234-5678').ok === true && M.validateInput('phone', '02-123-4567').ok === true &&
    M.validateInput('phone', '1234').ok === false);
  ok('CA28 연락처가 비면 전용 문구', /연락처를 입력해/.test(M.validateInput('phone', '').message));
  ok('CA29 이메일은 선택 — 비면 통과, 형식이 틀리면 문구', M.validateInput('email', '').ok === true &&
    M.validateInput('email', 'abc').ok === false && M.validateInput('email', 'a@b.co').ok === true);
  ok('CA30 단가·취득연도 범위 검증', M.validateInput('rate', '72000').ok === true && M.validateInput('rate', '30000').ok === false &&
    M.validateInput('year', '2021').ok === true && M.validateInput('year', '1899').ok === false && M.validateInput('year', '').ok === true);
  ok('CA31 면허번호 검증(4자 이상)', M.validateInput('license', '11-20').ok === true && M.validateInput('license', '11').ok === false);
  ok('CA32 규칙·문구는 모델 한 곳에 있다(화면과 테스트가 같은 문구)', M.inputKinds.length === 8 && !!M.inputMessages.phoneInvalid &&
    M.inputMessages.yearInvalid.indexOf('올해') > -1);

  /* 키보드 높이 계산 */
  ok('CA33 키보드 높이 = innerHeight - visualViewport.height - offsetTop', M.keyboardInset(812, 500, 0) === 312 &&
    M.keyboardInset(812, 620, 40) === 152);
  ok('CA34 키보드 계산은 0 미만·비정상 입력에서 0', M.keyboardInset(812, 900, 0) === 0 && M.keyboardInset(0, 0, 0) === 0 &&
    M.keyboardInset(NaN, 500, 0) === 0);

  /* ── 4) 실제 입력: 포맷·aria·자동 이동 ──────────────────────── */
  const B = makeDom();
  await sleep(520);
  const d = B.doc, W = B.window, MB = W.__ttokttokModel, IB = W.__ttokttokInput;
  const fire = (el, type) => el.dispatchEvent(new W.Event(type, { bubbles: true }));

  /* 4-1) 게이트 시트를 열면 번호 입력란에 초점(닫기 버튼이 아니라) */
  d.getElementById('gateCta').click();
  await sleep(60);
  ok('CA35 게이트 시트를 열면 번호 입력란에 자동 포커스', d.getElementById('gateSheet').classList.contains('is-open') &&
    d.activeElement && d.activeElement.id === 'gatePhone', (d.activeElement && (d.activeElement.id || d.activeElement.className)) || '');
  const gp = d.getElementById('gatePhone');
  gp.value = '010';
  fire(gp, 'input');
  gp.blur();
  ok('CA36 게이트 번호가 짧으면 aria-invalid·오류 문구 연결', gp.getAttribute('aria-invalid') === 'true' &&
    gp.getAttribute('aria-describedby') === 'gatePhoneErr' && d.querySelector('.gate-phone').classList.contains('is-error'));
  ok('CA37 오류 문구는 화면에도 보인다(.err 텍스트)', /연락처를 정확히/.test(d.getElementById('gatePhoneErr').textContent));
  gp.value = '01012345678';
  fire(gp, 'input');
  gp.blur();
  ok('CA38 고치면 aria-invalid 해제·descroption 제거', gp.getAttribute('aria-invalid') === 'false' &&
    !gp.getAttribute('aria-describedby') && !d.querySelector('.gate-phone').classList.contains('is-error') &&
    gp.value === '010-1234-5678', gp.value);

  /* 4-2) 예약 4단계 — 타이핑 즉시 하이픈, blur 검증 */
  const bp = d.getElementById('bookPhone');
  bp.focus();
  bp.value = '01012345678';
  fire(bp, 'input');
  ok('CA39 예약 연락처는 입력 즉시 010-1234-5678', bp.value === '010-1234-5678' && bp.getAttribute('aria-invalid') !== 'true', bp.value);
  bp.value = '0101234';
  fire(bp, 'input');
  bp.blur();
  ok('CA40 예약 연락처가 모자라면 필드 오류 + aria 설명', bp.getAttribute('aria-invalid') === 'true' &&
    bp.getAttribute('aria-describedby') === 'bookPhoneErr' && d.getElementById('bookPhoneErr').textContent.length > 0 &&
    d.getElementById('f-bookPhone').classList.contains('is-error'));
  bp.focus();
  bp.value = '01012345678';
  fire(bp, 'input');
  bp.blur();
  ok('CA41 고치면 필드 오류 해제', !d.getElementById('f-bookPhone').classList.contains('is-error') &&
    bp.getAttribute('aria-invalid') === 'false');

  /* 4-3) 자리수가 차면 다음 칸으로 — 실제 초점이 있을 때만 */
  const pp = d.getElementById('pPhone');
  pp.focus();
  pp.value = '01098765432';
  fire(pp, 'input');
  await sleep(10);
  ok('CA42 파트너 번호 11자리 → 이메일 칸으로 이동', pp.value === '010-9876-5432' && d.activeElement && d.activeElement.id === 'pEmail',
    (d.activeElement && d.activeElement.id) + '/' + pp.value);

  const c4 = d.getElementById('cardLast4');
  c4.focus();
  c4.value = '1234';
  fire(c4, 'input');
  await sleep(10);
  ok('CA43 카드 끝 4자리 → 유효기간 칸으로 이동', c4.value === '1234' && d.activeElement && d.activeElement.id === 'cardExpiry',
    (d.activeElement && d.activeElement.id) || '');
  const ce = d.getElementById('cardExpiry');
  ce.value = '1229';
  fire(ce, 'input');
  await sleep(10);
  ok('CA44 유효기간 4자리(12/29) → 등록 버튼으로 이동', ce.value === '12/29' && d.activeElement && d.activeElement.id === 'cardSave',
    (d.activeElement && d.activeElement.id) || '');

  /* 값만 넣는 경로(초안 복원·프로그램 입력)에서는 초점이 튀지 않는다 */
  d.getElementById('pName').focus();
  const pp2 = d.getElementById('pPhone');
  pp2.value = '01011112222';
  fire(pp2, 'input');
  await sleep(10);
  ok('CA45 초점이 없는 입력(복원·프로그램)은 다음 칸으로 넘기지 않는다', d.activeElement && d.activeElement.id === 'pName',
    (d.activeElement && d.activeElement.id) || '');

  /* 4-4) 제출 검증 경로도 aria를 함께 단다 */
  d.getElementById('payBtn').click();
  await sleep(40);
  const bn = d.getElementById('bookName');
  ok('CA46 폼 제출 오류가 aria-invalid·aria-describedby로 연결', bn.getAttribute('aria-invalid') === 'true' &&
    bn.getAttribute('aria-describedby') === 'bookNameErr' && d.getElementById('f-bookName').classList.contains('is-error'),
    (bn.getAttribute('aria-invalid') + '/' + bn.getAttribute('aria-describedby')));
  d.getElementById('bookName').value = '김순자';
  fire(d.getElementById('bookName'), 'input');
  d.getElementById('bookName').blur();
  ok('CA47 제출 오류도 입력하면 해제', bn.getAttribute('aria-invalid') === 'false' && !bn.getAttribute('aria-describedby'));

  /* 4-5) 쿠폰 시트를 열면 코드 입력란에 초점 */
  d.getElementById('mpCouponRow').click();
  await sleep(60);
  ok('CA48 쿠폰 시트를 열면 코드 입력란에 자동 포커스', d.getElementById('couponSheet').classList.contains('is-open') &&
    d.activeElement && d.activeElement.id === 'couponCode', (d.activeElement && (d.activeElement.id || d.activeElement.className)) || '');

  /* 4-6) 키보드 상태 — 시트가 그만큼 올라갈 준비 */
  IB.simulateKeyboard(320);
  ok('CA49 키보드 시뮬레이션 → --kb-inset 320px·is-keyboard', d.documentElement.style.getPropertyValue('--kb-inset') === '320px' &&
    d.body.classList.contains('is-keyboard') && MB.inputState().keyboard === true && MB.inputState().inset === 320);
  IB.simulateKeyboard(0);
  ok('CA50 키보드가 내려가면 원상 복구(--kb-inset 0px·class 해제)', d.documentElement.style.getPropertyValue('--kb-inset') === '0px' &&
    !d.body.classList.contains('is-keyboard') && MB.inputState().keyboard === false);
  ok('CA51 키보드가 없는 환경(visualViewport 없음)에서도 안전', MB.inputState().inset === 0 && d.documentElement.style.getPropertyValue('--kb-inset') === '0px');

  /* ── 5) 지켜야 할 것 ────────────────────────────────────────── */
  ok('CA52 단가·수수료·정산 규칙 불변', MB.pricing.consumerPrice === 90000 && MB.pricing.teacherPayout === 70000 &&
    MB.pricing.platformFeeRate === 0.2222 && MB.settlementRule.confirmDays === 3 &&
    JSON.stringify(MB.settlementRule.payDays) === '[15,"end"]');
  ok('CA53 시드 예약 TT-261021-7302 그대로', /TT-261021-7302/.test(d.body.textContent));
  ok('CA54 대화상자 이름 22/22 유지(v24 규칙)', (function () {
    const a = MB.a11y.auditAll();
    return a.blank.length === 0 && MB.a11y.labelledDialogs() === MB.a11y.dialogCount() && MB.a11y.dialogCount() >= 22;
  })());
  ok('CA55 규칙 입력란의 id·aria 설명 id가 겹치지 않는다', (function () {
    const ids = [].slice.call(d.querySelectorAll('[id]')).map((x) => x.id);
    const dup = ids.filter((x, i) => ids.indexOf(x) !== i);
    const errs = [].slice.call(d.querySelectorAll('.field .err, .gate-phone .err')).filter((x) => x.id).map((x) => x.id);
    return dup.length === 0 && errs.filter((x, i) => errs.indexOf(x) !== i).length === 0;
  })());
  ok('CA56 입력 UX 배선 뒤에도 JS 오류 0(흐름)', B.errors.length === 0, B.errors.slice(0, 3).join(' | '));

  console.log('\nRESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.log('FATAL', (e && e.stack) || e); process.exit(1); });
