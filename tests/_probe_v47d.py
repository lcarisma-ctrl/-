import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files"])
    pg = b.new_context(viewport={"width":1024,"height":900}, locale="ko-KR").new_page()
    pg.goto(URL + "?intro=0")
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(500)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()"); pg.wait_for_timeout(500)
    print(pg.evaluate("""() => {
      const cards=[...document.querySelectorAll('#teacherList .teacher')].slice(0,4);
      return cards.map(c=>{ const r=c.querySelector('.t-region'); const cs=getComputedStyle(r);
        const ic=r.querySelector('.ic'); const sp=r.querySelector('span');
        return {name:c.querySelector('.t-name').innerText.slice(0,6), html:r.innerHTML.slice(0,80),
          wrap:cs.flexWrap, gap:cs.gap, icW: ic?Math.round(ic.getBoundingClientRect().width):null,
          icY: ic?Math.round(ic.getBoundingClientRect().y):null, spY: sp?Math.round(sp.getBoundingClientRect().y):null,
          spW: sp?Math.round(sp.getBoundingClientRect().width):null, rgW:Math.round(r.getBoundingClientRect().width)};});
    }"""))
    b.close()
