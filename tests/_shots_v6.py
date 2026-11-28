"""v6 화면 컷: 홈 · 내 정보 커버링 스타일 확인용.

실행: python3 tests/_shots_v6.py  → preview/v6_*.png
"""
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = "/workspace/projects/ttokttok-app"
OUT = ROOT + "/preview"

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ko-KR")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    page.goto("file://" + ROOT + "/index.html")
    page.wait_for_function("window.__ttokttokBooted === true")
    page.wait_for_timeout(300)
    page.tap("#gateCta")
    page.wait_for_timeout(500)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(3200)
    page.screenshot(path=OUT + "/v6_home.png")
    print("home scrollHeight:", page.evaluate("document.querySelector('#screen-home').scrollHeight"))

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(900)
    page.screenshot(path=OUT + "/v6_mypage.png")

    page.tap('#mpAccountLink' if page.query_selector('#mpAccountLink') else '#mpBookLink')
    page.wait_for_timeout(700)
    page.screenshot(path=OUT + "/v6_account.png")
    page.tap('[data-account-close]')
    page.wait_for_timeout(300)

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]')
    page.wait_for_timeout(400)
    page.tap('#homeGuideBtn')
    page.wait_for_timeout(600)
    page.screenshot(path=OUT + "/v6_guide.png")
    page.tap('[data-guide-close]')
    page.wait_for_timeout(300)

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(700)
    page.screenshot(path=OUT + "/v6_teachers.png")

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(600)
    page.tap('#mpPayRow')
    page.wait_for_timeout(700)
    page.screenshot(path=OUT + "/v6_pay.png")
    page.tap('[data-pay-close]')
    page.wait_for_timeout(300)
    page.tap('#mpRoleRow')
    page.wait_for_timeout(600)
    page.screenshot(path=OUT + "/v6_role.png")
    page.tap('[data-role-close]')
    page.wait_for_timeout(300)
    page.tap('#mpRegionRow')
    page.wait_for_timeout(700)
    page.screenshot(path=OUT + "/v6_region.png")
    page.tap('[data-region-close]')
    page.wait_for_timeout(300)

    page.evaluate("window.scrollTo(0, 99999)")
    page.wait_for_timeout(500)
    page.screenshot(path=OUT + "/v6_home_bottom.png")

    print("js errors:", errs[:5])
    b.close()
print("shots done")
