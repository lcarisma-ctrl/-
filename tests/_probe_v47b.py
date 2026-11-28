import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files"])
    pg = b.new_context(viewport={"width":1280,"height":900}, locale="ko-KR").new_page()
    pg.goto(URL + "?intro=0")
    pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
    pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(500)
    pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()"); pg.wait_for_timeout(500)
    print(pg.evaluate("""() => {
      const main = document.getElementById('teacherMainCol');
      const cs = getComputedStyle(main);
      const kids = [...main.children].map(el => { const r = el.getBoundingClientRect();
        return {tag: el.tagName, id: el.id, cls: el.className, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), gc: getComputedStyle(el).gridColumn, disp: getComputedStyle(el).display}; });
      return {cols: cs.gridTemplateColumns, kids};
    }"""))
    b.close()
