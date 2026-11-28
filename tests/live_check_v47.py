#!/usr/bin/env python3
"""v47 라이브 실브라우저 확인 — 1280 3칸 방향키·프로필 열, 스켈레톤(흔들림 0), 1024·768·390·320."""
import hashlib
import os
import urllib.request

os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://lcarisma-ctrl.github.io/-/"
URL = BASE + "?v=47"
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


def box(pg, sel):
    return pg.evaluate("""(s) => { const el = document.querySelector(s); if (!el) return null;
      const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width),
      h: Math.round(r.height), r: Math.round(r.right), b: Math.round(r.bottom)}; }""", sel)


# 0) 파일 자체
local = open(os.path.join(ROOT, "index.html"), "rb").read()
live = urllib.request.urlopen(URL, timeout=30).read()
ok("live ?v=47 HTTP 200 · byte 동일", len(live) == len(local), "%d vs %d" % (len(live), len(local)))
ok("live md5 로컬과 일치", hashlib.md5(live).hexdigest() == hashlib.md5(local).hexdigest(),
   hashlib.md5(live).hexdigest())
ok("live meta v47", b'content="v47"' in live)
for old in ("45", "46"):
    m = urllib.request.urlopen(BASE + "?v=" + old, timeout=30)
    ok("live ?v=%s도 200" % old, m.status == 200, m.status)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])

    def open_page(w, h, mobile, theme=None, query="&intro=0"):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if w >= 768 else 2,
                            is_mobile=mobile, has_touch=mobile, locale="ko-KR")
        if theme:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        pg.goto(BASE + "?v=47" + query)
        pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000)
        pg.wait_for_timeout(600)
        return ctx, pg, errs

    def enter(pg, role="customer", tab=None, mode="customer"):
        pg.eval_on_selector('[data-login="%s"]' % role, "el => el.click()")
        pg.wait_for_timeout(700)
        if tab:
            pg.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode, tab), "el => el.click()")
            pg.wait_for_timeout(500)

    # ── 1) 1280: 3칸·방향키·빈 자리 안내 ─────────────────────────
    ctx, pg, errs = open_page(1280, 900, False)
    enter(pg, tab="teachers")
    ok("1280 키보드 안내 보임", pg.evaluate("() => getComputedStyle(document.getElementById('teacherKbdHint')).display") == "flex")
    ok("1280 안내 문구", all(t in pg.inner_text("#teacherKbdHint") for t in ["카드 이동", "프로필 열기", "닫기"]))
    ok("1280 빈 자리 안내 보임", pg.evaluate(
        "() => getComputedStyle(document.getElementById('teacherPaneEmpty')).display") == "flex" and
        pg.evaluate("() => document.getElementById('teacherPane').hidden"))
    ok("1280 상세 열 폭 348", 330 <= (box(pg, "#teacherPaneEmpty") or {"w": 0})["w"] <= 360, box(pg, "#teacherPaneEmpty"))
    names = pg.evaluate("() => [...document.querySelectorAll('#teacherList .teacher')].map(e => e.getAttribute('data-teacher'))")
    pg.eval_on_selector("#teacherList .teacher", "el => el.focus()")
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(400)
    st = pg.evaluate("""() => ({focused: document.activeElement.getAttribute('data-teacher'),
      pane: !document.getElementById('teacherPane').hidden,
      text: document.getElementById('teacherPane').innerText,
      live: document.getElementById('teacherNavLive').textContent})""")
    ok("1280 ↓로 다음 카드·열 갱신", st["focused"] == names[1] and st["pane"] and "이하늘" in st["text"], st)
    ok("1280 이동 낭독(2/8)", "2/8" in st["live"], st["live"])
    pg.keyboard.press("End")
    pg.wait_for_timeout(350)
    ok("1280 End는 마지막 카드", pg.evaluate("() => document.activeElement.getAttribute('data-teacher')") == names[-1])
    pg.keyboard.press("Home")
    pg.wait_for_timeout(350)
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(300)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(350)
    ok("1280 Enter는 열 안으로 초점", pg.evaluate("() => document.getElementById('teacherPane').contains(document.activeElement)"))
    pg.screenshot(path=os.path.join(OUT, "live_v47_1280_kbd.png"))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(350)
    ok("1280 Esc는 열 닫고 카드로", pg.evaluate("() => document.getElementById('teacherPane').hidden") and
       pg.evaluate("() => document.activeElement.getAttribute('data-teacher')") == names[1])
    ok("1280 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 2) 1280 다크 + 스켈레톤(라이브 ?skel=1) ──────────────────
    ctx, pg, errs = open_page(1280, 900, False, theme="dark", query="&intro=0&skel=1&skelms=2000")
    enter(pg, tab="teachers")
    pg.wait_for_timeout(250)
    sk = pg.evaluate("""() => ({n: document.querySelectorAll('#teacherList .teacher.is-skel').length,
      busy: document.getElementById('teacherList').getAttribute('aria-busy'),
      bg: (() => { const e = document.querySelector('#teacherList .tt-skel'); return e ? getComputedStyle(e).backgroundColor : null; })()})""")
    ok("1280 다크 스켈레톤 8장", sk["n"] == 8, sk)
    ok("1280 스켈레톤 중 aria-busy", sk["busy"] == "true", sk)
    ok("1280 다크 막대는 흰색이 아니다", sk["bg"] and "255, 255, 255" not in sk["bg"], sk)
    pg.screenshot(path=os.path.join(OUT, "live_v47_1280_dark_skel.png"))
    pg.wait_for_timeout(2100)
    ok("1280 지연 뒤 실제 카드", pg.evaluate(
        "() => document.querySelectorAll('#teacherList .is-skel').length === 0") and
        "박서준" in pg.inner_text("#teacherList"))
    ok("1280 다크 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 3) 1024: 레일 + 두 열, 안내 숨김 ─────────────────────────
    ctx, pg, errs = open_page(1024, 900, False)
    enter(pg, tab="teachers")
    ok("1024 안내 숨김", pg.evaluate("() => getComputedStyle(document.getElementById('teacherKbdHint')).display") == "none")
    ok("1024 상세 열 없음", pg.evaluate("() => getComputedStyle(document.getElementById('teacherPane')).display") == "none")
    cols = pg.evaluate("""() => { const els = [...document.querySelectorAll('#teacherList .teacher')];
      const top = Math.min(...els.map(e => Math.round(e.getBoundingClientRect().top)));
      return [...new Set(els.filter(e => Math.abs(Math.round(e.getBoundingClientRect().top) - top) < 6)
        .map(e => Math.round(e.getBoundingClientRect().x)))].length; }""")
    ok("1024 카드 두 열", cols == 2, cols)
    pg.screenshot(path=os.path.join(OUT, "live_v47_1024_teachers.png"))
    ok("1024 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 4) 768 · 390 · 320 ──────────────────────────────────────
    for w, h, mob in ((768, 1024, True), (390, 844, True), (320, 568, True)):
        ctx, pg, errs = open_page(w, h, mob)
        enter(pg, tab="teachers")
        ok("%d 안내 숨김" % w, pg.evaluate("() => getComputedStyle(document.getElementById('teacherKbdHint')).display") == "none")
        ov = pg.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        ok("%d 가로 넘침 0" % w, ov["sw"] <= ov["cw"] + 1, ov)
        ok("%d 카드 8명" % w, pg.evaluate("() => document.querySelectorAll('#teacherList .teacher').length") == 8)
        if w == 390:
            pg.screenshot(path=os.path.join(OUT, "live_v47_390_teachers.png"))
        ok("%d 오류 0" % w, not errs, errs[:2])
        ctx.close()

    b.close()

print("\nRESULT: %d passed, %d failed" % (ok_n, len(fails)))
if fails:
    for f in fails:
        print(" - " + f)
    raise SystemExit(1)
