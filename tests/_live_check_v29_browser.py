#!/usr/bin/env python3
"""똑똑쌤 v29 라이브(GitHub Pages) 실브라우저 점검 — 후기 신뢰 배지·원클릭 재예약.
실행: python3 tests/_live_check_v29_browser.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

LIVE = "https://lcarisma-ctrl.github.io/-/?v=29"
SHOT = os.path.join(ROOT, "preview")
passed, failed, failures = 0, 0, []


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print("  ✓ " + name)
    else:
        failed += 1
        failures.append(name + (" :: " + str(extra) if extra else ""))
        print("  ✗ " + name + (" :: " + str(extra) if extra else ""))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--font-render-hinting=none"])
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True, locale="ko-KR",
                                  user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.goto(LIVE, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)

        def overflow(state):
            m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
            return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

        ok("v29 라이브 앱 버전", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v29")
        ok("v29 라이브 부팅 오류 0", not errors, errors[:3])
        ok("v29 신뢰 모델 노출(태그 5)", page.evaluate("() => window.__ttokttokModel.trustVersion") == "v29" and
           page.evaluate("() => window.__ttokttokModel.reviewTagMaster.length") == 5)

        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(700)

        # 1) 홈 요약 — 최근 방문·재예약·후기
        ok("v29 홈 요약 최근 방문 블록", page.is_visible("#homeSummaryRebook") and
           "최근 방문" in page.inner_text("#homeSummaryRebook"))
        ok("v29 홈 요약 재예약 버튼", page.is_visible("#homeSummaryRebook [data-rebook='TT-261019-4811']"))
        if not os.path.exists(SHOT):
            os.makedirs(SHOT)
        page.screenshot(path=os.path.join(SHOT, "live_v29_home_rebook.png"))

        # 2) 후기 시트 — 태그 5종·1회 1후기
        page.tap("#homeSummaryRebook [data-review-booking]")
        page.wait_for_timeout(450)
        rs = page.evaluate("() => window.__ttokttokModel.reviewState()")
        ok("v29 후기 시트(예약 기준) 열림", page.eval_on_selector("#reviewSheet", "el => el.classList.contains('is-open')") and
           rs["reservationNo"] == "TT-261019-4811", rs["reservationNo"])
        ok("v29 후기 태그 5종·안내 문구", rs["chips"] == 5 and "방문 1회당 후기 1개" in rs["rule"])
        okk, why = overflow("reviewSheet/v29")
        ok("v29 후기 시트 넘침 없음", okk, why)
        page.tap('[data-star="5"]')
        page.tap('#reviewTags [data-rtag="체계적 평가"]')
        page.tap('#reviewTags [data-rtag="보호자 소통"]')
        page.fill("#reviewText", "매번 측정한 숫자를 보여주셔서 믿음이 갑니다")
        page.screenshot(path=os.path.join(SHOT, "live_v29_review_sheet.png"))
        before = page.evaluate("() => window.__ttokttokModel.trustOf('park')")
        page.tap("#reviewSubmit")
        page.wait_for_timeout(500)
        after = page.evaluate("() => window.__ttokttokModel.trustOf('park')")
        ok("v29 후기 등록 → 후기 수·대표 태그 반영", after["reviewCount"] == before["reviewCount"] + 1 and
           any(t["label"] == "체계적 평가" and t["count"] >= 2 for t in after["topTags"]),
           [before["reviewCount"], after["reviewCount"]])
        rows = page.evaluate("() => window.__ttokttokModel.reviewListState()")
        ok("v29 후기 목록 등록됨", any(r["session"] == "TT-261019-4811" and r["reviewed"] for r in rows))
        dup = page.evaluate("() => window.__ttokttokModel.openReviewForBooking('TT-261019-4811')")
        ok("v29 1방문 1후기 중복 차단", dup.get("code") == "already_reviewed", dup.get("code"))

        # 3) 선생님 신뢰 배지
        page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
        page.wait_for_timeout(450)
        card = page.inner_text('#teacherList [data-teacher="park"]')
        ok("v29 카드 대표 태그", "체계적 평가" in card)
        page.tap('#teacherList [data-teacher="park"]')
        page.wait_for_timeout(500)
        trust = page.inner_text("#teacherTrustBlock").replace("\n", " ")
        ok("v29 상세 신뢰 배지(평점·완료·재방문·태그·검증)",
           "평균 별점" in trust and "완료 방문" in trust and "재방문" in trust and "면허" in trust, trust[:120])
        okk, why = overflow("teacherSheet/v29")
        ok("v29 신뢰 배지 시트 넘침 없음", okk, why)
        page.screenshot(path=os.path.join(SHOT, "live_v29_teacher_trust.png"))
        page.tap("[data-sheet-close]")
        page.wait_for_timeout(300)

        # 4) 원클릭 재예약
        page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]')
        page.wait_for_timeout(300)
        page.tap("#homeSummaryRebook [data-rebook]")
        page.wait_for_timeout(550)
        form = page.evaluate("() => window.__ttokttokModel.bookingFormState()")
        ok("v29 재예약 → 1단계 미리 채움", form["teacherId"] == "park" and form["province"] == "서울" and
           form["district"] == "강남구" and form["syms"] == ["뇌졸중·편마비"] and form["passId"] == "p1", form)
        ok("v29 재예약 배너(90,000원·1회권)", "90,000원" in form["banner"] and "1회 방문권" in form["banner"], form["banner"])
        ok("v29 무료 평가 아님", not page.eval_on_selector('#passList [data-pass="eval"]', "el => el.classList.contains('is-on')"))
        okk, why = overflow("booking/rebook")
        ok("v29 재예약 화면 넘침 없음", okk, why)
        page.screenshot(path=os.path.join(SHOT, "live_v29_rebook_step1.png"))

        # 5) 완료 예약 상세 — 재예약·후기 등록 표시
        page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
        page.wait_for_timeout(300)
        page.tap("#mpBookLink")
        page.wait_for_timeout(500)
        ok("v29 완료 예약 카드 재예약", page.is_visible("#bookingList [data-rebook='TT-261019-4811']"))
        page.tap("#bookingList [data-manage='TT-261019-4811']")
        page.wait_for_timeout(450)
        man = page.inner_text("#manageSheetBody").replace("\n", " ")
        ok("v29 완료 상세(방문 완료·재예약·후기 등록됨)",
           "방문 완료된 회차" in man and "후기 등록됨" in man and
           page.is_visible("#manageSheetBody [data-rebook='TT-261019-4811']"), man[:120])
        page.screenshot(path=os.path.join(SHOT, "live_v29_completed_detail.png"))
        page.tap("#manageSheet [data-manage-close]")
        page.wait_for_timeout(250)
        page.tap("[data-account-close]")
        page.wait_for_timeout(300)

        # 6) 320px
        page.set_viewport_size({"width": 320, "height": 568})
        page.wait_for_timeout(350)
        okk, why = overflow("home/v29/320")
        ok("v29 320px 넓이 넘침 없음", okk, why)
        page.screenshot(path=os.path.join(SHOT, "live_v29_320_home.png"))

        ok("v29 전 화면 오류 0", not errors, errors[:3])
        browser.close()

    print("\nLIVE V29 RESULT: %d passed, %d failed" % (passed, failed))
    for f in failures:
        print(" - " + f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
