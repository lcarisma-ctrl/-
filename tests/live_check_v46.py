#!/usr/bin/env python3
"""v46 라이브 실브라우저 확인 — 1280/768/390/320 · 2단·상세 열·시작 화면 수납·다크."""
import hashlib
import os
import urllib.request

os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://lcarisma-ctrl.github.io/-/?v=46"
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


def no_overflow(pg):
    m = pg.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
    return m["sw"] <= m["cw"] + 1, m


def box(pg, sel):
    return pg.evaluate("""(s) => { const el = document.querySelector(s); if (!el) return null;
      const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), r: Math.round(r.right), b: Math.round(r.bottom)}; }""", sel)


# 0) 파일 자체
local = open(os.path.join(ROOT, "index.html"), "rb").read()
live = urllib.request.urlopen(URL, timeout=30).read()
ok("live ?v=46 HTTP 200 · byte 동일", len(live) == len(local), "%d vs %d" % (len(live), len(local)))
ok("live md5 로컬과 일치", hashlib.md5(live).hexdigest() == hashlib.md5(local).hexdigest(),
   hashlib.md5(live).hexdigest())

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])

    def open_page(w, h, mobile, theme=None):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1 if w >= 768 else 2,
                            is_mobile=mobile, has_touch=mobile, locale="ko-KR")
        if theme:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        pg.goto(URL + "&intro=0")
        pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000)
        pg.wait_for_timeout(600)
        return ctx, pg, errs

    # 1) 데스크톱 1280
    ctx, pg, errs = open_page(1280, 900, False)
    ok("live v46 meta", pg.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v46")
    app = box(pg, "#appRoot")
    ok("live 1280 작업면 1,180px", abs(app["w"] - 1180) <= 2, app)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(1200)
    ok("live 1280 홈 가로 넘침 없음", no_overflow(pg)[0], no_overflow(pg)[1])
    pg.screenshot(path=os.path.join(OUT, "live_v46_1280_home.png"))
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()")
    pg.wait_for_timeout(600)
    ok("live 1280 선생님 3칸(레일 288)", abs(box(pg, "#teacherSideCol")["w"] - 288) <= 2, box(pg, "#teacherSideCol"))
    pg.eval_on_selector("#teacherList .teacher", "el=>el.click()")
    pg.wait_for_timeout(700)
    ok("live 1280 카드 → 오른쪽 프로필 열", pg.evaluate("() => !document.getElementById('teacherPane').hidden"))
    ok("live 1280 프로필 열 348px", abs(box(pg, "#teacherPane")["w"] - 348) <= 2, box(pg, "#teacherPane"))
    ok("live 1280 시트는 겹쳐 뜨지 않음", not pg.evaluate("() => document.getElementById('teacherSheet').classList.contains('is-open')"))
    pg.screenshot(path=os.path.join(OUT, "live_v46_1280_teachers_pane.png"))
    pg.eval_on_selector("[data-pane-open]", "el=>el.click()")
    pg.wait_for_timeout(600)
    ok("live 1280 전체 프로필 → 시트 600px", abs(box(pg, "#teacherSheet .sheet")["w"] - 600) <= 2, box(pg, "#teacherSheet .sheet"))
    pg.screenshot(path=os.path.join(OUT, "live_v46_1280_teacher_sheet.png"))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]', "el=>el.click()")
    pg.wait_for_timeout(500)
    a, c = box(pg, "#journalSideCol"), box(pg, "#journalMainCol")
    ok("live 1280 일지 2단", a and c and a["r"] <= c["x"] + 2, [a, c])
    pg.screenshot(path=os.path.join(OUT, "live_v46_1280_journal.png"))
    ok("live 1280 오류 0", not errs, errs[:2])
    ctx.close()

    # 2) 태블릿 768
    ctx, pg, errs = open_page(768, 1024, True)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(900)
    ok("live 768 앱 720px", abs(box(pg, "#appRoot")["w"] - 720) <= 2, box(pg, "#appRoot"))
    ok("live 768 탭바 720px", abs(box(pg, '.tabbar[data-mode="customer"]')["w"] - 720) <= 2)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()")
    pg.wait_for_timeout(500)
    pg.eval_on_selector("#teacherList .teacher", "el=>el.click()")
    pg.wait_for_timeout(600)
    ok("live 768 시트 640px", abs(box(pg, "#teacherSheet .sheet")["w"] - 640) <= 2, box(pg, "#teacherSheet .sheet"))
    pg.screenshot(path=os.path.join(OUT, "live_v46_768_teacher_sheet.png"))
    ok("live 768 오류 0", not errs, errs[:2])
    ctx.close()

    # 3) 390 — 기존 1단 그대로
    ctx, pg, errs = open_page(390, 844, True)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(900)
    ok("live 390 1단(묶음 display:contents)",
       pg.evaluate("() => getComputedStyle(document.getElementById('teacherSideCol')).display") == "contents")
    ok("live 390 앱 폭 390", abs(box(pg, "#appRoot")["w"] - 390) <= 1, box(pg, "#appRoot"))
    ok("live 390 가로 넘침 없음", no_overflow(pg)[0], no_overflow(pg)[1])
    pg.screenshot(path=os.path.join(OUT, "live_v46_390_home.png"))
    ok("live 390 오류 0", not errs, errs[:2])
    ctx.close()

    # 4) 320 시작 화면 — 고지까지 한 화면
    ctx, pg, errs = open_page(320, 568, True)
    fit = pg.evaluate("""() => { const g = document.getElementById('entryGate'); const l = document.querySelector('.gate-legal');
      return {sh: g.scrollHeight, ch: g.clientHeight, bottom: Math.round(l.getBoundingClientRect().bottom), vh: window.innerHeight}; }""")
    ok("live 320 시작 화면 스크롤 0", fit["sh"] <= fit["ch"] + 1, fit)
    ok("live 320 법적 고지까지 화면 안", fit["bottom"] <= fit["vh"] + 1, fit)
    pg.screenshot(path=os.path.join(OUT, "live_v46_320_gate.png"))
    ok("live 320 오류 0", not errs, errs[:2])
    ctx.close()

    # 5) 데스크톱 다크
    ctx, pg, errs = open_page(1280, 900, False, theme="dark")
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(1100)
    lights = pg.evaluate("""() => [...document.querySelectorAll('#screen-home .card, #screen-home .home-hero')]
      .filter(el => /255, 255, 255/.test(getComputedStyle(el).backgroundColor)).length""")
    ok("live 1280 다크 흰 카드 0", lights == 0, lights)
    pg.screenshot(path=os.path.join(OUT, "live_v46_1280_dark_home.png"))
    ok("live 1280 다크 오류 0", not errs, errs[:2])
    ctx.close()
    b.close()

print("\nLIVE v46 RESULT: %d passed, %d failed" % (ok_n, len(fails)))
for f in fails:
    print(" - " + f)
