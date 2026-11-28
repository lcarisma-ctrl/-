"""v25 라이브 실브라우저 점검 — 홈 통합 요약·첫 방문 온보딩·FAQ 검색(390/320)."""
import os
ROOT = "/workspace/projects/ttokttok-app"
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ.get("LD_LIBRARY_PATH") if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=25&live=1"
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print("  OK " + name)
    else:
        fail += 1; print("  NG " + name + (" :: " + str(extra)))


def overflow(pg):
    m = pg.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
    return m["sw"] <= m["cw"] + 1, m


with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                        is_mobile=True, has_touch=True, locale="ko-KR")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(URL, wait_until="load")
    pg.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
    check("라이브 부팅", True)
    check("앱 버전 v25", pg.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v25")
    check("요약 모델 훅 v25", pg.evaluate("() => [window.__ttokttokModel.guardianVersion, window.__ttokttokModel.guardianReportDays]") == ["v25", 28])
    pg.eval_on_selector('[data-login="customer"]', "el => el.click()")
    pg.wait_for_timeout(600)

    check("홈 통합 요약 카드 표시", pg.is_visible("#homeSummaryCard"))
    check("다음 방문·예약번호·상태",
          "TT-261021-7302" in pg.eval_on_selector("#homeSummaryNext", "el => el.textContent") and
          "예약 확정" in pg.eval_on_selector("#homeSummaryNext", "el => el.textContent"))
    check("회차권 잔여·만료",
          "잔여 5회" in pg.eval_on_selector("#homeSummaryPass", "el => el.textContent") and
          "2027.01.27" in pg.eval_on_selector("#homeSummaryPass", "el => el.textContent"))
    check("최근 4주 리포트·재평가",
          "최근 4주 방문" in pg.eval_on_selector("#homeSummaryReport", "el => el.textContent") and
          "재평가" in pg.eval_on_selector("#homeSummaryReport", "el => el.textContent"))
    o = overflow(pg)
    check("홈 390px 넘침 없음", o[0], o[1])
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v25_home_summary.png"))

    pg.tap('#homeSummaryCard [data-summary="report"]'); pg.wait_for_timeout(600)
    check("리포트 바로가기 → 일지 탭+주간 시트",
          pg.eval_on_selector(".screen.is-active", "el => el.id") == "screen-journal" and
          pg.eval_on_selector("#weeklySheet", "el => el.classList.contains('is-open')"))
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v25_weekly_sheet.png"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(350)
    pg.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="home"]', "el => el.click()"); pg.wait_for_timeout(350)
    pg.tap('#homeSummaryCard [data-summary="visit"]'); pg.wait_for_timeout(500)
    check("방문 일정 바로가기 → 예약·이용권 시트", pg.eval_on_selector("#accountSheet", "el => el.classList.contains('is-open')"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(350)

    pg.tap("#homeGuideBtn"); pg.wait_for_timeout(550)
    check("준비물 3가지", pg.eval_on_selector_all("#onboardPrepCard input[type=checkbox]", "els => els.length") == 3)
    check("진행 3단계(15분·계획·60분)", pg.eval_on_selector_all("#onboardFlow .step-item", "els => els.length") == 3 and
          "60분 본 수업" in pg.eval_on_selector("#onboardFlow", "el => el.textContent"))
    check("불안 해소 2가지", "강제 결제 없음" in pg.eval_on_selector("#onboardAssurance", "el => el.textContent"))
    pg.tap("#obPrep-space"); pg.wait_for_timeout(250)
    check("준비물 체크 → 문구 갱신", "1가지 확인" in pg.eval_on_selector("#onboardPrepNote", "el => el.textContent"),
          pg.eval_on_selector("#onboardPrepNote", "el => el.textContent"))
    pg.eval_on_selector("#onboardPrepCard", "el => el.scrollIntoView({block:'center'})"); pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v25_onboarding.png"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(350)

    pg.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="mypage"]', "el => el.click()"); pg.wait_for_timeout(350)
    pg.tap("#mpFaqRow"); pg.wait_for_timeout(550)
    check("FAQ 기본 10문항", pg.eval_on_selector_all("#faqList .faq-item", "els => els.length") == 10)
    pg.fill("#faqSearch", "환불"); pg.wait_for_timeout(300)
    n = pg.eval_on_selector_all("#faqList .faq-item", "els => els.length")
    check("검색 결과 좁혀짐(환불)", 0 < n < 10, n)
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v25_faq_search.png"))
    pg.tap('#faqCatChips [data-faqcat="refund"]'); pg.wait_for_timeout(300)
    check("카테고리(비용/환불) 선택", pg.eval_on_selector('#faqCatChips [data-faqcat="refund"]', "el => el.classList.contains('is-on')"))
    pg.fill("#faqSearch", "없는검색어"); pg.wait_for_timeout(300)
    check("0건 빈 상태 + 상담 연결", pg.eval_on_selector("#faqEmpty", "el => !el.hidden") and
          pg.is_visible("#faqEmpty a[href*='naver.me']"))
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v25_faq_empty.png"))
    pg.tap("#faqReset"); pg.wait_for_timeout(300)
    check("검색 초기화 → 10문항", pg.eval_on_selector_all("#faqList .faq-item", "els => els.length") == 10)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)

    pg.set_viewport_size({"width": 320, "height": 568}); pg.wait_for_timeout(400)
    pg.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="home"]', "el => el.click()"); pg.wait_for_timeout(400)
    o = overflow(pg)
    check("320px 홈 요약 넘침 없음", o[0], o[1])
    check("320px 요약 카드 보임", pg.is_visible("#homeSummaryCard"))
    pg.screenshot(path=os.path.join(ROOT, "preview", "live_v25_320_home_summary.png"))
    check("JS 오류 0", not errs, errs[:2])
    b.close()

print("\nLIVE v25: %d ok, %d ng" % (ok, fail))
