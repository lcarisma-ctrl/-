import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright
URL = "file://" + os.path.join(ROOT, "index.html")
SHOT = os.path.join(ROOT, "preview")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    for w, h, name in [(390, 844, "390"), (320, 568, "320"), (1280, 800, "1280")]:
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=(w < 800), has_touch=(w < 800), locale="ko-KR")
        page = ctx.new_page()
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(120)
        page.eval_on_selector('[data-login="admin"]', "el => el.click()")
        page.wait_for_timeout(500)
        page.evaluate("() => { const t = document.querySelector('.toast'); if (t) t.remove(); }")
        el = page.query_selector("#adminMetricsSec")
        el.screenshot(path=os.path.join(SHOT, "v28_section_%s.png" % name))
        page.screenshot(path=os.path.join(SHOT, "v28_screen_%s.png" % name))
        # 7일 칩
        page.eval_on_selector('#adminMetricsPeriods [data-metrics-period="7d"]', "el => el.click()")
        page.wait_for_timeout(300)
        page.query_selector("#adminMetricsSec").screenshot(path=os.path.join(SHOT, "v28_section_%s_7d.png" % name))
        ctx.close()
    b.close()
print("done")
