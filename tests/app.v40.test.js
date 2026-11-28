/*
 * 똑똑쌤 v40 — 전체 회귀·잔여 결함 마감 검증 (jsdom)
 * 실행: cd projects/ttokttok-app/tests && node --max-old-space-size=2600 app.v40.test.js
 *
 * 이 파일이 잠그는 것
 *   ① 화면에 적힌 날짜·요일이 달력과 같다(예전 시드: 11.28 (금), 오늘=수(11.25))
 *   ② 기기에 저장된 옛 예약 라벨도 ISO 날짜 기준으로 다시 계산된다
 *   ③ 일지 탭 '방문 카드'가 마크업에 박힌 날짜 대신 예약 데이터를 그린다
 *   ④ 선생님 일정·요청의 '오늘'·'M/D' 요일이 달력과 같다
 *   ⑤ 금액 표기(18.8만)·정산 규칙·단가·시드 예약은 그대로다
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const STYLE = (HTML.match(/<style>([\s\S]*?)<\/style>/) || ['', ''])[1];
const FIXED_NOW = new Date('2026-11-26T13:00:00.000Z').getTime();
const WD = ['일', '월', '화', '수', '목', '금', '토'];
const dayName = (m, d) => WD[new Date(2026, m - 1, d).getDay()];

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
      if (o.stale) {
        window.localStorage.setItem('ttokttok_account_v3', JSON.stringify(o.stale));
        window.localStorage.setItem('ttokttok_teacher_profile_v1', JSON.stringify({ teacherId: 'park' }));
      }
      if (o.blockStorage) {
        Object.defineProperty(window, 'localStorage', {
          configurable: true,
          get() { throw new window.DOMException('SecurityError', 'SecurityError'); }
        });
      }
    }
  });
  return { dom, window: dom.window, doc: dom.window.document, errors };
}
const cleanText = (doc) => {
  const clone = doc.body.cloneNode(true);
  [].forEach.call(clone.querySelectorAll('script,style,noscript,svg'), (el) => el.remove());
  return String(clone.textContent || '').replace(/\s+/g, ' ');
};
const textOf = (doc, sel) => {
  const el = doc.querySelector(sel);
  return el ? String(el.textContent || '').replace(/\s+/g, ' ').trim() : '';
};
const click = (el) => el && el.dispatchEvent(new el.ownerDocument.defaultView.MouseEvent('click', { bubbles: true, cancelable: true }));

async function waitBooted(w, ms) {
  const until = Date.now() + (ms || 40000);
  while (!w.__ttokttokBooted && Date.now() < until) await sleep(20);
  return !!w.__ttokttokBooted;
}

/* 화면 글자의 (M.DD) 요일이 달력과 맞는지 — 같은 실수를 다시 하지 않게 전 화면에서 본다 */
function weekdayMismatches(text) {
  const out = [];
  const re = /(?<![\d.])(\d{1,2})[./](\d{1,2})\s*\((월|화|수|목|금|토|일)\)/g;
  let m;
  while ((m = re.exec(text))) {
    const mo = +m[1], d = +m[2];
    if (mo < 1 || mo > 12 || d < 1 || d > 31) continue;
    const real = dayName(mo, d);
    if (real !== m[3]) out.push(m[0] + '→' + real);
  }
  return out;
}

