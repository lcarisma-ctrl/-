#!/usr/bin/env python3
import os, json
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "preview", "v42-audit")
def go(pg):
    pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(900)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]', "el=>el.click()"); pg.wait_for_timeout(500)
    pg.eval_on_selector('#provinceQuick [data-prov="서울"]', "el=>el.click()"); pg.wait_for_timeout(200)
    pg.select_option("#bookDistrict", "강남구"); pg.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    pg.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el=>el.click()")
    pg.eval_on_selector('[data-next="1"]', "el=>el.click()"); pg.wait_for_timeout(350)
    pg.eval_on_selector('#bookDates .date-chip', "el=>el.click()"); pg.wait_for_timeout(150)
    pg.eval_on_selector('#bookSlots .slot:not([disabled])', "el=>el.click()")
    pg.eval_on_selector('[data-next="2"]', "el=>el.click()"); pg.wait_for_timeout(350)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"])
    for w,h,mob in [(390,844,True),(320,568,True),(1280,900,False)]:
        ctx = b.new_context(viewport={"width":w,"height":h}, device_scale_factor=2, is_mobile=mob, has_touch=mob, locale="ko-KR")
        pg = ctx.new_page(); go(pg); pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(OUT,"vp_%d_b3a.png"%w))
        pg.eval_on_selector('#passList [data-pass="p8"]', "el=>el.click()"); pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(OUT,"vp_%d_b3b.png"%w))
        pg.eval_on_selector('[data-next="3"]', "el=>el.click()"); pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(OUT,"vp_%d_b4a.png"%w))
        pg.fill("#bookName","김순자"); pg.fill("#bookPhone","01012345678")
        pg.eval_on_selector('#payMethods [data-pay="카카오페이"]',"el=>el.click()")
        pg.eval_on_selector("#screen-booking","el=>el.scrollTop=0")
        pg.screenshot(path=os.path.join(OUT,"vp_%d_b4b.png"%w))
        pg.evaluate("()=>{const s=document.querySelector('#screen-booking'); s.scrollTop = s.scrollHeight;}")
        pg.wait_for_timeout(300)
        pg.screenshot(path=os.path.join(OUT,"vp_%d_b4c.png"%w))
        print(w, pg.evaluate("""()=>{const q=s=>{const e=document.querySelector(s); if(!e)return null;const r=e.getBoundingClientRect();return [Math.round(r.top),Math.round(r.height)];};
          return {sum:q('#bookSummary'), total:q('.total'), pay:q('#payBtn'), nav:q('#wstep-4 .wiz-nav'), bar:q('#bookTotalBar'), tab:q('.tabbar[data-mode=customer]'), b3nav:q('#wstep-3 .wiz-nav'), b3cards:document.querySelectorAll('#passList .pass-card,#passList .pass-item,#passList > *').length, passHTML:document.querySelector('#passList').firstElementChild.className};}"""))
        ctx.close()
    b.close()
