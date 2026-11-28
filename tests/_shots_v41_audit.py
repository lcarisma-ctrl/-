#!/usr/bin/env python3
"""v41 감사용 화면 캡처 — preview/v41-audit/{before}/{width}_{state}.png

사용:  python3 tests/_shots_v41_audit.py before
       python3 tests/_shots_v41_audit.py after
"""
import os, sys
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
TAG = sys.argv[1] if len(sys.argv) > 1 else "before"
OUT = os.path.join(ROOT, "preview", "v41-audit", TAG)
os.makedirs(OUT, exist_ok=True)

# (state name, prep JS run after login)
CUSTOMER = [
    ("home", "() => {}"),
    ("teachers", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click()"),
    ("teacher_detail", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click(); setTimeout(()=>{const c=document.querySelector('[data-teacher]'); if(c)c.click();},250); }"),
    ("booking1", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]').click(); }"),
    ("journal", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click()"),
    ("weekly", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click(); setTimeout(()=>{const b=document.querySelector('#weeklyOpen'); if(b)b.click();},300); }"),
    ("mypage", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]').click()"),
]
PARTNER = [
    ("tp_home", "() => {}"),
    ("tp_schedule", "() => document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-schedule]').click()"),
    ("tp_journal", "() => document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-journal]').click()"),
    ("tp_settle", "() => document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-settle]').click()"),
    ("tp_mypage", "() => document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-mypage]').click()"),
]
ADMIN = [
    ("admin", "() => {}"),
]


def shot(b, width, height, mob, name, prep, login):
    ctx = b.new_context(viewport={"width": width, "height": height},
                        device_scale_factor=2 if mob else 1, is_mobile=mob, has_touch=mob, locale="ko-KR")
    pg = ctx.new_page()
    pg.goto(URL)
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
    pg.wait_for_timeout(350)
    if name == "gate":
        pg.screenshot(path=os.path.join(OUT, "%d_gate.png" % width))
        pg.close(); ctx.close(); return
    if login == "therapist":
        pg.eval_on_selector('[data-login="therapist"]', "el=>el.click()")
    elif login == "admin":
        pg.eval_on_selector('[data-login="admin"]', "el=>el.click()")
    else:
        pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
    pg.wait_for_timeout(600)
    pg.evaluate(prep)
    pg.wait_for_timeout(3200)
    pg.screenshot(path=os.path.join(OUT, "%d_%s.png" % (width, name)))
    # full-page (long) capture for scroll audit
    if name in ("home", "teachers", "tp_home", "admin", "journal"):
        try:
            pg.screenshot(path=os.path.join(OUT, "%d_%s_full.png" % (width, name)), full_page=True)
        except Exception:
            pass
    pg.close()
    ctx.close()


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
    for width, height, mob in [(390, 844, True), (1280, 900, False)]:
        shot(b, width, height, mob, "gate", "() => {}", "none")
        for n, js in CUSTOMER:
            shot(b, width, height, mob, n, js, "customer")
        for n, js in PARTNER:
            shot(b, width, height, mob, n, js, "therapist")
        for n, js in ADMIN:
            shot(b, width, height, mob, n, js, "admin")
    b.close()
print("audit shots ->", OUT)
