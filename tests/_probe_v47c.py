import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
OUT = os.path.join(ROOT, "preview", "v47-probe"); os.makedirs(OUT, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files","--font-render-hinting=none"])
    for label, theme, w, h in [("1280", None, 1280, 900), ("1280_dark", "dark", 1280, 900), ("1024", None, 1024, 900)]:
        ctx = b.new_context(viewport={"width":w,"height":h}, locale="ko-KR")
        if theme: ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}"%theme)
        pg = ctx.new_page(); pg.goto(URL+"?intro=0")
        pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(400)
        pg.eval_on_selector('[data-login="customer"]', "el=>el.click()"); pg.wait_for_timeout(500)
        pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()"); pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(OUT, "%s_teachers_empty.png"%label))
        pg.eval_on_selector('#teacherList .teacher', "el=>el.focus()")
        pg.keyboard.press("ArrowDown"); pg.wait_for_timeout(350)
        pg.screenshot(path=os.path.join(OUT, "%s_teachers_kbd.png"%label))
        ctx.close()
    b.close()
print("ok")