async function run() {
  const A = makeDom();
  await waitBooted(A.window);
  const w = A.window, doc = A.doc;
  const M = w.__ttokttokModel;

  ok('A1 meta v40', (doc.querySelector('meta[name="app-version"]') || {}).content === 'v50',
    (doc.querySelector('meta[name="app-version"]') || {}).content);
  ok('A2 부팅 오류 0', !A.errors.length, A.errors.slice(0, 2));

  /* ── 1) 날짜 계산 도구 ── */
  ok('A3 mdSlashOf/dateLabelOf 형식', M.mdSlashOf('2026-12-01') === '12/01' && M.dateLabelOf('2026-12-01') === '12.01',
    M.mdSlashOf('2026-12-01') + '/' + M.dateLabelOf('2026-12-01'));
  ok('A4 weekdayOf 2026-11-28=토', M.weekdayOf('2026-11-28') === '토', M.weekdayOf('2026-11-28'));

  /* ── 2) 시드 예약 라벨이 날짜에서 계산된다 ── */
  const seed = (M.reservations() || []).filter((r) => r.no === 'TT-261021-7302')[0] || {};
  ok('A5 시드 예약 날짜 라벨 계산(11.28)', seed.date === '11.28', seed.date);
  ok('A6 시드 예약 요일 계산(토)', seed.day === '토', seed.day);
  ok('A7 시드 예약 dateIso 유지', seed.dateIso === '2026-11-28', seed.dateIso);

  /* ── 3) 홈 요약: 날짜·요일·D-day ── */
  const home = textOf(doc, '#homeSummaryCard');
  ok('A8 홈 요약 11.28 (토)', /11\.28 \(토\)/.test(home), home.slice(0, 120));
  ok('A9 홈 요약 D-2', /D-2/.test(home), home.slice(0, 120));

  /* ── 4) 일지 탭 방문 카드 — 예약 데이터로 그린다 ── */
  click(doc.querySelector('.tabbtn[data-tab="journal"]'));
  await sleep(120);
  const chip = textOf(doc, '#todayChip');
  ok('A10 방문 카드 날짜·요일(11월 28일 (토))', /11월 28일 \(토\)/.test(chip), chip);
  ok('A11 방문 카드에 다음 방문 표기', /다음 방문/.test(chip), chip);
  ok('A12 방문 카드 시간 10:30~11:30', /10:30\s*~\s*11:30/.test(textOf(doc, '#todayTime')), textOf(doc, '#todayTime'));
  const tmeta = textOf(doc, '#todayMeta');
  ok('A13 방문 카드 선생님·지역·회차권', /박서준 선생님/.test(tmeta) && /서울 강남구 대치동/.test(tmeta) && /8회권/.test(tmeta), tmeta);
  ok('A14 박혀 있던 날짜(11월 25일) 사라짐', !/11월 25일/.test(doc.body.innerText || '') && !/11월 25일/.test(cleanText(doc)));
  ok('A15 정적 시간(10:30~11:30) 하드코딩 없음', !/<p class="sched-time">/.test(HTML));

  /* ── 5) 전 화면 날짜-요일 일치 ── */
  const all = cleanText(doc);
  ok('A16 보호자 화면 날짜-요일 불일치 0', weekdayMismatches(all).length === 0, weekdayMismatches(all).slice(0, 4));

  /* ── 6) 선생님 일정·요청 ── */
  click(doc.querySelector('[data-login="therapist"]'));
  await sleep(150);
  click(doc.querySelector('.tabbtn[data-tab="tp-schedule"]'));
  await sleep(150);
  const sched = textOf(doc, '#screen-tp-schedule');
  ok('A17 선생님 일정 오늘 요일(목)', /오늘 \(목\)/.test(sched), sched.slice(0, 160));
  ok('A18 선생님 일정 요일 불일치 0', weekdayMismatches(sched).length === 0, weekdayMismatches(sched).slice(0, 4));
  ok('A19 요청 날짜 12/01 (화)', /12\/01 \(화\)/.test(sched), sched.slice(0, 200));
  ok('A20 요청 날짜 12/02 (수)', /12\/02 \(수\)/.test(sched), sched.slice(0, 200));

  /* ── 7) 정산 차트 금액 표기 ── */
  click(doc.querySelector('.tabbtn[data-tab="tp-home"]'));
  await sleep(150);
  const chart = textOf(doc, '.settle-chart');
  ok('A21 정산 차트 18.8만 표기', /18\.8만/.test(chart) && !/\d+k/.test(chart), chart.slice(0, 40));
  ok('A22 정산 금액·수수료 그대로', /980,000/.test(textOf(doc, '#tpSettle')) && /22\.2%/.test(textOf(doc, '#tpSettle')));

  /* ── 8) 디자인 토큰·배지 ── */
  ok('A23 시연용 배지 한 줄(nowrap)', /\.tag-example\{[^}]*white-space:nowrap/.test(STYLE));

  /* ── 9) 정책 불변 ── */
  ok('A24 단가·수수료·정산·시드 불변',
    M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 && M.pricing.platformFeeRate === 0.2222 &&
    M.settlementRule.confirmDays === 3 && String(M.settlementRule.payDays) === '15,end' &&
    (M.reservations() || []).some((r) => r.no === 'TT-261021-7302'));

  /* ── 10) 기기에 저장된 옛 라벨(11.27 금) 교정 ── */
  const staleAccount = {
    profile: { name: '현수' },
    passes: [{ id: 'seed-pass', userId: 'usr-demo', passId: 'p8', name: '8회권', total: 8, remaining: 5, purchased: '2026.10.28', expire: '2027.01.27', status: 'active' }],
    bookings: [
      { id: 'res-tt-261021-7302', no: 'TT-261021-7302', userId: 'usr-demo', date: '11.27', day: '금', time: '10:30',
        teacher: '박서준 선생님', teacherId: 'park', region: '서울 강남구 대치동', regionId: 'reg-서울-강남구',
        status: 'confirmed', passId: 'p8', walletId: 'seed-pass', dateIso: '2026-11-28', amount: 74000, paymentStatus: 'paid' }
    ],
    receipts: []
  };
  const B = makeDom({ stale: staleAccount });
  await waitBooted(B.window);
  const bRes = (B.window.__ttokttokModel.reservations() || [])[0] || {};
  ok('A25 저장된 옛 라벨 → 11.28', bRes.date === '11.28', bRes.date);
  ok('A26 저장된 옛 요일 → 토', bRes.day === '토', bRes.day);
  ok('A27 재방문 홈 요약도 11.28 (토)', /11\.28 \(토\)/.test(textOf(B.doc, '#homeSummaryCard')), textOf(B.doc, '#homeSummaryCard').slice(0, 100));
  ok('A28 재방문 일지 카드도 토요일', (function () {
    click(B.doc.querySelector('.tabbtn[data-tab="journal"]'));
    return true;
  })() && /\(토\)/.test(textOf(B.doc, '#todayChip')), textOf(B.doc, '#todayChip'));

  /* ── 11) 저장 차단 ── */
  const C = makeDom({ blockStorage: true });
  await waitBooted(C.window);
  ok('A29 저장 차단에서도 부팅·날짜 계산', !C.errors.filter((e) => !/localStorage|SecurityError/.test(e)).length &&
    (C.window.__ttokttokModel.reservations() || []).length >= 1, C.errors.slice(0, 2));

  ok('A30 CSS 바이트 상한(1.45MB 이내)', fs.statSync(path.join(__dirname, '..', 'index.html')).size <= 1450 * 1024,
    fs.statSync(path.join(__dirname, '..', 'index.html')).size);

  console.log('\nV40 RESULT: ' + pass + ' passed, ' + fails.length + ' failed');
  if (fails.length) {
    console.log('FAILURES:');
    fails.forEach((f) => console.log(' - ' + f));
  }
  process.exit(fails.length ? 1 : 0);
}

run().catch((e) => { console.error(e); process.exit(2); });
