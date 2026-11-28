#!/usr/bin/env python3
"""v46 캡처 — 데스크톱 2단 레이아웃·태블릿·320 시작 화면.

사용: python3 tests/_shots_v46.py before|after [outdir]
  before → 기본값 preview/v46-audit/before/   after → preview/v46-audit/after/
"""
import os
import sys

os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
TAG = sys.argv[1] if len(sys.argv) > 1 else "after"
OUT = os.path.join(ROOT, "preview", "v46-audit", TAG)
if len(sys.argv) > 2:
    OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)


def boot(b, w, h, mobile, theme=None):
    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 900 else 1,
                        is_mobile=mobile, has_touch=mobile, locale="ko-KR")
    if theme:
        ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
    pg = ctx.new_page()
    pg.goto(URL)
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
    pg.wait_for_timeout(2600)
    return pg


def snap(pg, name):
    pg.screenshot(path=os.path.join(OUT, name + ".png"))


def run(p, w, h, mobile, label, theme=None):
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    pg = boot(b, w, h, mobile, theme)
    snap(pg, "%s_gate" % label)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(1000)
    snap(pg, "%s_home" % label)
    for tab in ["teachers", "booking", "journal", "mypage"]:
        pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=%s]' % tab, "el=>el.click()")
        pg.wait_for_timeout(500)
        snap(pg, "%s_%s" % (label, tab))
    # 선생님 상세 시트
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()")
    pg.wait_for_timeout(300)
    pg.eval_on_selector('#teacherList [data-teacher]', "el=>el.click()")
    pg.wait_for_timeout(600)
    snap(pg, "%s_teacher_sheet" % label)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(350)
    # 관리자
    pg.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    pg.wait_for_timeout(150)
    pg.eval_on_selector('[data-login="admin"]', "el=>el.click()")
    pg.wait_for_timeout(900)
    snap(pg, "%s_admin" % label)
    pg.evaluate("()=>window.scrollTo(0, 900)")
    pg.wait_for_timeout(400)
    snap(pg, "%s_admin_scrolled" % label)
    # 선생님 모드 정산
    pg.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    pg.wait_for_timeout(150)
    pg.eval_on_selector('[data-login="therapist"]', "el=>el.click()")
    pg.wait_for_timeout(700)
    pg.eval_on_selector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-settle]', "el=>el.click()")
    pg.wait_for_timeout(600)
    snap(pg, "%s_settle" % label)
    pg.eval_on_selector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-home]', "el=>el.click()")
    pg.wait_for_timeout(400)
    snap(pg, "%s_tp_home" % label)
    pg.context.close()
    b.close()


with sync_playwright() as p:
    run(p, 1440, 900, False, "1440")
    run(p, 1280, 800, False, "1280")
    run(p, 1024, 768, False, "1024")
    run(p, 768, 1024, True, "768")
    run(p, 390, 844, True, "390")
    run(p, 320, 568, True, "320")
    run(p, 1280, 800, False, "1280_dark", theme="dark")
print("done ->", OUT)
