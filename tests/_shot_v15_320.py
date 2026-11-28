#!/usr/bin/env python3
"""v15 좁은 화면(320px) 카드 배지 레이아웃 확인용 스크린샷."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "file://" + os.path.join(ROOT, "index.html")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    ctx = b.new_context(viewport={"width": 320, "height": 700}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    page = ctx.new_page()
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=10000)
    page.tap("#gateCta")
    page.wait_for_timeout(400)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(300)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(400)
    h = page.eval_on_selector_all("#teacherList .teacher", "els => els.map(e => Math.round(e.getBoundingClientRect().height))")
    print("card heights", h[:3])
    page.screenshot(path=os.path.join(ROOT, "preview", "v15_320_teachers.png"))
    b.close()
print("done")
