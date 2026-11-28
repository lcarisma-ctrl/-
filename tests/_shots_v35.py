#!/usr/bin/env python3
"""v35 화면 캡처 — preview/v35_{320,375,1280}_{gate,home,teachers,journal,partner,admin}.png"""
import os
os.environ["LD_LIBRARY_PATH"]="/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL="file://"+os.path.join(ROOT,"index.html"); SHOT=os.path.join(ROOT,"preview")
os.makedirs(SHOT,exist_ok=True)
STATES=[("home","() => {}"),
 ("teachers","() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click()"),
 ("journal","() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click()"),
 ("partner","() => { document.querySelector('#rolePill').click(); setTimeout(()=>document.querySelector('[data-role-switch=therapist]').click(),200); }"),
 ("admin","() => { document.querySelector('#rolePill').click(); setTimeout(()=>{const b=document.querySelector('[data-admin-open]'); if(b)b.click();},220); }")]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files"])
    for w,h,mob in [(320,568,True),(375,812,True),(1280,800,False)]:
        for name,prep in STATES:
            ctx=b.new_context(viewport={"width":w,"height":h},device_scale_factor=2 if mob else 1,is_mobile=mob,has_touch=mob,locale="ko-KR")
            pg=ctx.new_page(); pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true",timeout=20000); pg.wait_for_timeout(400)
            if name=="home": pg.screenshot(path=os.path.join(SHOT,"v35_%d_gate.png"%w))
            pg.eval_on_selector('[data-login="customer"]',"el=>el.click()"); pg.wait_for_timeout(500)
            pg.evaluate(prep); pg.wait_for_timeout(700)
            pg.screenshot(path=os.path.join(SHOT,"v35_%d_%s.png"%(w,name)))
            ctx.close()
    b.close()
print("shots done")
