#!/usr/bin/env python3
"""v47 개발용 프로브 — 방향키 이동·스켈레톤 흔들림·빈 자리 안내를 눈으로 확인한다."""
import os
from playwright.sync_api import sync_playwright

os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="ko-KR")
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(URL + "?intro=0")
        pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
        pg.wait_for_timeout(400)
        pg.eval_on_selector('[data-login="customer"]', "el=>el.click()")
        pg.wait_for_timeout(600)
        pg.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el=>el.click()")
        pg.wait_for_timeout(500)
        print("empty hint:", pg.evaluate("""() => { const e = document.getElementById('teacherPaneEmpty');
            const r = e.getBoundingClientRect();
            return {display: getComputedStyle(e).display, w: Math.round(r.width), x: Math.round(r.x), hasPane: document.getElementById('teacherMainCol').classList.contains('has-pane')}; }"""))
        pg.screenshot(path=os.path.join(ROOT, "preview", "v47-probe", "1280_pane_empty.png"))
        pg.eval_on_selector('#teacherList .teacher', "el=>el.click()")
        pg.wait_for_timeout(400)
        print("after click:", pg.evaluate("""() => ({hasPane: document.getElementById('teacherMainCol').classList.contains('has-pane'),
            empty: getComputedStyle(document.getElementById('teacherPaneEmpty')).display})"""))
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        print("after esc:", pg.evaluate("""() => ({hasPane: document.getElementById('teacherMainCol').classList.contains('has-pane'),
            paneHidden: document.getElementById('teacherPane').hidden})"""))
        print("errors", errs[:3])
        b.close()


if __name__ == "__main__":
    main()
