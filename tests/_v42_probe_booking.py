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
    for w,h,mob in [(390,844,True),(320,568,True)]:
        ctx = b.new_context(viewport={"width":w,"height":h}, device_scale_factor=2, is_mobile=mob, has_touch=mob, locale="ko-KR")
        pg = ctx.new_page(); go(pg); pg.wait_for_timeout(600)
        pg.screenshot(path=os.path.join(OUT,"probe_%d_b3.png"%w), full_page=True)
        pg.eval_on_selector('#passList [data-pass="p8"]', "el=>el.click()"); pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(OUT,"probe_%d_b3b.png"%w), full_page=True)
        print(w, "step3 heights", pg.evaluate("""()=>{const a=document.querySelector('#wstep-3');const r=a.getBoundingClientRect();return {h:Math.round(r.height), viewport:innerHeight, scroll:document.querySelector('#screen-booking').scrollHeight}}"""))
        pg.eval_on_selector('[data-next="3"]', "el=>el.click()"); pg.wait_for_timeout(500)
        pg.fill("#bookName","김순자"); pg.fill("#bookPhone","01012345678")
        pg.eval_on_selector('#payMethods [data-pay="카카오페이"]',"el=>el.click()")
        pg.screenshot(path=os.path.join(OUT,"probe_%d_b4.png"%w), full_page=True)
        print(w, "step4 heights", pg.evaluate("""()=>{const a=document.querySelector('#wstep-4');const r=a.getBoundingClientRect();const s=document.querySelector('#bookSummary');const sr=s.getBoundingClientRect();return {h:Math.round(r.height), sum:{top:Math.round(sr.top),h:Math.round(sr.height)}, viewport:innerHeight}}"""))
        ctx.close()
    b.close()
