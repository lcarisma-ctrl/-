#!/usr/bin/env python3
"""v43 before/after — before = v42(`.work/index_v42.html`), after = 현재 `index.html`."""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = {"before": "file://" + os.path.join(ROOT, ".work", "index_v42.html"),
         "after": "file://" + os.path.join(ROOT, "index.html")}
OUT = os.path.join(ROOT, "preview", "v43-audit")


def run(b, url, label):
    d = os.path.join(OUT, label)
    os.makedirs(d, exist_ok=True)
    # 1) 320 홈
    ctx = b.new_context(viewport={"width": 320, "height": 568}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page(); pg.goto(url + "?intro=0"); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(2200)
    pg.screenshot(path=os.path.join(d, "320_home.png")); ctx.close()

    # 2) 390 예약 3단계(선택 후)
    for w, h in [(390, 844)]:
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
        pg = ctx.new_page(); pg.goto(url + "?intro=0"); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(300)
        pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(700)
        pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]', "el=>el.click()"); pg.wait_for_timeout(400)
        pg.eval_on_selector('#provinceQuick [data-prov="서울"]', "el=>el.click()"); pg.wait_for_timeout(120)
        pg.select_option("#bookDistrict", "강남구"); pg.fill("#bookAddress", "대치동 123-4, 101동 1203호")
        pg.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el=>el.click()")
        pg.eval_on_selector('[data-next="1"]', "el=>el.click()"); pg.wait_for_timeout(250)
        pg.eval_on_selector('#bookDates .date-chip', "el=>el.click()"); pg.wait_for_timeout(100)
        pg.eval_on_selector('#bookSlots .slot:not([disabled])', "el=>el.click()")
        pg.eval_on_selector('[data-next="2"]', "el=>el.click()"); pg.wait_for_timeout(300)
        pg.eval_on_selector('#passList [data-pass="p8"]', "el=>el.click()"); pg.wait_for_timeout(1000)
        pg.screenshot(path=os.path.join(d, "%d_booking_step3_selected.png" % w))
        ctx.close()

    # 3) 빈 상태(관리자 노쇼 필터)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page(); pg.goto(url + "?intro=0"); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(300)
    pg.eval_on_selector('[data-login="admin"]', "el=>el.click()"); pg.wait_for_timeout(1600)
    pg.evaluate("""() => { const b = [...document.querySelectorAll('#adminResvFilters [data-admin-resv-filter]')].find((x) => /노쇼/.test(x.textContent)); if (b) b.click(); }""")
    pg.wait_for_timeout(700)
    pg.evaluate("()=>{const e=document.querySelector('#adminResvQueue'); if(e) e.scrollIntoView({block:'center'});}")
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(d, "390_empty_state.png")); ctx.close()

    # 4) 게이트(스크롤 그림자는 스크롤 상태에서)
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page(); pg.goto(url + "?intro=0"); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(300)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(1200)
    pg.evaluate("()=>window.scrollTo(0, 420)"); pg.wait_for_timeout(500)
    pg.screenshot(path=os.path.join(d, "390_home_scrolled.png"), clip={"x": 0, "y": 0, "width": 390, "height": 220})
    ctx.close()


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
    for label, url in FILES.items():
        run(b, url, label)
    b.close()
print("v43 shots done")
