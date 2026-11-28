#!/usr/bin/env python3
"""
똑똑쌤 v51 · 표기 전수 스캔 (Chromium)
─────────────────────────────────────────
화면·시트를 실제로 열어 보이는 글자에서 날짜·시간·금액·전화·비율 표기를 모으고,
v51 규칙에 어긋나는 표기를 화면 이름과 함께 보고한다.

규칙(DESIGN-v51.md §2)
  날짜  · 연도가 있으면 `2026.11.28 (토)` — 점(.) 구분, 요일은 괄호, 괄호 앞 한 칸
        · 연도가 없으면 `11.28 (토)`
        · `2026-11-28`·`11/28`·`11.28(토)`·`11월 28일`은 쓰지 않는다
  시간  · `09:30` (24시간, 두 자리) · 범위는 `09:30~10:30`
  금액  · `90,000원` · 음수는 `-32,340원` · 0원은 문맥에 따라 `무료`
  전화  · `010-9218-8577` · `031-919-8577` · `0507-1346-8577`
  비율  · `22.2%` (숫자와 붙여 쓴다)

실행:  python3 tests/format_scan_v51.py            # 보고서만
      python3 tests/format_scan_v51.py --gate     # 어긋난 표기가 있으면 실패(종료코드 1)
결과:  preview/v51-format/scan.json
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
if os.path.isdir("/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu"):
    os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")

from playwright.sync_api import sync_playwright

URL = "file://" + os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "preview", "v51-format")

# 화면 안 보이는 곳(aria-hidden·sprite·script)은 뺀다. 입력란 값은 화면 글자가 아니므로 뺀다.
TEXT_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return false;
    if (r.width < 1 || r.height < 1) return false;
    return true;
  };
  document.querySelectorAll('body *').forEach((el) => {
    if (el.closest('.sprite, [aria-hidden="true"], script, style, noscript, .sr-only')) return;
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.tagName === 'OPTION') return;
    if (!vis(el)) return;
    const own = Array.from(el.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ');
    const txt = own.replace(/\s+/g, ' ').trim();
    if (!txt) return;
    const key = txt + '|' + (el.id || el.className || el.tagName);
    if (seen.has(key)) return;
    seen.add(key);
    const ex = el.closest('.dday-badge, .date-chip, .week-chip, .bar-lab, .settle-chart, svg');
    out.push({ text: txt.slice(0, 220), el: (el.id ? '#' + el.id : (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).join('.') : el.tagName)), ex: ex ? (ex.className && typeof ex.className === 'string' ? ex.className.trim().split(/\s+/)[0] : ex.tagName) : '' });
  });
  return out;
}
"""

PATTERNS = [
    # (이름, 정규식, 설명)
    ("date_hyphen", re.compile(r"(?<![\d-])\d{4}-\d{1,2}-\d{1,2}(?![\d-])"), "붙임표 날짜(2026-11-28)"),
    ("date_slash", re.compile(r"(?<![\d/])\d{1,2}/\d{1,2}(?![\d/])"), "슬래시 날짜(11/28)"),
    ("date_tight", re.compile(r"(?<!\d)\d{1,2}\.\d{1,2}\("), "요일 괄호 앞 공백 없음(11.28(토))"),
    ("date_korean", re.compile(r"\d{1,2}\s*월\s*\d{1,2}\s*일"), "한글 날짜(11월 28일)"),
    ("date_no_weekday", re.compile(r"(?<![\d.])\d{1,2}\.\d{2}(?![\d.])(?!\s*\()"), "요일 없는 날짜(11.28)"),
    ("date_full_no_weekday", re.compile(r"(?<![\d.])\d{4}\.\d{2}\.\d{2}(?![\d.])(?!\s*\()"), "요일 없는 날짜(2026.11.28)"),
    ("time_1digit", re.compile(r"(?<![\d:.])\d:\d{2}(?![\d])"), "한 자리 시각(9:30)"),
    ("time_korean", re.compile(r"\d{1,2}\s*시\s*\d{1,2}\s*분"), "한글 시각(9시 30분)"),
    ("won_ungrouped", re.compile(r"(?<![\d,])\d{4,}원"), "천 단위 쉼표 없음(90000원)"),
    ("won_space", re.compile(r"\d\s+원(?!\s*이내)"), "숫자와 원 사이 공백"),
    ("phone_dot", re.compile(r"\d{2,4}\.\d{3,4}\.\d{4}"), "점 전화번호(010.9218.8577)"),
    ("phone_raw", re.compile(r"(?<![\d-])0\d{8,10}(?![\d-])"), "하이픈 없는 전화번호"),
    ("pct_space", re.compile(r"\d\s+%"), "퍼센트 앞 공백(22.2 %)"),
]


