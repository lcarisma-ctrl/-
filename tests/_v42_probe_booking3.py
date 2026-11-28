#!/usr/bin/env python3
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
def go(pg):
    pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(800)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]', "el=>el.click()"); pg.wait_for_timeout(400)
    pg.eval_on_selector('#provinceQuick [data-prov="서울"]', "el=>el.click()"); pg.wait_for_timeout(200)
    pg.select_option("#bookDistrict", "강남구"); pg.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    pg.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el=>el.click()")
    pg.eval_on_selector('[data-next="1"]', "el=>el.click()"); pg.wait_for_timeout(300)
    pg.eval_on_selector('#bookDates .date-chip', "el=>el.click()"); pg.wait_for_timeout(120)
    pg.eval_on_selector('#bookSlots .slot:not([disabled])', "el=>el.click()")
    pg.eval_on_selector('[data-next="2"]', "el=>el.click()"); pg.wait_for_timeout(300)
    pg.eval_on_selector('#passList [data-pass="p8"]', "el=>el.click()"); pg.wait_for_timeout(250)
    pg.eval_on_selector('[data-next="3"]', "el=>el.click()"); pg.wait_for_timeout(400)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"])
    for w,h,mob in [(390,844,True),(320,568,True)]:
        ctx = b.new_context(viewport={"width":w,"height":h}, device_scale_factor=2, is_mobile=mob, has_touch=mob, locale="ko-KR")
        pg = ctx.new_page(); go(pg)
        pg.evaluate("()=>{window.scrollTo(0, document.documentElement.scrollHeight);}")
        pg.wait_for_timeout(400)
        print(w, pg.evaluate("""()=>{const q=s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return [Math.round(r.top),Math.round(r.bottom)];};
        return {pay:q('#payBtn'), note:q('.pay-note'), prev:q('.prev-step'), tab:q('.tabbar[data-mode=customer]'), y:Math.round(window.scrollY), max:Math.round(document.documentElement.scrollHeight-innerHeight), bodyW:document.body.scrollWidth};}"""))
        pg.screenshot(path=os.path.join(ROOT,"preview","v42-audit","vp_%d_b4end.png"%w))
        ctx.close()
    b.close()
