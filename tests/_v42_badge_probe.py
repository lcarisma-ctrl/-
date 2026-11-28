#!/usr/bin/env python3
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"])
    for w in (390, 320):
        ctx = b.new_context(viewport={"width":w,"height":844 if w==390 else 568}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
        pg = ctx.new_page()
        pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(500)
        pg.eval_on_selector('[data-login="admin"]', "el=>el.click()"); pg.wait_for_timeout(1500)
        pg.evaluate("()=>{const e=document.querySelector('#adminResvQueue'); e.scrollIntoView({block:'start'});}"); pg.wait_for_timeout(500)
        before = pg.evaluate("()=>{const c=document.querySelector('#adminResvQueue [data-resv]'); return c? c.innerText.replace(/\\s+/g,' ').slice(0,80):null;}")
        print(w, "before:", before)
        btns = pg.evaluate("""()=>{const c=document.querySelector('#adminResvQueue [data-resv]'); if(!c) return []; return [...c.querySelectorAll('button')].map(b=>b.textContent.trim());}""")
        print("  buttons:", btns)
        # click '방문 완료' 류 버튼
        target = pg.evaluate("""()=>{const c=document.querySelector('#adminResvQueue [data-resv]'); if(!c) return null;
          const b=[...c.querySelectorAll('button')].find(x=>/완료|확정|수락/.test(x.textContent)); if(!b) return null; const r=b.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2,t:b.textContent.trim()};}""")
        if target:
            pg.mouse.click(target["x"], target["y"])
            pg.wait_for_timeout(120)
            print("  clicked", target["t"], "swaps:", pg.evaluate("()=>__ttokttokGesture.badgeSwaps"), "class:", pg.evaluate("()=>!!document.querySelector('.tt-badge-swap')"))
            pg.wait_for_timeout(600)
            after = pg.evaluate("()=>{const c=document.querySelector('#adminResvQueue [data-resv]'); return c? c.innerText.replace(/\\s+/g,' ').slice(0,80):null;}")
            print("  after:", after, "swaps:", pg.evaluate("()=>__ttokttokGesture.badgeSwaps"))
        ctx.close()
    b.close()
