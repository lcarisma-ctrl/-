import os, sys
os.environ.setdefault("LD_LIBRARY_PATH","/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu")
from playwright.sync_api import sync_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL="file://"+os.path.join(ROOT,"index.html")
SHOT=os.path.join(ROOT,"preview")
def main():
    with sync_playwright() as p:
        b=p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files","--font-render-hinting=none"])
        for w,h,mob in [(320,720,True),(375,812,True),(1280,900,False)]:
            ctx=b.new_context(viewport={"width":w,"height":h},is_mobile=mob,has_touch=mob,locale="ko-KR")
            pg=ctx.new_page(); pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted === true",timeout=8000)
            pg.screenshot(path=os.path.join(SHOT,"v31_%d_gate.png"%w))
            pg.eval_on_selector('[data-login="customer"]',"el=>el.click()"); pg.wait_for_timeout(350)
            for t in ["home","teachers","booking"]:
                pg.eval_on_selector('.tabbar .tabbtn[data-tab="%s"]'%t,"el=>el.click()"); pg.wait_for_timeout(300)
                pg.screenshot(path=os.path.join(SHOT,"v31_%d_%s.png"%(w,t)))
            pg.eval_on_selector('.tabbar .tabbtn[data-tab="mypage"]',"el=>el.click()"); pg.wait_for_timeout(300)
            pg.screenshot(path=os.path.join(SHOT,"v31_%d_mypage.png"%w))
            pg.eval_on_selector("#mpBookLink","el=>el.click()"); pg.wait_for_timeout(400)
            pg.screenshot(path=os.path.join(SHOT,"v31_%d_account.png"%w))
            pg.keyboard.press("Escape"); pg.wait_for_timeout(250)
            pg.eval_on_selector('.tabbar .tabbtn[data-tab="journal"]',"el=>el.click()"); pg.wait_for_timeout(300)
            pg.screenshot(path=os.path.join(SHOT,"v31_%d_journal.png"%w))
            ctx.close()
        b.close()
main()