def looks_like_md(match):
    """0.77·0.24 같은 측정값을 날짜로 오해하지 않도록 월·일 범위를 확인한다."""
    try:
        mo, da = match.split('.')
        return 1 <= int(mo) <= 12 and 1 <= int(da) <= 31
    except ValueError:
        return False


def scan_text(text, el, ex=''):
    """v51 규칙에 어긋나는 표기만 돌려준다. 점수·단계 표기(3/10, 2/4)는 날짜가 아니다."""
    hits = []
    for name, rx, desc in PATTERNS:
        for m in rx.finditer(text):
            if name == 'date_no_weekday' and not looks_like_md(m.group(0)):
                continue
            if allowed_context(name, m.group(0), text, el, ex):
                continue
            hits.append({"kind": name, "desc": desc, "match": m.group(0)})
    return hits


# 날짜가 아닌 슬래시(점수·단계·진행률·카드 유효기간)와, 요일을 빼도 되는 자리
IGNORE_TEXT = [
    re.compile(r"통증 \d+/\d+"),
    re.compile(r"\d+/\d+ 완료"),
    re.compile(r"제출 서류 \d+/\d+"),
    re.compile(r"유효기간 \d{2}/\d{2}"),
    re.compile(r"^\d+/\d+$"),          # 1/4 단계·0/5 진행률 같은 맨 숫자
]
IGNORE_EL = ("#bookStepCount", "#checkCount", "#qlProgress")


def allowed_context(kind, match, text, el, ex=''):
    if ex in ("dday-badge", "date-chip", "week-chip", "bar-lab", "settle-chart", "svg"):
        return True
    if kind == "date_slash":
        if any(p.search(text) for p in IGNORE_TEXT):
            return True
        if el in IGNORE_EL:
            return True
    if kind in ("date_no_weekday", "date_full_no_weekday"):
        # 괄호 속 근거일(요율 확정일)은 요일을 빼도 된다: '22.2% (2026.11.26 확정)'
        i = text.find(match)
        before = text[:i]
        if before.count("(") > before.count(")"):
            return True
        # 기간의 양 끝: '11.24~11.30'
        if re.search(r"\d{1,2}\.\d{1,2}\s*~", text) or re.search(r"~\s*\d{1,2}\.\d{1,2}", text):
            return True
    return False


def collect(page, state, store, counts):
    try:
        nodes = page.evaluate(TEXT_JS)
    except Exception as e:
        store.append({"state": state, "error": str(e)})
        return
    counts[state] = len(nodes)
    for n in nodes:
        for h in scan_text(n["text"], n["el"], n.get("ex", "")):
            store.append({"state": state, "el": n["el"], "text": n["text"], "hit": h})


def nav_tab(page, tab):
    page.eval_on_selector('.tabbar .tabbtn[data-tab="%s"]' % tab, "el => el.click()")
    page.wait_for_timeout(230)


def open_sheet(page, sid):
    page.evaluate("(id) => { const s = document.getElementById(id); if (s) s.classList.add('is-open'); }", sid)
    page.wait_for_timeout(260)


def close_all(page):
    page.evaluate("() => { document.querySelectorAll('.sheet-backdrop.is-open, .backdrop.is-open').forEach(function (s) { s.classList.remove('is-open'); }); }")
    page.wait_for_timeout(180)


