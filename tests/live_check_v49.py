#!/usr/bin/env python3
"""v49 라이브 실브라우저 확인 — 카드 열기/찜 분리·.btn-sm 경계·정산 인쇄 머리글·시트 스크롤 복원.

실행: python3 tests/live_check_v49.py
결과물: preview/live_v49_*.png
"""
import hashlib
import os
import urllib.request

os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://lcarisma-ctrl.github.io/-/"
URL = BASE + "?v=49"
OUT = os.path.join(ROOT, "preview")
ok_n = 0
fails = []


def ok(name, cond, extra=""):
    global ok_n
    if cond:
        ok_n += 1
        print("  ✓", name)
    else:
        fails.append("%s :: %s" % (name, extra))
        print("  ✗", name, "::", extra)


# 0) 파일 자체 — HTTP 200 · 로컬과 같은 바이트
local = open(os.path.join(ROOT, "index.html"), "rb").read()
live = urllib.request.urlopen(URL, timeout=30).read()
ok("live ?v=49 HTTP 200 · byte 동일", len(live) == len(local), "%d vs %d" % (len(live), len(local)))
md5 = hashlib.md5(live).hexdigest()
ok("live md5 로컬과 일치", md5 == hashlib.md5(local).hexdigest(), md5)
ok("live meta v49", b'content="v49"' in live)
ok("live v49 훅 포함", b"data-teacher-open" in live and b"printRunnerTitle" in live and b"__ttokttokSheetScroll" in live)
for v in (48, 47, 46):
    try:
        r = urllib.request.urlopen(BASE + "?v=%d" % v, timeout=30)
        ok("이전 버전 ?v=%d HTTP 200" % v, r.status == 200, r.status)
    except Exception as e:
        ok("이전 버전 ?v=%d HTTP 200" % v, False, str(e)[:60])

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])

    def make(w, h, mob, theme=None):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 900 else 1,
                            is_mobile=mob, has_touch=mob, locale="ko-KR")
        if theme:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def enter(page, role, tab=None, mode=None):
        page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
        page.wait_for_timeout(250)
        page.eval_on_selector('[data-login="%s"]' % role, "el => el.click()")
        page.wait_for_timeout(600)
        if tab:
            page.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode or "customer", tab), "el => el.click()")
            page.wait_for_timeout(450)

    # 1) 375 — 카드 구조·Tab 순서·하트·스크롤 복원
    ctx, page, errs = make(375, 812, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    st = page.evaluate("""() => ({n: document.querySelectorAll('#teacherList .teacher').length,
      role: document.querySelectorAll('#teacherList .teacher[role]').length,
      tab: document.querySelectorAll('#teacherList .teacher[tabindex]').length,
      openers: document.querySelectorAll('#teacherList .teacher .t-open').length,
      nested: window.__ttokttokRoving.nestedButtons(), stops: window.__ttokttokRoving.tabStops()})""")
    ok("live 카드 8·role 0·카드 tabindex 0", st["n"] == 8 and st["role"] == 0 and st["tab"] == 0, st)
    ok("live 열기 버튼 8개·중첩 0·정지점 1", st["openers"] == 8 and st["nested"] == 0 and st["stops"] == 1, st)
    page.evaluate("() => { const c = [...document.querySelectorAll('#regionFilters .chip')]; c[c.length - 1].focus(); }")
    page.keyboard.press("Tab")
    page.wait_for_timeout(220)
    a1 = page.evaluate("() => ({cls: document.activeElement.className, card: document.activeElement.closest('.teacher') && document.activeElement.closest('.teacher').getAttribute('data-teacher')})")
    ok("live Tab 한 번에 카드 열기 버튼", a1["cls"] == "t-open" and a1["card"] == "park", a1)
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    ok("live 그다음 Tab은 하트", page.evaluate("() => !!document.activeElement.closest('[data-fav]')"))
    page.evaluate("() => document.querySelector('#teacherList .teacher .t-fav').click()")
    page.wait_for_timeout(250)
    h = page.evaluate("""() => ({fav: document.querySelector('#teacherList .teacher .t-fav').getAttribute('aria-pressed'),
      sheet: document.getElementById('teacherSheet').classList.contains('is-open')})""")
    ok("live 하트 클릭은 찜만", h["fav"] == "true" and h["sheet"] is False, h)
    page.screenshot(path=os.path.join(OUT, "live_v49_375_teachers.png"))
    # 스크롤 복원
    page.evaluate("() => window.scrollTo(0, 900)")
    page.wait_for_timeout(250)
    y0 = page.evaluate("() => window.scrollY")
    page.evaluate("() => document.querySelectorAll('#teacherList .t-open')[3].click()")
    page.wait_for_timeout(400)
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(150)
    page.evaluate("() => document.querySelector('#teacherSheet .sheet-close').click()")
    page.wait_for_timeout(400)
    y1 = page.evaluate("() => window.scrollY")
    ok("live 시트를 닫으면 보던 스크롤 자리로", y0 > 100 and abs(y1 - y0) <= 2, [y0, y1])
    ok("live 375 오류 0", not errs, errs[:2])
    ctx.close()

    # 2) 다크 375 — 같은 구조·경계
    ctx, page, errs = make(375, 812, True, theme="dark")
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    ok("live 다크 카드·하트 구조 유지", page.evaluate("() => document.querySelectorAll('#teacherList .t-open').length === 8 && window.__ttokttokRoving.nestedButtons() === 0"))
    page.screenshot(path=os.path.join(OUT, "live_v49_375_dark_teachers.png"))
    ok("live 다크 오류 0", not errs, errs[:2])
    ctx.close()

    # 3) 1280 — 방향키·프로필 열
    ctx, page, errs = make(1280, 900, False)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    page.evaluate("() => document.querySelector('#teacherList .t-open').focus()")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(320)
    ok("live 1280 ↓ 다음 카드 + 프로필 열", page.evaluate("""() => { const a = document.activeElement;
      return !!(a.closest('.teacher') && a.closest('.teacher').getAttribute('data-teacher') === 'lee' &&
        !document.getElementById('teacherPane').hidden); }"""))
    page.screenshot(path=os.path.join(OUT, "live_v49_1280_kbd.png"))
    ok("live 1280 오류 0", not errs, errs[:2])
    ctx.close()

    # 4) 인쇄 — 정산서 머리글·회차 통째로 + 관리자 콘솔 숨은 섹션 0
    ctx, page, errs = make(390, 844, True)
    page.goto(URL + "?intro=0")
    enter(page, "therapist", "tp-settle", "therapist")
    page.evaluate("() => { const b = document.querySelector('[data-stl-preview]'); if (b) b.click(); }")
    page.wait_for_timeout(500)
    page.emulate_media(media="print")
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    page.wait_for_timeout(350)
    pr = page.evaluate("""() => { const rows = [...document.querySelectorAll('#settlementPrintBody [data-print-row]')];
      return {rows: rows.length, brk: rows.length ? getComputedStyle(rows[0]).breakInside : '',
        runner: document.getElementById('printRunnerTitle').textContent,
        note: document.getElementById('printRunnerNote').textContent,
        runnerDisp: getComputedStyle(document.getElementById('printRunner')).display}; }""")
    ok("live 정산서 회차 쪽나눔 잠금", pr["rows"] > 0 and pr["brk"] == "avoid", pr)
    ok("live 종이 머리글에 문서·월·선생님", "정산 명세서" in pr["runner"] and "2026년 11월" in pr["runner"] and "선생님" in pr["runner"], pr["runner"])
    ok("live 종이 머리에 발급일·시연용", "발급" in pr["note"] and "시연용" in pr["note"], pr["note"])
    ok("live 종이 머리글 표시", pr["runnerDisp"] == "flex", pr["runnerDisp"])
    page.screenshot(path=os.path.join(OUT, "live_v49_settle_print.png"))
    page.emulate_media(media="screen")
    page.evaluate("() => window.dispatchEvent(new Event('afterprint'))")
    ctx.close()

    ctx, page, errs = make(1280, 900, False)
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(700)
    page.emulate_media(media="print")
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    page.wait_for_timeout(350)
    adm = page.evaluate("""() => { const scr = document.getElementById('screen-admin');
      const rev = [...scr.querySelectorAll('.tt-reveal')];
      const cols = scr.querySelector('.tt46-cols');
      return {hidden: rev.filter((el) => parseFloat(getComputedStyle(el).opacity) < 0.99).length,
        cols: cols ? getComputedStyle(cols).display : 'missing',
        runner: document.getElementById('printRunnerTitle').textContent}; }""")
    ok("live 관리자 콘솔 인쇄에 숨은 섹션 0", adm["hidden"] == 0, adm)
    ok("live 관리자 콘솔은 종이에서 한 줄", adm["cols"] == "block", adm["cols"])
    page.screenshot(path=os.path.join(OUT, "live_v49_admin_print.png"))
    page.emulate_media(media="screen")
    ctx.close()

    # 5) 요약 카드 보조 버튼 경계 3:1
    ctx, page, errs = make(375, 812, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer")
    bd = page.evaluate("""() => { const el = document.querySelector('#homeSummaryRebook .btn-outline.btn-sm'); if (!el) return null;
      const cs = getComputedStyle(el);
      const parse = (c) => { const m = String(c).match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
        const p = m[1].split(/[\\s,\\/]+/).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
      const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
      const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
      return {bw: parseFloat(cs.borderTopWidth) || 0, cr: Math.round(ratio(parse(cs.borderTopColor), parse('rgb(255,255,255)')) * 100) / 100,
        h: Math.round(el.getBoundingClientRect().height)}; }""")
    ok("live 요약 보조 버튼 1px 경계·3:1·44px", bd and bd["bw"] >= 1 and bd["cr"] >= 3 and bd["h"] >= 44, bd)
    page.screenshot(path=os.path.join(OUT, "live_v49_375_home.png"))
    ok("live 홈 오류 0", not errs, errs[:2])
    ctx.close()
    b.close()

print("\nRESULT: %d passed, %d failed" % (ok_n, len(fails)))
if fails:
    for f in fails:
        print(" - " + f)
    raise SystemExit(1)
