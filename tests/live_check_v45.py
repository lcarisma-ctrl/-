#!/usr/bin/env python3
"""v45 라이브 실브라우저 확인 — 라이트/다크·테마 전환·오류·넘침."""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=45"
OUT = "/workspace/projects/ttokttok-app/preview"
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


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])

    # 1) 라이트(기본)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL + "&intro=0")
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000)
    pg.wait_for_timeout(500)
    ok("live v45 meta", pg.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v45",
       pg.evaluate("() => document.querySelector('meta[name=app-version]').content"))
    ok("live 기본 테마 라이트", pg.evaluate("() => document.documentElement.getAttribute('data-theme')") == "light")
    ok("live 테마 훅", pg.evaluate("() => window.__ttokttokTheme && window.__ttokttokTheme.version") == "v45")
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(1800)
    ok("live 라이트 홈 카드 흰색", pg.evaluate("() => getComputedStyle(document.querySelector('#homePassCard')).backgroundColor") == "rgb(255, 255, 255)")
    pg.screenshot(path=os.path.join(OUT, "live_v45_light_home.png"))
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]', "el=>el.click()")
    pg.wait_for_timeout(600)
    pg.eval_on_selector('#mpThemeCard', "el=>el.scrollIntoView({block:'center'})")
    pg.wait_for_timeout(600)
    pg.evaluate("()=>{document.querySelectorAll('.toast').forEach(e=>e.remove())}")
    pg.screenshot(path=os.path.join(OUT, "live_v45_light_theme_card.png"))
    # 테마 바꾸기(라이브)
    pg.eval_on_selector('#mpTheme [data-theme-opt=dark]', "el=>el.click()")
    pg.wait_for_timeout(700)
    ok("live 다크 전환", pg.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark")
    ok("live 다크 카드 면", pg.evaluate("() => getComputedStyle(document.querySelector('#mpThemeCard')).backgroundColor") == "rgb(21, 29, 41)",
       pg.evaluate("() => getComputedStyle(document.querySelector('#mpThemeCard')).backgroundColor"))
    ok("live 다크 저장", pg.evaluate("() => localStorage.getItem('ttokttok_theme_v1')") == "dark")
    ok("live 다크 주소창 색", pg.evaluate("() => document.querySelector('meta[name=theme-color]').content") == "#0B1119")
    pg.evaluate("()=>{document.querySelectorAll('.toast').forEach(e=>e.remove())}")
    pg.add_style_tag(content="*,*::before,*::after{transition:none!important;animation:none!important}")
    pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(OUT, "live_v45_dark_theme_card.png"))
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=home]', "el=>el.click()")
    pg.wait_for_timeout(700)
    ok("live 다크 홈 넘침 없음", pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
    pg.screenshot(path=os.path.join(OUT, "live_v45_dark_home.png"))
    # 새로고침 유지
    pg.reload()
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000)
    pg.wait_for_timeout(500)
    ok("live 새로고침 후 다크 유지", pg.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark")
    ok("live 오류 0", not errs, errs[:2])
    ctx.close()

    # 2) 기기 다크 · 시스템 선택
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    pg.emulate_media(color_scheme="dark")
    pg.goto(URL + "&intro=0")
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000)
    pg.wait_for_timeout(400)
    ok("live 기기 다크 → 시스템이 다크로", pg.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark")
    ctx.close()

    # 3) 320 다크
    ctx = b.new_context(viewport={"width": 320, "height": 568}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','dark')}catch(e){}")
    pg = ctx.new_page()
    pg.goto(URL + "&intro=0")
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=30000)
    pg.wait_for_timeout(500)
    ok("live 320 다크 넘침 없음", pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
    pg.screenshot(path=os.path.join(OUT, "live_v45_dark_320_gate.png"))
    ctx.close()
    b.close()

print("\nLIVE RESULT: %d passed, %d failed" % (ok_n, len(fails)))
for f in fails:
    print(" - " + f)