def run():
    os.makedirs(OUT, exist_ok=True)
    found = []
    counts = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="ko-KR")
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(400)

        collect(page, "gate", found, counts)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(420)

        # 보호자 5개 화면
        for tab in ["home", "teachers", "booking", "journal", "mypage"]:
            nav_tab(page, tab)
            collect(page, "customer/" + tab, found, counts)

        # 예약 1~4단계
        nav_tab(page, "booking")
        page.eval_on_selector('#provinceQuick [data-prov="서울"]', "el => el.click()")
        page.select_option("#bookDistrict", "강남구")
        page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
        page.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
        page.eval_on_selector('[data-next="1"]', "el => el.click()")
        page.wait_for_timeout(320)
        collect(page, "booking/step2", found, counts)
        page.eval_on_selector("#bookDates .date-chip", "el => el.click()")
        page.wait_for_timeout(160)
        page.eval_on_selector("#bookSlots .slot:not([disabled])", "el => el.click()")
        page.eval_on_selector('[data-next="2"]', "el => el.click()")
        page.wait_for_timeout(320)
        collect(page, "booking/step3", found, counts)
        page.eval_on_selector('#passList [data-pass="p8"]', "el => el.click()")
        page.wait_for_timeout(220)
        collect(page, "booking/step3-pass", found, counts)
        page.eval_on_selector('[data-next="3"]', "el => el.click()")
        page.wait_for_timeout(340)
        collect(page, "booking/step4", found, counts)

        # 보호자 시트
        nav_tab(page, "mypage")
        page.eval_on_selector("#mpBookLink", "el => el.click()")
        page.wait_for_timeout(280)
        collect(page, "accountSheet", found, counts)
        if page.eval_on_selector_all("[data-manage]", "els => els.length"):
            page.eval_on_selector("[data-manage]", "el => el.click()")
            page.wait_for_timeout(300)
            collect(page, "manageSheet", found, counts)
            close_all(page)
        page.eval_on_selector("#mpNotifRow", "el => el.click()")
        page.wait_for_timeout(280)
        collect(page, "notifSheet", found, counts)
        close_all(page)
        page.eval_on_selector("#mpCouponRow", "el => el.click()")
        page.wait_for_timeout(260)
        collect(page, "couponSheet", found, counts)
        close_all(page)
        page.eval_on_selector("#mpFaqRow", "el => el.click()")
        page.wait_for_timeout(300)
        collect(page, "faqSheet", found, counts)
        close_all(page)
        page.eval_on_selector("#mpGuideLink", "el => el.click()")
        page.wait_for_timeout(260)
        collect(page, "guideSheet", found, counts)
        close_all(page)
        page.eval_on_selector("#mpPayRow", "el => el.click()")
        page.wait_for_timeout(260)
        collect(page, "paySheet", found, counts)
        close_all(page)

        nav_tab(page, "journal")
        if page.is_visible("[data-safety-open]"):
            page.eval_on_selector("[data-safety-open]", "el => el.click()")
            page.wait_for_timeout(280)
            collect(page, "safetySheet", found, counts)
            close_all(page)
        if page.is_visible("#weeklyOpen"):
            page.eval_on_selector("#weeklyOpen", "el => el.click()")
            page.wait_for_timeout(300)
            collect(page, "weeklySheet", found, counts)
            close_all(page)
        if page.is_visible("#reportOpen"):
            page.eval_on_selector("#reportOpen", "el => el.click()")
            page.wait_for_timeout(320)
            collect(page, "reportSheet", found, counts)
            close_all(page)

        # 선생님 상세
        nav_tab(page, "teachers")
        page.eval_on_selector("#teacherList .teacher", "el => el.click()")
        page.wait_for_timeout(320)
        collect(page, "teacherSheet", found, counts)
        close_all(page)
        page.eval_on_selector('#teacherViewTabs [data-view="near"]', "el => el.click()")
        page.wait_for_timeout(340)
        collect(page, "teachers/near", found, counts)
        page.eval_on_selector('#teacherViewTabs [data-view="list"]', "el => el.click()")
        page.wait_for_timeout(220)

        # 선생님 모드
        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(140)
        page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
        page.wait_for_timeout(400)
        for tab in ["tp-home", "tp-schedule", "tp-journal", "tp-settle", "tp-mypage"]:
            nav_tab(page, tab)
            collect(page, "partner/" + tab, found, counts)
        nav_tab(page, "tp-settle")
        if page.eval_on_selector_all("#tpsScreen [data-stl-preview]", "els => els.length"):
            page.eval_on_selector("#tpsScreen [data-stl-preview]", "el => el.click()")
            page.wait_for_timeout(360)
            collect(page, "settlementPrintSheet", found, counts)
            close_all(page)
        if page.eval_on_selector_all("[data-tp-noti-open]", "els => els.length"):
            page.eval_on_selector("[data-tp-noti-open]", "el => el.click()")
            page.wait_for_timeout(320)
            collect(page, "tpNotiSheet", found, counts)
            close_all(page)

        # 관리자
        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(140)
        page.eval_on_selector('[data-login="admin"]', "el => el.click()")
        page.wait_for_timeout(460)
        collect(page, "admin", found, counts)
        page.eval_on_selector('#adminMetricsPeriods [data-metrics-period="7d"]', "el => el.click()")
        page.wait_for_timeout(280)
        collect(page, "admin/7d", found, counts)
        page.eval_on_selector('#adminMetricsPeriods [data-metrics-period="all"]', "el => el.click()")
        page.wait_for_timeout(240)

        # 인쇄 문서 5종(정산서·정산 화면·관리자·방문 일지·주간 리포트)
        page.evaluate("() => window.__ttokttokPrint && window.__ttokttokPrint.frame && window.__ttokttokPrint.frame()")
        page.wait_for_timeout(200)
        for doc in ["settlement", "settle", "admin", "journal", "weekly"]:
            try:
                page.evaluate("(d) => window.__ttokttokPrint && window.__ttokttokPrint.build && window.__ttokttokPrint.build(d)", doc)
                page.wait_for_timeout(420)
                collect(page, "print/" + doc, found, counts)
            except Exception:
                pass

        browser.close()

    with open(os.path.join(OUT, "scan.json"), "w", encoding="utf-8") as f:
        json.dump({"states": counts, "hits": found}, f, ensure_ascii=False, indent=1)

    # 요약: 종류별 건수 + 예시
    by_kind = {}
    for item in found:
        if "hit" not in item:
            continue
        k = item["hit"]["kind"]
        by_kind.setdefault(k, []).append(item)
    print("화면 %d곳 · 글자 노드 %d개 · 어긋난 표기 %d건" % (len(counts), sum(counts.values()), len([x for x in found if 'hit' in x])))
    empty = [k for k, v in counts.items() if v < 3]
    if empty:
        print("  (글자가 거의 없는 상태: %s)" % ", ".join(empty))
    for k, items in sorted(by_kind.items(), key=lambda x: -len(x[1])):
        print("\n== %s (%d) — %s" % (k, len(items), items[0]["hit"]["desc"]))
        seen = set()
        for it in items:
            key = it["hit"]["match"] + "|" + it["state"]
            if key in seen:
                continue
            seen.add(key)
            print("   [%s] %r %s :: %s" % (it["state"], it["hit"]["match"], it["el"], it["text"][:90]))
            if len(seen) >= 40:
                print("   …")
                break
    return found


if __name__ == "__main__":
    hits = [x for x in run() if "hit" in x]
    if "--gate" in sys.argv:
        allow = set(x.strip() for x in os.environ.get("V51_ALLOW", "").split(",") if x.strip())
        bad = [x for x in hits if x["hit"]["kind"] not in allow]
        print("\n게이트: 어긋난 표기 %d건" % len(bad))
        sys.exit(1 if bad else 0)
