#!/usr/bin/env python3
import os, json
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"])
    ctx = b.new_context(viewport={"width":390,"height":844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(500)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(900)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()"); pg.wait_for_timeout(600)
    pg.eval_on_selector('[data-teacher]', "el=>el.click()"); pg.wait_for_timeout(600)
    print("open?", pg.evaluate("()=>document.querySelector('#teacherSheet').classList.contains('is-open')"))
    print("gest", pg.evaluate("()=>({sheets:__ttokttokGesture.sheets})"))
    box = pg.evaluate("""()=>{const h=document.querySelector('#teacherSheet .sheet-handle');const r=h.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};}""")
    # small drag -> snap back
    pg.mouse.move(box["x"], box["y"]); pg.mouse.down()
    for i in range(1,7): pg.mouse.move(box["x"], box["y"]+i*12); pg.wait_for_timeout(20)
    print("mid transform", pg.evaluate("()=>document.querySelector('#teacherSheet .sheet').style.transform"))
    pg.mouse.up(); pg.wait_for_timeout(400)
    print("after small drag open?", pg.evaluate("()=>document.querySelector('#teacherSheet').classList.contains('is-open')"))
    # big drag -> close
    pg.mouse.move(box["x"], box["y"]); pg.mouse.down()
    for i in range(1,13): pg.mouse.move(box["x"], box["y"]+i*14); pg.wait_for_timeout(16)
    pg.mouse.up(); pg.wait_for_timeout(600)
    print("after big drag open?", pg.evaluate("()=>document.querySelector('#teacherSheet').classList.contains('is-open')"), pg.evaluate("()=>__ttokttokGesture.closes"))
    # badge swap: admin transition
    pg.evaluate("()=>{document.querySelector('[data-login]');}")
    pg.eval_on_selector('[data-role-switch], #rolePill', "el=>el.click()"); pg.wait_for_timeout(400)
    print("role sheet", pg.evaluate("()=>!!document.querySelector('#roleSheet')"))
    ctx.close()
    b.close()
