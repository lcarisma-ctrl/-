#!/usr/bin/env python3
"""v17 라이브 실브라우저 확인: 부팅·버전·운영자 예약 큐(고지·필터·전이 버튼)·상태 전이 1건."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ.get("LD_LIBRARY_PATH") if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=17"
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
      return { version: document.querySelector('meta[name="app-version"]').content,
               booted: window.__ttokttokBooted === true,
               adminVersion: m.adminVersion, filters: m.adminFilters,
               counts: m.adminCounts() };
    }""")
    print(info)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(500)
    print("queue visible:", page.is_visible("#adminResvQueue"))
    print("demo notice:", "로컬 데모 저장 · 서버 미연결(이 기기 브라우저에만 반영)" in page.inner_text("#adminResvDemoNotice"))
    print("chips:", page.eval_on_selector_all("#adminResvFilters .chip", "els => els.length"))
    print("cards:", page.eval_on_selector_all("#adminResvQueue .admin-card", "els => els.length"))
    # 시드 예약 1건(확정) — 허용 전이 버튼만 노출되는지
    btns = page.eval_on_selector_all("#adminResvQueue .admin-card:first-child [data-admin-resv-to]",
                                     "els => els.map(e => e.getAttribute('data-admin-resv-to'))")
    print("first card buttons:", btns)
    page.eval_on_selector("#adminResvSec", "el => el.scrollIntoView({block:'start'})")
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(SHOT, "live_v17_admin_queue.png"))
    # 안내 문구 복사 버튼 동작(발송 없음)
    if page.query_selector("#adminResvQueue [data-admin-notice]"):
        page.eval_on_selector("#adminResvQueue [data-admin-notice]", "el => el.click()")
        page.wait_for_timeout(300)
        copy = page.evaluate("() => window.__ttokttokAdmin || null")
        print("notice copy ok:", bool(copy) and "[보호자 안내]" in (copy or {}).get("noticeText", ""))
    print("pageerrors", errs)
    browser.close()
