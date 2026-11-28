import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=8"
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    try:
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin="https://lcarisma-ctrl.github.io")
    except Exception as e:
        print("permission grant skipped:", e)
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL, wait_until="load")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    print("booted, errors:", errs[:3])
    print("title meta:", page.eval_on_selector("meta[name='apple-mobile-web-app-title']", "el => el.content"))
    print("theme:", page.eval_on_selector("meta[name='theme-color']", "el => el.content"))
    print("icon:", page.eval_on_selector("link[rel='apple-touch-icon']", "el => el.getAttribute('href').slice(0,30)"))
    page.tap("#gateCta")
    page.wait_for_timeout(400)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(900)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]')
    page.wait_for_timeout(500)
    page.tap("#reportOpen")
    page.wait_for_timeout(700)
    print("report open:", page.eval_on_selector("#reportSheet", "el => el.classList.contains('is-open')"))
    print("card:", page.inner_text("#reportCard").replace("\n", " | ")[:160])
    print("lines:", page.eval_on_selector_all("#reportChart .rc-line", "els => els.length"))
    page.tap("#reportCopy")
    page.wait_for_timeout(400)
    print("toast:", page.inner_text("#toast"))
    try:
        txt = page.evaluate("navigator.clipboard.readText()")
        print("clipboard:", repr(txt[:120]))
        print("clipboard has report header:", "[똑똑쌤 회복 리포트]" in txt, "| next visit:", "다음 방문" in txt)
    except Exception as e:
        print("clipboard read failed:", type(e).__name__, str(e)[:80])
    page.screenshot(path="/workspace/projects/ttokttok-app/preview/v8_live_report.png")
    b.close()
