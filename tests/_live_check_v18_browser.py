#!/usr/bin/env python3
"""v18 라이브 실브라우저 확인: 부팅·버전·지역 마스터 3단계·교집합 후보·대기열·예외·리마인드."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=18"
SHOT = os.path.join(ROOT, "preview")

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                              is_mobile=True, has_touch=True, locale="ko-KR")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL, wait_until="load")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.tap("#gateCta")
    page.wait_for_selector('[data-login="customer"]', state="visible", timeout=8000)
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(400)
    info = page.evaluate("""() => {
      const m = window.__ttokttokModel;
      return {
        version: document.querySelector('meta[name="app-version"]').content,
        booted: window.__ttokttokBooted === true,
        scaling: m.scalingVersion,
        counts: m.regionMasterCounts(),
        mapped: m.teacherRegions().every(r => r.regionId !== null),
        candidate: (m.matchTeachers({ regionId: 'reg-서울-마포구', symptom: 'stroke', dateIso: '2026-11-30', timeSlot: '10:00' })[0] || {}).teacherId,
        empty: m.matchTeachers({ regionId: 'reg-제주-제주시', dateIso: '2026-11-30', timeSlot: '10:00' }).length,
        reminder: (m.reminderNotice('TT-261021-7302', 'd_minus_1') || {}).title
      };
    }""")
    print(info)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(500)
    print("queue visible:", page.is_visible("#adminResvQueue"))
    print("chips:", page.eval_on_selector_all("#adminResvFilters .chip", "els => els.length"))
    page.screenshot(path=os.path.join(SHOT, "live_v18_admin.png"))
    print("errors:", errs[:3])
    browser.close()
