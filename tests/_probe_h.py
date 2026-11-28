import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files"])
    for w,h,mob in [(320,568,True),(375,812,True),(390,844,True),(768,1024,True),(1024,900,False),(1280,900,False)]:
        ctx = b.new_context(viewport={"width":w,"height":h}, locale="ko-KR", is_mobile=mob, has_touch=mob)
        pg = ctx.new_page(); pg.goto(URL+"?intro=0")
        pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
        pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(500)
        pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()"); pg.wait_for_timeout(500)
        print(w, pg.evaluate("""() => { const l=document.getElementById('teacherList');
          const cs=[...l.querySelectorAll('.teacher')];
          const hs=cs.map(c=>Math.round(c.getBoundingClientRect().height));
          return {heights:hs, avg: Math.round(hs.reduce((a,b)=>a+b,0)/hs.length), listH: Math.round(l.getBoundingClientRect().height)}; }"""))
        ctx.close()
    b.close()
