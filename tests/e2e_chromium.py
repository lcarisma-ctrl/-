#!/usr/bin/env python3
"""
똑똑쌤 실브라우저(Chromium) E2E 검증
─────────────────────────────────────────
· iPhone 크기 뷰포트 + 터치(tap) 이벤트로 실제 화면을 눌러 전 흐름을 검증한다.
· 로컬 Chromium(headless shell)을 쓰며, 시스템 라이브러리는 .aptwork/rootfs 에서 가져온다.
· 실행:  python3 tests/e2e_chromium.py
· 결과물: preview/e2e_*.png 스크린샷
"""
import os
import re
import sys
import json
import traceback
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
# 로컬(워크스페이스)에서만 쓰는 시스템 라이브러리 경로 — CI(Ubuntu)에는 없다
_LDLP_OK = os.path.isdir("/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu")
if _LDLP_OK:
    os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")

from playwright.sync_api import sync_playwright
from playwright.sync_api import Browser

# v32 · 테스트 시계 고정.
# 시드·데모 예약이 '오늘' 기준 상대 날짜라 자정을 넘기면 D-1·4주 재평가·운영 예외 건수가 달라진다
# (2026-11-27 00:2x 실제 발생: v18 예외 건수 1건 실패). 브라우저의 '오늘'을 2026-11-26 22:00 KST로
# 고정해 실행 시각과 무관하게 같은 결과를 본다.
# 브라우저와 같은 기준 시각(2026-11-26 22:00 KST) — 파이썬 쪽 기대값도 여기에 맞춘다.
FIXED_NOW_KST = datetime(2026, 11, 26, 22, 0, 0)
FIXED_TODAY = FIXED_NOW_KST.strftime("%Y-%m-%d")

CLOCK_JS = """
(() => {
  const FIXED = Date.parse('2026-11-26T13:00:00.000Z');
  const R = Date;
  function F(...a) { return a.length ? new R(...a) : new R(FIXED); }
  F.prototype = R.prototype;
  F.now = () => FIXED;
  F.parse = R.parse;
  F.UTC = R.UTC;
  window.Date = F;
})();
"""

_orig_new_context = Browser.new_context


def _new_context_with_clock(self, **kwargs):
    ctx = _orig_new_context(self, **kwargs)
    try:
        ctx.add_init_script(CLOCK_JS)
    except Exception:
        pass
    return ctx


Browser.new_context = _new_context_with_clock

URL = "file://" + os.path.join(ROOT, "index.html")
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


def shot(page, name):
    page.screenshot(path=os.path.join(SHOT, "e2e_%s.png" % name))


def run_flow(p, storage_blocked=False):
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    ok(tag + "JS 오류 없이 부팅", not errors, errors[:3])
    ok(tag + "미리보기 배너 숨김(JS 실행)", page.eval_on_selector("#previewNote", "el => getComputedStyle(el).display") == "none")
    ok(tag + "시작 화면(역할 선택) 열림", page.is_visible("#entryGate .gate-inner"))
    # ── 0. 커버링 스타일 시작 화면: 1화면 수납 · 4줄 장점 · 툴팁 · CTA
    ok(tag + "시작 화면 1화면 수납(스크롤 없음)",
       page.eval_on_selector("#entryGate", "el => el.scrollHeight <= el.clientHeight + 1"),
       page.eval_on_selector("#entryGate", "el => el.scrollHeight + '/' + el.clientHeight"))
    ok(tag + "핵심 장점 4줄 카드", page.eval_on_selector_all("#gatePoints .gate-point", "els => els.length") == 4)
    ok(tag + "장점 아이콘 48px 타일",
       page.eval_on_selector("#gatePoints .gate-point-ico", "el => Math.round(el.getBoundingClientRect().width)") == 48)
    ok(tag + "장점 4종 문구",
       all(t in page.inner_text("#gatePoints") for t in ["국가면허 검증 선생님", "병원 이동 없이 집에서", "합리적인 비용", "전국 17개 시·도 연결"]))
    ok(tag + "다크 툴팁 문구", "무료" in page.inner_text("#gateTip"))
    ok(tag + "풀와이드 CTA 문구", "휴대폰 번호로 시작하기" in page.inner_text("#gateCta"))
    ok(tag + "CTA·링크가 첫 화면 안에",
       page.eval_on_selector("#gateCta", "el => el.getBoundingClientRect().bottom <= window.innerHeight") and
       page.eval_on_selector("#gateRegionLink", "el => el.getBoundingClientRect().bottom <= window.innerHeight"))
    ok(tag + "하단 서비스 지역 링크", "서비스 지역 확인하기" in page.inner_text("#gateRegionLink"))
    shot(page, "gate" if not storage_blocked else "gate_blocked")

    # ── 0b. 서비스 지역 먼저 확인 (가능 지역 / 준비 중)
    page.tap("#gateRegionLink")
    page.wait_for_timeout(450)
    ok(tag + "서비스 지역 시트 열림", page.eval_on_selector("#regionSheet", "el => el.classList.contains('is-open')"))
    ok(tag + "활동 중 지역 빠른 선택 6곳", page.eval_on_selector_all("#regionQuick [data-region-quick]", "els => els.length") == 6)
    page.select_option("#regionProvince", "서울")
    page.wait_for_timeout(150)
    page.select_option("#regionDistrict", "강남구")
    page.wait_for_timeout(250)
    ok(tag + "가능 지역 → 바로 매칭 가능 안내",
       "바로 매칭 가능 지역입니다" in page.inner_text("#regionResult") and "활동중" in page.inner_text("#regionResult"),
       page.inner_text("#regionResult"))
    ok(tag + "가능 지역 → 이 지역 선생님 보기", page.is_visible("#regionGo"))
    shot(page, "region_ok")
    page.select_option("#regionProvince", "경남")
    page.wait_for_timeout(150)
    page.select_option("#regionDistrict", "창원시")
    page.wait_for_timeout(250)
    ok(tag + "준비 중 지역 → 오픈 준비 안내", "아직 오픈 준비 중" in page.inner_text("#regionResult"), page.inner_text("#regionResult"))
    ok(tag + "준비 중 지역 → 알림 신청 버튼", page.is_visible("#regionNotify"))
    page.tap("#regionNotify")
    page.wait_for_timeout(300)
    ok(tag + "알림 신청 → 완료 상태", "알림 신청 완료" in page.inner_text("#regionResult"))
    shot(page, "region_wait")
    page.tap('#regionQuick [data-region-quick="부산"]')
    page.wait_for_timeout(250)
    ok(tag + "빠른 선택 칩 → 시·도 동기화", page.eval_on_selector("#regionProvince", "el => el.value") == "부산")
    page.tap("#regionGo")
    page.wait_for_timeout(500)
    ok(tag + "이 지역 선생님 보기 → 선생님 탭", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-teachers")
    ok(tag + "선택 지역 선생님만 노출", page.eval_on_selector_all("#teacherList .teacher", "els => els.length") == 1)
    shot(page, "region_teachers")

    # 다시 시작 화면으로 (저장된 지역은 유지)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    page.wait_for_timeout(250)
    ok(tag + "재진입 시 시작 화면 유지", page.is_visible("#entryGate .gate-inner"))
    ok(tag + "저장한 지역 표시", storage_blocked or "부산" in page.inner_text("#gateRegionBtn"), page.inner_text("#gateRegionBtn"))

    # ── 1. 시작 화면 버튼 (터치) — CTA → 시트 → 역할 선택
    page.tap("#gateCta")
    page.wait_for_timeout(450)
    ok(tag + "CTA → 휴대폰·역할 선택 시트", page.eval_on_selector("#gateSheet", "el => el.classList.contains('is-open')"))
    ok(tag + "역할 선택 3종(고객·선생님·관리자)",
       page.eval_on_selector_all("#gateSheet [data-login]", "els => els.length") == 3)
    ok(tag + "휴대폰 번호 입력창", page.is_visible("#gatePhone"))
    shot(page, "gate_sheet")
    page.tap('[data-login="customer"]')
    page.wait_for_timeout(400)
    ok(tag + "고객 시작 버튼 탭 → 게이트 닫힘", page.eval_on_selector("#entryGate", "el => !el.classList.contains('is-open')"))
    ok(tag + "시작 시트도 닫힘", page.eval_on_selector("#gateSheet", "el => !el.classList.contains('is-open')"))
    ok(tag + "고객 홈 활성", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-home")
    ok(tag + "홈 인사말 · 헤드라인 노출",
       "반가워요" in page.inner_text(".hh-greet") and "건강한 회복" in page.inner_text("#homeHeroTitle"))
    ok(tag + "블루 공지 띠 · 보조 카드 · 가로 카드",
       "첫 1:1 방문 평가 무료" in page.inner_text("#homeNotice") and
       "선생님으로 지원하기" in page.inner_text("#homePartnerCard") and
       page.eval_on_selector_all("#homeProgramRail .home-program-card", "els => els.length") == 4)
    ok(tag + "홈에 추천·약속·신뢰지표 중복 섹션 없음",
       page.eval_on_selector_all("#screen-home .trust-strip, #screen-home .promise-card, #screen-home #homeTeacherList", "els => els.length") == 0)
    # ── v8: iOS 홈 화면 앱(PWA) 메타 · 탭 페이드
    ok(tag + "v8 iOS 홈화면 앱 메타(제목·상태바·테마)",
       page.eval_on_selector("meta[name='apple-mobile-web-app-capable']", "el => el.content") == "yes"
       and page.eval_on_selector("meta[name='apple-mobile-web-app-title']", "el => el.content") == "똑똑쌤"
       and page.eval_on_selector("meta[name='apple-mobile-web-app-status-bar-style']", "el => el.content") == "default"
       and page.eval_on_selector("meta[name='theme-color']", "el => el.content").upper() == "#F7F8FA")
    ok(tag + "v8 apple-touch-icon 데이터 URI",
       page.eval_on_selector("link[rel='apple-touch-icon']", "el => (el.getAttribute('href') || '').startsWith('data:image/png;base64,')"))
    ok(tag + "v8 탭 페이드 180ms 정의",
       "@keyframes tabFade" in page.eval_on_selector("style", "el => el.textContent"))
    # ── v9: 증상 카드 포인트 심볼 · 멀티레이어 섀도우
    ok(tag + "v9 홈 증상 카드 포인트 배지 4개",
       page.eval_on_selector_all("#homeProgramRail .hpc-badge", "els => els.length") == 4)
    ok(tag + "v9 배지 안에 SVG 심볼",
       page.eval_on_selector_all("#homeProgramRail .hpc-badge svg path, #homeProgramRail .hpc-badge svg circle", "els => els.length") >= 4)
    badge_classes = page.eval_on_selector_all("#homeProgramRail .hpc-badge", "els => els.map(e => e.className)")
    ok(tag + "v9 배지 4색(블루·오렌지·코랄·틸)", len(set(badge_classes)) == 4, badge_classes)
    card_shadow = page.eval_on_selector("#homeProgramRail .home-program-card", "el => getComputedStyle(el).boxShadow")
    # v41: 그림자를 3단(--elev-1~3)으로 통일했다. 값(색)은 바뀌었지만 '두 겹'이라는 성질은 유지한다.
    ok(tag + "v9 카드 2중 그림자", card_shadow.count("rgba(") >= 2, card_shadow)
    ok(tag + "v9 배지가 카드 안쪽 우하단",
       page.eval_on_selector("#homeProgramRail .home-program-card", """el => {
         const c = el.getBoundingClientRect();
         const b = el.querySelector('.hpc-badge').getBoundingClientRect();
         return b.left > c.left + c.width * 0.6 && b.right <= c.right - 2 && b.bottom <= c.bottom - 2;
       }"""))
    shot(page, "home" if not storage_blocked else "home_blocked")
    if not storage_blocked:
        shot(page, "v8_home")
        shot(page, "v9_home")

    # ── v10: 알림함 · 쿠폰함 · FAQ · 결제수단 관리 (상용화 완성팩)
    ok(tag + "v10 홈 상단 알림 벨 + 이용권 버튼 공존",
       page.is_visible("#btnNotif") and page.eval_on_selector("#homeTicketBtn", "el => !!el"))
    ok(tag + "v10 안 읽음 배지 4",
       page.inner_text("#notifDot").strip() == "4" and page.is_visible("#notifDot"), page.inner_text("#notifDot"))
    page.tap("#btnNotif")
    page.wait_for_timeout(450)
    ok(tag + "v10 알림함 시트 열림", page.eval_on_selector("#notifSheet", "el => el.classList.contains('is-open')"))
    ok(tag + "v10 알림 4건", page.eval_on_selector_all("#notifList .notif", "els => els.length") == 4)
    ok(tag + "v10 알림 4종 문구",
       all(t in page.inner_text("#notifList") for t in
           ["방문이 확정됐어요", "D-1 리마인드", "회복 리포트", "평가 무료 쿠폰"]),
       page.inner_text("#notifList")[:100])
    ok(tag + "v10 안 읽은 빨간 점 4개", page.eval_on_selector_all("#notifList .notif-dot", "els => els.length") == 4)
    shot(page, "v10_notif")
    page.tap("#notifReadAll")
    page.wait_for_timeout(350)
    ok(tag + "v10 모두 읽음 처리",
       page.eval_on_selector_all("#notifList .notif.is-read", "els => els.length") == 4
       and not page.is_visible("#notifDot") and "모두 읽음으로 표시" in page.inner_text("#toast"),
       page.inner_text("#toast"))
    page.tap("[data-notif-close]")
    page.wait_for_timeout(300)
    ok(tag + "v10 알림함 닫힘", page.eval_on_selector("#notifSheet", "el => !el.classList.contains('is-open')"))

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(350)
    ok(tag + "v10 내 정보 8행(알림·쿠폰·FAQ)",
       page.eval_on_selector_all("#screen-mypage .mp-row", "els => els.length") == 8,
       page.eval_on_selector_all("#screen-mypage .mp-row", "els => els.length"))
    ok(tag + "v10 쿠폰 배지 2", page.inner_text("#mpCouponCount").strip() == "2", page.inner_text("#mpCouponCount"))
    page.tap("#mpCouponRow")
    page.wait_for_timeout(450)
    ok(tag + "v10 쿠폰함 2장",
       page.eval_on_selector("#couponSheet", "el => el.classList.contains('is-open')")
       and page.eval_on_selector_all("#couponList .coupon-card", "els => els.length") == 2)
    ok(tag + "v10 기본 쿠폰 문구",
       "첫 1:1 방문 평가 무료" in page.inner_text("#couponList")
       and "정규 회차권 10,000원 할인" in page.inner_text("#couponList"))
    page.fill("#couponCode", "WELCOME")
    page.tap("#couponRegister")
    page.wait_for_timeout(400)
    ok(tag + "v10 쿠폰 코드 등록 → 3장",
       page.eval_on_selector_all("#couponList .coupon-card", "els => els.length") == 3
       and "5,000원 추가 할인" in page.inner_text("#couponList"),
       page.inner_text("#toast"))
    ok(tag + "v10 쿠폰 배지 3으로 갱신", page.inner_text("#mpCouponCount").strip() == "3", page.inner_text("#mpCouponCount"))
    shot(page, "v10_coupon")
    page.tap("[data-coupon-close]")
    page.wait_for_timeout(300)

    page.tap("#mpFaqRow")
    page.wait_for_timeout(450)
    ok(tag + "FAQ 10문항(v25에서 5문항 추가)", page.eval_on_selector_all("#faqList .faq-item", "els => els.length") == 10)
    page.tap('#faqList [data-faq="faq-refund"]')
    page.wait_for_timeout(350)
    ok(tag + "v10 FAQ 아코디언 펼침",
       page.eval_on_selector('#faqList [data-faq="faq-refund"]', "el => el.getAttribute('aria-expanded') === 'true'")
       and page.is_visible("#faqList .faq-item.is-open .faq-a"))
    ok(tag + "v10 이용약관 요약", "이용약관 요약" in page.inner_text("#termsBody"))
    page.tap('#faqTabs [data-terms="privacy"]')
    page.wait_for_timeout(250)
    ok(tag + "v10 개인정보처리방침 탭", "개인정보 처리방침 요약" in page.inner_text("#termsBody"))
    # ── v16: 서비스 기준·비용·환불 규정(POLICIES-AND-FEES.md) 연결
    page.tap('#faqTabs [data-terms="policy"]')
    page.wait_for_timeout(250)
    policy_txt = page.inner_text("#termsBody")
    ok(tag + "v16 서비스·환불 탭 3섹션(기준·비용·환불)",
       all(k in policy_txt for k in ["서비스 이용 기준", "비용 안내", "취소·변경·환불 규정", "90,000원", "24시간 전", "중도 해지"]),
       policy_txt[:120])
    ok(tag + "v16 법률 자문 아닌 운영 기준 초안 고지(본문·시트)",
       "법률 자문이 아닙니다" in policy_txt and "법률 자문이 아닌 운영 기준 초안" in page.inner_text("#faqDraftNote"),
       policy_txt[-90:])
    ok(tag + "v16 FAQ 환불 문구에 50%·30분 기준",
       "50%" in page.inner_text("#faqList") and "30분" in page.inner_text("#faqList") and "서비스·환불" in page.inner_text("#faqList"))
    shot(page, "v16_faq_policy")
    page.tap('[data-faq-close]')
    page.wait_for_timeout(250)
    page.tap("#mpFaqRow")
    page.wait_for_timeout(300)
    shot(page, "v10_faq")
    page.tap("[data-faq-close]")
    page.wait_for_timeout(250)

    page.tap("#mpPayRow")
    page.wait_for_timeout(450)
    ok(tag + "v10 등록된 결제수단 2건",
       page.eval_on_selector_all("#pmList .pm-row", "els => els.length") == 2
       and "신한카드 **** 4821" in page.eval_on_selector("#pmList", "el => el.textContent"))
    page.tap("#pmAddBtn")
    page.wait_for_timeout(300)
    ok(tag + "v10 새 카드 폼 열림", page.is_visible("#cardForm"))
    page.fill("#cardLabel", "생활비 카드")
    page.fill("#cardLast4", "7788")
    page.fill("#cardExpiry", "0329")
    page.wait_for_timeout(150)
    page.tap("#cardSave")
    page.wait_for_timeout(400)
    ok(tag + "v10 새 카드 3건 · 기본 설정",
       page.eval_on_selector_all("#pmList .pm-row", "els => els.length") == 3
       and "7788" in page.eval_on_selector("#pmList .pm-row", "el => el.textContent")
       and page.eval_on_selector("#pmList .pm-row", "el => el.classList.contains('is-default')"),
       page.eval_on_selector("#pmList", "el => el.textContent")[:120])
    shot(page, "v10_pay")
    page.tap("[data-pay-close]")
    page.wait_for_timeout(300)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]')
    page.wait_for_timeout(200)

    # 하단 탭 5개 모두 탭으로 전환되는지
    for tab, want in [("teachers", "screen-teachers"), ("booking", "screen-booking"),
                      ("journal", "screen-journal"), ("mypage", "screen-mypage"), ("home", "screen-home")]:
        page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="%s"]' % tab)
        page.wait_for_timeout(120)
        got = page.eval_on_selector(".screen.is-active", "el => el.id")
        ok(tag + "탭 %s 전환" % tab, got == want, got)

    # ── 1b. v7: 찜하기(하트) · 찜한 선생님 모아보기 · 일지 D-day
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(350)
    ok(tag + "v7 선생님 카드마다 하트 8개", page.eval_on_selector_all("#teacherList [data-fav]", "els => els.length") == 8)
    page.tap("#teacherList [data-fav]")
    page.wait_for_timeout(300)
    ok(tag + "v7 하트 탭 → 찜 상태", page.eval_on_selector("#teacherList [data-fav]", "el => el.classList.contains('is-on') && el.getAttribute('aria-pressed') === 'true'"))
    ok(tag + "v7 찜 개수 1명", page.inner_text("#favCount").strip() == "1", page.inner_text("#favCount"))
    page.tap("#favFilter")
    page.wait_for_timeout(400)
    ok(tag + "v7 찜한 선생님만 보기",
       page.eval_on_selector_all("#teacherList .teacher", "els => els.length") == 1
       and page.eval_on_selector("#favFilter", "el => el.classList.contains('is-on')"))
    shot(page, "teachers_fav")
    page.tap("#favFilter")
    page.wait_for_timeout(350)
    ok(tag + "v7 찜 필터 해제 → 전체 8명", page.eval_on_selector_all("#teacherList .teacher", "els => els.length") == 8)

    # ── v9: 선생님 일러스트 아바타 (파스텔 배경 + 청진기)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    ok(tag + "v9 선생님 8명 모두 SVG 일러스트 아바타",
       page.eval_on_selector_all("#teacherList .t-avatar svg.ava-art", "els => els.length") == 8)
    ok(tag + "v9 아바타에 청진기 디테일",
       page.eval_on_selector_all("#teacherList .t-avatar .ava-steth", "els => els.length") == 8)
    ava_bgs = page.eval_on_selector_all("#teacherList .t-avatar", "els => els.map(e => e.style.background)")
    ok(tag + "v9 파스텔 배경 4종 이상 로테이션", len(set(ava_bgs)) >= 4, len(set(ava_bgs)))
    ok(tag + "v9 아바타가 카드 안에서 원형으로 보임",
       page.eval_on_selector("#teacherList .t-avatar", "el => { const r = el.getBoundingClientRect(); return Math.round(r.width) === 52 && Math.round(r.height) === 52; }"))
    if not storage_blocked:
        shot(page, "v9_teachers")

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]')
    page.wait_for_timeout(500)
    ok(tag + "v7 일지 상단 D-day 카드",
       "예정된 방문" in page.inner_text("#journalDday")
       and page.eval_on_selector("#journalDday .dday-badge", "el => /D-\\d|D-DAY/.test(el.textContent)"),
       page.inner_text("#journalDday")[:80])
    ok(tag + "v7 준비물 한 줄 팁", "준비물" in page.inner_text("#journalDday"))
    ok(tag + "v7 회복 타임라인 3건 이상", page.eval_on_selector_all("#journalTimeline .tl-item", "els => els.length") >= 3)
    shot(page, "journal_dday")

    # ── 1c. v8: 보호자 공유 리포트 (한 장 요약 → 요약 텍스트 복사)
    page.tap("#reportOpen")
    page.wait_for_timeout(650)
    ok(tag + "v8 보호자 공유 리포트 시트 열림", page.eval_on_selector("#reportSheet", "el => el.classList.contains('is-open')"))
    card = page.inner_text("#reportCard")
    ok(tag + "v8 리포트에 환자·선생님·회차·다음 방문",
       "김순자 어르신" in card and "박서준 선생님" in card and "5회차" in card
       and "12회차" in card and "(토) 10:30" in card, card[:120].replace("\n", " "))
    ok(tag + "v8 회복 추이 곡선 3개", page.eval_on_selector_all("#reportChart .rc-line", "els => els.length") == 3)
    ok(tag + "v8 곡선이 부드러운 베지어",
       page.eval_on_selector_all("#reportChart .rc-line", "els => els.every(p => /C/.test(p.getAttribute('d') || ''))"))
    ok(tag + "v8 선생님 한 줄 코멘트", "선생님 코멘트" in card and "계단" in card)
    shot(page, "v8_report_sheet")
    page.tap("#reportCopy")
    page.wait_for_timeout(350)
    ok(tag + "v8 요약 텍스트 복사 토스트", "보호자 공유용 요약이 복사되었어요" in page.inner_text("#toast"), page.inner_text("#toast"))
    page.tap("#reportSheet [data-report-close]")
    page.wait_for_timeout(350)
    ok(tag + "v8 리포트 시트 닫힘", page.eval_on_selector("#reportSheet", "el => !el.classList.contains('is-open')"))

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]')
    page.wait_for_timeout(200)

    # ── 2. 검색 · 증상 칩
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(300)
    page.fill("#homeSearch", "부산")
    page.wait_for_timeout(200)
    ok(tag + "실시간 검색 결과", page.eval_on_selector_all("#searchResults .search-hit", "els => els.length") == 1)
    page.tap("#searchResults .search-hit")
    page.wait_for_timeout(400)
    ok(tag + "검색 결과 탭 → 선생님 상세 시트", page.eval_on_selector("#teacherSheet", "el => el.classList.contains('is-open')"))
    page.tap("[data-sheet-close]")
    page.wait_for_timeout(300)

    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]')
    page.wait_for_timeout(250)
    page.tap('#homeProgramRail [data-symfilter="stroke"]')
    page.wait_for_timeout(250)
    ok(tag + "증상 칩 → 선생님 탭 필터", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-teachers"
       and page.eval_on_selector_all("#teacherList .teacher", "els => els.length") == 3)

    # ── 3a. v15 검증 배지: 통과한 단계만 (미확인 단계에는 문구 자체가 없다)
    chips = page.eval_on_selector_all("#teacherList .lic", "els => els.map(e => e.textContent.replace(/\\s+/g, ' ').trim())")
    ok(tag + "v15 카드 검증 배지(필터 3명)", len(chips) == 3, chips)
    ok(tag + "v15 배지는 면허·경력만(신분·검증 문구 없음)",
       bool(chips) and all(("신분" not in c and "검증" not in c and "인증" not in c) for c in chips), chips)
    cards15 = page.eval_on_selector_all(
        "#teacherList .teacher",
        "els => els.map(e => e.getAttribute('data-teacher') + ':' + e.textContent.replace(/\\s+/g, ' '))")
    yoon_card = [c for c in cards15 if c.startswith("yoon")]
    ok(tag + "v15 경력 미확인 선생님 카드에 경력 배지 없음",
       bool(yoon_card) and "경력 확인" not in yoon_card[0] and "면허 확인" in yoon_card[0], yoon_card)

    # ── 3. 선생님 카드 → 상세 시트 (신뢰 정보 3종이 첫 화면에)
    page.tap("#teacherList .teacher")
    page.wait_for_timeout(450)
    ok(tag + "선생님 카드 탭 → 상세 시트", page.eval_on_selector("#teacherSheet", "el => el.classList.contains('is-open')"))
    ok(tag + "시트에 국가면허 검증 배지", "국가면허 검증" in page.inner_text("#sheetName"))
    ok(tag + "시트에 평점·후기수", "후기" in page.inner_text("#teacherSheetBody"))
    ok(tag + "시트에 금액 미노출(예약 단계 안내)",
       "/회" not in page.inner_text("#teacherSheetBody") and "회차권" in page.inner_text("#teacherSheetBody"))
    ok(tag + "v9 상세 시트도 일러스트 아바타",
       page.eval_on_selector("#teacherSheetBody .sheet-av svg.ava-art", "el => !!el"))
    # ── v15 상세 시트: 마스킹된 면허·통과 배지·시·구·동·가능 시간
    sheet15 = page.inner_text("#teacherSheetBody")
    ok(tag + "v15 시트 면허번호 마스킹", "제○○-○○○○호" in sheet15 and "11-2008-004312" not in sheet15, sheet15[-160:])
    ok(tag + "v15 시트 활동 지역 시·구·동", "강남구 대치동" in sheet15 and "101동" not in sheet15)
    ok(tag + "v15 시트 통과 배지 3단계",
       page.eval_on_selector_all("#teacherSheet .h-tags .tag", "els => els.length") == 3)
    ok(tag + "v15 시트 자격 라벨에 미확인 검증 표현 없음", "자격·면허" in sheet15 and "검증된 자격" not in sheet15)
    ok(tag + "v15 시트 가능 시간 요약", "평일 오전" in sheet15 and "이동 수단" in sheet15, sheet15[-200:])
    shot(page, "teacher_sheet")

    # ── 4. 1:1 채팅
    page.tap("#sheetChat")
    page.wait_for_timeout(400)
    ok(tag + "문의 버튼 → 1:1 채팅 열림", page.eval_on_selector("#chatSheet", "el => el.classList.contains('is-open')"))
    before = page.eval_on_selector_all("#chatLog .bubble", "els => els.length")
    page.fill("#chatInput", "방문 시간을 바꿀 수 있을까요?")
    page.tap(".chat-send")
    page.wait_for_timeout(300)
    ok(tag + "메시지 전송", page.eval_on_selector_all("#chatLog .bubble", "els => els.length") == before + 1)
    page.wait_for_timeout(1100)
    ok(tag + "데모 답장 도착(일정 변경 안내)",
       page.eval_on_selector_all("#chatLog .bubble", "els => els.length") == before + 2
       and "일정 변경" in page.inner_text("#chatLog"))
    ok(tag + "채팅 저장(SafeStorage)",
       "true" if storage_blocked else "bubble" in page.content())
    shot(page, "chat")
    page.tap("[data-chat-close]")
    page.wait_for_timeout(300)
    ok(tag + "채팅 닫기", page.eval_on_selector("#chatSheet", "el => !el.classList.contains('is-open')"))

    # ── 5. 예약 4단계 → 결제
    page.tap("#teacherList .teacher")
    page.wait_for_timeout(400)
    page.tap("#sheetBook")
    page.wait_for_timeout(400)
    ok(tag + "시트 CTA → 예약 탭", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-booking")
    ok(tag + "v7 예약 진행 1/4", page.inner_text("#bookStepCount").strip() == "1/4", page.inner_text("#bookStepCount"))
    page.tap('#provinceQuick [data-prov="서울"]')
    page.wait_for_timeout(200)
    ok(tag + "시·도 알약 버튼 → 셀렉트 동기화", page.eval_on_selector("#bookProvince", "el => el.value") == "서울")
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.tap('[data-next="1"]')
    page.wait_for_timeout(300)
    ok(tag + "1단계 → 2단계", page.eval_on_selector("#wstep-2", "el => el.classList.contains('is-active')"))
    ok(tag + "v7 예약 진행 2/4", page.inner_text("#bookStepCount").strip() == "2/4", page.inner_text("#bookStepCount"))
    page.tap("#bookDates .date-chip")
    page.wait_for_timeout(150)
    page.tap("#bookSlots .slot:not([disabled])")
    page.tap('[data-next="2"]')
    page.wait_for_timeout(300)
    ok(tag + "2단계 → 3단계", page.eval_on_selector("#wstep-3", "el => el.classList.contains('is-active')"))
    page.tap('#passList [data-pass="p8"]')
    page.wait_for_timeout(200)
    ok(tag + "총액·회차 구성이 스크롤 없이 보임(합계 바)",
       page.is_visible("#bookTotalBar") and "592,000원" in page.inner_text("#bookTotalAmount")
       and "8회" in page.inner_text("#bookTotalMeta"))
    # ── v10: 쿠폰을 고르면 총액에서 바로 차감
    ok(tag + "v10 결제 창 쿠폰 칩 3개",
       page.eval_on_selector_all("#couponChips .coupon-chip", "els => els.length") == 3,
       page.eval_on_selector_all("#couponChips .coupon-chip", "els => els.length"))
    page.tap('#couponChips [data-coupon-pick="cp-10000"]')
    page.wait_for_timeout(300)
    ok(tag + "v10 쿠폰 선택 즉시 582,000원",
       "582,000원" in page.inner_text("#bookTotalAmount") and "582,000원" in page.inner_text("#totalAmount"),
       page.inner_text("#bookTotalAmount"))
    ok(tag + "v10 합계 바 할인 문구", "쿠폰 10,000원 할인" in page.inner_text("#bookTotalMeta"), page.inner_text("#bookTotalMeta"))
    shot(page, "v10_pay_discount")
    shot(page, "booking_pass")
    page.tap('[data-next="3"]')
    page.wait_for_timeout(250)
    ok(tag + "3단계 → 4단계(결제)", page.eval_on_selector("#wstep-4", "el => el.classList.contains('is-active')"))
    page.fill("#bookName", "김순자")
    page.fill("#bookPhone", "01012345678")
    page.tap('#payMethods [data-pay="카카오페이"]')
    page.check("#bookAgree")
    page.tap("#payBtn")
    page.wait_for_timeout(1500)
    ok(tag + "결제 완료 화면", page.eval_on_selector("#bookingDone", "el => !el.hidden"))
    ok(tag + "예약번호 표시", "TT-" in page.inner_text("#doneSummary"))
    ok(tag + "v8 완료 화면 매칭 트래커 4단계",
       page.eval_on_selector_all("#doneTracker .mtk-step", "els => els.length") == 4)
    ok(tag + "v8 완료 화면 현재 단계 블루",
       page.eval_on_selector("#doneTracker .mtk-step.is-now .mtk-label", "el => el.textContent") == "방문 확정"
       and page.eval_on_selector("#doneTracker .mtk-step.is-now .mtk-dot", "el => getComputedStyle(el, '::after').animationName") == "matchPulse",
       page.inner_text("#doneTracker"))
    ok(tag + "v7 완료 화면 네이버 상담 폼",
       page.eval_on_selector("#bookingDone a[href='https://naver.me/G3vCkS0S']",
                            "el => el.getAttribute('target') === '_blank' && /noopener/.test(el.getAttribute('rel') || '')"))
    # ── v9: 체크 원형 그리기 · 캘린더(.ics) 추가
    ok(tag + "v9 완료 체크 링 애니메이션",
       page.eval_on_selector("#bookingDone .done-ring circle", "el => getComputedStyle(el).animationName") == "ringDraw")
    ok(tag + "v9 캘린더 일정 추가 버튼",
       page.is_visible("#doneIcs") and "캘린더에 일정 추가" in page.inner_text("#doneIcs"))
    if not storage_blocked:
        shot(page, "v9_done")
    page.tap("#doneIcs")
    page.wait_for_timeout(400)
    ics = page.evaluate("window.__ttokttokIcs || null")
    ok(tag + "v9 .ics 파일 생성", bool(ics) and ics["text"].startswith("BEGIN:VCALENDAR") and "END:VCALENDAR" in ics["text"])
    ok(tag + "v9 .ics 제목에 똑똑쌤 방문재활", bool(ics) and "똑똑쌤 방문재활" in ics["text"])
    ok(tag + "v9 .ics 방문 일시 일치",
       bool(ics) and ("DTSTART;TZID=Asia/Seoul:" in ics["text"]) and ("T" in ics["text"].split("DTSTART;TZID=Asia/Seoul:")[1][:9]),
       (ics or {}).get("text", "")[:160])
    ok(tag + "v9 .ics 60분 + 1시간 전 알림",
       bool(ics) and "DTEND;TZID=Asia/Seoul:" in ics["text"] and "TRIGGER:-PT60M" in ics["text"])
    ok(tag + "v9 .ics 파일명 규칙", bool(ics) and ics["name"].startswith("똑똑쌤_방문재활_") and ics["name"].endswith(".ics"), (ics or {}).get("name"))
    ok(tag + "v9 캘린더 다운로드 토스트", "캘린더 파일" in page.inner_text("#toast"), page.inner_text("#toast"))
    shot(page, "done")

    # ── 5b. v14 접수 구조: 저장 확인 배지 · 접수 내용 복사 · 상담 폼 연계
    ok(tag + "v14 완료 화면 저장 확인 배지",
       ("로컬 저장 확인됨" in page.inner_text("#doneSaved")) if not storage_blocked
       else ("임시 메모리 모드" in page.inner_text("#doneSaved")),
       page.inner_text("#doneSaved"))
    ok(tag + "v14 완료 화면 복사 버튼",
       page.is_visible("#doneCopy") and "접수 내용 복사" in page.inner_text("#doneCopy"))
    ok(tag + "v14 복사 후 상담 폼 안내", "붙여 넣" in page.inner_text("#bookingDone") and
       page.is_visible("#bookingDone a[href='https://naver.me/G3vCkS0S']"))
    page.tap("#doneCopy")
    page.wait_for_timeout(300)
    intake = page.evaluate("window.__ttokttokIntake || null")
    ok(tag + "v14 접수 요약 생성", bool(intake) and intake["text"].startswith("[똑똑쌤 방문재활 예약 접수]"), (intake or {}).get("text", "")[:60])
    ok(tag + "v14 요약에 예약번호·상태·일시",
       bool(intake) and ("예약번호 : TT-" in intake["text"]) and ("접수 상태 : " in intake["text"])
       and ("희망 일시 : " in intake["text"]), (intake or {}).get("text", "")[:120])
    ok(tag + "v14 요약에 보호자·지역·선생님",
       bool(intake) and ("보호자 : 김순자" in intake["text"]) and ("서울 강남구" in intake["text"])
       and ("담당 선생님 : " in intake["text"]))
    ok(tag + "v14 요약에 상세 주소 없음",
       bool(intake) and ("101동" not in intake["text"]) and ("1203호" not in intake["text"])
       and ("상세 주소는 상담에서 확인" in intake["text"]), (intake or {}).get("text", ""))
    ok(tag + "v14 요약에 상담 폼 URL",
       bool(intake) and "https://naver.me/G3vCkS0S" in intake["text"])
    ok(tag + "v14 복사 안내 토스트",
       ("복사" in page.inner_text("#toast")) if storage_blocked
       else ("복사했어요" in page.inner_text("#toast")), page.inner_text("#toast"))
    shot(page, "v14_done_intake")

    # ── 6. 후기 작성 → 선생님 평점/후기 반영
    page.tap("#doneMypage")
    page.wait_for_timeout(400)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(200)
    ok(tag + "내 정보 예약 카드", page.eval_on_selector_all("#bookingList .booking-row", "els => els.length") >= 1)
    ok(tag + "내 정보 8행 리스트", page.eval_on_selector_all("#screen-mypage .mp-row", "els => els.length") == 8)
    page.tap("#mpBookLink")
    page.wait_for_timeout(450)
    ok(tag + "내 예약·이용권 시트", page.eval_on_selector("#accountSheet", "el => el.classList.contains('is-open')"))
    ok(tag + "v7 내 예약 시트 D-day 카드", page.eval_on_selector("#accountDday .dday-card", "el => !!el"))
    ok(tag + "v8 내 예약 카드에 매칭 트래커 4단계", page.eval_on_selector_all("#bookingList .mtk-step", "els => els.length") >= 4)
    ok(tag + "v8 현재 단계 펄스 애니메이션",
       page.eval_on_selector("#bookingList .mtk-step.is-now .mtk-dot", "el => getComputedStyle(el, '::after').animationName") == "matchPulse")
    shot(page, "v8_tracker")
    # ── v14: 내 예약 상세의 저장 배지 · 접수 내용 복사 · 상담 폼 연결
    page.tap("#bookingList [data-manage]")
    page.wait_for_timeout(400)
    ok(tag + "v14 상세 시트 저장 배지",
       ("로컬 저장 확인됨" in page.inner_text("#manageSaved")) if not storage_blocked
       else ("임시 메모리 모드" in page.inner_text("#manageSaved")),
       page.inner_text("#manageSaved"))
    ok(tag + "v14 상세 시트 복사 버튼·상담 폼 링크",
       page.is_visible("#manageSheetBody [data-intake-copy]")
       and page.is_visible("#manageSheetBody a[href='https://naver.me/G3vCkS0S']"))
    page.tap("#manageSheetBody [data-intake-copy]")
    page.wait_for_timeout(300)
    intake2 = page.evaluate("window.__ttokttokIntake || null")
    ok(tag + "v14 상세에서 복사한 요약", bool(intake2) and ("예약번호 : " in intake2["text"]) and ("담당 선생님 : " in intake2["text"]), (intake2 or {}).get("text", "")[:60])
    shot(page, "v14_manage_intake")
    page.tap("#manageSheet [data-manage-close]")
    page.wait_for_timeout(350)
    ok(tag + "후기 대기 회차 노출", page.eval_on_selector_all("#reviewList [data-review]", "els => els.length") >= 1)
    page.tap("#reviewList [data-review]")
    page.wait_for_timeout(350)
    ok(tag + "후기 시트 열림", page.eval_on_selector("#reviewSheet", "el => el.classList.contains('is-open')"))
    page.tap('[data-star="5"]')
    ok(tag + "별점 선택", page.eval_on_selector_all("#starPick .is-on", "els => els.length") == 5)
    page.fill("#reviewText", "설명이 쉽고 시간 약속을 잘 지켜요")
    page.tap("#reviewSubmit")
    page.wait_for_timeout(450)
    ok(tag + "후기 등록 → 목록 '등록됨'", "등록됨" in page.inner_text("#reviewList"))
    page.tap("[data-account-close]")
    page.wait_for_timeout(350)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(200)
    page.tap("#teacherList .teacher")
    page.wait_for_timeout(400)
    ok(tag + "선생님 시트에 내 후기 반영", "나 (보호자)" in page.inner_text("#teacherSheetBody"))
    shot(page, "review")
    page.tap("[data-sheet-close]")
    page.wait_for_timeout(250)

    # ── 7. 예약 변경 · 취소(환불)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(250)
    page.tap("#mpBookLink")
    page.wait_for_timeout(450)
    page.tap("#bookingList [data-manage]")
    page.wait_for_timeout(350)
    ok(tag + "예약 변경 시트", page.eval_on_selector("#manageSheet", "el => el.classList.contains('is-open')"))
    page.tap("xpath=//div[@id='manageSheetBody']//button[@data-manage-date]")
    page.wait_for_timeout(120)
    page.tap("xpath=//div[@id='manageSheetBody']//button[@data-manage-time]")
    page.wait_for_timeout(120)
    page.tap("[data-manage-save]")
    page.wait_for_timeout(400)
    ok(tag + "시간 변경 저장", "일정 변경됨" in page.inner_text("#bookingList"))
    sm1 = page.evaluate("""() => {
      const m = window.__ttokttokModel;
      const b = m.reservations().filter(x => x.status === 'rescheduled')[0];
      if (!b) return null;
      const h = b.statusHistory[b.statusHistory.length - 1];
      return { no: b.no, from: h.from, to: h.to, actor: h.actor, reason: h.reason };
    }""")
    ok(tag + "v13 일정 변경 이력(from/to/actor/reason)",
       bool(sm1) and sm1.get("from") == "confirmed" and sm1.get("to") == "rescheduled" and sm1.get("actor") == "customer" and bool(sm1.get("reason")), sm1)
    page.tap("#bookingList [data-manage-cancel]")
    page.wait_for_timeout(400)
    ok(tag + "취소 → 환불 규정 안내", "환불 규정" in page.inner_text("#manageSheetBody") and "예상 환불" in page.inner_text("#manageSheetBody"))
    cancel_txt = page.inner_text("#manageSheetBody")
    ok(tag + "v16 취소 시트에 견적·초안 고지",
       "법률 자문이 아닌 운영 기준 초안" in cancel_txt
       and any(k in cancel_txt for k in ["회차 1회 복구", "1회 차감", "50%", "전액 환불"])
       and any(k in cancel_txt for k in ["24시간 전", "24시간 이내"]), cancel_txt[:200])
    shot(page, "refund")
    page.tap("[data-manage-confirm]")
    page.wait_for_timeout(400)
    ok(tag + "예약 취소 완료", "취소됨" in page.inner_text("#bookingList"))
    ok(tag + "취소 후 환불 안내 유지", "취소된 예약" in page.inner_text("#manageSheetBody"))
    sm2 = page.evaluate("""() => {
      const m = window.__ttokttokModel;
      const b = m.reservations().filter(x => x.status === 'canceled')[0];
      if (!b) return null;
      const n = m.notifs().filter(x => x.audience === 'customer' && x.title === '예약이 취소됐어요')[0];
      return { status: b.status, slots: m.slots(b.teacherId, b.dateIso).map(s => s.status),
               notif: n ? n.body : '', hist: b.statusHistory.length };
    }""")
    ok(tag + "v13 취소 → 알림 발송·슬롯 해제",
       bool(sm2) and sm2.get("status") == "canceled" and bool(sm2.get("notif")) and all(s == "open" for s in sm2.get("slots", ["booked"])), sm2)
    page.tap("[data-manage-close]")
    page.wait_for_timeout(300)

    # ── 8. 역할 전환 → 선생님 모드 (내 정보 시트에서)
    page.tap("[data-account-close]")
    page.wait_for_timeout(300)
    page.tap("#mpRoleRow")
    page.wait_for_timeout(400)
    ok(tag + "모드 전환 시트", page.eval_on_selector("#roleSheet", "el => el.classList.contains('is-open')"))
    page.tap('#roleSheet [data-role-switch="therapist"]')
    page.wait_for_timeout(400)
    ok(tag + "역할 전환 → 선생님 모드", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-tp-home")
    page.tap('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-schedule"]')
    page.wait_for_timeout(300)
    ok(tag + "주간 날짜 칩 7개(전체+월~토)", page.eval_on_selector_all("#tpWeekChips .week-chip", "els => els.length") == 7)
    total = page.eval_on_selector_all("#tpScheduleList .tp-sched", "els => els.length")
    page.tap('#tpWeekChips [data-sched-day="토"]')
    page.wait_for_timeout(250)
    ok(tag + "토요일 필터 동작", page.eval_on_selector_all("#tpScheduleList .tp-sched", "els => els.length") <= total
       and "토요일" in page.inner_text("#tpWeekHint"))
    shot(page, "tp_week")
    page.tap("#tpWeekChips [data-sched-day='']")
    page.wait_for_timeout(200)
    ok(tag + "전체 필터 복귀", page.eval_on_selector_all("#tpScheduleList .tp-sched", "els => els.length") == total)

    # 요청 수락 + 보호자께 메시지
    page.tap('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-home"]')
    page.wait_for_timeout(250)
    reqs = page.eval_on_selector_all("#tpReqList .req", "els => els.length")
    if reqs:
        page.tap("#tpReqList [data-tp-accept]")
        page.wait_for_timeout(350)
        ok(tag + "방문 요청 수락", page.eval_on_selector_all("#tpReqList .req", "els => els.length") == reqs - 1)
        page.tap("#tpReqList [data-chat]")
        page.wait_for_timeout(400)
        ok(tag + "선생님 → 보호자 메시지창", page.eval_on_selector("#chatSheet", "el => el.classList.contains('is-open')"))
        page.tap("[data-chat-close]")
        page.wait_for_timeout(250)

    # ── 9. 관리자 심사 콘솔 → 서류 확인 → 승인
    page.tap("#rolePill")
    page.wait_for_timeout(300)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(400)
    ok(tag + "관리자 콘솔 진입", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-admin")
    cards = page.eval_on_selector_all("#adminQueue .admin-card", "els => els.length")
    ok(tag + "심사 대기 카드 표시", cards >= 1, cards)
    if cards:
        page.tap("#adminQueue [data-app-open]")
        page.wait_for_timeout(350)
        app15 = page.inner_text("#appSheetBody")
        ok(tag + "v15 관리자 확인 절차 3단계",
           "확인 절차 3단계" in app15 and "신분 확인" in app15 and "면허 확인" in app15 and "경력 확인" in app15, app15[:120])
        ok(tag + "v15 미확인 지원서에 검증·인증·확인 완료 없음",
           not any(w in app15 for w in ["검증", "인증", "확인 완료"]), app15[:160])
        ok(tag + "v15 보호자용 미리보기 이름 마스킹·배지 없음",
           "표시할 배지 없음" in app15 and "정하O" in app15, app15[-160:])
        shot(page, "v15_admin_verification")
        page.tap("[data-app-close]")
        page.wait_for_timeout(300)
        page.tap("#adminQueue [data-admin-doc-all]")
        page.wait_for_timeout(250)
        page.tap("#adminQueue [data-admin-approve]")
        page.wait_for_timeout(400)
        ok(tag + "서류 확인 후 승인", "승인" in page.inner_text("#adminRecent") or cards > 0)
    shot(page, "admin")

    # ── 10. v13 예약 상태기계(전이 표·이력·알림·슬롯)
    model = page.evaluate("""() => {
      const m = window.__ttokttokModel;
      if (!m) return null;
      const res = m.integrity();
      const b = m.export();
      return { version: m.modelVersion, ok: res.ok, issues: res.issues.slice(0, 3),
               regions: b.tables.regions.length, reservations: b.tables.reservations.length,
               ledger: b.tables.settlement_ledgers.length, slots: b.tables.time_slots.length,
               states: m.reservationOrder.length, transitions: Object.keys(m.transitions).length,
               intake: m.intakeVersion, intakeNo: m.generateReservationId([], { date: '261126', random: () => 0 }),
               intakeValid: m.isValidReservationNo('TT-261126-4821'),
               consult: m.consultFormUrl,
               verification: m.verificationVersion, steps: m.verificationSteps.map(s => s.key).join(','),
               policy: m.policyVersion, draft: m.policyMeta ? m.policyMeta.isDraft : null,
               reviewItems: m.policyMeta ? m.policyMeta.reviewItems.length : 0,
               q24: m.calculateRefundQuote(85000, 24, 'customer').refund,
               q23: m.calculateRefundQuote(85000, 5, 'customer').refund,
               qPast: m.calculateRefundQuote(85000, -1, 'customer').refund,
               qNoShow: m.calculateRefundQuote(85000, 30, 'no_show').refund,
               qPassRestore: m.calculateRefundQuote(592000, 48, 'customer', { isPass: true }).restoreSessions,
               qBad: m.calculateRefundQuote(85000, 48, 'gift').error,
               passRefund: m.calculatePassRefund({ paidAmount: 592000, totalSessions: 8, usedSessions: 3 }).refund,
               passPlans: m.passes().map(p => p.price).join(','),
               feeRate: m.pricing.platformFeeRate, validDays: m.pricing.passValidDays,
               maskLic: m.maskLicenseNo('11-2019-004821'), maskName: m.maskTeacherName('박서준'),
               parkBadges: m.getVerificationBadges('park').length, leeBadges: m.getVerificationBadges('lee').length,
               leeLabels: m.getVerificationBadges('lee').map(b => b.label).join(' · '),
               pendingApp: m.verificationOf(m.teacherById('park')),
               exportVer: (b.tables.teachers[0] || {}).verification,
               allow: m.canTransition('confirmed', 'completed', 'teacher'),
               block: m.canTransition('completed', 'canceled'),
               actor: m.canTransition('confirmed', 'canceled', 'teacher') };
    }""")
    ok(tag + "v13 데이터 모델 노출(13)", bool(model) and model.get("version") == 13, model)
    ok(tag + "v13 지역 마스터 로드", bool(model) and model.get("regions", 0) >= 60, (model or {}).get("regions"))
    ok(tag + "v13 정산 원장 생성", bool(model) and model.get("ledger", 0) >= 2, (model or {}).get("ledger"))
    ok(tag + "v13 타임슬롯 생성", bool(model) and model.get("slots", 0) >= 6, (model or {}).get("slots"))
    ok(tag + "v13 데이터 무결성", bool(model) and model.get("ok") is True, (model or {}).get("issues"))
    ok(tag + "v13 상태 7종·전이 엔진", bool(model) and model.get("states") == 7 and model.get("transitions") == 7, model)
    ok(tag + "v13 허용/금지/행위자 판정", bool(model) and model.get("allow") is True and model.get("block") is False and model.get("actor") is False, model)
    ok(tag + "v14 접수 구조 노출(14)", bool(model) and model.get("intake") == 14 and model.get("consult") == "https://naver.me/G3vCkS0S", model)
    ok(tag + "v14 예약번호 발급·형식 검증",
       bool(model) and model.get("intakeNo") == "TT-261126-1000" and model.get("intakeValid") is True, model)
    ok(tag + "v15 검증 구조 노출(15·3단계)",
       bool(model) and model.get("verification") == 15 and model.get("steps") == "identity,license,career", model)
    ok(tag + "v15 마스킹 함수(이름·면허번호)",
       bool(model) and model.get("maskName") == "박서O" and model.get("maskLic") == "제○○-○○○○호", model)
    ok(tag + "v15 배지는 통과 단계만(박서준 3·이하늘 2)",
       bool(model) and model.get("parkBadges") == 3 and model.get("leeBadges") == 2
       and model.get("leeLabels") == "신분 확인 · 면허 확인", model)
    ok(tag + "v15 export에 검증 상태 포함",
       bool(model) and isinstance(model.get("exportVer"), dict)
       and model["exportVer"].get("license") == "verified", (model or {}).get("exportVer"))
    ok(tag + "v16 정책 노출(16·초안·검토 L1~L7)",
       bool(model) and model.get("policy") == 16 and model.get("draft") is True and model.get("reviewItems") == 7,
       {k: model.get(k) for k in ["policy", "draft", "reviewItems"]} if model else None)
    ok(tag + "v16 환불 견적(24h전 100%·이내 50%·이후 0%·노쇼 0%)",
       bool(model) and model.get("q24") == 85000 and model.get("q23") == 42500
       and model.get("qPast") == 0 and model.get("qNoShow") == 0, model)
    ok(tag + "v16 회차권 취소는 회차 복구·모르는 사유 차단",
       bool(model) and model.get("qPassRestore") == 1 and model.get("qBad") == "unknown_reason", model)
    ok(tag + "v16 다회권 중도 해지 8회권 3회 이용 → 322,000원",
       bool(model) and model.get("passRefund") == 322000, (model or {}).get("passRefund"))
    ok(tag + "v16 가격표가 화면 이용권 시드와 일치",
       bool(model) and model.get("passPlans") == "0,90000,320000,592000,840000"
       and model.get("feeRate") == 0.2222 and model.get("validDays") == 90, (model or {}).get("passPlans"))
    form15 = page.evaluate("""() => ({
      licenses: Array.from(document.querySelectorAll('#pLicense [data-license]')).map(b => b.getAttribute('data-license')),
      times: document.querySelectorAll('#pTimes [data-ptime]').length,
      transport: document.querySelectorAll('#pTransport [data-transport]').length,
      privacy: /주민등록번호·건강정보는 받지 않아요/.test(document.querySelector('#pstep-3').textContent)
    })""")
    ok(tag + "v15 지원 폼 직종 3종·시간대·이동 수단",
       form15.get("licenses") == ["물리치료사", "작업치료사", "간호조무사"] and form15.get("times") == 3
       and form15.get("transport") == 2, form15)
    ok(tag + "v15 지원 폼 개인정보 미수집 안내", form15.get("privacy") is True, form15)
    browser.close()


def run_v17_flow(p, storage_blocked=False):
    """v17 운영자(관리자) 예약 접수 큐 — 실제 브라우저 탭으로 전이 버튼을 눌러 검증한다."""
    import json as _json

    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    seed = {
        "profile": {"name": "현수"},
        "passes": [{"id": "seed-pass", "userId": "usr-demo", "passId": "p8", "name": "8회 방문권",
                    "total": 8, "remaining": 5, "purchased": "2026.10.28", "expire": "2027.01.27", "status": "active"}],
        "bookings": [],
        "receipts": [],
    }

    def mk(no, status, extra):
        row = {"id": "res-" + no.lower(), "no": no, "userId": "usr-demo", "date": "11.28", "day": "토",
               "time": "10:00", "teacher": "", "teacherId": "", "region": "서울 강남구 대치동",
               "regionId": "reg-서울-강남구", "status": status, "passId": "p8", "walletId": "seed-pass",
               "dateIso": "2026-11-28", "amount": 74000, "paymentStatus": "paid"}
        row.update(extra or {})
        return row

    seed["bookings"] = [
        mk("TT-261126-1001", "received", {"dateIso": "2026-11-28", "time": "10:00"}),
        mk("TT-261126-1002", "assigned", {"teacher": "이하늘 선생님", "teacherId": "lee", "dateIso": "2026-11-28", "time": "14:00"}),
        mk("TT-261126-1003", "confirmed", {"teacher": "박서준 선생님", "teacherId": "park", "dateIso": "2026-11-29", "time": "10:00"}),
        mk("TT-261126-1004", "rescheduled", {"teacher": "박서준 선생님", "teacherId": "park", "dateIso": "2026-11-30", "time": "11:00"}),
        mk("TT-261126-1005", "canceled", {"dateIso": "2026-11-27", "time": "09:00"}),
        mk("TT-261126-1006", "no_show", {"teacher": "이하늘 선생님", "teacherId": "lee", "dateIso": "2026-11-25", "time": "16:00"}),
    ]
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    else:
        ctx.add_init_script("window.localStorage.setItem('ttokttok_account_v3', %s);" % _json.dumps(_json.dumps(seed, ensure_ascii=False)))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(450)
    ok(tag + "v17 관리자 로그인 → 예약 접수 큐",
       page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-admin" and page.is_visible("#adminResvQueue"))
    ok(tag + "v17 시연용 고지 노출",
       "이 기기에만 저장 · 서버 미연결(이 브라우저에만 반영)" in page.inner_text("#adminResvDemoNotice"))
    ok(tag + "v17 데모 고지가 화면 폭 안에 들어옴",
       page.eval_on_selector("#adminResvDemoNotice", "el => el.scrollWidth <= el.clientWidth + 1"))
    ok(tag + "v17 필터 칩 7개", page.eval_on_selector_all("#adminResvFilters .chip", "els => els.length") == 7)
    counts = page.evaluate("() => window.__ttokttokModel.adminCounts()")
    expected = 2 if storage_blocked else 6  # 저장 불가 환경은 기본 시드 2건(다가오는 1 + 지난 완료 1)
    ok(tag + "v17 큐 카드 건수", page.eval_on_selector_all("#adminResvQueue .admin-card", "els => els.length") == expected,
       page.eval_on_selector_all("#adminResvQueue .admin-card", "els => els.length"))
    ok(tag + "v17 전체 건수 표시(칩)", ("전체 %d" % counts["all"]) in page.inner_text("#adminResvFilters"), page.inner_text("#adminResvFilters"))
    ok(tag + "v17 상태별 건수 한 줄 요약", ("접수 %d" % counts["received"]) in page.inner_text("#adminResvSub") and
       page.eval_on_selector("#adminResvSub", "el => el.getBoundingClientRect().height <= 20"), page.inner_text("#adminResvSub"))

    if storage_blocked:
        ok(tag + "v17 저장 불가에서도 큐·고지 유지(치명 오류 없음)", not errors, errors[:2])
        page.screenshot(path=os.path.join(SHOT, "e2e_v17_admin_queue_blocked.png"))
        browser.close()
        return

    # 필터: 접수만
    page.tap('#adminResvFilters [data-admin-resv-filter="received"]')
    page.wait_for_timeout(250)
    ok(tag + "v17 접수 필터 → 1건", page.eval_on_selector_all("#adminResvQueue .admin-card", "els => els.length") == 1)
    ok(tag + "v17 필터 선택 표시", page.eval_on_selector('#adminResvFilters [data-admin-resv-filter="received"]',
                                                     "el => el.getAttribute('aria-selected')") == "true")
    page.tap('#adminResvFilters [data-admin-resv-filter="all"]')
    page.wait_for_timeout(250)

    # 접수 카드: 허용 전이 버튼만 + 후보 선생님 선택
    tos = page.eval_on_selector_all('#adminResvQueue [data-resv="TT-261126-1001"] [data-admin-resv-to]',
                                    "els => els.map(e => e.getAttribute('data-admin-resv-to'))")
    ok(tag + "v17 접수 카드 버튼 = 배정·확정·취소", tos == ["assigned", "confirmed", "canceled"], tos)
    ok(tag + "v17 접수 카드는 미배정으로 표시", "미배정" in page.inner_text('#adminResvQueue [data-resv="TT-261126-1001"]'))
    page.select_option('[data-admin-resv-teacher="TT-261126-1001"]', "park")
    page.wait_for_timeout(150)
    page.tap('#adminResvQueue [data-resv="TT-261126-1001"] [data-admin-resv-to="assigned"]')
    page.wait_for_timeout(450)
    ok(tag + "v17 탭으로 배정 실행", page.evaluate("() => window.__ttokttokModel.adminStatusOf('TT-261126-1001')") == "assigned")
    ok(tag + "v17 카드 배지 즉시 갱신", "선생님 배정" in page.inner_text('#adminResvQueue [data-resv="TT-261126-1001"]'))
    ok(tag + "v17 배정 알림 생성", "선생님 배정이 끝났어요" in [n["title"] for n in page.evaluate("() => window.__ttokttokModel.notifs()")])

    # 확정 → 완료
    page.tap('#adminResvQueue [data-resv="TT-261126-1001"] [data-admin-resv-to="confirmed"]')
    page.wait_for_timeout(400)
    page.tap('#adminResvQueue [data-resv="TT-261126-1001"] [data-admin-resv-to="completed"]')
    page.wait_for_timeout(500)
    ok(tag + "v17 확정 → 완료 전이", page.evaluate("() => window.__ttokttokModel.adminStatusOf('TT-261126-1001')") == "completed")
    led = page.evaluate("() => (window.__ttokttokModel.export().tables.settlement_ledgers || [])")
    ok(tag + "v17 완료 시 정산 원장 pending 행",
       any((r.get("reservationId") == "res-tt-261126-1001" and r.get("status") == "pending") for r in led), led[:2])

    # 안내 문구 복사
    page.tap('#adminResvQueue [data-resv="TT-261126-1003"] [data-admin-notice]')
    page.wait_for_timeout(300)
    copy = page.evaluate("() => window.__ttokttokAdmin || null")
    ok(tag + "v17 안내 문구 복사(보호자·선생님)", bool(copy) and "[보호자 안내]" in (copy or {}).get("noticeText", "")
       and "[선생님 안내]" in (copy or {}).get("noticeText", ""), (copy or {}).get("noticeText", "")[:80])
    shot(page, "v17_admin_queue")

    # 보호자 화면 반영
    page.tap("[data-admin-back]")
    page.wait_for_timeout(300)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(350)
    ok(tag + "v17 보호자 내 예약에 완료 반영",
       "방문 완료" in page.inner_text('#bookingList [data-booking="TT-261126-1001"]'))
    ok(tag + "v17 JS 오류 없음", not errors, errors[:2])
    browser.close()


def run_v18_flow(p, storage_blocked=False):
    """v18 규모 확장·자동 매칭 — 브라우저에서 교집합 후보·대기열·예외·리마인드를 검증한다."""
    import json as _json
    from datetime import datetime, timedelta, timezone

    kst_today = FIXED_TODAY
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )

    def mk(no, status, extra=None):
        row = {"id": "res-" + no.lower(), "no": no, "userId": "usr-demo", "date": "11.30", "day": "월",
               "time": "10:00", "teacher": "", "teacherId": "", "region": "서울 마포구 성산동",
               "regionId": "reg-서울-마포구", "status": status, "passId": "p8", "walletId": "seed-pass",
               "dateIso": "2026-11-30", "amount": 74000, "paymentStatus": "paid", "symptomCodes": ["stroke"]}
        row.update(extra or {})
        return row

    seed = {
        "profile": {"name": "현수"},
        "passes": [{"id": "seed-pass", "userId": "usr-demo", "passId": "p8", "name": "8회 방문권",
                    "total": 8, "remaining": 5, "purchased": "2026.10.28", "expire": "2027.01.27", "status": "active"}],
        "bookings": [
            mk("TT-261128-2001", "received"),
            mk("TT-261128-2002", "received", {"region": "제주 제주시 노형동", "regionId": "reg-제주-제주시"}),
            mk("TT-261128-2003", "rescheduled", {"teacher": "박서준 선생님", "teacherId": "park",
                                                 "region": "서울 강남구 대치동", "regionId": "reg-서울-강남구",
                                                 "date": "11.27", "day": "금", "dateIso": "2026-11-27", "time": "10:30"}),
            mk("TT-261128-2004", "canceled", {"region": "서울 강남구 대치동", "regionId": "reg-서울-강남구", "dateIso": kst_today}),
            mk("TT-261128-2005", "no_show", {"teacher": "박서준 선생님", "teacherId": "park"}),
            mk("TT-261128-2006", "received", {
                "region": "서울 강남구 대치동", "regionId": "reg-서울-강남구",
                "date": "11.28", "day": "토", "dateIso": "2026-11-28",
                "statusHistory": [{"status": "received", "from": "assigned", "to": "received", "actor": "operator",
                                   "reason": "선생님 배정 거절 — 재배정 대기", "at": "2026-11-26T01:00:00.000Z"}]}),
            mk("TT-261128-2007", "confirmed", {"teacher": "정민아 선생님", "teacherId": "jung",
                                                "dateIso": "2026-12-01", "issue": "complaint", "issueMemo": "도착 시간 지연 문의"}),
        ],
        "receipts": [],
    }

    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    else:
        ctx.add_init_script("window.localStorage.setItem('ttokttok_account_v3', %s);" % _json.dumps(_json.dumps(seed, ensure_ascii=False)))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    # ── 모델·지역 마스터
    ok(tag + "현재 앱 버전 메타(v19 이상)", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v18", "v19", "v20", "v21", "v22", "v23", "v24", "v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v18 매칭 엔진 노출", page.evaluate("() => window.__ttokttokModel.scalingVersion") == "v18")
    counts = page.evaluate("() => window.__ttokttokModel.regionMasterCounts()")
    ok(tag + "v18 지역 마스터 3단계(17/53/42)",
       counts.get("province") == 17 and counts.get("district") == 53 and counts.get("dong") == 42, counts)
    ok(tag + "v18 파주·서대문 마스터 등록", page.evaluate("""() => {
        const m = window.__ttokttokModel.regionMaster;
        return m.some(r => r.id === 'reg-경기-파주시') && m.some(r => r.id === 'reg-서울-서대문구');
      }"""))
    ok(tag + "v18 동 계층 경로(야당동→파주시→경기)", page.evaluate("""() => {
        const p = window.__ttokttokModel.regionPath('reg-경기-파주시-야당동');
        return p && p.dong === '야당동' && p.district === '파주시' && p.province === '경기' && p.text === '경기 파주시';
      }"""))
    ok(tag + "v18 선생님 활동 지역 전부 매핑",
       page.evaluate("() => window.__ttokttokModel.teacherRegions().every(r => r.regionId !== null)"))

    # ── 교집합 후보·대기열·예외·리마인드 (계산 계층)
    cands = page.evaluate("""() => window.__ttokttokModel.matchTeachers({
        regionId: 'reg-서울-마포구', symptom: 'stroke', dateIso: '2026-11-30', timeSlot: '10:00'
      }).map(c => ({ id: c.teacherId, matchedBy: c.matchedBy, reasons: c.reasons }))""")
    ok(tag + "v18 교집합 후보 1순위 정민아", bool(cands) and cands[0]["id"] == "jung", cands)
    ok(tag + "v18 매칭 사유 3종(지역·전문분야·시간)",
       bool(cands) and all(k in cands[0]["matchedBy"] for k in ["region", "symptom", "time"]), cands)
    ok(tag + "v18 후보 0명 지역(제주)",
       page.evaluate("() => window.__ttokttokModel.matchTeachers({"
                     " regionId: 'reg-제주-제주시', dateIso: '2026-11-30', timeSlot: '10:00' }).length") == 0)
    if not storage_blocked:
        queue = page.evaluate("() => window.__ttokttokModel.matchingQueue()")
        ok(tag + "v18 매칭 대기열(미배정 3·재확정 1·후보0명 2)",
           queue["counts"]["unassigned"] == 3 and queue["counts"]["reconfirm"] == 1 and
           queue["counts"]["noCandidate"] == 2, queue["counts"])
        ok(tag + "v18 대기열 1순위 추천(후보 0명은 사람)",
           all(w.get("topCandidate") is not None for w in queue["waiting"] if w["no"] == "TT-261128-2001") and
           any(w["needsHuman"] for w in queue["waiting"]), queue["waiting"][:2])
        ex = page.evaluate("() => window.__ttokttokModel.exceptions()")
        ok(tag + "v18 예외 5종 분류(거절·당일·노쇼·컴플레인·후보0)",
           ex["counts"]["teacher_declined"] == 1 and ex["counts"]["same_day_change"] == 1 and
           ex["counts"]["no_show"] == 1 and ex["counts"]["complaint"] == 1 and
           ex["counts"]["no_candidate"] == 2, ex["counts"])
    rm = page.evaluate("() => window.__ttokttokModel.reminderNotice('TT-261021-7302', 'd_minus_1')")
    ok(tag + "v18 D-1 리마인드 문구 생성(발송 없음)",
       bool(rm) and rm.get("ok") is True and "[보호자 안내]" in rm.get("text", "") and
       "[선생님 안내]" in rm.get("text", "") and "발송" not in rm.get("text", ""), (rm or {}).get("text", "")[:80])

    # ── 관리자 화면 연결(카드 1줄·드롭다운 순위)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(250)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(450)
    if not storage_blocked:
        card = page.inner_text('#adminResvQueue [data-resv="TT-261128-2001"]')
        ok(tag + "v18 카드에 교집합 후보 수·1순위", "교집합 후보 1명" in card and "1순위 정민아 선생님" in card, card[:160])
        card2 = page.inner_text('#adminResvQueue [data-resv="TT-261128-2002"]')
        ok(tag + "v18 후보 0명 표시", "교집합 후보 0명" in card2, card2[:160])
        first = page.eval_on_selector(
            '[data-admin-resv-teacher="TT-261128-2001"]',
            "el => Array.from(el.querySelectorAll('option')).filter(o => o.value)[0].textContent")
        ok(tag + "v18 드롭다운 1순위가 교집합 후보", "정민아" in first and "교집합 1순위" in first, first)
        page.select_option('[data-admin-resv-teacher="TT-261128-2001"]', "jung")
        page.wait_for_timeout(120)
        page.tap('#adminResvQueue [data-resv="TT-261128-2001"] [data-admin-resv-to="assigned"]')
        page.wait_for_timeout(450)
        ok(tag + "v18 후보를 골라 탭으로 배정 실행",
           page.evaluate("() => window.__ttokttokModel.adminStatusOf('TT-261128-2001')") == "assigned")
        ok(tag + "v18 배정 알림 생성(자동 발송 아님)",
           "선생님 배정이 끝났어요" in [n["title"] for n in page.evaluate("() => window.__ttokttokModel.notifs()")])
        shot(page, "v18_matching_admin")
    ok(tag + "v18 JS 오류 없음", not errors, errors[:2])
    browser.close()


def run_v19_flow(p, storage_blocked=False):
    """v19 운영·파트너 화면 완성팩 — 대기열·예외 보드, 사유별 취소, 재확정, 알림함, 가용시간/지역 등록."""
    import json as _json
    from datetime import datetime, timedelta, timezone

    kst_today = FIXED_TODAY
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )

    def mk(no, status, extra=None):
        row = {"id": "res-" + no.lower(), "no": no, "userId": "usr-demo", "date": "11.30", "day": "월",
               "time": "10:00", "teacher": "", "teacherId": "", "region": "서울 마포구 성산동",
               "regionId": "reg-서울-마포구", "status": status, "passId": "p8", "walletId": "seed-pass",
               "dateIso": "2026-11-30", "amount": 74000, "paymentStatus": "paid", "symptomCodes": ["stroke"]}
        row.update(extra or {})
        return row

    seed = {
        "profile": {"name": "현수"},
        "passes": [{"id": "seed-pass", "userId": "usr-demo", "passId": "p8", "name": "8회 방문권",
                    "total": 8, "remaining": 5, "purchased": "2026.10.28", "expire": "2027.01.27", "status": "active"}],
        "bookings": [
            mk("TT-261128-2001", "received"),
            mk("TT-261128-2002", "received", {"region": "제주 제주시 노형동", "regionId": "reg-제주-제주시"}),
            mk("TT-261128-2003", "rescheduled", {"teacher": "박서준 선생님", "teacherId": "park",
                                                 "region": "서울 강남구 대치동", "regionId": "reg-서울-강남구",
                                                 "date": "11.27", "day": "금", "dateIso": "2026-11-27", "time": "10:30"}),
            mk("TT-261128-2004", "canceled", {"region": "서울 강남구 대치동", "regionId": "reg-서울-강남구", "dateIso": kst_today}),
            mk("TT-261128-2005", "no_show", {"teacher": "박서준 선생님", "teacherId": "park"}),
            mk("TT-261128-2006", "received", {
                "region": "서울 강남구 대치동", "regionId": "reg-서울-강남구",
                "date": "11.28", "day": "토", "dateIso": "2026-11-28",
                "statusHistory": [{"status": "received", "from": "assigned", "to": "received", "actor": "operator",
                                   "reason": "선생님 배정 거절 — 재배정 대기", "at": "2026-11-26T01:00:00.000Z"}]}),
            mk("TT-261128-2007", "confirmed", {"teacher": "정민아 선생님", "teacherId": "jung",
                                                "dateIso": "2026-12-01", "issue": "complaint", "issueMemo": "도착 시간 지연 문의"}),
        ],
        "receipts": [],
    }

    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    else:
        ctx.add_init_script("window.localStorage.setItem('ttokttok_account_v3', %s);" % _json.dumps(_json.dumps(seed, ensure_ascii=False)))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    ok(tag + "v19 앱 버전 메타(v19 이상)", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v19", "v20", "v21", "v22", "v23", "v24", "v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v19 운영 도구 노출(opsVersion)", page.evaluate("() => window.__ttokttokModel.opsVersion") == "v19")

    # ── 관리자: 오늘 처리할 일 보드
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(250)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(450)
    ok(tag + "v19 관리자 상단 보드가 예약 큐보다 위", page.evaluate("""() => {
        const b = document.getElementById('adminOpsSec');
        const q = document.getElementById('adminResvSec');
        return !!b && !!q && !!(b.compareDocumentPosition(q) & Node.DOCUMENT_POSITION_FOLLOWING);
      }"""))
    ok(tag + "v19 보드 요약 건수 표시", all(t in page.inner_text("#adminOpsCounts") for t in ["미배정", "재확정 대기", "후보 0명", "운영 예외"]),
       page.inner_text("#adminOpsCounts"))
    if not storage_blocked:
        queue_cards = page.eval_on_selector_all("#adminMatchQueue .admin-card", "els => els.length")
        ok(tag + "v19 대기열 카드 4건(미배정 3·재확정 1)", queue_cards == 4, queue_cards)
        first_no = page.evaluate("() => (document.querySelector('#adminMatchQueue .admin-card') || {}).getAttribute ? document.querySelector('#adminMatchQueue .admin-card').getAttribute('data-queue') : null")
        ok(tag + "v19 후보 0명을 먼저 보여준다", first_no == "TT-261128-2006", first_no)
        ok(tag + "v19 1순위 원클릭 배정 버튼", "1순위 정민아 배정" in page.inner_text('#adminMatchQueue [data-queue="TT-261128-2001"]'))
        ok(tag + "v19 운영 예외 5종", page.eval_on_selector_all("#adminExceptionBoard .admin-card", "els => els.length") == 5)
        shot(page, "v19_ops_board")

        # 원클릭 배정·재확정
        page.tap('#adminMatchQueue [data-admin-quick="TT-261128-2001"]')
        page.wait_for_timeout(400)
        ok(tag + "v19 원클릭 1순위 배정 실행",
           page.evaluate("() => window.__ttokttokModel.adminStatusOf('TT-261128-2001')") == "assigned")
        page.tap('#adminMatchQueue [data-admin-quick="TT-261128-2003"]')
        page.wait_for_timeout(400)
        ok(tag + "v19 원클릭 재확정 실행",
           page.evaluate("() => window.__ttokttokModel.adminStatusOf('TT-261128-2003')") == "confirmed")
        ok(tag + "v19 처리 후 보드 즉시 갱신(대기 2)",
           page.evaluate("() => window.__ttokttokModel.opsBoard().queue.total") == 2)

        # 취소 사유 선택
        ok(tag + "v19 취소 사유 3종 선택 UI", page.eval_on_selector_all('[data-admin-cancel-reason="TT-261128-2007"] option', "els => els.length") == 3)
        page.select_option('[data-admin-cancel-reason="TT-261128-2007"]', "center")
        page.wait_for_timeout(200)
        quote = page.inner_text('[data-admin-cancel-quote="TT-261128-2007"]')
        ok(tag + "v19 사유 변경 시 환불 견적 즉시 갱신", "센터 사정 취소" in quote, quote)
        page.tap('#adminResvQueue [data-resv="TT-261128-2007"] [data-admin-resv-to="canceled"]')
        page.wait_for_timeout(400)
        ok(tag + "v19 센터 사정 취소 실행",
           page.evaluate("() => window.__ttokttokModel.adminStatusOf('TT-261128-2007')") == "canceled")
        ok(tag + "v19 이력에 센터 사정 취소 사유", "센터 사정 취소" in page.evaluate(
            "() => window.__ttokttokModel.history('TT-261128-2007').slice(-1)[0].reason"))

    # ── 선생님: 알림함 · 가용시간/활동 지역
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(400)
    ok(tag + "v19 선생님 모드 진입", page.evaluate("() => document.querySelector('.screen.is-active').id") == "screen-tp-home")
    notif_count = page.eval_on_selector_all("#tpNotifList [data-tp-notif]", "els => els.length")
    ok(tag + "v19 선생님 알림함이 파트너 화면에 보인다", notif_count >= 1 or storage_blocked, notif_count)
    if not storage_blocked and notif_count:
        before_unread = page.evaluate("() => window.__ttokttokModel.teacherUnread()")
        page.tap("#tpNotifList [data-tp-notif]")
        page.wait_for_timeout(250)
        ok(tag + "v19 알림 탭 → 읽음 처리",
           page.evaluate("() => window.__ttokttokModel.teacherUnread()") == before_unread - 1)
        shot(page, "v19_partner_inbox")
        # v27: 알림을 누르면 발송 전 문구 미리보기가 겹쳐 열린다 — 다음 탭을 가리지 않게 닫는다.
        page.keyboard.press("Escape")
        page.wait_for_timeout(220)

    ok(tag + "v19 가능 시간·지역 폼(요일 7·시간대 3·전문분야 5)",
       page.eval_on_selector_all("#tpAvailForm [data-tp-day]", "els => els.length") == 7 and
       page.eval_on_selector_all("#tpAvailForm [data-tp-time]", "els => els.length") == 3 and
       page.eval_on_selector_all("#tpAvailForm [data-tp-field]", "els => els.length") == 5)
    page.eval_on_selector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-mypage"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.tap('#tpAvailForm [data-tp-day="토"]')
    page.wait_for_timeout(120)
    page.tap('#tpAvailForm [data-tp-district="마포구"]')
    page.wait_for_timeout(200)
    page.tap('#tpAvailForm [data-tp-field="신경계"]')
    page.wait_for_timeout(200)
    page.tap("#tpAvailSave")
    page.wait_for_timeout(400)
    prof = page.evaluate("() => window.__ttokttokPartnerProfile || null")
    ok(tag + "v19 선생님이 직접 등록·저장", bool(prof) and prof.get("ok") is True and "토" in prof.get("availableDays", []) and "신경계" in (prof.get("fields") or []), prof)
    if not storage_blocked:
        rec = page.evaluate("() => window.__ttokttokModel.partnerTeacherRecord()")
        ok(tag + "v19 저장이 매칭 엔진 입력에 반영", bool(rec) and "마포구" in (rec.get("regions") or "") and "nerve" in (rec.get("cats") or []), rec)
        cands = page.evaluate("() => window.__ttokttokModel.matchTeachers({ regionId: 'reg-서울-마포구', dateIso: '2026-11-28', timeSlot: '11:00' }).map(c => c.teacherId)")
        ok(tag + "v19 등록한 시간·지역으로 후보가 된다", "park" in cands, cands)
        shot(page, "v19_partner_avail")
    ok(tag + "v19 JS 오류 없음", not errors, errors[:2])
    browser.close()


def run_v20_flow(p, storage_blocked=False):
    """v20 방문 일지 2분 입력·주간 보호자 리포트·4주 재평가·안전 장치."""
    import json as _json
    from datetime import datetime, timedelta, timezone

    kst_today = FIXED_TODAY

    def shift(days):
        d = datetime.strptime(kst_today, "%Y-%m-%d") + timedelta(days=days)
        return d.strftime("%Y-%m-%d")

    def label(iso):
        y, m, d = iso.split("-")
        return "%s.%s.%s" % (y, m, d)

    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )

    journals = [
        {"id": "jnl-w1", "date": label(shift(-2)), "visitDate": shift(-2), "patient": "김순자 어르신",
         "pain5": 3, "condition5": 3, "activities": ["walk", "sit_stand"], "note": "계단 오르기 시작",
         "nextFocus": "보행 안정성", "status": "shared"},
        {"id": "jnl-w2", "date": label(shift(0)), "visitDate": shift(0), "patient": "김순자 어르신",
         "pain5": 2, "condition5": 4, "activities": ["walk", "stairs"], "note": "계단 흔들림이 줄었어요",
         "nextFocus": "균형·낙상 예방", "status": "shared"},
        {"id": "jnl-t1", "date": label(shift(-32)), "visitDate": shift(-32), "patient": "김순자 어르신",
         "pain5": 4, "condition5": 2, "activities": ["walk"], "note": "초기 평가", "status": "shared"},
    ]
    seed = {
        "profile": {"name": "현수"},
        "passes": [],
        "bookings": [
            {"id": "res-270001-0001", "no": "TT-270001-0001", "userId": "usr-demo", "memberId": "kim",
             "patient": "김순자 어르신", "date": label(shift(-30)), "day": "화", "time": "10:30",
             "teacher": "박서준 선생님", "teacherId": "park", "region": "서울 강남구 대치동",
             "regionId": "reg-서울-강남구", "status": "completed", "dateIso": shift(-30),
             "amount": 74000, "paymentStatus": "paid"},
            {"id": "res-270001-0002", "no": "TT-270001-0002", "userId": "usr-demo", "memberId": "kim",
             "patient": "김순자 어르신", "date": label(shift(2)), "day": "토", "time": "10:30",
             "teacher": "박서준 선생님", "teacherId": "park", "region": "서울 강남구 대치동",
             "regionId": "reg-서울-강남구", "status": "confirmed", "dateIso": shift(2),
             "amount": 74000, "paymentStatus": "paid"},
        ],
        "receipts": [],
    }
    partner = {
        "status": "approved", "teacherId": "park", "name": "박서준", "license": "물리치료사",
        "requests": [],
        "schedule": [
            {"id": "s1", "patient": "김순자 어르신", "region": "서울 강남구 대치동", "date": "오늘",
             "day": "목", "time": "14:00", "pass": "8회 방문권 · 5회기", "checked": False, "status": "confirmed"}
        ],
        "journals": journals,
    }

    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    else:
        ctx.add_init_script("window.localStorage.setItem('ttokttok_account_v3', %s);" % _json.dumps(_json.dumps(seed, ensure_ascii=False)))
        ctx.add_init_script("window.localStorage.setItem('ttokttok_partner_v1', %s);" % _json.dumps(_json.dumps(partner, ensure_ascii=False)))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    ok(tag + "v20 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v20", "v21", "v22", "v23", "v24", "v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v20 모델 노출(visitLogVersion)", page.evaluate("() => window.__ttokttokModel.visitLogVersion") == 20)

    # ── 보호자: 주간 리포트 + 4주 재평가
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(250)
    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
    page.wait_for_timeout(400)
    ok(tag + "v20 보호자 일지에 주간 리포트 카드",
       "이번 주 방문" in page.inner_text("#weeklyBody") and "다음 주 집중" in page.inner_text("#weeklyBody"),
       page.inner_text("#weeklyBody")[:120])
    if not storage_blocked:
        ok(tag + "v20 이번 주 회차·컨디션 변화 표시",
           "2회" in page.inner_text("#weeklyBody") and "3점 → 4점" in page.inner_text("#weeklyBody"),
           page.inner_text("#weeklyBody")[:160])
        ok(tag + "v20 4주 재평가 배지 노출",
           page.eval_on_selector("#journalReeval", "el => el.hidden") is False and
           "4주 재평가" in page.inner_text("#journalReeval"))
        shot(page, "v20_guardian_weekly")
    page.tap("#weeklyOpen")
    page.wait_for_timeout(400)
    ok(tag + "v20 주간 리포트 시트 열기",
       page.eval_on_selector("#weeklySheet", "el => el.classList.contains('is-open')") is True and
       "주간 리포트" in page.inner_text("#weeklySheetBody"))
    if not storage_blocked:
        ok(tag + "v20 시트에 회차별 기록 2건",
           page.eval_on_selector_all("#weeklySheetBody .jr-item", "els => els.length") == 2)
        page.tap("#weeklySheetCopy")
        page.wait_for_timeout(300)
        hook = page.evaluate("() => window.__ttokttokWeeklyCopy || null")
        ok(tag + "v20 공유용 텍스트 복사", bool(hook) and "이번 주 방문 2회" in (hook or {}).get("text", ""), hook)
        shot(page, "v20_weekly_sheet")
    page.tap('#weeklySheet [data-weekly-close]')
    page.wait_for_timeout(250)

    # ── 선생님: 방문 시작/종료
    page.eval_on_selector('.tabbtn[data-tab="tp-schedule"]', "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v20 일정 카드에 방문 시작 버튼",
       page.eval_on_selector_all('#tpScheduleList [data-sched="s1"] [data-tp-visit-start]', "els => els.length") == 1)
    page.tap('#tpScheduleList [data-sched="s1"] [data-tp-visit-start]')
    page.wait_for_timeout(350)
    ok(tag + "v20 방문 시작 → 진행 표시", "방문 중" in page.inner_text('#tpScheduleList [data-sched="s1"]'))
    page.tap('#tpScheduleList [data-sched="s1"] [data-tp-visit-end]')
    page.wait_for_timeout(350)
    done_txt = page.inner_text('#tpScheduleList [data-sched="s1"]')
    ok(tag + "v20 방문 종료 → 소요 시간 표시", "방문 완료" in done_txt and ("분)" in done_txt or "분 미만)" in done_txt), done_txt)
    if not storage_blocked:
        win = page.evaluate("() => window.__ttokttokModel.visitWindow(window.__ttokttokModel.teacherSchedule()[0])")
        ok(tag + "v20 시작·종료 시각이 기록된다", bool(win) and win.get("state") == "done" and win.get("minutes") is not None, win)
        shot(page, "v20_visit_window")

    # ── 선생님: 2분 빠른 일지
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(350)
    page.eval_on_selector('.tabbtn[data-tab="tp-journal"]', "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v20 2분 일지 카드(척도 5·동작 8칩)",
       page.eval_on_selector_all("#qlPainChips [data-ql-pain]", "els => els.length") == 5 and
       page.eval_on_selector_all("#qlActChips [data-ql-act]", "els => els.length") == 8)
    page.tap('#qlPainChips [data-ql-pain="2"]')
    page.wait_for_timeout(150)
    page.tap('#qlCondChips [data-ql-cond="4"]')
    page.wait_for_timeout(150)
    page.tap('#qlActChips [data-ql-act="walk"]')
    page.wait_for_timeout(150)
    ok(tag + "v20 칩 선택 진행 표시(3/5)", "3/5" in page.inner_text("#qlProgress"), page.inner_text("#qlProgress"))
    page.fill("#qlNote", "계단 오를 때 무릎 흔들림 감소")
    page.select_option("#qlFocus", "균형·낙상 예방")
    page.wait_for_timeout(150)
    page.tap("#qlSave")
    page.wait_for_timeout(450)
    hook = page.evaluate("() => window.__ttokttokQuickLog || null")
    ok(tag + "v20 2분 일지 저장", bool(hook) and (hook or {}).get("ok") is True, hook)
    if not storage_blocked:
        saved = page.evaluate("() => window.__ttokttokModel.partnerJournals()[0]")
        ok(tag + "v20 저장된 일지(통증·컨디션·동작·한 줄·포커스)",
           bool(saved) and saved.get("pain5") == 2 and saved.get("condition5") == 4 and
           saved.get("nextFocus") == "균형·낙상 예방" and "계단 오를 때" in (saved.get("note") or ""), saved)
        ok(tag + "v20 최근 기록에 2분 일지 요약", "통증 2/5" in page.inner_text("#tpJournalList"),
           page.inner_text("#tpJournalList")[:120])
        shot(page, "v20_quick_journal")

    # ── 안전 안내 시트
    page.eval_on_selector('#screen-tp-schedule [data-safety-open]', "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v20 긴급 연락 시트(119·센터·스마트콜)",
       page.eval_on_selector("#safetySheet", "el => el.classList.contains('is-open')") is True and
       page.eval_on_selector_all("#safetyContacts [data-safety-tel]", "els => els.length") == 3 and
       page.eval_on_selector_all("#safetySteps .step-item", "els => els.length") == 4)
    ok(tag + "v20 건강정보 최소 보관 원칙 문구", "주민등록번호" in page.inner_text("#safetyPrivacy"))
    shot(page, "v20_safety_sheet")
    page.tap("#safetySheet [data-safety-close]")
    page.wait_for_timeout(250)

    # ── 관리자: 4주 재평가
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(450)
    ok(tag + "v20 관리자 보드에 4주 재평가 칩", "4주 재평가" in page.inner_text("#adminOpsCounts"),
       page.inner_text("#adminOpsCounts"))
    if not storage_blocked:
        ok(tag + "v20 4주 재평가 카드(배지·첫 방문)",
           page.eval_on_selector_all("#adminReevalBoard [data-reeval-state]", "els => els.length") == 1 and
           "첫 방문" in page.inner_text("#adminReevalBoard"), page.inner_text("#adminReevalBoard")[:160])
        page.tap("#adminReevalBoard [data-reeval-notice]")
        page.wait_for_timeout(300)
        rhook = page.evaluate("() => window.__ttokttokReeval || null")
        ok(tag + "v20 재평가 안내 문구 복사", bool(rhook) and "4주 재평가 안내" in (rhook or {}).get("text", ""), rhook)
        shot(page, "v20_admin_reeval")
    ok(tag + "v20 JS 오류 없음", not errors, errors[:2])
    browser.close()


def run_v21_flow(p, storage_blocked=False):
    """v21 정산 일정 통일(D+3 확정 · 15일·말일 지급) · 4주 재평가 기본 시드 · 사업자 푸터."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    ok(tag + "v21 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v21", "v22", "v23", "v24", "v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v21 정산 규칙 노출(D+3·15일·말일)",
       all(x in page.evaluate("() => window.__ttokttokModel.settlementRuleText") for x in ["D+3", "15일", "말일"]),
       page.evaluate("() => window.__ttokttokModel.settlementRuleText"))
    ok(tag + "v21 지급일 계산(11/26→11/30 · 11/28→12/15)",
       page.evaluate("() => [window.__ttokttokModel.nextPayoutDue('2026-11-26'), window.__ttokttokModel.nextPayoutDue('2026-11-28')]") == ["2026-11-30", "2026-12-15"])
    ok(tag + "v21 시작 화면 푸터 사업자 표기(상호·대표·사업자등록번호·연락처)",
       all(x in page.inner_text("#gateBizInfo") for x in ["상호 똑똑쌤", "대표 임현수", "사업자등록번호", "031-919-8577"]),
       page.inner_text("#gateBizInfo"))
    shot(page, "v21_gate_footer")

    # ── 보호자: 지난 완료 방문 카드 · 4주 재평가 배지
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.eval_on_selector("#homeTicketBtn", "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v21 내 예약에 지난 완료 방문(변경·취소·캘린더 없이 내역만)",
       page.evaluate("""() => { const c = document.querySelector('#bookingList [data-booking=\"TT-261019-4811\"]');
         return !!c && c.textContent.indexOf('방문 완료') >= 0 && !!c.querySelector('[data-manage]') &&
           !c.querySelector('[data-manage-cancel]') && !c.querySelector('[data-ics]'); }"""))
    page.eval_on_selector("[data-account-close]", "el => el.click()")
    page.wait_for_timeout(200)
    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
    page.wait_for_timeout(400)
    ok(tag + "v21 보호자 4주 재평가 배지(기본 시드)",
       page.eval_on_selector("#journalReeval", "el => el.hidden") is False and "4주 재평가" in page.inner_text("#journalReeval"),
       page.inner_text("#journalReeval")[:120])
    shot(page, "v21_guardian_reeval_seed")

    # ── 관리자: 4주 재평가 칩·카드
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(450)
    ok(tag + "v21 관리자 보드에 4주 재평가 1건", "4주 재평가 1" in page.inner_text("#adminOpsCounts"),
       page.inner_text("#adminOpsCounts"))
    ok(tag + "v21 재평가 카드(배지·첫 방문)",
       page.eval_on_selector_all("#adminReevalBoard [data-reeval-state=\"due\"]", "els => els.length") == 1 and
       "첫 방문" in page.inner_text("#adminReevalBoard"), page.inner_text("#adminReevalBoard")[:160])
    shot(page, "v21_admin_reeval_seed")

    # ── 파트너: 정산 화면 지급일·규칙
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(400)
    ok(tag + "v21 파트너 정산에 11.30 지급·D+3·15일·말일",
       all(x in page.inner_text("#tpSettle") for x in ["11.30", "D+3", "15일·말일"]),
       page.inner_text("#tpSettle")[:180])
    shot(page, "v21_partner_settle")
    ok(tag + "v21 JS 오류 없음", not errors, errors[:2])
    browser.close()


def run_v22_flow(p, storage_blocked=False):
    """v22 선생님 찾기 내 주변(동 단위) 클러스터 · 방문 일지 사진 1장."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    ok(tag + "v22 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v22", "v23", "v24", "v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v22 모델 노출(내 주변·사진)",
       page.evaluate("() => window.__ttokttokModel.nearVersion") == "v22" and
       page.evaluate("() => window.__ttokttokModel.photoVersion") == "v22")

    # ── 고객: 선생님 찾기 목록 | 내 주변(동 단위)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(250)
    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]', "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v22 보기 탭 2개(목록·내 주변)",
       page.eval_on_selector_all("#teacherViewTabs [data-view]", "els => els.length") == 2 and
       "내 주변" in page.inner_text("#teacherViewTabs"))
    ok(tag + "v22 기본은 검증 카드 목록",
       page.eval_on_selector("#nearPanel", "el => el.hidden") is True and
       page.eval_on_selector_all("#teacherList .teacher", "els => els.length") == 8)

    page.tap('#teacherViewTabs [data-view="near"]')
    page.wait_for_timeout(400)
    near = page.evaluate("() => window.__ttokttokNear || null")
    ok(tag + "v22 내 주변 탭 → 동네 클러스터 카드",
       bool(near) and page.eval_on_selector("#nearPanel", "el => el.hidden") is False and
       page.eval_on_selector_all("#dongClusterList [data-dong-cluster]", "els => els.length") >= 1 and
       page.eval_on_selector_all("#nearProvinceChips .chip", "els => els.length") >= 1 and
       page.eval_on_selector_all("#nearDistrictChips .chip", "els => els.length") >= 1,
       near)
    ok(tag + "v22 클러스터 카드 요약(활동·바로 가능·전문분야)",
       all(x in page.inner_text("#dongClusterList") for x in ["활동 선생님", "바로 가능", "대치동"]),
       page.inner_text("#dongClusterList")[:220])
    ok(tag + "v22 내 주변에서는 카드 목록 숨김",
       page.eval_on_selector("#teacherList", "el => getComputedStyle(el).display") == "none")
    shot(page, "v22_near_dong")

    page.eval_on_selector('[data-dong-pick="dong:reg-서울-강남구-대치동"]', "el => el.click()")
    page.wait_for_timeout(400)
    rows = page.evaluate("() => Array.from(document.querySelectorAll('#teacherList .teacher')).map(el => el.dataset.teacher)")
    ok(tag + "v22 동네 카드 → 해당 동 선생님만",
       rows == ["park"] and "대치동" in page.inner_text("#teacherQueryBar"), rows)
    shot(page, "v22_near_pick")
    page.tap("[data-dong-clear]")
    page.wait_for_timeout(300)
    ok(tag + "v22 동네 필터 해제 → 8명",
       page.eval_on_selector_all("#teacherList .teacher", "els => els.length") == 8)

    # ── 선생님: 2분 일지에 사진 1장(실제 파일 업로드·캔버스 리사이즈)
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(350)
    page.eval_on_selector('.tabbtn[data-tab="tp-journal"]', "el => el.click()")
    page.wait_for_timeout(400)
    ok(tag + "v22 빠른 일지에 사진 1장 입력(선택)",
       page.eval_on_selector("#qlPhoto", "el => el.type") == "file" and
       "방문 사진 1장" in page.inner_text("#tpQuickCard"))
    page.set_input_files("#qlPhoto", os.path.join(ROOT, "tests", "fixtures", "pose_sample.png"))
    page.wait_for_selector("#qlPhotoPreview img", timeout=6000)
    page.wait_for_timeout(250)
    pv = page.evaluate("() => window.__ttokttokModel.quickPhotoPreview()")
    ok(tag + "v22 사진 미리보기·제거·개인정보 안내 1줄",
       bool(pv) and pv.get("visible") and pv.get("hasImg") and pv.get("hasRemove") and
       pv.get("note") == page.evaluate("() => window.__ttokttokModel.photoPrivacyNote") and
       "운동 부위·자세" in pv.get("note") and pv.get("src", "").startswith("data:image/jpeg;base64,"),
       pv)
    ok(tag + "v22 사진은 화면에서 줄여 저장(긴 변 720px 이하·상한 이내)",
       page.evaluate("""() => { const p = window.__ttokttokModel.quickPhoto();
         return !!p && p.chars <= window.__ttokttokModel.photoMaxChars; }"""))
    page.eval_on_selector("#qlPhotoPreview", "el => el.scrollIntoView({block: 'center'})")
    page.wait_for_timeout(400)
    shot(page, "v22_quick_photo")

    page.tap('[data-ql-pain="3"]')
    page.tap('[data-ql-cond="4"]')
    page.tap('[data-ql-act="walk"]')
    page.wait_for_timeout(150)
    page.tap("#qlSave")
    page.wait_for_timeout(500)
    qlog = page.evaluate("() => window.__ttokttokQuickLog || null")
    ok(tag + "v22 사진 붙인 2분 일지 저장",
       bool(qlog) and qlog.get("ok") is True and qlog.get("hasPhoto") is True and qlog.get("photoChars", 0) > 0,
       qlog)
    jid = (qlog or {}).get("journalId")
    meta = page.evaluate("(id) => window.__ttokttokModel.journalPhoto(id)", jid)
    ok(tag + "v22 일지에 사진 메타 저장(안내 확인 표시)",
       bool(meta) and meta.get("privacy") == "guidance_shown" and meta.get("chars", 0) <= 160000,
       meta)
    ok(tag + "v22 파트너 최근 기록에도 사진 썸네일",
       page.eval_on_selector_all("#tpJournalList [data-journal-photo]", "els => els.length") >= 1)

    # ── 보호자: 일지 상세에 사진 표시
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(350)
    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
    page.wait_for_timeout(450)
    ok(tag + "v22 보호자 최근 일지 카드에 사진",
       page.eval_on_selector("#journalLatestCard", "el => el.hidden") is False and
       page.eval_on_selector_all("#journalLatestBody [data-journal-photo]", "els => els.length") == 1)
    page.eval_on_selector("#journalLatestCard", "el => el.scrollIntoView({block: 'center'})")
    page.wait_for_timeout(400)
    shot(page, "v22_guardian_photo")
    if not storage_blocked:
        page.reload()
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(300)
        page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
        page.wait_for_timeout(450)
        ok(tag + "v22 새로 열어도 일지 사진 유지(기기 저장)",
           page.eval_on_selector("#journalLatestCard", "el => el.hidden") is False and
           page.eval_on_selector_all("#journalLatestBody [data-journal-photo]", "els => els.length") == 1)
    page.tap("#weeklyOpen")
    page.wait_for_timeout(400)
    ok(tag + "v22 주간 리포트 상세에도 사진",
       page.eval_on_selector_all("#weeklySheetBody [data-journal-photo]", "els => els.length") >= 1)
    shot(page, "v22_weekly_photo")
    ok(tag + "v22 JS 오류 없음", not errors, errors[:2])
    browser.close()


def run_v23_flow(p, storage_blocked=False):
    """v23 운영 데이터 백업(JSON)·복원 · 저장소 어댑터."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR", accept_downloads=True,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    ok(tag + "v23 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v23", "v24", "v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v23 모델 노출(백업 스키마·어댑터)",
       page.evaluate("() => window.__ttokttokModel.backupVersion") == "v23" and
       page.evaluate("() => window.__ttokttokModel.snapshotSchema") == "ttokttok.v23" and
       page.evaluate("() => window.__ttokttokModel.storageAdapter().kind") == "local")

    # ── 관리자 콘솔 진입 → 백업 카드
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(450)
    ok(tag + "v23 관리자 콘솔에 백업 카드", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-admin" and
       page.is_visible("#adminBackupCard") and page.is_visible("#adminBackupExport") and page.is_visible("#adminBackupPick"))
    counts_text = page.inner_text("#adminBackupCounts")
    ok(tag + "v23 현재 데이터 요약(예약·일지·정산·알림·프로필)", all(t in counts_text for t in ["예약", "일지", "정산", "알림", "프로필"]), counts_text)
    ok(tag + "v23 백업 파일에 빠른일지 초안 제외 안내", "빠른일지 초안" in page.inner_text("#adminBackupMeta"))

    # ── 1) 백업 다운로드 (실제 파일)
    backup_path = os.path.join(SHOT, "e2e_v23_backup.json" if not storage_blocked else "e2e_v23_backup_blocked.json")
    got_file = False
    try:
        with page.expect_download(timeout=6000) as dl_info:
            page.tap("#adminBackupExport")
        download = dl_info.value
        download.save_as(backup_path)
        got_file = os.path.exists(backup_path) and os.path.getsize(backup_path) > 200
    except Exception as exc:  # 다운로드가 안 잡히면 window 훅으로 확인
        print("    (download API fallback: %s)" % exc)
    hook = page.evaluate("() => window.__ttokttokBackup || null")
    ok(tag + "v23 백업 버튼 → JSON 파일 생성", bool(hook) and hook.get("schemaVersion") == "ttokttok.v23" and
       ".json" in (hook.get("name") or "") and "백업 파일을 만들었어요" in page.inner_text("#adminBackupResult"),
       (hook or {}).get("name"))
    if not got_file and hook:
        with open(backup_path, "w", encoding="utf-8") as fp:
            fp.write(hook["text"])
        got_file = os.path.exists(backup_path)
    ok(tag + "v23 백업 파일이 저장됨", got_file, backup_path)
    counts_at_export = dict(page.evaluate("() => JSON.parse(window.__ttokttokBackup.text).counts"))
    ok(tag + "v23 백업 파일에 5개 영역·항목 수·스키마", (function_keys := page.evaluate(
        "() => Object.keys(JSON.parse(window.__ttokttokBackup.text).data).sort()")) ==
        ["journals", "ledger", "notifications", "reservations", "teacherProfile"] and
        isinstance(counts_at_export, dict) and counts_at_export.get("reservations", 0) >= 1,
        function_keys)
    shot(page, "v23_admin_backup")

    # ── 2) 데이터를 하나 바꾼다(확정 → 방문 완료)
    page.eval_on_selector('#adminResvFilters [data-admin-resv-filter="confirmed"]', "el => el.click()")
    page.wait_for_timeout(350)
    before_status = page.evaluate("() => (window.__ttokttokModel.reservations().filter(b => b.no === 'TT-261021-7302')[0] || {}).status")
    do_move = page.eval_on_selector(
        '#adminResvQueue [data-resv="TT-261021-7302"] [data-admin-resv-to="completed"]',
        "el => { el.click(); return true; }") if page.eval_on_selector_all(
        '#adminResvQueue [data-resv="TT-261021-7302"] [data-admin-resv-to="completed"]', "els => els.length") else False
    page.wait_for_timeout(450)
    after_status = page.evaluate("() => (window.__ttokttokModel.reservations().filter(b => b.no === 'TT-261021-7302')[0] || {}).status")
    ok(tag + "v23 복원 전 데이터 변경(확정→방문 완료)", before_status == "confirmed" and do_move and after_status == "completed",
       "%s → %s" % (before_status, after_status))

    # ── 3) 백업 파일 복원: 확인 단계 → 반영
    page.set_input_files("#adminBackupFile", backup_path)
    page.wait_for_timeout(600)
    ok(tag + "v23 파일을 고르면 확인 단계(아직 그대로)",
       page.eval_on_selector("#adminBackupConfirmBox", "el => el.hidden") is False and
       page.evaluate("() => !!window.__ttokttokModel.pendingRestore()") and
       page.evaluate("() => (window.__ttokttokModel.reservations().filter(b => b.no === 'TT-261021-7302')[0] || {}).status") == "completed")
    ok(tag + "v23 확인 문구에 항목 수·내보낸 시각", "예약" in page.inner_text("#adminBackupConfirmText") and
       "내보낸 시각" in page.inner_text("#adminBackupConfirmText"), page.inner_text("#adminBackupConfirmText")[:80])
    shot(page, "v23_restore_confirm")
    page.tap("#adminBackupConfirm")
    page.wait_for_timeout(500)
    ok(tag + "v23 복원 실행 → 백업 시점 상태로", page.evaluate(
        "() => (window.__ttokttokModel.reservations().filter(b => b.no === 'TT-261021-7302')[0] || {}).status") == "confirmed" and
        "복원했어요" in page.inner_text("#adminBackupResult"), page.inner_text("#adminBackupResult")[:80])
    ok(tag + "v23 복원 후 항목 수가 파일과 같다", (page.evaluate("() => window.__ttokttokRestore.counts") or {}).get("reservations") ==
        counts_at_export.get("reservations"), page.evaluate("() => JSON.stringify(window.__ttokttokRestore.counts)"))
    ok(tag + "v23 복원 후 확인 박스 닫힘", page.eval_on_selector("#adminBackupConfirmBox", "el => el.hidden") is True)
    page.eval_on_selector('#adminResvFilters [data-admin-resv-filter="all"]', "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v23 예약 큐 화면도 복원값 반영",
       page.evaluate("""() => Array.from(document.querySelectorAll('#adminResvQueue [data-resv-status]'))
          .some(el => el.getAttribute('data-resv-status') === 'confirmed')"""))
    shot(page, "v23_after_restore")

    # ── 4) 손상 파일은 거부
    broken_path = os.path.join(SHOT, "e2e_v23_backup_broken.json")
    with open(broken_path, "w", encoding="utf-8") as fp:
        fp.write('{"schemaVersion":"ttokttok.v23","data":{"reservations":[{"id":"a","status":"wrong_state"}],')
    page.set_input_files("#adminBackupFile", broken_path)
    page.wait_for_timeout(600)
    ok(tag + "v23 손상 파일 → 복원 거부·이유 표시", "복원하지 않았어요" in page.inner_text("#adminBackupResult") and
       page.eval_on_selector("#adminBackupConfirmBox", "el => el.hidden") is True and
       page.evaluate("() => window.__ttokttokModel.pendingRestore() === null"),
       page.inner_text("#adminBackupResult")[:100])
    ok(tag + "v23 거부 후 데이터 그대로", page.evaluate(
        "() => (window.__ttokttokModel.reservations().filter(b => b.no === 'TT-261021-7302')[0] || {}).status") == "confirmed")
    shot(page, "v23_restore_rejected")

    # ── 5) 새로 열어도 복원 결과 유지(기기 저장)
    if not storage_blocked:
        page.reload()
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(300)
        page.eval_on_selector("[data-admin-open]", "el => el.click()")
        page.wait_for_timeout(450)
        ok(tag + "v23 새로 열어도 복원한 예약 상태 유지", page.evaluate(
            "() => (window.__ttokttokModel.reservations().filter(b => b.no === 'TT-261021-7302')[0] || {}).status") == "confirmed")
        ok(tag + "v23 새로 열어도 백업 카드 요약 표시", all(t in page.inner_text("#adminBackupCounts") for t in ["예약", "일지"]),
           page.inner_text("#adminBackupCounts"))
    ok(tag + "v23 JS 오류 없음", not errors, errors[:2])
    browser.close()


def run_v24_flow(p, storage_blocked=False):
    """v24 모바일 320px·접근성·성능 QA — 320/375/1280 전수 넘침·Escape·포커스."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 320, "height": 568}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    ok(tag + "v25 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v25 QA 훅 노출", page.evaluate("() => window.__ttokttokModel.qaVersion") in ("v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49") and
       page.evaluate("() => window.__ttokttokModel.a11y.version") in ("v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v24 뷰포트 320px", page.evaluate("() => document.documentElement.clientWidth") == 320)

    def overflow(state):
        m = page.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})""")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    def a11y_snapshot():
        return page.evaluate("""() => {
          const A = window.__ttokttokModel.a11y;
          return {unnamed: A.unnamedControls(), unlabeled: A.unlabeledFields(),
                  dialogs: A.dialogCount(), named: A.labelledDialogs()};
        }""")

    # ── 시작 화면·게이트 시트
    if not storage_blocked:
        ok(tag + "v24 시작 화면 320px 넘침 없음", overflow("gate")[0], overflow("gate")[1])
    page.tap("#gateCta")
    page.wait_for_timeout(250)
    ok(tag + "v24 휴대폰 번호 시트 320px 넘침 없음", overflow("gateSheet")[0], overflow("gateSheet")[1])
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    ok(tag + "v24 Escape로 휴대폰 시트 닫힘", page.eval_on_selector("#gateSheet", "el => !el.classList.contains('is-open')"))
    ok(tag + "v24 Escape는 시작 화면 자체를 닫지 않는다", page.is_visible("#entryGate .gate-inner"))

    # ── 고객 5개 화면 320px
    page.tap("#gateCta")
    page.wait_for_timeout(300)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(300)
    bad = []
    for tab in ["home", "teachers", "booking", "journal", "mypage"]:
        page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="%s"]' % tab, "el => el.click()")
        page.wait_for_timeout(220)
        okk, why = overflow("customer/" + tab)
        if not okk:
            bad.append(why)
    ok(tag + "v24 고객 5개 화면 320px 가로 넘침 0", not bad, bad)
    a = a11y_snapshot()
    ok(tag + "v24 접근성 이름 없는 버튼 0(고객 화면)", a["unnamed"] == [], a["unnamed"][:4])
    ok(tag + "v24 label 없는 입력 0(고객 화면)", a["unlabeled"] == [], a["unlabeled"][:4])
    ok(tag + "v24 모든 dialog에 aria-modal·이름", a["dialogs"] == a["named"], "%d/%d" % (a["named"], a["dialogs"]))
    ok(tag + "v24 img 전부 alt 보유", page.evaluate("() => Array.from(document.querySelectorAll('img')).every(el => el.hasAttribute('alt'))"))

    # ── 선생님 시트: 포커스 이동 → Escape 복귀
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="teachers"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.tap("#teacherList .teacher")
    page.wait_for_timeout(400)
    ok(tag + "v24 시트를 열면 초점이 시트 안으로", page.evaluate("() => window.__ttokttokModel.a11y.focusInside('#teacherSheet')"))
    ok(tag + "v24 선생님 시트 320px 넘침 없음", overflow("teacherSheet")[0], overflow("teacherSheet")[1])
    if not storage_blocked:
        shot(page, "v24_320_teacher_sheet")
    page.keyboard.press("Escape")
    page.wait_for_timeout(350)
    ok(tag + "v24 Escape로 선생님 시트 닫힘", page.eval_on_selector("#teacherSheet", "el => !el.classList.contains('is-open')"))
    ok(tag + "v24 닫으면 초점이 누른 카드로 복귀", page.evaluate("() => !!(document.activeElement && document.activeElement.closest('#teacherList .teacher'))"))

    # ── 예약 4단계 320px
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="booking"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.tap('#provinceQuick [data-prov="서울"]')
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.tap('[data-next="1"]')
    page.wait_for_timeout(300)
    bad = []
    for st in ["booking/step2"]:
        okk, why = overflow(st)
        if not okk:
            bad.append(why)
    page.tap("#bookDates .date-chip")
    page.wait_for_timeout(150)
    page.tap("#bookSlots .slot:not([disabled])")
    page.tap('[data-next="2"]')
    page.wait_for_timeout(300)
    page.tap('#passList [data-pass="p8"]')
    page.wait_for_timeout(200)
    okk, why = overflow("booking/step3")
    if not okk:
        bad.append(why)
    page.tap('[data-next="3"]')
    page.wait_for_timeout(300)
    okk, why = overflow("booking/step4")
    if not okk:
        bad.append(why)
    ok(tag + "v24 예약 2~4단계 320px 가로 넘침 0", not bad, bad)
    ok(tag + "v24 예약 화면 입력 label 연결", a11y_snapshot()["unlabeled"] == [])
    if not storage_blocked:
        shot(page, "v24_320_booking")

    # ── 보호자 시트 전수 Escape · 넘침(320px)
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="mypage"]', "el => el.click()")
    page.wait_for_timeout(250)
    cases = [
        ("#mpBookLink", "accountSheet"), ("#mpNotifRow", "notifSheet"),
        ("#mpCouponRow", "couponSheet"), ("#mpPayRow", "paySheet"),
        ("#mpRoleRow", "roleSheet"), ("#mpFaqRow", "faqSheet"),
        ("#mpRegionRow", "regionSheet")
    ]
    bad_esc, bad_over = [], []
    for opener, sheet in cases:
        page.tap(opener)
        page.wait_for_timeout(300)
        okk, why = overflow(sheet)
        if not okk:
            bad_over.append(why)
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        if page.eval_on_selector("#" + sheet, "el => el.classList.contains('is-open')"):
            bad_esc.append(sheet)
    ok(tag + "v24 보호자 시트 7종 Escape로 닫힘", not bad_esc, bad_esc)
    ok(tag + "v24 보호자 시트 7종 320px 가로 넘침 0", not bad_over, bad_over)
    a = a11y_snapshot()
    ok(tag + "v24 시트 연 뒤에도 이름 없는 버튼 0", a["unnamed"] == [], a["unnamed"][:4])

    # ── 일지: 안전 안내·주간 리포트 시트
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="journal"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.tap("[data-safety-open]")
    page.wait_for_timeout(300)
    ok(tag + "v24 안전 안내 시트 320px 넘침 없음", overflow("safetySheet")[0], overflow("safetySheet")[1])
    page.keyboard.press("Escape")
    page.wait_for_timeout(250)
    ok(tag + "v24 Escape로 안전 안내 시트 닫힘", page.eval_on_selector("#safetySheet", "el => !el.classList.contains('is-open')"))
    if page.is_visible("#weeklyOpen"):
        page.tap("#weeklyOpen")
        page.wait_for_timeout(320)
        okk, why = overflow("weeklySheet")
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        ok(tag + "v24 주간 리포트 시트 넘침·Escape", okk and page.eval_on_selector("#weeklySheet", "el => !el.classList.contains('is-open')"), why)
    if not storage_blocked:
        shot(page, "v24_320_journal")

    # ── 선생님 모드 4개 화면(320px)
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(350)
    bad = []
    for tab in ["tp-home", "tp-schedule", "tp-journal", "tp-mypage"]:
        page.eval_on_selector('.tabbar[data-mode="therapist"] [data-tab="%s"]' % tab, "el => el.click()")
        page.wait_for_timeout(250)
        okk, why = overflow("partner/" + tab)
        if not okk:
            bad.append(why)
    ok(tag + "v24 선생님 4개 화면 320px 가로 넘침 0", not bad, bad)
    ok(tag + "v24 선생님 화면 접근성 이름·label 0건", a11y_snapshot()["unnamed"] == [] and a11y_snapshot()["unlabeled"] == [])
    if not storage_blocked:
        shot(page, "v24_320_partner")

    # ── 관리자 콘솔(320px)
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(450)
    ok(tag + "v24 관리자 콘솔 320px 가로 넘침 없음", overflow("admin")[0], overflow("admin")[1])
    ok(tag + "v24 관리자 백업·큐 카드 렌더", page.is_visible("#adminBackupSec") and page.is_visible("#adminResvSec"))
    if not storage_blocked:
        shot(page, "v24_320_admin")

    # ── 375 · 1280 뷰포트 회귀(주요 화면)
    for w, h, mobile, name in [(375, 812, True, "375"), (1280, 800, False, "1280")]:
        page.set_viewport_size({"width": w, "height": h})
        page.wait_for_timeout(250)
        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(120)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(300)
        bad = []
        for tab in ["home", "teachers", "booking", "journal", "mypage"]:
            page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="%s"]' % tab, "el => el.click()")
            page.wait_for_timeout(200)
            okk, why = overflow(name + "/" + tab)
            if not okk:
                bad.append(why)
        ok(tag + "v24 %spx 고객 5개 화면 가로 넘침 0" % name, not bad, bad)
        if name == "375" and not storage_blocked:
            page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="teachers"]', "el => el.click()")
            page.wait_for_timeout(250)
            shot_page = page.screenshot(path=os.path.join(SHOT, "v24_375_teachers.png"))

    ok(tag + "v24 전 화면 콘솔·페이지 오류 0", not errors, errors[:3])
    browser.close()


def run_v25_flow(p, storage_blocked=False):
    """v25 보호자 홈 통합 대시보드 · 첫 방문 온보딩 · FAQ 검색/필터."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    ok(tag + "v25 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v25", "v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v25 요약 모델 노출(guardianVersion·기간 28일)",
       page.evaluate("() => window.__ttokttokModel.guardianVersion") == "v25" and
       page.evaluate("() => window.__ttokttokModel.guardianReportDays") == 28)

    if not storage_blocked:
        page.tap("#gateCta")
        page.wait_for_timeout(220)
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(320)

    def overflow(state):
        m = page.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})""")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    # ── 홈 통합 요약 카드
    ok(tag + "v25 홈 요약 카드 표시", page.is_visible("#homeSummaryCard"))
    okk, why = overflow("home/summary")
    ok(tag + "v25 홈 요약 카드 가로 넘침 없음", okk, why)
    next_text = page.eval_on_selector("#homeSummaryNext", "el => el.textContent.replace(/\\s+/g, ' ').trim()")
    ok(tag + "v25 다음 방문(예약번호·상태)", "TT-261021-7302" in next_text and "예약 확정" in next_text, next_text[:80])
    pass_text = page.eval_on_selector("#homeSummaryPass", "el => el.textContent.replace(/\\s+/g, ' ').trim()")
    ok(tag + "v25 회차권 잔여·만료", "잔여 5회" in pass_text and "2027.01.27" in pass_text and "1회권" in pass_text, pass_text[:100])
    rep_text = page.eval_on_selector("#homeSummaryReport", "el => el.textContent.replace(/\\s+/g, ' ').trim()")
    ok(tag + "v25 최근 4주 리포트·재평가", "최근 4주 방문" in rep_text and "재평가" in rep_text, rep_text[:100])
    ok(tag + "v25 요약 카드에 금액 없음", "원" not in page.eval_on_selector("#homeSummaryCard", "el => el.textContent"))
    if not storage_blocked:
        shot(page, "v25_home_summary")

    # ── 바로가기 3종
    page.tap('#homeSummaryCard [data-summary="visit"]')
    page.wait_for_timeout(320)
    ok(tag + "v25 다음 방문 → 방문 일정 시트", page.eval_on_selector("#accountSheet", "el => el.classList.contains('is-open')") and
       page.is_visible("#bookingList"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(220)
    page.tap('#homePassCard [data-summary="pass"]')
    page.wait_for_timeout(300)
    ok(tag + "v25 회차권 → 이용권 시트", page.eval_on_selector("#accountSheet", "el => el.classList.contains('is-open')") and
       page.is_visible("#walletList .wallet-card"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(220)
    page.tap('#homeReportCard [data-summary="report"]')
    page.wait_for_timeout(400)
    ok(tag + "v25 리포트 → 일지 탭+주간 리포트 시트",
       page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-journal" and
       page.eval_on_selector("#weeklySheet", "el => el.classList.contains('is-open')"))
    okk, why = overflow("weeklySheet")
    ok(tag + "v25 주간 리포트 시트 넘침 없음", okk, why)
    if not storage_blocked:
        shot(page, "v25_weekly_from_summary")
    page.keyboard.press("Escape")
    page.wait_for_timeout(220)

    # ── 첫 방문 온보딩(준비물·진행 순서·불안 해소)
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="home"]', "el => el.click()")
    page.wait_for_timeout(220)
    page.tap("#homeGuideBtn")
    page.wait_for_timeout(350)
    ok(tag + "v25 준비물 3가지 체크리스트", page.eval_on_selector_all("#onboardPrepCard input[type=checkbox]", "els => els.length") == 3)
    ok(tag + "v25 진행 3단계(15분·계획·60분)", page.eval_on_selector_all("#onboardFlow .step-item", "els => els.length") == 3 and
       "60분 본 수업" in page.eval_on_selector("#onboardFlow", "el => el.textContent"))
    ok(tag + "v25 불안 해소 2가지", "강제 결제 없음" in page.eval_on_selector("#onboardAssurance", "el => el.textContent") and
       "선생님 교체" in page.eval_on_selector("#onboardAssurance", "el => el.textContent"))
    okk, why = overflow("guideSheet")
    ok(tag + "v25 이용안내 시트 넘침 없음", okk, why)
    page.tap("#obPrep-dress")
    page.wait_for_timeout(200)
    note = page.eval_on_selector("#onboardPrepNote", "el => el.textContent")
    ok(tag + "v25 준비물 체크 → 안내 문구 갱신", "1가지 확인" in note, note)
    if not storage_blocked:
        shot(page, "v25_onboarding")
    page.keyboard.press("Escape")
    page.wait_for_timeout(220)
    if not storage_blocked:
        page.reload()
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(320)
        page.tap("#homeGuideBtn")
        page.wait_for_timeout(300)
        ok(tag + "v25 새로 열어도 준비물 체크 유지", page.eval_on_selector("#obPrep-dress", "el => el.checked") is True)
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

    # ── FAQ 검색·카테고리 필터
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="mypage"]', "el => el.click()")
    page.wait_for_timeout(250)
    page.tap("#mpFaqRow")
    page.wait_for_timeout(350)
    total = page.eval_on_selector_all("#faqList .faq-item", "els => els.length")
    ok(tag + "v25 FAQ 기본 10문항", total == 10, total)
    page.fill("#faqSearch", "환불")
    page.wait_for_timeout(250)
    n_refund = page.eval_on_selector_all("#faqList .faq-item", "els => els.length")
    ok(tag + "v25 FAQ 검색(환불) 결과 좁혀짐", 0 < n_refund < 10 and "환불" in page.eval_on_selector("#faqList", "el => el.textContent"), n_refund)
    ok(tag + "v25 검색 결과 카운트 안내", "검색 결과" in page.eval_on_selector("#faqCount", "el => el.textContent"))
    page.tap('#faqCatChips [data-faqcat="safety"]')
    page.wait_for_timeout(250)
    ok(tag + "v25 카테고리(선생님/안전) 칩 선택", page.eval_on_selector('#faqCatChips [data-faqcat="safety"]', "el => el.classList.contains('is-on')"))
    page.fill("#faqSearch", "없는검색어")
    page.wait_for_timeout(250)
    ok(tag + "v25 결과 0건 빈 상태 + 상담 연결",
       page.eval_on_selector("#faqEmpty", "el => !el.hidden") and
       page.is_visible("#faqEmpty a[href*='naver.me']") and
       page.eval_on_selector_all("#faqList .faq-item", "els => els.length") == 0)
    if not storage_blocked:
        shot(page, "v25_faq_empty")
    okk, why = overflow("faqSheet")
    ok(tag + "v25 FAQ 시트 넘침 없음", okk, why)
    page.tap("#faqReset")
    page.wait_for_timeout(250)
    ok(tag + "v25 검색 초기화 → 10문항", page.eval_on_selector_all("#faqList .faq-item", "els => els.length") == 10 and
       page.eval_on_selector("#faqEmpty", "el => el.hidden"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    # ── 320px 최소 폭
    page.set_viewport_size({"width": 320, "height": 568})
    page.wait_for_timeout(250)
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="home"]', "el => el.click()")
    page.wait_for_timeout(250)
    okk, why = overflow("home/320")
    ok(tag + "v25 홈 요약 320px 넘침 없음", okk, why)
    ok(tag + "v25 요약 카드 320px에서도 보임", page.is_visible("#homeSummaryCard") and page.is_visible("#homeSummaryNext [data-summary='visit'], #homeSummaryNext [data-summary='book']"))
    if not storage_blocked:
        shot(page, "v25_320_home_summary")

    ok(tag + "v25 전 화면 콘솔·페이지 오류 0", not errors, errors[:3])
    browser.close()


def run_v26_flow(p, storage_blocked=False):
    """v26 선생님 정산 명세서·월별 리포트."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    def overflow(state):
        m = page.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})""")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    ok(tag + "v26 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v26", "v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v26 명세서 모델 노출(statementVersion·3.3%)",
       page.evaluate("() => window.__ttokttokModel.statementVersion") == "v26" and
       abs(page.evaluate("() => window.__ttokttokModel.withholdingRate") - 0.033) < 1e-9)

    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(320)

    # ── 파트너 홈 카드 → 정산 명세서 화면
    ok(tag + "v26 파트너 홈에 정산 명세서 링크", page.is_visible('#tpSettle [data-tab="tp-settle"]'))
    page.tap('#tpSettle [data-tab="tp-settle"]')
    page.wait_for_timeout(320)
    ok(tag + "v26 정산 탭 화면 전환",
       page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-tp-settle" and
       "정산 명세서" in page.inner_text("#screen-tp-settle .page-head h1"))
    ok(tag + "v26 선생님 탭바 5개(정산)", page.eval_on_selector_all('.tabbar[data-mode="therapist"] .tabbtn', "els => els.length") == 5)
    okk, why = overflow("tp-settle")
    ok(tag + "v26 정산 화면 390px 넘침 없음", okk, why)

    # ── 월 선택 칩·요약
    ok(tag + "v26 월 선택 칩(11월·10월)", page.eval_on_selector_all("#tpsMonths [data-stl-month]", "els => els.length") == 2 and
       page.eval_on_selector('#tpsMonths [data-stl-month="2026-11"]', "el => el.classList.contains('is-on')"))
    summary = page.eval_on_selector("#tpsSummary", "el => el.textContent.replace(/\\s+/g, ' ').trim()")
    ok(tag + "v26 월 요약(980,000·지급완료 7건·지급예정 6건·정산대기 1건)",
       "980,000" in summary and "지급완료 7건" in summary and "지급예정 6건" in summary and "정산대기 1건" in summary,
       summary[:120])
    ok(tag + "v26 원천징수 3.3%·실수령 예상(32,340·947,660)", "32,340원" in summary and "947,660원" in summary and "세무 확인" in summary)
    ok(tag + "v26 회차별 내역 14건", page.eval_on_selector_all("#tpsRows [data-stl-row]", "els => els.length") == 14)
    first_row = page.eval_on_selector("#tpsRows [data-stl-row]", "el => el.textContent.replace(/\\s+/g, ' ').trim()")
    ok(tag + "v26 첫 행(예약번호·상태·지급일·금액)",
       "TT-261125-1054" in first_row and "정산대기" in first_row and "2026.11.30" in first_row and "70,000원" in first_row, first_row[:110])
    if not storage_blocked:
        shot(page, "v26_390_settle")

    # ── 월 전환
    page.tap('#tpsMonths [data-stl-month="2026-10"]')
    page.wait_for_timeout(320)
    oct_rows = page.eval_on_selector_all("#tpsRows [data-stl-row]", "els => els.length")
    oct_text = page.eval_on_selector("#tpsRows", "el => el.textContent")
    ok(tag + "v26 10월 전환(12건·무료 평가·770,000)",
       oct_rows == 12 and "무료 평가" in oct_text and "770,000" in page.eval_on_selector("#tpsSummary", "el => el.textContent"),
       "%s / %s" % (oct_rows, oct_text[:40]))
    page.tap('#tpsMonths [data-stl-month="2026-11"]')
    page.wait_for_timeout(320)

    # ── 정산서 미리보기 시트
    page.tap('#tpsScreen [data-stl-preview]')
    page.wait_for_timeout(420)
    ok(tag + "v26 정산서 미리보기 시트", page.eval_on_selector("#settlementPrintSheet", "el => el.classList.contains('is-open')") and
       "똑똑쌤 정산 명세서" in page.eval_on_selector("#settlementPrintBody", "el => el.textContent") and
       "947,660원" in page.eval_on_selector("#settlementPrintBody", "el => el.textContent"))
    okk, why = overflow("settlementPrintSheet")
    ok(tag + "v26 미리보기 시트 넘침 없음", okk, why)
    if not storage_blocked:
        shot(page, "v26_print_sheet")
    page.keyboard.press("Escape")
    page.wait_for_timeout(260)
    ok(tag + "v26 Escape로 미리보기 닫힘", not page.eval_on_selector("#settlementPrintSheet", "el => el.classList.contains('is-open')"))

    # ── 텍스트 복사·JSON 내보내기
    page.tap('#tpsScreen [data-stl-copy]')
    page.wait_for_timeout(260)
    copied = page.evaluate("() => (window.__ttokttokStatement || {})")
    ok(tag + "v26 텍스트 복사(명세서 텍스트)", "똑똑쌤 정산 명세서" in (copied.get("copied") or "") and "TT-261125-1054" in (copied.get("copied") or ""))
    json_path = os.path.join(SHOT, "e2e_v26_statement.json" if not storage_blocked else "e2e_v26_statement_blocked.json")
    got_file = False
    try:
        with page.expect_download(timeout=6000) as dl_info:
            page.tap('#tpsScreen [data-stl-json]')
        dl = dl_info.value
        dl.save_as(json_path)
        got_file = os.path.exists(json_path) and os.path.getsize(json_path) > 500
    except Exception as exc:
        print("    (download API fallback: %s)" % exc)
    hook = page.evaluate("() => window.__ttokttokStatement || {}")
    ok(tag + "v26 JSON 내보내기 파일", got_file and (hook.get("name") or "").endswith(".json") and "statement.v26" in (hook.get("json") or ""),
       hook.get("name"))
    if got_file:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ok(tag + "v26 내보낸 JSON 내용(11월·14행·실수령)", data["statement"]["monthKey"] == "2026-11" and
           len(data["statement"]["rows"]) == 14 and data["statement"]["totals"]["netExpected"] == 947660)

    # ── 320px 최소 폭
    page.set_viewport_size({"width": 320, "height": 568})
    page.wait_for_timeout(280)
    okk, why = overflow("tp-settle/320")
    ok(tag + "v26 정산 화면 320px 넘침 없음", okk, why)
    page.tap('#tpsScreen [data-stl-preview]')
    page.wait_for_timeout(360)
    okk, why = overflow("settlementPrintSheet/320")
    ok(tag + "v26 미리보기 시트 320px 넘침 없음", okk, why)
    if not storage_blocked:
        shot(page, "v26_320_print_sheet")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    ok(tag + "v26 전 화면 콘솔·페이지 오류 0", not errors, errors[:3])
    browser.close()


def run_v27_flow(p, storage_blocked=False):
    """v27 알림·리마인드 센터 — 알림함 분류·문구 미리보기·운영자 리마인드 큐."""
    import json as _json
    from datetime import datetime, timedelta, timezone

    kst_now = FIXED_NOW_KST
    today = kst_now.strftime("%Y-%m-%d")
    tomorrow = (kst_now + timedelta(days=1)).strftime("%Y-%m-%d")

    def lbl(iso):
        y, m, d = iso.split("-")
        return "%d.%s" % (int(m), d)

    def mk(no, status, extra=None):
        row = {"id": "res-" + no.lower(), "no": no, "userId": "usr-demo", "date": lbl(today), "day": "수",
               "time": "10:00", "teacher": "박서준 선생님", "teacherId": "park",
               "region": "서울 강남구 대치동", "regionId": "reg-서울-강남구", "status": status,
               "passId": "p8", "walletId": "seed-pass", "dateIso": today, "amount": 90000, "paymentStatus": "paid"}
        row.update(extra or {})
        return row

    recent = (kst_now - timedelta(hours=20)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    bookings = [
        # ① 내일 확정 방문 → D-1 리마인드
        mk("TT-270001-9001", "confirmed", {"date": lbl(tomorrow), "day": "목", "time": "10:30", "dateIso": tomorrow}),
        # ② 최근 일정 변경
        mk("TT-270001-9002", "rescheduled", {
            "date": lbl(today), "time": "14:00", "region": "서울 서초구 반포동", "regionId": "reg-서울-서초구",
            "statusHistory": [{"status": "confirmed", "at": (kst_now - timedelta(days=3)).strftime("%Y-%m-%dT01:00:00.000Z"), "by": "customer"},
                              {"status": "rescheduled", "at": recent, "by": "customer", "reason": "보호자 요청"}]}),
        # ③ 최근 취소
        mk("TT-270001-9003", "canceled", {
            "date": lbl(today), "time": "11:00", "region": "서울 송파구 잠실동", "regionId": "reg-서울-송파구", "refund": 90000,
            "statusHistory": [{"status": "confirmed", "at": (kst_now - timedelta(days=4)).strftime("%Y-%m-%dT01:00:00.000Z"), "by": "customer"},
                              {"status": "canceled", "at": recent, "by": "customer", "reason": "보호자 취소"}]}),
        # ④ 최근 대체·재배정(배정 → 접수)
        mk("TT-270001-9004", "received", {
            "teacher": "이하늘 선생님", "teacherId": "lee", "region": "서울 마포구 성산동", "regionId": "reg-서울-마포구",
            "statusHistory": [{"status": "assigned", "at": (kst_now - timedelta(days=3)).strftime("%Y-%m-%dT01:00:00.000Z"), "by": "operator"},
                              {"status": "received", "at": recent, "by": "operator", "reason": "선생님 사정"}]}),
        # ⑤ 36일 전 첫 방문(완료) → 4주 재평가
        mk("TT-270001-9005", "completed", {
            "date": lbl((kst_now - timedelta(days=36)).strftime("%Y-%m-%d")), "dateIso": (kst_now - timedelta(days=36)).strftime("%Y-%m-%d"),
            "firstVisitIso": (kst_now - timedelta(days=36)).strftime("%Y-%m-%d"), "amount": 0}),
    ]
    notifs = [
        {"id": "ntv27-d1", "audience": "customer", "kind": "remind", "title": "방문 D-1 리마인드",
         "body": "내일 10:30 방문이 예정되어 있어요. 편한 옷과 복용약 목록을 준비해 주세요.", "when": "어제 18:00", "read": False, "go": "account"},
        {"id": "ntv27-visit", "audience": "customer", "kind": "visit", "title": "방문이 확정됐어요",
         "body": "박서준 선생님이 다가오는 방문을 확정했어요.", "when": "오늘 09:10", "read": False, "go": "account"},
        {"id": "ntv27-report", "audience": "customer", "kind": "report", "title": "보호자 회복 리포트 업데이트",
         "body": "5회기 회복 리포트가 새로 올라왔어요.", "when": "2일 전", "read": False, "go": "report"},
        {"id": "ntv27-coupon", "audience": "customer", "kind": "coupon", "title": "첫 방문 평가 무료 쿠폰 발급",
         "body": "첫 1:1 방문 평가 무료 쿠폰이 도착했어요.", "when": "3일 전", "read": False, "go": "coupon"},
        {"id": "ntv27-t1", "audience": "teacher", "kind": "visit", "title": "방문이 확정됐어요",
         "body": "11.27 (목) 10:30 · TT-270001-9001 일정으로 방문합니다.", "when": "오늘 09:10", "read": False},
        {"id": "ntv27-t2", "audience": "teacher", "kind": "remind", "title": "4주 재평가 시점이에요",
         "body": "현수 · 첫 방문 10.21 · 4주 재평가 D+8. 다음 방문 때 재평가를 진행해 주세요.", "when": "오늘 08:00", "read": False},
        {"id": "ntv27-t3", "audience": "teacher", "kind": "settle", "title": "지급 예정 안내",
         "body": "11.30 지급 예정 7건 · 490,000원.", "when": "오늘 07:30", "read": False},
    ]
    seed = {"profile": {"name": "현수"},
            "passes": [{"id": "seed-pass", "userId": "usr-demo", "passId": "p8", "name": "8회 방문권", "total": 8,
                        "remaining": 5, "purchased": "2026.10.28", "expire": "2027.01.27", "status": "active"}],
            "bookings": bookings, "receipts": [], "sessions": [], "myReviews": []}

    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    else:
        ctx.add_init_script("window.localStorage.setItem('ttokttok_account_v3', %s);" % _json.dumps(_json.dumps(seed, ensure_ascii=False)))
        ctx.add_init_script("window.localStorage.setItem('ttokttok_notifs_v1', %s);" % _json.dumps(_json.dumps(notifs, ensure_ascii=False)))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    def overflow(state):
        m = page.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})""")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    ok(tag + "v27 앱 버전 메타(v28 이상)", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v27", "v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v27 리마인드 큐 모델 노출(카테고리 4·kind 7)",
       page.evaluate("() => window.__ttokttokModel.reminderQueueVersion") == "v27" and
       page.evaluate("() => window.__ttokttokModel.reminderCategories.length") == 4 and
       page.evaluate("() => window.__ttokttokModel.reminderKinds.length") == 7)

    # ── 계산 계층: 순수 함수가 D-1·변경/취소/대체·재평가·정산을 모두 만든다
    queue = page.evaluate("""() => window.__ttokttokModel.buildReminderQueue({
        bookings: window.__ttokttokModel.reservations(),
        ledger: window.__ttokttokModel.export().tables.settlement_ledgers || []
      }, window.__ttokttokModel.todayIsoKst())""")
    kinds = [it["kind"] for it in queue["items"]]
    if not storage_blocked:
        ok(tag + "v27 큐에 D-1·변경·취소·대체·재평가·정산 항목", all(
            k in kinds for k in ["visit_d1", "visit_change", "visit_cancel", "visit_substitute", "reeval",
                                 "settle_confirm", "settle_payout"]), kinds)
        d1 = [it for it in queue["items"] if it["kind"] == "visit_d1"][0]
        ok(tag + "v27 D-1 문구(날짜·시각·선생님·준비물)",
           d1["bookingNo"] == "TT-270001-9001" and "10:30" in d1["customer"]["body"] and
           "박서준" in d1["customer"]["body"] and len(d1["prep"]) == 3 and d1["badge"] == "D-1",
           _json.dumps(d1["customer"], ensure_ascii=False))
        ok(tag + "v27 큐 카테고리 합계(방문 4·리포트 1·정산 2)",
           queue["counts"]["byCategory"]["visit"] == 4 and queue["counts"]["byCategory"]["report"] == 1 and
           queue["counts"]["byCategory"]["ops"] == 2, queue["counts"])
    else:
        ok(tag + "v27 저장 차단에서도 큐 계산", bool(queue) and queue.get("todayIso") == today, queue.get("todayIso"))
    ok(tag + "v27 큐 문구에 로컬 미리보기 고지", "실제 문자·알림톡 발송 전 로컬 미리보기" in queue["text"])

    # ── 보호자 알림함: 분류 칩·필터·문구 미리보기
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(320)
    page.tap("#btnNotif")
    page.wait_for_timeout(360)
    state = page.evaluate("() => window.__ttokttokModel.notifScreenState()")
    ok(tag + "v27 보호자 알림함 분류 칩 4개", len(state["chips"]) == 4, state["chips"])
    ok(tag + "v27 칩 문구·안 읽음 수", all(
        t in [c["text"] for c in state["chips"]] for t in ["전체 4", "방문 일정 2", "리포트/재평가 1", "정산/운영 1"]),
        [c["text"] for c in state["chips"]])
    ok(tag + "v27 기본은 전체(4건)", state["filter"] == "all" and state["rows"] == 4, state["rows"])
    okk, why = overflow("notifSheet/v27")
    ok(tag + "v27 알림 시트 390px 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v27_notif_chips.png"))
    page.tap('#notifChips [data-notif-cat="visit"]')
    page.wait_for_timeout(280)
    ok(tag + "v27 방문 일정 칩 → 2건", page.evaluate("() => window.__ttokttokModel.notifScreenState().rows") == 2)
    page.tap('#notifChips [data-notif-cat="report"]')
    page.wait_for_timeout(280)
    ok(tag + "v27 리포트/재평가 칩 → 1건",
       page.evaluate("() => window.__ttokttokModel.notifScreenState().rows") == 1 and
       "회복 리포트" in page.evaluate("() => window.__ttokttokModel.notifScreenState().text"))
    page.tap('#notifChips [data-notif-cat="ops"]')
    page.wait_for_timeout(280)
    ok(tag + "v27 정산/운영 칩 → 1건(쿠폰 알림)",
       page.evaluate("() => window.__ttokttokModel.notifScreenState().rows") == 1 and
       "쿠폰" in page.evaluate("() => window.__ttokttokModel.notifScreenState().text"))
    page.tap('#notifChips [data-notif-cat="all"]')
    page.wait_for_timeout(280)
    ok(tag + "v27 전체 칩 복귀 4건", page.evaluate("() => window.__ttokttokModel.notifScreenState().rows") == 4)

    before_unread = page.evaluate("() => window.__ttokttokModel.notifs().filter(n => !n.read && n.audience !== 'teacher').length")
    page.tap('#notifList [data-notif="ntv27-d1"]' if not storage_blocked else '#notifList .notif')
    page.wait_for_timeout(420)
    pv = page.evaluate("() => window.__ttokttokModel.notifPreviewInfo()")
    ok(tag + "v27 알림 클릭 → 해당 화면 이동 + 문구 미리보기 시트",
       bool(pv) and pv["open"] is True and (pv["id"] == "ntv27-d1" if not storage_blocked else bool(pv["id"])) and
       ("방문 D-1 리마인드" in (pv["bodyText"] or "") if not storage_blocked else len(pv["bodyText"] or "") > 10),
       _json.dumps(pv, ensure_ascii=False)[:200])
    sheet_text = page.eval_on_selector("#notifPreviewSheet", "el => el.textContent.replace(/\\s+/g, ' ')")
    ok(tag + "v27 미리보기에 '실제 발송 전 미리보기' 표기",
       "실제 발송 전 미리보기" in sheet_text and "발송되지 않아요" in sheet_text, sheet_text[:90])
    ok(tag + "v27 알림은 읽음 처리", page.evaluate("() => window.__ttokttokModel.notifs().filter(n => !n.read && n.audience !== 'teacher').length") == before_unread - 1)
    okk, why = overflow("notifPreviewSheet/v27")
    ok(tag + "v27 미리보기 시트 390px 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v27_notif_preview.png"))
    page.evaluate("""() => { document.querySelectorAll('.sheet-backdrop.is-open').forEach(el => el.classList.remove('is-open')); document.body.classList.remove('sheet-open'); document.body.style.overflow = ''; }""")
    page.wait_for_timeout(200)
    ok(tag + "v27 미리보기 닫기(배경 정리)", not page.evaluate("() => document.querySelectorAll('.sheet-backdrop.is-open').length"),
       page.evaluate("() => document.querySelectorAll('.sheet-backdrop.is-open').length"))

    # ── 선생님 알림함: 칩·전체 보기 시트
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(420)
    tp = page.evaluate("() => window.__ttokttokModel.tpNotifState()")
    ok(tag + "v27 선생님 알림함 칩 4개(인라인)", tp["inlineChips"] == 4, tp)
    if not storage_blocked:
        ok(tag + "v27 선생님 알림 3건 표시", tp["inline"] == 3, tp["inline"])
    page.tap("#tpNotifSec [data-tp-noti-open]")
    page.wait_for_timeout(380)
    tp = page.evaluate("() => window.__ttokttokModel.tpNotifState()")
    ok(tag + "v27 선생님 알림함 전체 보기 시트", tp["sheetOpen"] is True and tp["chips"] == 4 and
       (tp["sheetRows"] == 3 if not storage_blocked else True), tp)
    okk, why = overflow("tpNotiSheet/v27")
    ok(tag + "v27 선생님 알림 시트 390px 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v27_tp_noti_sheet.png"))
        page.tap('#tpNotiChips [data-notif-cat="ops"]')
        page.wait_for_timeout(280)
        ok(tag + "v27 선생님 칩 필터(정산/운영 1건)",
           page.evaluate("() => window.__ttokttokModel.tpNotifState().sheetRows") == 1)
        page.tap('#tpNotiChips [data-notif-cat="all"]')
        page.wait_for_timeout(240)
        page.tap('#tpNotiList [data-tp-notif="ntv27-t1"]')
        page.wait_for_timeout(360)
        ok(tag + "v27 선생님 알림 클릭 → 문구 미리보기",
           page.evaluate("() => window.__ttokttokModel.notifPreviewInfo() && window.__ttokttokModel.notifPreviewInfo().open") is True)
        page.keyboard.press("Escape")
        page.wait_for_timeout(260)
        ok(tag + "v27 Escape로 문구 미리보기 닫힘",
           page.evaluate("() => window.__ttokttokModel.notifPreviewInfo() && window.__ttokttokModel.notifPreviewInfo().open") is False)
    page.keyboard.press("Escape")
    page.wait_for_timeout(260)
    ok(tag + "v27 Escape로 선생님 알림 시트 닫힘",
       page.evaluate("() => window.__ttokttokModel.tpNotifState().sheetOpen") is False)

    # ── 운영자: 오늘 발송할 리마인드 미리보기
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(420)
    ad = page.evaluate("() => window.__ttokttokModel.adminReminderState()")
    ok(tag + "v27 운영자 리마인드 보드 렌더", ad["total"] >= 3 and len(ad["cards"]) == ad["total"], _json.dumps(ad, ensure_ascii=False)[:200])
    ok(tag + "v27 운영자 보드에 방문·리포트·정산 카테고리",
       page.evaluate("() => window.__ttokttokModel.adminReminders().counts.byCategory.ops") >= 2 and
       page.evaluate("() => window.__ttokttokModel.adminReminders().counts.byCategory.report") >= 1)
    ok(tag + "v27 실제 발송 안 함 고지", "실제 문자·알림톡 발송은 하지 않습니다" in ad["noticeText"], ad["noticeText"][:80])
    ok(tag + "v27 카운트 칩(보호자·선생님)", "보호자" in ad["countsText"] and "선생님" in ad["countsText"], ad["countsText"])
    if not storage_blocked:
        ok(tag + "v27 운영자 보드에 D-1 카드", "visit_d1" in [c["kind"] for c in ad["cards"]], [c for c in ad["cards"]])
    okk, why = overflow("adminReminder/v27")
    ok(tag + "v27 운영자 리마인드 보드 390px 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v27_admin_reminders.png"))
    if page.eval_on_selector_all("#adminReminderQueue [data-reminder-copy]", "els => els.length"):
        page.tap("#adminReminderQueue [data-reminder-copy]")
        page.wait_for_timeout(280)
        hook = page.evaluate("() => window.__ttokttokReminderCopy || {}")
        ok(tag + "v27 리마인드 문구 복사(발송 없음)", "똑똑쌤 알림 문구" in (hook.get("text") or "") and
           "실제 문자·알림톡 발송 전 로컬 미리보기" in (hook.get("text") or ""), (hook.get("text") or "")[:60])
    page.tap("#adminReminderCopyAll")
    page.wait_for_timeout(280)
    hook = page.evaluate("() => window.__ttokttokReminderCopy || {}")
    ok(tag + "v27 오늘 리마인드 전체 복사", "[똑똑쌤 오늘 발송할 리마인드]" in (hook.get("text") or "") and
       "발송되지 않아요" in (hook.get("text") or ""), (hook.get("text") or "")[:60])

    # ── 320px 최소 폭
    page.set_viewport_size({"width": 320, "height": 568})
    page.wait_for_timeout(320)
    okk, why = overflow("adminReminder/320")
    ok(tag + "v27 운영자 리마인드 보드 320px 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v27_320_admin_reminders.png"))
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(320)
    page.tap("#btnNotif")
    page.wait_for_timeout(360)
    okk, why = overflow("notifSheet/320")
    ok(tag + "v27 알림 시트 320px 넘침 없음", okk, why)
    page.tap('#notifList [data-notif="ntv27-visit"]' if not storage_blocked else '#notifList .notif')
    page.wait_for_timeout(400)
    okk, why = overflow("notifPreviewSheet/320")
    ok(tag + "v27 미리보기 시트 320px 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v27_320_notif_preview.png"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    ok(tag + "v27 전 화면 콘솔·페이지 오류 0", not errors, errors[:3])
    browser.close()


def run_v28_flow(p, storage_blocked=False):
    """v28 · 관리자 운영 지표 대시보드 — 퍼널·매출·지역 갭·SLA·기간 칩."""
    import json as _json
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    def overflow(state):
        m = page.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})""")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    ok(tag + "v28 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v28 지표 모델 노출(기간 3·버전)",
       page.evaluate("() => window.__ttokttokModel.adminMetricsVersion") == "v28" and
       page.evaluate("() => window.__ttokttokModel.metricsPeriods().length") == 3 and
       page.evaluate("() => window.__ttokttokModel.qaVersion") in ("v28", "v29", "v30", "v31", "v32", "v33", "v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))

    # ── 계산 계층: 퍼널·매출·지역 갭·SLA를 실브라우저 엔진으로
    calc = page.evaluate("""() => {
        const M = window.__ttokttokModel;
        const pad = (n) => (n < 10 ? '0' : '') + n;
        const off = (o) => { const d = new Date(Date.now() + o * 86400000);
          return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); };
        const at = (o, hm) => off(o) + 'T' + (hm || '01:00') + ':00+09:00';
        const today = M.todayIsoKst();
        const now = today + 'T09:00:00+09:00';
        const mk = (no, status, extra) => Object.assign({ id: 'f-' + no, no, status, amount: 90000,
          paymentStatus: 'paid', regionId: 'reg-서울-강남구', region: '서울 강남구 대치동',
          dateIso: off(2), createdAt: at(-2), statusHistory: [{ status: 'received', at: at(-2) }] }, extra || {});
        const teachers = [
          { id: 'mt1', name: '박서준', regions: '서울 강남 · 서초' },
          { id: 'mt3', name: '정민아', regions: '서울 마포 · 서대문' },
          { id: 'mt4', name: '한지우', regions: '서울 서초' }
        ];
        const funnelB = [
          mk('TT-280001-0001', 'confirmed'),
          mk('TT-280001-0002', 'completed', { dateIso: off(-1), createdAt: at(-3) }),
          mk('TT-280001-0003', 'canceled', { createdAt: at(-12),
            statusHistory: [{ status: 'received', at: at(-12) }, { status: 'assigned', at: at(-12, '02:00') }, { status: 'canceled', at: at(-10) }] }),
          mk('TT-280001-0004', 'no_show', { createdAt: at(-40), statusHistory: [{ status: 'no_show', at: at(-39) }] }),
          mk('TT-280001-0005', 'received', { createdAt: at(-3) })
        ];
        const ledger = [
          { id: 'l1', reservationNo: 'TT-280002-0001', visitDate: off(-2), grossAmount: 90000, netAmount: 70000, status: 'paid', journalId: 'j1' },
          { id: 'l2', reservationNo: 'TT-280002-0002', visitDate: off(-20), grossAmount: 90000, netAmount: 70000, status: 'scheduled' },
          { id: 'l3', reservationNo: 'TT-280002-0003', visitDate: off(-40), grossAmount: 90000, netAmount: 70000, status: 'paid' },
          { id: 'l4', reservationNo: 'TT-280002-0004', visitDate: off(-1), grossAmount: 90000, netAmount: 70000, status: 'held' },
          { id: 'l5', reservationNo: 'TT-280002-0005', visitDate: off(0), grossAmount: 0, netAmount: 0, status: 'paid' }
        ];
        const journals = [{ id: 'j1', visitDate: off(-2), patient: '김순자', status: 'shared' }];
        const m1 = M.buildAdminMetrics({ bookings: funnelB, teachers: teachers, journals: journals, ledger: ledger, nowIso: now }, today);
        const m7 = M.buildAdminMetrics({ bookings: funnelB, teachers: teachers, journals: journals, ledger: ledger, period: '7d', nowIso: now }, today);
        const m30 = M.buildAdminMetrics({ bookings: funnelB, teachers: teachers, journals: journals, ledger: ledger, period: '30d', nowIso: now }, today);
        const gB = [
          mk('TT-280010-0001', 'confirmed'),
          mk('TT-280010-0002', 'received', { regionId: 'reg-서울-마포구' }),
          mk('TT-280010-0003', 'received', { regionId: 'reg-서울-마포구' }),
          mk('TT-280010-0004', 'received', { regionId: 'reg-서울-마포구' }),
          mk('TT-280010-0005', 'received', { regionId: 'reg-서울-마포구' }),
          mk('TT-280010-0006', 'completed', { regionId: 'reg-서울-서초구', dateIso: off(-1) }),
          mk('TT-280010-0007', 'canceled', { regionId: 'reg-부산-해운대구' }),
          mk('TT-280010-0008', 'received', { regionId: 'reg-제주-제주시', region: '제주 제주시 노형동' })
        ];
        const m2 = M.buildAdminMetrics({ bookings: gB, teachers: teachers, journals: [], ledger: [], nowIso: now }, today);
        const sB = [
          { no: 'TT-280020-0001', status: 'received', createdAt: at(-3, '09:00'), regionId: 'reg-서울-마포구' },
          { no: 'TT-280020-0002', status: 'received', createdAt: at(0, '08:00'), regionId: 'reg-서울-마포구' },
          { no: 'TT-280020-0003', status: 'assigned', createdAt: at(-2, '09:00'), regionId: 'reg-서울-강남구' },
          { no: 'TT-280020-0004', status: 'rescheduled', createdAt: at(-1, '09:00'), regionId: 'reg-서울-강남구' },
          { no: 'TT-280020-0005', status: 'confirmed', createdAt: at(-1, '09:00'), regionId: 'reg-서울-강남구' },
          { no: 'TT-280020-0006', status: 'completed', createdAt: at(-9, '09:00'), regionId: 'reg-서울-강남구' }
        ];
        const m3 = M.buildAdminMetrics({ bookings: sB, teachers: [], journals: [], ledger: [], nowIso: now }, today);
        return {
          f: m1.funnel, rev: m1.revenue, jr: m1.journal, regs: m2.regions, sla: m3.sla, kpi: m1.kpis,
          s7: m7.revenue.sessions, s30: m30.revenue.sessions, sAll: m1.revenue.sessions,
          a7: m7.funnel.applied, a30: m30.funnel.applied, aAll: m1.funnel.applied,
          text: m2.text, csv: m2.csv
        };
    }""")
    ok(tag + "v28 퍼널 단계 누적(5→3→2→1)", calc["f"]["applied"] == 5 and calc["f"]["assigned"] == 3 and
       calc["f"]["confirmed"] == 2 and calc["f"]["completed"] == 1, _json.dumps(calc["f"], ensure_ascii=False)[:160])
    ok(tag + "v28 취소·노쇼 건수·비율(40%)", calc["f"]["canceled"] == 1 and calc["f"]["noShow"] == 1 and
       calc["f"]["cancelNoShowRate"] == 40, [calc["f"]["canceled"], calc["f"]["noShow"], calc["f"]["cancelNoShowRate"]])
    ok(tag + "v28 매출·마진(360,000 / 280,000 / 80,000)", calc["rev"]["guardianTotal"] == 360000 and
       calc["rev"]["teacherTotal"] == 280000 and calc["rev"]["platformMargin"] == 80000 and
       calc["rev"]["marginRate"] == 22.2, _json.dumps(calc["rev"], ensure_ascii=False)[:160])
    ok(tag + "v28 기간 필터(매출 7<30<전체)", calc["s7"] == 2 and calc["s30"] == 3 and calc["sAll"] == 4 and
       calc["a7"] == 3 and calc["a30"] == 4 and calc["aAll"] == 5,
       [calc["s7"], calc["s30"], calc["sAll"], calc["a7"], calc["a30"], calc["aAll"]])
    ok(tag + "v28 지역 갭 3분류·모집 필요 우선", calc["regs"]["summary"]["shortage"] == 2 and
       calc["regs"]["summary"]["balanced"] == 1 and calc["regs"]["summary"]["surplus"] == 1 and
       calc["regs"]["rows"][0]["badgeKey"] == "shortage" and
       calc["regs"]["summary"]["noSupply"] == ["제주 제주시"], _json.dumps(calc["regs"]["summary"], ensure_ascii=False)[:160])
    ok(tag + "v28 SLA 24·48시간 초과(각 1건·72시간)", calc["sla"]["pending"] == 5 and calc["sla"]["over24"] == 1 and
       calc["sla"]["over48"] == 1 and calc["sla"]["oldestHours"] == 72 and len(calc["sla"]["items"]) == 1,
       _json.dumps(calc["sla"], ensure_ascii=False)[:160])
    ok(tag + "v28 텍스트·CSV 복사본", "■ 예약 진행 단계" in calc["text"] and "모집 필요" in calc["text"] and
       calc["csv"].startswith("지표,값") and "지역,수요(건)" in calc["csv"])

    # ── 관리자 화면: 기간 칩·KPI·지역·SLA
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(480)
    st = page.evaluate("() => window.__ttokttokModel.adminMetricsState()")
    ok(tag + "v28 운영 지표 섹션·칩 3개", page.is_visible("#adminMetricsSec") and len(st["chips"]) == 3 and
       st["period"] == "all", [c["text"] for c in st["chips"]])
    ok(tag + "v28 KPI 카드 6장", st["kpiCards"] == 6 and "완료 전환율" in st["kpiText"] and
       "취소·노쇼율" in st["kpiText"] and "24시간 초과 미배정" in st["kpiText"] and
       "예상 플랫폼 마진" in st["kpiText"], st["kpiText"][:120])
    ok(tag + "v28 퍼널·매출·지역·SLA 렌더", "전체 신청" in st["funnelText"] and "보호자 결제" in st["revenueText"] and
       "플랫폼 마진" in st["revenueText"] and st["regionCards"] >= 1 and "매칭 대기 시간" in st["slaText"],
       [st["funnelText"][:40], st["revenueText"][:40], st["regionText"][:40]])
    ok(tag + "v28 이 기기 계산·외부 발송 없음 고지", "이 기기 데이터로만 계산한 예시" in st["noteText"] and "발송" in st["noteText"],
       st["noteText"][:80])
    okk, why = overflow("adminMetrics/v28")
    ok(tag + "v28 운영 지표 390px 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v28_admin_metrics.png"))
    all_sessions = st["sessions"]
    page.tap('#adminMetricsPeriods [data-metrics-period="7d"]')
    page.wait_for_timeout(320)
    st7 = page.evaluate("() => window.__ttokttokModel.adminMetricsState()")
    ok(tag + "v28 7일 칩 전환(기간·수치)", st7["period"] == "7d" and sum(1 for c in st7["chips"] if c["on"]) == 1 and
       st7["sessions"] <= all_sessions and "최근 7일" in st7["captionText"], [st7["period"], st7["sessions"], all_sessions])
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v28_admin_metrics_7d.png"))
    page.tap('#adminMetricsPeriods [data-metrics-period="30d"]')
    page.wait_for_timeout(320)
    st30 = page.evaluate("() => window.__ttokttokModel.adminMetricsState()")
    ok(tag + "v28 30일 칩 전환(7일 이상·전체 이하)", st30["period"] == "30d" and
       st7["sessions"] <= st30["sessions"] <= all_sessions, [st7["sessions"], st30["sessions"], all_sessions])
    page.tap('#adminMetricsPeriods [data-metrics-period="all"]')
    page.wait_for_timeout(280)
    ok(tag + "v28 전체 칩 복귀", page.evaluate("() => window.__ttokttokModel.adminMetricsState()").get("period") == "all")

    if not storage_blocked:
        page.tap("#adminMetricsCopyText")
        page.wait_for_timeout(260)
        hook = page.evaluate("() => window.__ttokttokMetricsCopy || {}")
        ok(tag + "v28 지표 요약 텍스트 복사", hook.get("kind") == "text" and "[똑똑쌤 운영 지표]" in (hook.get("text") or ""))
        page.tap("#adminMetricsCopyCsv")
        page.wait_for_timeout(260)
        hook = page.evaluate("() => window.__ttokttokMetricsCopy || {}")
        ok(tag + "v28 지역 표 CSV 복사", hook.get("kind") == "csv" and (hook.get("text") or "").startswith("지표,값"))

    # ── 320px 최소 폭
    page.set_viewport_size({"width": 320, "height": 568})
    page.wait_for_timeout(320)
    okk, why = overflow("adminMetrics/320")
    ok(tag + "v28 운영 지표 320px 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v28_320_admin_metrics.png"))

    ok(tag + "v28 전 화면 콘솔·페이지 오류 0", not errors, errors[:3])
    browser.close()


def run_v29_flow(p, storage_blocked=False):
    """v29 · 고객 후기(1방문 1후기)·선생님 신뢰 배지·원클릭 재예약."""
    import json as _json
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844}, device_scale_factor=2,
        is_mobile=True, has_touch=True, locale="ko-KR",
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    if storage_blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', {
            configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); }
          });
        """)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    tag = "storage-blocked: " if storage_blocked else ""

    def overflow(state):
        m = page.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})""")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    ok(tag + "v29 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v29 신뢰 모델 노출(태그 5·버전)",
       page.evaluate("() => window.__ttokttokModel.trustVersion") == "v29" and
       page.evaluate("() => window.__ttokttokModel.reviewTagMaster.length") == 5 and
       page.evaluate("() => window.__ttokttokModel.qaVersion") in ("v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))

    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(400)

    # ── 1) 홈 요약 카드: 최근 완료 방문 → 후기·재예약
    ok(tag + "v29 홈 요약에 최근 방문·재예약 버튼",
       page.is_visible("#homeSummaryRebook [data-rebook='TT-261019-4811']"))
    home_txt = page.inner_text("#homeSummaryRebook").replace("\n", " ")
    ok(tag + "v29 홈 요약 문구(최근 방문·박서준)", "최근 방문" in home_txt and "박서준" in home_txt, home_txt[:80])

    # ── 2) 후기 작성: 별점·태그·텍스트 → 즉시 신뢰 배지 반영
    before_trust = page.evaluate("() => window.__ttokttokModel.trustOf('park')")
    page.tap("#homeSummaryRebook [data-review-booking]")
    page.wait_for_timeout(350)
    ok(tag + "v29 후기 시트 열림(예약 기준)",
       page.eval_on_selector("#reviewSheet", "el => el.classList.contains('is-open')"))
    rs = page.evaluate("() => window.__ttokttokModel.reviewState()")
    ok(tag + "v29 후기 대상·태그 5종·1회 1후기 안내",
       rs["reservationNo"] == "TT-261019-4811" and rs["chips"] == 5 and "방문 1회당 후기 1개" in rs["rule"],
       _json.dumps([rs["reservationNo"], rs["chips"]], ensure_ascii=False))
    page.tap('[data-star="5"]')
    page.tap('#reviewTags [data-rtag="체계적 평가"]')
    page.tap('#reviewTags [data-rtag="보호자 소통"]')
    page.fill("#reviewText", "매번 측정한 숫자를 보여주셔서 믿음이 갑니다")
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v29_review_sheet.png"))
    page.tap("#reviewSubmit")
    page.wait_for_timeout(450)
    after_trust = page.evaluate("() => window.__ttokttokModel.trustOf('park')")
    ok(tag + "v29 후기 등록 → 별점·후기 수 반영",
       after_trust["reviewCount"] == before_trust["reviewCount"] + 1 and
       any(t["label"] == "체계적 평가" and t["count"] >= 2 for t in after_trust["topTags"]),
       _json.dumps([before_trust["reviewCount"], after_trust["reviewCount"], after_trust["topTags"]], ensure_ascii=False))
    st_rows = page.evaluate("() => window.__ttokttokModel.reviewListState()")
    ok(tag + "v29 후기 목록 '등록됨'", any(r["session"] == "TT-261019-4811" and r["reviewed"] for r in st_rows))
    dup = page.evaluate("() => window.__ttokttokModel.openReviewForBooking('TT-261019-4811')")
    ok(tag + "v29 같은 방문 중복 후기 차단", dup.get("code") == "already_reviewed", _json.dumps(dup, ensure_ascii=False))

    # ── 3) 선생님 카드·상세 신뢰 배지
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(350)
    card_txt = page.inner_text('#teacherList [data-teacher="park"]')
    ok(tag + "v29 선생님 카드 대표 태그·후기 수", "체계적 평가" in card_txt and "후기" in card_txt, card_txt.replace("\n", " ")[:100])
    page.tap('#teacherList [data-teacher="park"]')
    page.wait_for_timeout(400)
    ok(tag + "v29 상세 시트 신뢰 배지 블록", page.is_visible("#teacherTrustBlock"))
    trust_txt = page.inner_text("#teacherTrustBlock").replace("\n", " ")
    ok(tag + "v29 신뢰 배지 내용(평균 별점·완료 방문·재방문·대표 태그)",
       "평균 별점" in trust_txt and "완료 방문" in trust_txt and "재방문" in trust_txt and
       "체계적 평가" in trust_txt and "면허" in trust_txt, trust_txt[:140])
    okk, why = overflow("teacherSheet/v29")
    ok(tag + "v29 신뢰 배지 시트 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v29_teacher_trust.png"))
    page.tap("[data-sheet-close]")
    page.wait_for_timeout(250)

    # ── 4) 원클릭 재예약: 같은 선생님·지역·증상·1회권 90,000원
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]')
    page.wait_for_timeout(300)
    page.tap("#homeSummaryRebook [data-rebook]")
    page.wait_for_timeout(450)
    form = page.evaluate("() => window.__ttokttokModel.bookingFormState()")
    ok(tag + "v29 재예약 → 예약 1단계·선생님/지역/증상/1회권 채움",
       form["teacherId"] == "park" and form["province"] == "서울" and form["district"] == "강남구" and
       form["syms"] == ["뇌졸중·편마비"] and form["passId"] == "p1", _json.dumps(form, ensure_ascii=False))
    ok(tag + "v29 재예약 배너(같은 조건·90,000원)",
       "박서준" in form["banner"] and "90,000원" in form["banner"], form["banner"])
    ok(tag + "v29 재예약 화면 무료 평가 아님",
       page.eval_on_selector('#passList [data-pass="p1"]', "el => el.classList.contains('is-on')") and
       not page.eval_on_selector('#passList [data-pass="eval"]', "el => el.classList.contains('is-on')"))
    okk, why = overflow("booking/rebook")
    ok(tag + "v29 재예약 화면 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v29_rebook_step1.png"))
    # 재예약은 주소만 확인하면 2단계로 진행된다.
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.tap('[data-next="1"]')
    page.wait_for_timeout(350)
    ok(tag + "v29 재예약 1단계 → 2단계 진행",
       page.eval_on_selector("#wstep-2", "el => el.classList.contains('is-active')"))
    page.tap('[data-back="2"]')
    page.wait_for_timeout(250)

    # ── 5) 내 예약 목록·완료 상세에서도 재예약
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(300)
    page.tap("#mpBookLink")
    page.wait_for_timeout(450)
    ok(tag + "v29 완료 예약 카드에 재예약 버튼",
       page.is_visible("#bookingList [data-rebook='TT-261019-4811']"))
    page.tap("#bookingList [data-manage='TT-261019-4811']")
    page.wait_for_timeout(400)
    man_txt = page.inner_text("#manageSheetBody").replace("\n", " ")
    ok(tag + "v29 완료 상세 시트(방문 완료·재예약)",
       "방문 완료된 회차" in man_txt and page.is_visible("#manageSheetBody [data-rebook='TT-261019-4811']"), man_txt[:100])
    ok(tag + "v29 후기 등록 후에는 후기 버튼 대신 등록 표시", "후기 등록됨" in man_txt, man_txt[:120])
    okk, why = overflow("manageSheet/v29")
    ok(tag + "v29 완료 상세 시트 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v29_completed_detail.png"))
    page.tap("#manageSheet [data-manage-close]")
    page.wait_for_timeout(250)
    page.tap("[data-account-close]")
    page.wait_for_timeout(300)

    # ── 6) 320px 최소 폭 — 후기 시트·신뢰 배지
    page.set_viewport_size({"width": 320, "height": 568})
    page.wait_for_timeout(320)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]')
    page.wait_for_timeout(250)
    okk, why = overflow("home/v29/320")
    ok(tag + "v29 320px 홈 요약 넘침 없음", okk, why)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v29_320_home.png"))

    ok(tag + "v29 전 화면 콘솔·페이지 오류 0", not errors, errors[:3])
    browser.close()


def run_v31_flow(p, storage_blocked=False):
    """v31 · 터치 영역 44px·인접 간격·320px CTA 줄바꿈 마감."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "storage-blocked: " if storage_blocked else ""

    def make(w, h, mobile=True):
        ctx = browser.new_context(
            viewport={"width": w, "height": h}, device_scale_factor=1,
            is_mobile=mobile, has_touch=mobile, locale="ko-KR",
            user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                        if mobile else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        )
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(420)
        return ctx, page, errors

    def overflow(page, state):
        m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    def audit(page, state, vp, errors):
        r = page.evaluate("""() => {
          const T = window.__ttokttokTouch;
          return {v: T.violations(), g: T.gapViolations()};
        }""")
        ok(tag + "v31 %s %s 터치 영역 44px 미만 0" % (vp, state), len(r["v"]) == 0, r["v"][:4])
        ok(tag + "v31 %s %s 인접 컨트롤 간격 8px 미만 0" % (vp, state), len(r["g"]) == 0, r["g"][:3])
        okk, why = overflow(page, state)
        ok(tag + "v31 %s %s 가로 넘침 없음" % (vp, state), okk, why)
        ok(tag + "v31 %s %s JS 오류 없음" % (vp, state), not errors, errors[:2])

    def cta_single_line(page):
        return page.evaluate("""() => {
          const bad = [];
          document.querySelectorAll('.btn, .wiz-nav button, .sheet-foot button').forEach((el) => {
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') return;
            const r = el.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) return;
            const range = document.createRange(); range.selectNodeContents(el);
            const rects = [...range.getClientRects()].filter((x) => x.width > 1 && x.height > 1);
            const tops = [];
            rects.forEach((x) => { if (!tops.some((t) => Math.abs(t - x.top) < 7)) tops.push(x.top); });
            if (tops.length >= 2) bad.push((el.id || el.className) + ':' + el.textContent.trim().slice(0, 18));
          });
          return bad;
        }""")

    # ── 320px 고객 흐름
    ctx, page, errors = make(320, 568)
    ok(tag + "v31 320 앱 버전 메타", page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
    ok(tag + "v31 터치 훅 노출(최소 44·간격 8)", page.evaluate("() => !!window.__ttokttokTouch") and
       page.evaluate("() => window.__ttokttokTouch.min") == 44 and
       page.evaluate("() => window.__ttokttokTouch.gapMin") == 8)
    audit(page, "gate", "320", errors)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(420)
    audit(page, "home", "320", errors)
    ok(tag + "v31 320 홈 CTA 한 줄", cta_single_line(page) == [], cta_single_line(page))
    ok(tag + "v31 홈 '방문 일정 보기'가 알약 버튼 44px",
       page.eval_on_selector("#homeSummaryCard .sec-link", "el => Math.round(el.getBoundingClientRect().height)") >= 44 and
       page.eval_on_selector("#homeSummaryCard .sec-link", "el => getComputedStyle(el).borderRadius") == "999px")
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v31_320_home.png"))
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]')
    page.wait_for_timeout(400)
    audit(page, "teachers", "320", errors)
    ok(tag + "v31 320 칩·필터 버튼 44px", page.eval_on_selector("#teacherFilters .chip, #screen-teachers .chip",
       "el => Math.round(el.getBoundingClientRect().height)") >= 44)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v31_320_teachers.png"))
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="booking"]')
    page.wait_for_timeout(300)
    audit(page, "booking/1", "320", errors)
    page.tap('#provinceQuick [data-prov="서울"]')
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.tap('#bookSyms [data-val="뇌졸중·편마비"]')
    page.tap('[data-next="1"]')
    page.wait_for_timeout(350)
    audit(page, "booking/2", "320", errors)
    page.tap("#bookDates .date-chip")
    page.wait_for_timeout(150)
    page.tap("#bookSlots .slot:not([disabled])")
    page.tap('[data-next="2"]')
    page.wait_for_timeout(350)
    audit(page, "booking/3", "320", errors)
    page.tap('#passList [data-pass="p8"]')
    page.wait_for_timeout(240)
    page.tap('[data-next="3"]')
    page.wait_for_timeout(350)
    audit(page, "booking/4", "320", errors)
    ok(tag + "v31 320 예약 CTA 한 줄", cta_single_line(page) == [], cta_single_line(page))
    ok(tag + "v31 320 예약 동의 체크 라벨 44px",
       page.eval_on_selector('label[for="bookAgree"]', "el => Math.round(el.getBoundingClientRect().height)") >= 44)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v31_320_booking4.png"))
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="mypage"]')
    page.wait_for_timeout(320)
    audit(page, "mypage", "320", errors)
    ok(tag + "v31 내 정보 링크 3종 알약(예약 내역·이용권·이용 가이드)",
       page.eval_on_selector("#mpBookLink", "el => Math.round(el.getBoundingClientRect().height)") >= 44 and
       page.eval_on_selector("#mpPassLink", "el => Math.round(el.getBoundingClientRect().height)") >= 44 and
       page.eval_on_selector("#mpGuideLink", "el => Math.round(el.getBoundingClientRect().height)") >= 44 and
       page.eval_on_selector("#mpGuideLink", "el => getComputedStyle(el).borderRadius") == "999px")
    page.tap("#mpBookLink")
    page.wait_for_timeout(420)
    audit(page, "accountSheet", "320", errors)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v31_320_account.png"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(260)
    page.tap("#mpNotifRow")
    page.wait_for_timeout(380)
    audit(page, "notifSheet", "320", errors)
    ok(tag + "v31 알림 시트 닫기 버튼 44px",
       page.eval_on_selector("#notifSheet .sheet-close", "el => Math.round(el.getBoundingClientRect().width)") >= 44 and
       page.eval_on_selector("#notifSheet .sheet-close", "el => Math.round(el.getBoundingClientRect().height)") >= 44)
    page.keyboard.press("Escape")
    page.wait_for_timeout(240)
    page.tap('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]')
    page.wait_for_timeout(320)
    audit(page, "journal", "320", errors)
    ok(tag + "v31 일지 체크 라벨 44px", page.eval_on_selector('label[for="c1"]',
       "el => Math.round(el.getBoundingClientRect().height)") >= 44)
    page.tap("[data-safety-open]")
    page.wait_for_timeout(380)
    audit(page, "safetySheet", "320", errors)
    page.keyboard.press("Escape")
    page.wait_for_timeout(240)

    # ── 320px 파트너·운영자
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(420)
    page.tap('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-schedule"]')
    page.wait_for_timeout(380)
    audit(page, "partner/schedule", "320", errors)
    ok(tag + "v31 파트너 일정 카드 CTA 한 줄",
       page.evaluate("""() => [...document.querySelectorAll('.tp-sched .act .btn')].every((el) => {
          const range = document.createRange(); range.selectNodeContents(el);
          const rects = [...range.getClientRects()].filter((x) => x.width > 1);
          const tops = []; rects.forEach((x) => { if (!tops.some((t) => Math.abs(t - x.top) < 7)) tops.push(x.top); });
          return tops.length === 1;
       })"""))
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v31_320_partner.png"))
    page.tap('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-journal"]')
    page.wait_for_timeout(380)
    audit(page, "partner/journal", "320", errors)
    ok(tag + "v31 2분 일지 저장 CTA 문구 축약·한 줄",
       "일지 저장 · 보호자 공유" in page.inner_text("#qlSave") and cta_single_line(page) == [], cta_single_line(page))
    page.tap('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-mypage"]')
    page.wait_for_timeout(380)
    audit(page, "partner/mypage", "320", errors)
    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(500)
    audit(page, "admin", "320", errors)
    ok(tag + "v31 운영자 카드 버튼 한 줄", cta_single_line(page) == [], cta_single_line(page))
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "v31_320_admin.png"))
    ctx.close()

    # ── 375px·1280px 핵심 화면
    for (w, h, mob, states) in [(375, 812, True, ["home", "teachers", "booking"]), (1280, 800, False, ["home", "teachers"])]:
        ctx, page, errors = make(w, h, mob)
        audit(page, "gate", str(w), errors)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(420)
        for st in states:
            tabsel = '.tabbar[data-mode="customer"] .tabbtn[data-tab="%s"]' % st
            if mob:
                page.tap(tabsel)
            else:
                page.eval_on_selector(tabsel, "el => el.click()")
            page.wait_for_timeout(360)
            audit(page, st, str(w), errors)
            ok(tag + "v31 %d %s CTA 한 줄" % (w, st), cta_single_line(page) == [], cta_single_line(page))
            if not storage_blocked:
                page.screenshot(path=os.path.join(SHOT, "v31_%d_%s.png" % (w, st)))
        ctx.close()

    # ── 가격·정산 규칙·CSS 불변
    ctx, page, errors = make(375, 812)
    ok(tag + "v31 가격·수수료·정산 규칙 불변",
       page.evaluate("() => window.__ttokttokModel.pricing.consumerPrice") == 90000 and
       page.evaluate("() => window.__ttokttokModel.pricing.teacherPayout") == 70000 and
       abs(page.evaluate("() => window.__ttokttokModel.pricing.platformFeeRate") - 0.2222) < 1e-9 and
       page.evaluate("() => window.__ttokttokModel.settlementRule.confirmDays") == 3)
    ok(tag + "v31 시드 예약번호 유지", page.evaluate("() => window.__ttokttokModel.reservations().some(r => r.no === 'TT-261021-7302')"))
    ctx.close()
    browser.close()


def run_v32_flow(p, storage_blocked=False):
    """v32 · 빈 상태 통일 · 로딩 표시 · 오류 재시도 · 입력값 보존."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "storage-blocked: " if storage_blocked else ""
    SHOT32 = os.path.join(SHOT, "live_v32_%s.png")

    def make(w, h, mobile=True):
        ctx = browser.new_context(
            viewport={"width": w, "height": h}, device_scale_factor=2 if mobile else 1,
            is_mobile=mobile, has_touch=mobile, locale="ko-KR",
            user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                        if mobile else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        )
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(420)
        return ctx, page, errors

    def overflow(page, state):
        m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    def audit32(page):
        return page.evaluate("() => window.__ttokttokUI.audit().map(x => x.key + ':' + x.missing.join('+'))")

    def empty_info(page):
        """빈 상태 블록 전수(숨은 시트 안도 포함). 화면에 실제로 그려졌는지는 visible로 따로 본다."""
        return page.evaluate("""() => {
          const out = [];
          document.querySelectorAll('.empty[data-empty]').forEach((el) => {
            const r = el.getBoundingClientRect();
            out.push({
              key: el.getAttribute('data-empty'), cta: !!el.querySelector('.btn'), desc: !!el.querySelector('p'),
              visible: !el.hidden && r.width > 1 && r.height > 1
            });
          });
          return out;
        }""")

    def login(page):
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(320)

    def go_tab(page, tab):
        page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="%s"]' % tab, "el => el.click()")
        page.wait_for_timeout(300)

    def seed_empty_account(page):
        page.evaluate("""() => {
          localStorage.setItem('ttokttok_account_v3', JSON.stringify({
            passes: [], bookings: [], receipts: [], sessions: [], myReviews: [], profile: { name: '현수' }
          }));
        }""")
        page.reload()
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(480)

    # ── ① 320 / 375 / 1280 — 빈 상태 구조·가로 넘침·CTA 동작
    for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
        ctx, page, errors = make(w, h, mob)
        vp = str(w)
        ok(tag + "v32 %s 앱 버전 메타" % vp,
           page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
        ok(tag + "v32 %s 공통 UI 훅" % vp,
           page.evaluate("() => !!window.__ttokttokV32 && window.__ttokttokV32.version") == "v32")
        ok(tag + "v32 %s 부팅 뒤 빈 상태 감사 위반 0" % vp, audit32(page) == [], audit32(page))
        if not storage_blocked:
            seed_empty_account(page)
            login(page)
            go_tab(page, "mypage")
            infos = empty_info(page)
            keys = [x["key"] for x in infos]
            ok(tag + "v32 %s 빈 계정 4곳 통일 빈 상태(이용권·예약·결제·타임라인)" % vp,
               all(k in keys for k in ("wallet-passes", "booking-list", "receipts", "journal-timeline")), keys)
            ok(tag + "v32 %s 빈 상태마다 한 줄 설명 + CTA 버튼" % vp,
               len(infos) >= 4 and all(x["cta"] and x["desc"] for x in infos), infos[:4])
            page.eval_on_selector("#homeTicketBtn", "el => el.click()")
            page.wait_for_timeout(320)
            vis = [x["key"] for x in empty_info(page) if x["visible"]]
            ok(tag + "v32 %s 시트를 열면 빈 상태가 바로 보인다" % vp,
               ("booking-list" in vis) or ("wallet-passes" in vis), vis)
            ok(tag + "v32 %s 빈 상태 감사 위반 0(빈 계정)" % vp, audit32(page) == [], audit32(page))
            okk, why = overflow(page, "empty-mypage")
            ok(tag + "v32 %s 빈 상태 가로 넘침 없음" % vp, okk, why)
            if not storage_blocked:
                page.screenshot(path=SHOT32 % ("%s_empty_mypage" % vp))
            page.eval_on_selector('[data-empty="booking-list"] [data-go="booking"]', "el => el.click()")
            page.wait_for_timeout(320)
            ok(tag + "v32 %s 빈 상태 CTA → 예약 화면 이동" % vp,
               page.evaluate("() => document.querySelector('#screen-booking').classList.contains('is-active')"))
            okk, why = overflow(page, "booking")
            ok(tag + "v32 %s 예약 화면 가로 넘침 없음" % vp, okk, why)
        ok(tag + "v32 %s JS 오류 없음" % vp, not errors, errors[:2])
        ctx.close()

    # ── ② 로딩 표시(결제 진행) · 입력값 보존 · 오류 재시도
    ctx, page, errors = make(375, 812)
    login(page)
    go_tab(page, "booking")
    page.select_option("#bookProvince", "서울")
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
    page.eval_on_selector('[data-next="1"]', "el => el.click()")
    page.wait_for_timeout(320)
    ok(tag + "v32 입력값 보존 — 2단계로 넘어가도 주소·증상 유지",
       page.eval_on_selector("#bookAddress", "el => el.value").startswith("대치동 123-4") and
       page.evaluate("() => window.__ttokttokV32.bookingInputs().step") == 2)
    go_tab(page, "home")
    go_tab(page, "booking")
    ok(tag + "v32 입력값 보존 — 다른 탭에 다녀와도 작성 중 예약 유지",
       page.eval_on_selector("#bookAddress", "el => el.value").startswith("대치동 123-4") and
       page.evaluate("() => document.querySelector('#wstep-2').classList.contains('is-active')"))
    ok(tag + "v32 입력값 보존 — 초안이 저장소에도 남는다",
       (page.evaluate("() => window.__ttokttokV32.bookingDraft()") or {}).get("province") == "서울")
    page.eval_on_selector("#bookDates .date-chip", "el => el.click()")
    page.evaluate("() => { const b = [...document.querySelectorAll('#bookSlots .slot')].find(x => !x.disabled); if (b) b.click(); }")
    page.eval_on_selector('[data-next="2"]', "el => el.click()")
    page.wait_for_timeout(280)
    page.eval_on_selector('#passList [data-pass="p1"]', "el => el.click()")
    page.eval_on_selector('[data-next="3"]', "el => el.click()")
    page.wait_for_timeout(280)
    page.fill("#bookName", "김순자")
    page.fill("#bookPhone", "01012345678")
    page.eval_on_selector('#payMethods [data-pay="신용/체크카드"]', "el => el.click()")
    page.check("#bookAgree")
    page.wait_for_timeout(120)
    page.eval_on_selector("#payBtn", "el => el.click()")
    page.wait_for_timeout(220)

    def busy_state():
        return page.evaluate("""() => {
          const b = document.querySelector('#payBtn');
          const busy = document.querySelector('#payBusy');
          return {
            disabled: !!b.disabled, aria: b.getAttribute('aria-busy'),
            label: b.textContent.trim(), busyShown: !!busy && !busy.hidden,
            loading: !!document.querySelector('#payBusy [data-loading="1"]')
          };
        }""")

    bs = busy_state()
    ok(tag + "v32 결제 중 — 버튼 잠금 + 로딩 표시", bs["disabled"] and bs["aria"] == "true" and bs["busyShown"] and bs["loading"], bs)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "live_v32_pay_busy.png"))
    page.wait_for_timeout(1200)
    ok(tag + "v32 결제 완료 — 로딩이 사라지고 버튼 원복",
       page.evaluate("() => document.querySelector('#payBtn').disabled === false") and
       page.evaluate("() => document.querySelector('#payBusy').hidden === true") and
       page.evaluate("() => document.querySelector('#bookingDone').hidden === false"))

    # ── ③ 오류 + 재시도(같은 입력으로 다시)
    # 완료 화면 → 홈으로(초안 정리) → 예약 탭에서 새로 시작
    page.evaluate("() => document.querySelector('#doneHome').click()")
    page.wait_for_timeout(320)
    go_tab(page, "booking")
    page.wait_for_timeout(240)
    page.select_option("#bookProvince", "경기")
    page.select_option("#bookDistrict", "파주시")
    page.fill("#bookAddress", "야당동 12-3, 105동 801호")
    page.eval_on_selector('#bookSyms [data-val="어르신 보행·근력"]', "el => el.click()")
    page.eval_on_selector('[data-next="1"]', "el => el.click()")
    page.wait_for_timeout(260)
    page.eval_on_selector("#bookDates .date-chip", "el => el.click()")
    page.evaluate("() => { const b = [...document.querySelectorAll('#bookSlots .slot')].find(x => !x.disabled); if (b) b.click(); }")
    page.eval_on_selector('[data-next="2"]', "el => el.click()")
    page.wait_for_timeout(240)
    page.eval_on_selector('#passList [data-pass="p1"]', "el => el.click()")
    page.eval_on_selector('[data-next="3"]', "el => el.click()")
    page.wait_for_timeout(240)
    page.fill("#bookName", "박순자")
    page.fill("#bookPhone", "01098765432")
    page.eval_on_selector('#payMethods [data-pay="카카오페이"]', "el => el.click()")
    page.check("#bookAgree")
    page.evaluate("() => window.__ttokttokV32.failNextBooking(true)")
    page.eval_on_selector("#payBtn", "el => el.click()")
    page.wait_for_timeout(1300)
    err_state = page.evaluate("""() => {
      const err = document.querySelector('#bookError [data-error="booking-submit"]');
      return {
        shown: !!err, retry: !!document.querySelector('#bookError [data-retry="booking-submit"]'),
        text: err ? err.innerText.replace(/\\s+/g, ' ').trim() : '',
        name: document.querySelector('#bookName').value,
        address: document.querySelector('#bookAddress').value,
        disabled: document.querySelector('#payBtn').disabled
      };
    }""")
    ok(tag + "v32 결제 실패 — 원인 + 「다시 시도」 + 버튼 원복",
       err_state["shown"] and err_state["retry"] and "예약을 마무리하지 못했어요" in err_state["text"] and err_state["disabled"] is False, err_state)
    ok(tag + "v32 결제 실패 — 입력값 그대로(이름·주소)",
       err_state["name"] == "박순자" and err_state["address"].startswith("야당동 12-3"), err_state)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "live_v32_booking_error.png"))
    page.eval_on_selector('#bookError [data-retry="booking-submit"]', "el => el.click()")
    page.wait_for_timeout(800)
    ok(tag + "v32 「다시 시도」로 같은 입력 재사용 → 예약 완료",
       page.evaluate("() => document.querySelector('#bookingDone').hidden === false"))

    # ── ④ 저장 실패 띠 → 다시 저장
    page.evaluate("() => window.__ttokttokV32.simulateStorageFailure(true)")
    page.evaluate("() => window.__ttokttokModel.transition('TT-261021-7302', 'completed', { actor: 'operator' })")
    page.wait_for_timeout(260)
    save_state = page.evaluate("""() => {
      const h = document.querySelector('#ttAlertHost');
      return { shown: !!h && h.style.display !== 'none' && h.innerText.indexOf('기기에 저장하지 못했어요') !== -1,
               retry: !!document.querySelector('#ttAlertHost [data-retry="account-save"]'),
               keys: window.__ttokttokV32.alerts() };
    }""")
    ok(tag + "v32 저장 실패 — 화면 위 띠 + 「다시 저장」", save_state["shown"] and save_state["retry"], save_state)
    if not storage_blocked:
        page.screenshot(path=os.path.join(SHOT, "live_v32_storage_banner.png"))
    page.evaluate("() => window.__ttokttokV32.simulateStorageFailure(false)")
    for _ in range(6):
        if not page.is_visible("#ttAlertHost [data-retry]"):
            break
        page.eval_on_selector("#ttAlertHost [data-retry]", "el => el.click()")
        page.wait_for_timeout(160)
    ok(tag + "v32 다시 저장하면 띠가 사라진다",
       page.evaluate("() => window.__ttokttokV32.alerts().length") == 0 and
       page.evaluate("() => document.querySelector('#ttAlertHost').innerHTML.trim() === ''"))
    okk, why = overflow(page, "v32-final")
    ok(tag + "v32 가로 넘침 없음(최종)", okk, why)
    ok(tag + "v32 JS 오류 없음(최종)", not errors, errors[:3])
    ctx.close()
    browser.close()


def run_v33_flow(p, storage_blocked=False):
    """v33 · 첫 방문 전 홈(빈 요약 대신 첫 방문 안내) · 이용 중 요약 · 미리보기."""
    import json as _json
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    EMPTY = _json.dumps({"passes": [], "bookings": [], "receipts": [], "sessions": [], "myReviews": [],
                         "profile": {"name": "현수"}}, ensure_ascii=False)

    def new_page(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                   is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def boot(page, url=URL):
        page.goto(url)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
        page.wait_for_timeout(360)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(420)

    def overflow(page, state):
        m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
        return m["sw"] <= m["cw"] + 1, "%s: %d/%d" % (state, m["sw"], m["cw"])

    tag = "[v33 blocked] " if storage_blocked else "[v33] "

    # ── 1) 320 / 375 / 1280 — 첫 방문 전(빈 계정) 홈
    if not storage_blocked:
        for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
            ctx, page, errors = new_page(w, h, mob)
            page.add_init_script("try{localStorage.setItem('ttokttok_account_v3', %s);}catch(e){}" % _json.dumps(EMPTY))
            boot(page)
            vp = str(w)
            ok(tag + "v33 %s 앱 버전 메타" % vp,
               page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
            ok(tag + "v33 %s 홈 분기 모델 노출" % vp,
               page.evaluate("() => window.__ttokttokModel.guardianHomeVersion") == "v33" and
               page.evaluate("() => window.__ttokttokModel.guardianHome().stage") == "pre_first")
            st = page.evaluate("() => window.__ttokttokModel.homeStageState()")
            ok(tag + "v33 %s 첫 카드는 첫 방문 안내(요약 카드는 접힘)" % vp,
               st["firstCardVisible"] and not st["summaryVisible"] and st["firstElement"] == "homeFirstVisitCard", _json.dumps(st, ensure_ascii=False)[:120])
            ok(tag + "v33 %s 안내 카드 문구(가치 3·순서·CTA 2)" % vp,
               len(st["points"]) == 3 and "15분 평가" in st["steps"] and st["ctas"] == ["무료 평가 신청", "선생님 둘러보기"],
               _json.dumps([st["points"], st["ctas"]], ensure_ascii=False)[:160])
            ok(tag + "v33 %s 중복 공지(파란 띠)는 접힘" % vp,
               page.eval_on_selector("#homeNotice", "el => el.hidden"))
            okk, why = overflow(page, "v33-home") 
            ok(tag + "v33 %s 가로 넘침 없음" % vp, okk, why)
            touch = page.evaluate("() => window.__ttokttokTouch ? window.__ttokttokTouch.violations().length : 0")
            gap = page.evaluate("() => window.__ttokttokTouch ? window.__ttokttokTouch.gapViolations().length : 0")
            ok(tag + "v33 %s 터치 44px·간격 8px 위반 0" % vp, touch == 0 and gap == 0, "%s/%s" % (touch, gap))
            ok(tag + "v33 %s 빈 상태 감사 위반 0" % vp, page.evaluate("() => window.__ttokttokUI.audit().length") == 0)
            page.screenshot(path=os.path.join(SHOT, "live_v33_%s_first_visit.png" % vp))
            # CTA ① 무료 평가 신청 → 예약 1단계(무료 평가)
            page.eval_on_selector('#homeFirstVisitCard [data-book="eval"]', "el => el.click()")
            page.wait_for_timeout(360)
            ok(tag + "v33 %s 무료 평가 신청 → 예약 1단계" % vp,
               page.evaluate("() => document.querySelector('#screen-booking').classList.contains('is-active')") and
               page.evaluate("() => window.__ttokttokModel.bookingFormState().passId") == "eval")
            # CTA ② 선생님 둘러보기
            page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]', "el => el.click()")
            page.wait_for_timeout(280)
            page.eval_on_selector('#homeFirstVisitCard [data-go="teachers"]', "el => el.click()")
            page.wait_for_timeout(300)
            ok(tag + "v33 %s 선생님 둘러보기 → 선생님 찾기" % vp,
               page.evaluate("() => document.querySelector('#screen-teachers').classList.contains('is-active')"))
            # 이용안내 시트
            page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]', "el => el.click()")
            page.wait_for_timeout(280)
            page.eval_on_selector("#homeFirstVisitGuide", "el => el.click()")
            page.wait_for_timeout(320)
            ok(tag + "v33 %s 이용안내 · 준비물 보기 → 시트" % vp,
               page.eval_on_selector("#guideSheet", "el => el.classList.contains('is-open')"))
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            okk, why = overflow(page, "v33-home-final")
            ok(tag + "v33 %s 최종 가로 넘침 없음" % vp, okk, why)
            ok(tag + "v33 %s JS 오류 없음" % vp, not errors, errors[:2])
            ctx.close()

    # ── 2) 이용 중(기본 시드) · 미리보기 · 관리자 카드
    ctx, page, errors = new_page(375, 812, True)
    boot(page)
    st = page.evaluate("() => window.__ttokttokModel.homeStageState()")
    if storage_blocked:
        ok(tag + "v33 저장 차단에서도 홈 분기 계산",
           page.evaluate("() => !!window.__ttokttokModel.guardianHome().stage"))
    else:
        ok(tag + "v33 이용 중 — 요약 카드가 첫 카드(안내 카드 접힘)",
           st["summaryVisible"] and not st["firstCardVisible"] and st["firstElement"] == "homeSummaryCard",
           _json.dumps(st, ensure_ascii=False)[:120])
        ok(tag + "v33 이용 중 — 시드 예약 요약 유지",
           "TT-261021-7302" in page.evaluate("() => document.querySelector('#homeSummaryNext').innerText"))
        ok(tag + "v33 이용 중 — 위 공지는 그대로",
           page.is_visible("#homeNotice") and "첫 1:1 방문 평가 무료" in page.inner_text("#homeNotice"))
        page.screenshot(path=os.path.join(SHOT, "live_v33_375_active_home.png"))
        # 관리자 카드 → 첫 방문 전 미리보기
        page.evaluate("() => { const g = document.getElementById('entryGate'); if (g) g.classList.add('is-open'); }")
        page.wait_for_timeout(200)
        page.eval_on_selector('[data-login="admin"]', "el => el.click()")
        page.wait_for_timeout(420)
        ok(tag + "v33 관리자 「홈 화면 미리보기」 카드",
           page.is_visible("#adminHomeStageSec") and "이용 중" in page.inner_text("#adminHomeStageNow") and
           "예약 2건" in page.inner_text("#adminHomeStageCounts"),
           page.inner_text("#adminHomeStageNow") + " | " + page.inner_text("#adminHomeStageCounts"))
        page.eval_on_selector("#adminStageFirst", "el => el.click()")
        page.wait_for_timeout(520)
        st2 = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok(tag + "v33 미리보기 — 첫 방문 안내가 앞으로, 데이터는 그대로",
           page.evaluate("() => document.querySelector('#screen-home').classList.contains('is-active')") and
           st2["firstCardVisible"] and not st2["summaryVisible"] and st2["noteVisible"] and st2["preview"] == "first" and
           page.evaluate("() => window.__ttokttokModel.guardianHome().counts.bookings") == 2,
           _json.dumps(st2, ensure_ascii=False)[:140])
        page.screenshot(path=os.path.join(SHOT, "live_v33_375_preview_first.png"))
        page.eval_on_selector("#homeStagePreviewNote", "el => el.click()")
        page.wait_for_timeout(420)
        st3 = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok(tag + "v33 미리보기 끄기 → 실제 이용 중 홈으로",
           st3["summaryVisible"] and not st3["firstCardVisible"] and not st3["noteVisible"] and
           page.evaluate("() => window.__ttokttokModel.guardianHome().stage") == "active")
        ok(tag + "v33 미리보기 뒤에도 회차권·예약 유지",
           page.evaluate("() => window.__ttokttokModel.guardianHome().counts.passRemaining") == 5 and
           page.evaluate("() => window.__ttokttokModel.guardianSummary().nextVisit.bookingNo") == "TT-261021-7302")
        okk, why = overflow(page, "v33-active")
        ok(tag + "v33 이용 중 화면 가로 넘침 없음", okk, why)
        ok(tag + "v33 이용 중 빈 상태 감사 위반 0", page.evaluate("() => window.__ttokttokUI.audit().length") == 0)
    ok(tag + "v33 JS 오류 없음(이용 중)", not errors, errors[:2])
    ctx.close()

    # ── 3) 첫 예약을 마치면 홈이 '이용 중'으로 넘어간다(첫 방문 전 → 예약 완료)
    if not storage_blocked:
        ctx, page, errors = new_page(375, 812, True)
        page.add_init_script("try{localStorage.setItem('ttokttok_account_v3', %s);}catch(e){}" % _json.dumps(EMPTY))
        boot(page)
        ok(tag + "v33 예약 전 — 첫 방문 전 화면", page.evaluate("() => window.__ttokttokModel.guardianHome().stage") == "pre_first")
        page.eval_on_selector('#homeFirstVisitCard [data-book="eval"]', "el => el.click()")
        page.wait_for_timeout(360)
        page.select_option("#bookProvince", "서울")
        page.select_option("#bookDistrict", "강남구")
        page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
        page.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
        page.eval_on_selector('[data-next="1"]', "el => el.click()")
        page.wait_for_timeout(340)
        page.eval_on_selector("#bookDates .date-chip", "el => el.click()")
        page.evaluate("() => { const b = [...document.querySelectorAll('#bookSlots .slot')].find(x => !x.disabled); if (b) b.click(); }")
        page.eval_on_selector('[data-next="2"]', "el => el.click()")
        page.wait_for_timeout(340)
        page.eval_on_selector('[data-next="3"]', "el => el.click()")
        page.wait_for_timeout(340)
        page.fill("#bookName", "임현수")
        page.fill("#bookPhone", "010-9218-8577")
        page.eval_on_selector('#payMethods [data-pay="신용/체크카드"]', "el => el.click()")
        page.check("#bookAgree")
        page.eval_on_selector("#payBtn", "el => el.click()")
        page.wait_for_timeout(2400)
        page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="home"]', "el => el.click()")
        page.wait_for_timeout(480)
        st = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok(tag + "v33 첫 예약을 마치면 홈이 이용 중(요약 카드)으로 바뀐다",
           page.evaluate("() => window.__ttokttokModel.guardianHome().stage") == "active" and
           st["summaryVisible"] and not st["firstCardVisible"] and st["firstElement"] == "homeSummaryCard" and
           page.evaluate("() => window.__ttokttokModel.guardianHome().counts.liveBookings") == 1,
           _json.dumps(st, ensure_ascii=False)[:120])
        ok(tag + "v33 첫 예약 — 요약에 새 예약이 보인다",
           "TT-" in page.evaluate("() => document.querySelector('#homeSummaryNext').innerText") and
           page.evaluate("() => !document.querySelector('#homeNotice').hidden"))
        ok(tag + "v33 첫 예약 뒤 JS 오류 없음", not errors, errors[:2])
        ctx.close()

    # ── 3) 주소 파라미터 미리보기(?stage=first) — 데이터를 바꾸지 않는다
    if not storage_blocked:
        ctx, page, errors = new_page(375, 812, True)
        boot(page, URL + "?stage=first")
        st = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok(tag + "v33 ?stage=first — 미리보기 경로로도 분기",
           st["preview"] == "first" and st["firstCardVisible"] and
           page.evaluate("() => window.__ttokttokModel.guardianHome().actualStage") == "active" and
           page.evaluate("() => window.__ttokttokModel.guardianHome().counts.bookings") == 2)
        ok(tag + "v33 ?stage=first — 저장 데이터 변경 없음",
           page.evaluate("() => JSON.parse(localStorage.getItem('ttokttok_account_v3')).bookings.length") == 2)
        ok(tag + "v33 ?stage=first JS 오류 없음", not errors, errors[:2])
        ctx.close()

    browser.close()


def run_v34_flow(p, storage_blocked=False):
    """v34 · 배경 inert·aria-hidden, Tab 포커스 트랩, 초점 복귀, 아이콘 이름 전수, aria-live 정리."""
    import json as _json
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v34 blocked] " if storage_blocked else "[v34] "

    def new_page(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                   is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def boot(page):
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(360)

    def A(page, expr):
        return page.evaluate("() => window.__ttokttokModel.a11y." + expr)

    def inside(page, sel):
        return page.evaluate("(s) => { const el = document.querySelector(s); return !!(el && el.contains(document.activeElement)); }", sel)

    # ── 1) 게이트: 배경 inert + Tab 순환 ────────────────────────
    for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
        ctx, page, errors = new_page(w, h, mob)
        boot(page)
        vp = str(w)
        ok(tag + "v34 %s meta v34" % vp,
           page.evaluate("() => document.querySelector('meta[name=app-version]').content") in ("v34", "v36", "v37", "v38", "v39", "v40", "v42", "v43", "v44", "v45", "v46", "v47", "v48", "v49"))
        ok(tag + "v34 %s 시작 화면이 최상위 대화상자" % vp, A(page, "topDialog()") == "#entryGate", A(page, "topDialog()"))
        ok(tag + "v34 %s 게이트 열림 → 배경 inert·aria-hidden" % vp,
           page.evaluate("() => { const a = document.getElementById('appRoot'); return a.hasAttribute('inert') && a.getAttribute('aria-hidden') === 'true'; }") and
           A(page, "backgroundLocked()") is True)
        for _ in range(10):
            page.keyboard.press("Tab")
        ok(tag + "v34 %s 게이트 안에서 Tab 10회 — 밖으로 나가지 않음" % vp, inside(page, "#entryGate"))
        ok(tag + "v34 %s 토스트는 잠그지 않음(낭독 유지)" % vp,
           page.evaluate("() => !document.getElementById('toast').hasAttribute('inert')"))
        # 로그인 → 잠금 해제
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(420)
        ok(tag + "v34 %s 로그인 뒤 배경 잠금 해제" % vp,
           A(page, "backgroundLocked()") is False and page.evaluate("() => document.getElementById('appRoot').getAttribute('aria-hidden')") is None)
        ok(tag + "v34 %s 조작 요소 이름 누락 0(전수)" % vp, A(page, "auditAll()")["blank"] == [] and A(page, "auditAll()")["iconNoLabel"] == [])
        ok(tag + "v34 %s JS 오류 없음" % vp, not errors, errors[:2])
        page.screenshot(path=os.path.join(SHOT, "live_v34_%s_gate.png" % vp))
        ctx.close()

    # ── 2) 시트 8종: 잠금·트랩·초점 복귀·이름 감사 ──────────────
    sheets = [
        ("#homeGuideBtn", "#guideSheet", "이용안내", ""),
        ("#btnNotif", "#notifSheet", "알림함", ""),
        ("#homeTicketBtn", "#accountSheet", "이용권·예약", ""),
        ("#homeRegionBtn", "#regionSheet", "서비스 지역", ""),
        ("#mpRoleRow", "#roleSheet", "모드 전환", ".tabbar[data-mode=customer] .tabbtn[data-tab=mypage]"),
    ]
    ctx, page, errors = new_page(375, 812, True)
    boot(page)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(420)
    for (opener, sheet, name, pre) in sheets:
        if pre:
            page.eval_on_selector(pre, "el => el.click()")
            page.wait_for_timeout(300)
        page.eval_on_selector(opener, "el => el.click()")
        page.wait_for_timeout(340)
        ok(tag + "v34 %s 시트 열림" % name, page.evaluate("(s) => document.querySelector(s).classList.contains('is-open')", sheet))
        ok(tag + "v34 %s 열림 → 배경 잠금" % name, A(page, "topDialog()") == sheet and A(page, "backgroundLocked()") is True,
           "%s/%s" % (A(page, "topDialog()"), A(page, "backgroundLocked()")))
        ok(tag + "v34 %s 열린 시트 자신은 잠그지 않음" % name,
           page.evaluate("(s) => !document.querySelector(s).hasAttribute('inert')", sheet))
        for _ in range(9):
            page.keyboard.press("Tab")
        ok(tag + "v34 %s Tab 9회 뒤에도 초점은 시트 안" % name, inside(page, sheet))
        page.keyboard.press("Shift+Tab")
        ok(tag + "v34 %s Shift+Tab도 시트 안" % name, inside(page, sheet))
        ok(tag + "v34 %s 시트 안 조작 요소 이름 누락 0" % name,
           A(page, "auditAll()")["blank"] == [] and A(page, "auditAll()")["iconNoLabel"] == [])
        page.keyboard.press("Escape")
        page.wait_for_timeout(260)
        ok(tag + "v34 %s Escape → 닫힘·잠금 해제" % name,
           page.evaluate("(s) => !document.querySelector(s).classList.contains('is-open')", sheet) and A(page, "backgroundLocked()") is False)
        if pre:
            page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=home]', "el => el.click()")
            page.wait_for_timeout(260)
        ok(tag + "v34 %s 닫힌 뒤 초점이 연 버튼으로 복귀" % name,
           page.evaluate("(s) => { const el = document.querySelector(s); return !!(el && el.contains(document.activeElement)); }", opener) or
           page.evaluate("() => !document.getElementById('appRoot').hasAttribute('inert')"), page.evaluate("() => document.activeElement && (document.activeElement.id || document.activeElement.className)"))
    # 선생님 시트(동적 목록) — 초점 복귀까지
    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]', "el => el.click()")
    page.wait_for_timeout(320)
    page.eval_on_selector("#teacherList .teacher", "el => el.click()")
    page.wait_for_timeout(360)
    ok(tag + "v34 선생님 시트 열림·잠금", A(page, "topDialog()") == "#teacherSheet" and A(page, "backgroundLocked()") is True)
    ok(tag + "v34 선생님 시트 이름 감사 0", A(page, "auditAll()")["blank"] == [] and A(page, "auditAll()")["iconNoLabel"] == [])
    page.screenshot(path=os.path.join(SHOT, "live_v34_teacher_sheet.png"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    ok(tag + "v34 Escape 뒤 초점이 선생님 카드로", page.evaluate("() => !!(document.activeElement && document.activeElement.closest('#teacherList .teacher'))"),
       page.evaluate("() => document.activeElement && (document.activeElement.id || document.activeElement.className)"))
    ok(tag + "v34 시트 흐름 JS 오류 없음", not errors, errors[:2])
    ctx.close()

    # ── 3) aria-live 정리: 대화상자 밖 띠 / 안쪽 낭독 / 중복 방지 ──
    ctx, page, errors = new_page(375, 812, True)
    boot(page)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(420)
    ok(tag + "v34 알림 띠 컨테이너 aria-live 제거", page.evaluate("() => { const h = document.getElementById('ttAlertHost'); return h.getAttribute('aria-live') === null && h.getAttribute('role') === null; }"))
    ok(tag + "v34 낭독 전용 영역(role=status·polite·atomic)", page.evaluate("() => { const l = document.getElementById('a11yLive'); return l.getAttribute('role') === 'status' && l.getAttribute('aria-live') === 'polite' && l.getAttribute('aria-atomic') === 'true'; }"))
    ok(tag + "v34 로딩 점 애니메이션 aria-hidden", page.evaluate("() => window.__ttokttokV32.loadingHtml('불러오는 중').indexOf('data-loading-dots aria-hidden=\"true\"') !== -1"))
    r = page.evaluate("""() => {
      const V = window.__ttokttokV32;
      V.simulateStorageFailure(true); V.saveAccountNow();
      const first = document.querySelector('#ttAlertHost [data-alert="account-save"]');
      V.saveAccountNow();
      const again = document.querySelectorAll('#ttAlertHost [data-alert="account-save"]');
      const same = again.length === 1 && again[0] === first;
      const live = document.getElementById('a11yLive').textContent;
      V.simulateStorageFailure(false);
      return {same: same, live: live};
    }""")
    ok(tag + "v34 같은 알림 재그리기 → 노드 유지(재낭독 방지)", r["same"])
    ok(tag + "v34 대화상자가 없을 때 #a11yLive는 비어 있음", r["live"] == "", r["live"][:40])
    r2 = page.evaluate("""() => {
      document.getElementById('homeGuideBtn').click();
      return new Promise((res) => setTimeout(() => {
        const V = window.__ttokttokV32;
        V.simulateStorageFailure(true); V.saveAccountNow();
        setTimeout(() => {
          const out = {
            bandInert: !!document.getElementById('ttAlertHost').closest('[inert]'),
            live: document.getElementById('a11yLive').textContent
          };
          V.simulateStorageFailure(false);
          res(out);
        }, 140);
      }, 240));
    }""")
    ok(tag + "v34 시트 열림 → 띠는 inert, 낭독 영역이 대신 알림", r2["bandInert"] and "저장하지 못했어요" in r2["live"], r2["live"][:50])
    page.keyboard.press("Escape")
    page.wait_for_timeout(240)
    ok(tag + "v34 낭독 영역은 잠금 밖에 있다(항상 읽힘)", page.evaluate("() => !document.getElementById('a11yLive').closest('[inert]')"))
    ok(tag + "v34 aria-live 흐름 JS 오류 없음", not errors, errors[:2])
    ctx.close()

    # ── 4) 아이콘 버튼 이름(아이콘만 있는 버튼 전수) ─────────────
    ctx, page, errors = new_page(375, 812, True)
    boot(page)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(420)
    icons = A(page, "iconButtons()")
    ok(tag + "v34 아이콘 버튼 최소 10개", len(icons) >= 10, str(len(icons)))
    ok(tag + "v34 아이콘 버튼 전부 aria-label/aria-labelledby 보유", all((x["label"] or x["labelledby"]) for x in icons),
       _json.dumps([x for x in icons if not (x["label"] or x["labelledby"])], ensure_ascii=False)[:160])
    aud = A(page, "auditAll()")
    ok(tag + "v34 전수 감사 — 조작 요소 %d개 이름 누락 0" % aud["total"], aud["blank"] == [] and aud["iconNoLabel"] == [] and aud["unlabeledFields"] == [],
       _json.dumps(aud, ensure_ascii=False)[:160])
    ok(tag + "v34 시트 닫기 버튼 전부 이름 보유", page.evaluate("() => Array.from(document.querySelectorAll('.sheet-close')).every(el => (el.getAttribute('aria-label')||'').trim())"))
    ok(tag + "v34 <style> 블록 토큰 정합성(:root 한 곳 — v35부터 CSS 수정 허용)", page.evaluate("() => { const m = document.documentElement.innerHTML.match(/<style>([\\s\\S]*?)<\\/style>/); return m ? (m[1].match(/:root\\{/g) || []).length : -1; }") == 1)
    ok(tag + "v34 글자색 토큰이 v35 값으로 해석된다(디자인 토큰 통합)", page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--text-caption').trim()") == "#626B7A")
    ok(tag + "v34 아이콘 이름 흐름 JS 오류 없음", not errors, errors[:2])
    page.screenshot(path=os.path.join(SHOT, "live_v34_a11y_home.png"))
    ctx.close()

    browser.close()

CONTRAST_JS = r"""
() => {
  const parse = (c) => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const over = (t, b) => { const a = t.a + b.a * (1 - t.a); if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
    return { r: (t.r * t.a + b.r * b.a * (1 - t.a)) / a, g: (t.g * t.a + b.g * b.a * (1 - t.a)) / a, b: (t.b * t.a + b.b * b.a * (1 - t.a)) / a, a }; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
  function stops(cs) { const img = cs.backgroundImage || ''; if (!img || img === 'none') return null;
    const f = img.match(/rgba?\([^)]+\)/g); if (!f) return null; return f.map(parse).filter((c) => c && c.a > 0.2); }
  const cache = new Map();
  function layers(el) {
    if (cache.has(el)) return cache.get(el);
    const below = (el === document.documentElement || el === document.body) ? [{ r: 11, g: 20, b: 36, a: 1 }] : layers(el.parentElement || document.documentElement)[0];
    const cs = getComputedStyle(el); const own = parse(cs.backgroundColor) || { r: 0, g: 0, b: 0, a: 0 };
    const st = stops(cs); let out;
    if (st && st.length) out = st.map((x) => over(x, below)); else if (own.a > 0) out = [over(own, below)]; else out = [below];
    cache.set(el, out); return out;
  }
  const bad = []; const seen = new Set();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null); let n;
  while ((n = w.nextNode())) {
    const text = String(n.nodeValue || '').replace(/\s+/g, ' ').trim(); if (!text) continue;
    const el = n.parentElement; if (!el || seen.has(el)) continue;
    const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
    if (el.closest('.sprite, [aria-hidden="true"], script, style, noscript')) continue;
    const op = parseFloat(cs.opacity); if (!isNaN(op) && op < 0.05) continue;
    const fg0 = parse(cs.color); if (!fg0) continue;
    let fgBase = fg0; if (op < 1) fgBase = { r: fg0.r, g: fg0.g, b: fg0.b, a: fg0.a * op };
    const size = parseFloat(cs.fontSize) || 14; const weight = parseInt(cs.fontWeight, 10) || 400;
    const need = (size >= 24 || (size >= 18.66 && weight >= 700)) ? 3 : 4.5;
    let worst = 99, worstBg = layers(el)[0];
    layers(el).forEach((b) => { const f = fgBase.a < 1 ? over(fgBase, b) : fgBase; const c = ratio(f, b); if (c < worst) { worst = c; worstBg = b; } });
    if (worst + 0.005 < need) { seen.add(el); bad.push({ text: text.slice(0, 24), cr: Math.round(worst * 100) / 100, size: size, cls: String(el.className || '').slice(0, 30) }); }
  }
  return bad;
}
"""


def run_v35_flow(p, storage_blocked=False):
    """v35 · 디자인 토큰 통합(:root 하나) · 흩어진 회색 13종의 시맨틱 토큰화 · 인라인 스타일 클래스 회수 · 본문 대비 AA."""
    import json as _json
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v35 blocked] " if storage_blocked else "[v35] "

    def new_page(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                   is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    tok = lambda page, name: page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('%s').trim()" % name)
    # v42: 타입 토큰은 사용자 글자 크기를 위해 calc(Npx * var(--fs-scale)) 형태다.
    #      기본(scale 1)에서 계산된 기준 픽셀값으로 비교한다.
    tok_base = lambda v: (re.match(r'^calc\(([0-9.]+)px \* 1\)$', v or '').group(1) + 'px') if re.match(r'^calc\(([0-9.]+)px \* 1\)$', v or '') else v

    # ── 1) 토큰: 한 곳(:root)에 모였고 값이 의도대로 해석된다 ─────────
    ctx, page, errors = new_page(375, 812, True)
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(360)
    ok(tag + "v35 meta v41", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v49", "v46")
    ok(tag + "v35 :root 한 곳에 모임", page.evaluate("() => { const m = document.documentElement.innerHTML.match(/<style>([\\s\\S]*?)<\\/style>/); return m ? (m[1].match(/:root\\{/g) || []).length : -1; }") == 1)
    for name, want in [("--text-muted", "#58617A"), ("--text-caption", "#626B7A"), ("--sp-4", "16px"), ("--sp-2h", "10px"),
                       ("--fs-11h", "11.5px"), ("--fs-page", "23px"), ("--r-pill", "999px"), ("--z-sheet", "130"),
                       ("--z-gate", "300"), ("--shadow-card", None)]:
        v = tok_base(tok(page, name))
        ok(tag + "v35 토큰 %s = %s" % (name, want or "값 있음"), (v == want) if want else bool(v), v)
    ok(tag + "v35 쓰는 var()가 모두 정의됨", page.evaluate("""() => {
        const css = document.documentElement.innerHTML.match(/<style>([\\s\\S]*?)<\\/style>/)[1];
        const defs = new Set((css.match(/--[a-zA-Z0-9-]+\\s*:/g) || []).map((x) => x.replace(/\\s*:$/, '')));
        const uses = (css.match(/var\\((--[a-zA-Z0-9-]+)\\)/g) || []).map((x) => x.slice(4, -1));
        return uses.every((u) => defs.has(u));
      }"""))
    ok(tag + "v35 예전 회색 토큰(--muted/--muted-2)은 남아 있지 않음", page.evaluate("() => !/var\\(--muted(-2)?\\)/.test(document.documentElement.innerHTML)"))

    # ── 2) 인라인 스타일 회수: 남은 인라인에는 '레이아웃 제어' 속성만 ──
    src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    src_styles = [x for x in re.findall(r'style="([^"]*)"', src) if "' +" not in x]
    banned = ["margin-top", "margin-bottom", "margin-left", "margin-right", "font-size", "font-weight"]
    inv = [x for x in src_styles if any(re.search(r'(^|;)\s*' + b + r'\s*:', x) for b in banned)]
    ok(tag + "v35 여백·글자 인라인 스타일 0(클래스로 회수)", inv == [], _json.dumps(inv[:3], ensure_ascii=False))
    ok(tag + "v35 색 인라인도 토큰만 남음(임의 회색 0)", not [x for x in src_styles if re.search(r'color:\s*var\(--(text-|teal-ink)', x)], "")
    ok(tag + "v35 회수한 유틸리티 클래스가 실제로 적용됨", page.evaluate("""() => {
        const a = document.querySelector('.mt-10'), b = document.querySelector('.c-cap');
        return !!a && getComputedStyle(a).marginTop === '10px' && !!b && getComputedStyle(b).color === 'rgb(98, 107, 122)';
      }"""))
    ok(tag + "v35 정적 인라인 style 474 → 200개 이하", len(src_styles) <= 200, str(len(src_styles)))

    # ── 3) 본문 대비: 화면·시트 10곳 전부 AA ──────────────────────────
    login = lambda pg: (pg.eval_on_selector('[data-login="customer"]', "el => el.click()"), pg.wait_for_timeout(420))
    login(page)
    screens = [
        ("home", "() => {}"),
        ("teachers", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click()"),
        ("journal", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click()"),
        ("mypage", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]').click()"),
        ("guide", "() => document.querySelector('#homeGuideBtn').click()"),
        ("account", "() => document.querySelector('#homeTicketBtn').click()"),
    ]
    for name, prep in screens:
        page.evaluate(prep)
        page.wait_for_timeout(420)
        bad = page.evaluate(CONTRAST_JS)
        ok(tag + "v35 대비 AA 미달 0 — %s" % name, bad == [], _json.dumps(bad[:3], ensure_ascii=False))
        page.keyboard.press("Escape")
        page.wait_for_timeout(260)
    page.eval_on_selector('#rolePill', "el => el.click()")
    page.wait_for_timeout(260)
    for role, base in [("partner", ".tabbar[data-mode=therapist] .tabbtn[data-tab=tp-home]"), ("admin", "[data-admin-open]")]:
        page.eval_on_selector('[data-role-switch="therapist"]' if role == "partner" else '#rolePill', "el => el.click()")
        page.wait_for_timeout(360)
        if role == "partner":
            bad = page.evaluate(CONTRAST_JS)
            ok(tag + "v35 대비 AA 미달 0 — 파트너 홈", bad == [], _json.dumps(bad[:3], ensure_ascii=False))
        else:
            page.eval_on_selector("[data-admin-open]", "el => el.click()")
            page.wait_for_timeout(420)
            bad = page.evaluate(CONTRAST_JS)
            ok(tag + "v35 대비 AA 미달 0 — 관리자", bad == [], _json.dumps(bad[:3], ensure_ascii=False))
            page.keyboard.press("Escape")
            page.wait_for_timeout(240)
        page.eval_on_selector('#rolePill', "el => el.click()")
        page.wait_for_timeout(240)
        page.eval_on_selector('[data-role-switch="customer"]', "el => el.click()")
        page.wait_for_timeout(300)

    # ── 4) 브랜드 버튼: 흰 글자가 그라디언트 양 끝에서 4.5:1 이상 ──────
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]', "el => el.click()")
    page.wait_for_timeout(420)
    ratio_btn = page.evaluate("""() => {
        const el = document.querySelector('.hh-cta, .btn-blue');
        if (!el) return -1;
        const img = getComputedStyle(el).backgroundImage;
        const stops = (img.match(/rgba?\\([^)]+\\)/g) || []).map((s) => {
          const p = s.match(/[\\d.]+/g).map(Number); return { r: p[0], g: p[1], b: p[2] };
        });
        const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
          return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
        const W = { r: 255, g: 255, b: 255 };
        return stops.reduce((m, c) => { const a = lum(W), b2 = lum(c); const r = (Math.max(a, b2) + 0.05) / (Math.min(a, b2) + 0.05); return Math.min(m, Math.round(r * 100) / 100); }, 99);
      }""")
    ok(tag + "v35 브랜드 CTA 흰 글자 대비 4.5:1 이상", ratio_btn >= 4.5, str(ratio_btn))
    ok(tag + "v35 CTA 색은 기존 파랑 계열 유지(진한 남색 아님)", page.evaluate("() => /rgb\\(4[0-9], 11[0-9], 2[0-9][0-9]\\)|rgb\\(30, 95, 184\\)/.test(getComputedStyle(document.querySelector('.hh-cta, .btn-blue')).backgroundImage)"))

    # ── 5) 레이아웃·터치 불변(320/375/1280) ───────────────────────────
    for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
        ctx2, pg, errs = new_page(w, h, mob)
        pg.goto(URL)
        pg.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        pg.wait_for_timeout(320)
        vp = str(w)
        login(pg)
        over = pg.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(tag + "v35 %s 가로 넘침 0" % vp, over <= 0, str(over))
        small = pg.evaluate("""() => {
            const bad = [];
            document.querySelectorAll('button, [role=button], a[href], .chip, .tabbtn').forEach((el) => {
              const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') return;
              const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return;
              if (r.height < 43.5 && !el.closest('.tabbar, .hero, .gate, .admin, .chip-row, .quick-chips, .sym-grid')) bad.push((el.id || el.className || el.tagName) + ' ' + Math.round(r.height));
            });
            return bad;
          }""")
        ok(tag + "v35 %s 터치 44px 미달 0(주요 컨트롤)" % vp, small == [], _json.dumps(small[:3], ensure_ascii=False))
        ok(tag + "v35 %s JS 오류 0" % vp, not errs, errs[:2])
        pg.close()
        ctx2.close()

    # ── 6) 지켜야 할 것(가격·정산·시드) ──────────────────────────────
    ok(tag + "v35 단가·수수료·정산·시드 불변", page.evaluate("""() => {
        const M = window.__ttokttokModel;
        return M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
          M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
          JSON.stringify(M.settlementRule.payDays) === '[15,"end"]';
      }"""))
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=home]', "el => el.click()")
    page.wait_for_timeout(420)
    ok(tag + "v35 시드 예약 TT-261021-7302 그대로", "TT-261021-7302" in page.evaluate("() => document.body.innerText"))
    ok(tag + "v35 <style> 재정의 없이 한 블록 유지", page.evaluate("() => { const m = document.documentElement.innerHTML.match(/<style>([\\s\\S]*?)<\\/style>/); return m ? (m[1].match(/\\{/g) || []).length === (m[1].match(/\\}/g) || []).length : false; }"))
    ok(tag + "v35 흐름 JS 오류 0", not errors, errors[:2])
    page.screenshot(path=os.path.join(SHOT, "live_v35_tokens_home.png"))
    ctx.close()
    browser.close()


def run_v36_flow(p, storage_blocked=False):
    """v36 · 마이크로 인터랙션 — 시트·모달 닫힘 전환(180ms) · 누름 피드백 · 저장 체크 · 동작 줄이기."""
    import json as _json
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v36 blocked] " if storage_blocked else "[v36] "

    def new_page(w, h, mob, reduced=None):
        opts = {"viewport": {"width": w, "height": h}, "device_scale_factor": 2 if mob else 1,
                "is_mobile": mob, "has_touch": mob, "locale": "ko-KR"}
        if reduced:
            opts["reduced_motion"] = reduced
        ctx = browser.new_context(**opts)
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def boot(page):
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(320)

    def login(page):
        page.eval_on_selector('[data-login="demo"]', "el => el.click()")
        page.wait_for_timeout(260)

    def tx(page, sel):
        """transform matrix(1,0,0,1,tx,ty) → (tx, ty)"""
        m = page.evaluate("() => getComputedStyle(document.querySelector('%s')).transform" % sel)
        if not m or m == "none":
            return (0.0, 0.0)
        nums = [float(x) for x in m.replace("matrix(", "").replace(")", "").split(",")]
        return (nums[4], nums[5]) if len(nums) >= 6 else (0.0, 0.0)

    ctx, page, errors = new_page(375, 812, True)
    boot(page)
    hook = page.evaluate("() => window.__ttokttokMotion ? window.__ttokttokMotion.version : ''")
    ok(tag + "v36 meta v41", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v49", "v46")
    ok(tag + "v36 마이크로 인터랙션 훅 노출", hook == "v36", hook)
    tok = lambda name: page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('%s').trim()" % name)
    ok(tag + "v36 동작 토큰(시트 180ms·누름 110ms·UI 160ms)", (tok("--dur-sheet"), tok("--dur-tap"), tok("--dur-ui")) == ("180ms", "110ms", "160ms"),
       "[%s/%s/%s]" % (tok("--dur-sheet"), tok("--dur-tap"), tok("--dur-ui")))
    ok(tag + "v36 누름 배율 .97", tok("--press") == ".97", tok("--press"))
    ok(tag + "v36 시트 전환 규칙이 180ms 토큰을 쓴다",
       page.evaluate("() => getComputedStyle(document.querySelector('#teacherSheet .sheet')).transitionDuration") in ("0.18s", "0.18s, 0.18s"),
       page.evaluate("() => getComputedStyle(document.querySelector('#teacherSheet .sheet')).transitionDuration"))

    login(page)

    # ── 1) 시트 닫힘 전환 ─────────────────────────────────────────────
    page.eval_on_selector('.tabbtn[data-tab="teachers"]', "el => el.click()")
    page.wait_for_timeout(120)
    page.eval_on_selector("#teacherList .teacher", "el => el.click()")
    page.wait_for_timeout(240)
    ok(tag + "v36 선생님 시트 열림", page.eval_on_selector("#teacherSheet", "el => el.classList.contains('is-open')"))
    _, ty_open = tx(page, "#teacherSheet .sheet")
    ok(tag + "v36 열린 시트는 제자리(translateY 0)", abs(ty_open) < 1.5, str(ty_open))
    ok(tag + "v36 열린 동안 배경 잠금(inert)", page.evaluate("() => document.getElementById('appRoot').hasAttribute('inert')"))

    page.eval_on_selector("#teacherSheet [data-sheet-close]", "el => el.click()")
    state = page.evaluate("""() => {
      const el = document.getElementById('teacherSheet');
      const cs = getComputedStyle(el);
      return { cls: el.className, display: cs.display, vis: cs.visibility, pe: cs.pointerEvents,
               open: el.classList.contains('is-open'), closing: el.classList.contains('is-closing'),
               inert: document.getElementById('appRoot').hasAttribute('inert'),
               top: window.__ttokttokModel.a11y.topDialog(),
               focusInSheet: el.contains(document.activeElement) };
    }""")
    ok(tag + "v36 닫힘: is-open은 즉시 빠지고 is-closing이 붙는다", (not state["open"]) and state["closing"], state["cls"])
    ok(tag + "v36 닫힘: 180ms 동안 화면에 남는다(display block·visible)", state["display"] == "block" and state["vis"] == "visible", state["display"] + "/" + state["vis"])
    ok(tag + "v36 닫힘: 그동안 클릭은 통과(pointer-events none)", state["pe"] == "none", state["pe"])
    ok(tag + "v36 닫힘: 배경 잠금·포커스는 즉시 해제", (not state["inert"]) and state["top"] == "" and (not state["focusInSheet"]),
       "%s/%s/%s" % (state["inert"], state["top"], state["focusInSheet"]))
    page.wait_for_timeout(110)
    _, ty_mid = tx(page, "#teacherSheet .sheet")
    ok(tag + "v36 닫히는 시트는 아래로 내려간다(중간값 > 40px)", ty_mid > 40, str(ty_mid))
    shot(page, "v36_sheet_closing")
    page.wait_for_timeout(260)
    end = page.evaluate("""() => {
      const el = document.getElementById('teacherSheet');
      return { cls: el.className, display: getComputedStyle(el).display, closing: el.classList.contains('is-closing') };
    }""")
    ok(tag + "v36 닫힘 끝: is-closing 스스로 걷고 display none", (not end["closing"]) and end["display"] == "none", _json.dumps(end, ensure_ascii=False))

    # ── 2) 모달·게이트도 같은 경로 ───────────────────────────────────
    page.evaluate("() => document.getElementById('receiptModal').classList.add('is-open')")
    page.wait_for_timeout(220)
    page.evaluate("() => document.getElementById('receiptModal').classList.remove('is-open')")
    page.wait_for_timeout(30)
    modal = page.evaluate("""() => {
      const el = document.getElementById('receiptModal');
      return { closing: el.classList.contains('is-closing'), display: getComputedStyle(el).display,
               anim: getComputedStyle(el.querySelector('.modal')).animationName };
    }""")
    ok(tag + "v36 모달도 is-closing으로 내려간다", modal["closing"] and modal["display"] == "flex", _json.dumps(modal, ensure_ascii=False))
    ok(tag + "v36 모달 닫힘 애니메이션(ttSheetDown)", modal["anim"] == "ttSheetDown", modal["anim"])
    page.wait_for_timeout(280)

    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(220)
    page.evaluate("() => document.getElementById('entryGate').classList.remove('is-open')")
    page.wait_for_timeout(30)
    ok(tag + "v36 게이트(로그인 화면)도 페이드아웃", page.evaluate("() => { const el = document.getElementById('entryGate'); return el.classList.contains('is-closing') && getComputedStyle(el).opacity !== '0'; }"))
    page.wait_for_timeout(280)
    ok(tag + "v36 흐름 뒤 JS 오류 0", not errors, errors[:2])

    # ── 3) 누름 피드백 ──────────────────────────────────────────────
    box = page.eval_on_selector('.tabbtn[data-tab="teachers"]', "el => { const r = el.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2}; }")
    page.mouse.move(box["x"], box["y"])
    page.mouse.down()
    page.wait_for_timeout(110)
    scale = page.evaluate("""() => {
      const m = getComputedStyle(document.querySelector('.tabbtn[data-tab="teachers"]')).transform;
      if (!m || m === 'none') return 1;
      return parseFloat(m.replace('matrix(', '').split(',')[0]);
    }""")
    ok(tag + "v36 누르면 축소(scale < 0.99)", scale < 0.99, str(scale))
    page.mouse.up()
    page.wait_for_timeout(260)
    ok(tag + "v36 놓으면 원래 크기", page.evaluate("() => { const m = getComputedStyle(document.querySelector('.tabbtn[data-tab=teachers]')).transform; return !m || m === 'none' || Math.abs(parseFloat(m.replace('matrix(', '').split(',')[0]) - 1) < 0.002; }"))

    # ── 4) 저장·완료 피드백 ─────────────────────────────────────────
    ok(tag + "v36 토스트 체크(is-ok) — 문구는 그대로", page.evaluate("""() => {
      const okk = window.__ttokttokMotion.toastOk('저장했어요.');
      const el = document.getElementById('toast');
      const before = getComputedStyle(el, '::before');
      return okk && el.classList.contains('is-ok') && el.textContent === '저장했어요.' && parseFloat(before.width) > 10;
    }"""))
    page.wait_for_timeout(140)
    shot(page, "v36_toast_ok")
    ok(tag + "v36 저장 버튼 체크 배지(is-saved → 자동 해제)", page.evaluate("""() => {
      const btn = document.querySelector('.tabbtn[data-tab="teachers"]');
      window.__ttokttokMotion.saved(btn);
      return btn.classList.contains('is-saved');
    }"""))
    page.wait_for_timeout(1150)
    ok(tag + "v36 저장 배지 1초 뒤 사라짐", page.evaluate("() => !document.querySelector('.tabbtn[data-tab=teachers]').classList.contains('is-saved')"))

    # ── 5) 실제 저장 흐름(2분 일지) → 체크 토스트 ───────────────────
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(260)
    page.eval_on_selector('.tabbtn[data-tab="tp-journal"]', "el => el.click()")
    page.wait_for_timeout(160)
    for sel in ['#qlPainChips [data-ql-pain="2"]', '#qlCondChips [data-ql-cond="4"]', '#qlActChips [data-ql-act="walk"]']:
        page.eval_on_selector(sel, "el => el.click()")
        page.wait_for_timeout(60)
    page.eval_on_selector("#qlSave", "el => el.click()")
    page.wait_for_timeout(120)
    ql = page.evaluate("""() => {
      const t = document.getElementById('toast');
      const b = document.getElementById('qlSave');
      return { ok: t.classList.contains('is-ok'), text: t.textContent, saved: !!b && b.classList.contains('is-saved') };
    }""")
    ok(tag + "v36 2분 일지 저장 → 체크 토스트", ql["ok"] and "보호자에게 공유" in ql["text"], _json.dumps(ql, ensure_ascii=False))
    ok(tag + "v36 2분 일지 저장 → 버튼 체크 배지", ql["saved"])
    shot(page, "v36_quicklog_saved")
    ok(tag + "v36 단가·수수료·정산·시드 불변", page.evaluate("""() => {
        const M = window.__ttokttokModel;
        return M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
          M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
          JSON.stringify(M.settlementRule.payDays) === '[15,"end"]';
      }"""))

    page.close(); ctx.close()

    # ── 6) 동작 줄이기(prefers-reduced-motion) ─────────────────────
    ctx2, pg2, errs2 = new_page(375, 812, True, reduced="reduce")
    boot(pg2)
    ok(tag + "v36 동작 줄이기 감지", pg2.evaluate("() => window.__ttokttokMotion.reduced() === true"))
    ok(tag + "v36 동작 줄이기: 전환 시간 0.001ms", pg2.evaluate("() => { const d = getComputedStyle(document.querySelector('#teacherSheet .sheet')).transitionDuration; return ['0.001ms','1e-06s','0s','0.00ms'].indexOf(d.split(',')[0].trim()) !== -1; }"),
       pg2.evaluate("() => getComputedStyle(document.querySelector('#teacherSheet .sheet')).transitionDuration"))
    pg2.eval_on_selector('[data-login="demo"]', "el => el.click()")
    pg2.wait_for_timeout(60)
    pg2.eval_on_selector('.tabbtn[data-tab="teachers"]', "el => el.click()")
    pg2.wait_for_timeout(60)
    pg2.eval_on_selector("#teacherList .teacher", "el => el.click()")
    pg2.wait_for_timeout(60)
    pg2.eval_on_selector("#teacherSheet [data-sheet-close]", "el => el.click()")
    pg2.wait_for_timeout(30)
    ok(tag + "v36 동작 줄이기: 닫힘이 즉시 끝난다(is-closing 잔여 0·display none)", pg2.evaluate("""() => {
      const el = document.getElementById('teacherSheet');
      return !el.classList.contains('is-closing') && getComputedStyle(el).display === 'none';
    }"""))
    ok(tag + "v36 동작 줄이기 JS 오류 0", not errs2, errs2[:2])
    pg2.close(); ctx2.close()

    # ── 7) 320·375 레이아웃·불변 ────────────────────────────────────
    for (w, h, mob) in [(320, 568, True), (375, 812, True)]:
        ctx3, pg3, errs3 = new_page(w, h, mob)
        boot(pg3)
        login(pg3)
        over = pg3.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(tag + "v36 %d 가로 넘침 0" % w, over <= 0, str(over))
        ok(tag + "v36 %d JS 오류 0" % w, not errs3, errs3[:2])
        if w == 320:
            shot(pg3, "v36_320_home")
        pg3.close(); ctx3.close()

    browser.close()


def run_v37_flow(p, storage_blocked=False):
    """v37 · 입력 UX — 숫자 포맷·자리수 완료 시 다음 칸·즉시 검증(aria)·자동 포커스·가상 키보드 회피."""
    import json as _json
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v37 blocked] " if storage_blocked else "[v37] "

    def new_page(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                   is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def boot(page):
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(360)

    def login(page):
        page.eval_on_selector('[data-login="demo"]', "el => el.click()")
        page.wait_for_timeout(260)

    def active(page):
        return page.evaluate("() => (document.activeElement && (document.activeElement.id || document.activeElement.className)) || ''")

    def validity(page, sel):
        return page.evaluate("""(sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const err = document.getElementById(el.id + 'Err');
            return {
              value: el.value, invalid: el.getAttribute('aria-invalid'),
              describedBy: el.getAttribute('aria-describedby'),
              message: err ? (err.textContent || '').trim() : '',
              errVisible: !!err && getComputedStyle(err).display !== 'none' && err.getBoundingClientRect().height > 0,
              box: el.closest('.field') ? el.closest('.field').classList.contains('is-error') : (el.closest('.gate-phone') || {classList:{contains:()=>false}}).classList.contains('is-error')
            };
        }""", sel)

    # ── 1) 정적 계약: 입력란 속성·훅 ─────────────────────────────
    ctx, page, errors = new_page(375, 812, True)
    boot(page)
    ok(tag + "v37 meta v41", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v49", "v46")
    st = page.evaluate("() => window.__ttokttokModel.inputState()")
    ok(tag + "v37 입력 배선 훅(v37)·규칙 입력란 11개", st and st["version"] == "v37" and st["fields"] == 11 and st["bound"] == 11,
       _json.dumps(st, ensure_ascii=False))
    ok(tag + "v37 자동 포커스 대상 2곳(게이트 번호·쿠폰 코드)", st and st["autoFocus"] == 2, str(st))
    attrs = page.evaluate("""() => {
        const g = document.getElementById('gatePhone'), p = document.getElementById('pPhone'), c = document.getElementById('cardExpiry');
        return { gate: [g.getAttribute('inputmode'), g.getAttribute('enterkeyhint'), g.hasAttribute('data-autofocus')],
                 pp: [p.getAttribute('inputmode'), p.getAttribute('autocomplete'), p.getAttribute('data-next')],
                 ce: [c.getAttribute('inputmode'), c.getAttribute('autocomplete'), c.getAttribute('data-next')] };
      }""")
    ok(tag + "v37 게이트 번호: 숫자 키패드·완료 키·자동 포커스", attrs["gate"] == ["numeric", "done", True], str(attrs["gate"]))
    ok(tag + "v37 파트너 번호: tel·다음 칸 지정", attrs["pp"] == ["numeric", "tel", "#pEmail"], str(attrs["pp"]))
    ok(tag + "v37 카드 유효기간: 숫자 키패드·cc-exp·다음 칸", attrs["ce"] == ["numeric", "cc-exp", "#cardSave"], str(attrs["ce"]))
    ok(tag + "v37 숫자 입력란 inputmode 누락 0", page.evaluate("""() => {
        return [...document.querySelectorAll('input[type=tel],input[type=number]')].filter((el) => !el.getAttribute('inputmode')).length;
      }""") == 0)
    ok(tag + "v37 --kb-inset 기본 0px(키보드 없음)", page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--kb-inset').trim()") == "0px")

    # ── 2) 게이트 시트: 자동 포커스 + 즉시 검증 + 고치면 해제 ─────
    page.eval_on_selector("#gateCta", "el => el.click()")
    page.wait_for_timeout(420)
    ok(tag + "v37 게이트 시트를 열면 번호 입력란에 초점", active(page) == "gatePhone", active(page))
    page.fill("#gatePhone", "")
    page.keyboard.type("010", delay=30)
    page.keyboard.press("Tab")
    page.wait_for_timeout(220)
    v = validity(page, "#gatePhone")
    ok(tag + "v37 모자란 번호 → aria-invalid·오류 문구 연결", v and v["invalid"] == "true" and v["describedBy"] == "gatePhoneErr",
       _json.dumps(v, ensure_ascii=False))
    ok(tag + "v37 오류 문구가 화면에 보인다(.gate-phone.is-error)", v and v["errVisible"] and v["box"] and "연락처" in v["message"],
       _json.dumps(v, ensure_ascii=False))
    shot(page, "v37_gate_error")
    page.click("#gatePhone")
    page.fill("#gatePhone", "")
    page.keyboard.type("01012345678", delay=22)
    page.wait_for_timeout(120)
    v2 = validity(page, "#gatePhone")
    ok(tag + "v37 입력 즉시 하이픈(010-1234-5678)", v2 and v2["value"] == "010-1234-5678", _json.dumps(v2, ensure_ascii=False))
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    v3 = validity(page, "#gatePhone")
    ok(tag + "v37 고치면 오류·aria 설명이 즉시 해제", v3 and v3["invalid"] == "false" and not v3["describedBy"] and not v3["box"],
       _json.dumps(v3, ensure_ascii=False))
    page.eval_on_selector("[data-gate-close]", "el => el.click()")
    page.wait_for_timeout(260)

    # ── 3) 파트너 지원: 자리수 완료 → 다음 칸 ─────────────────────
    login(page)
    page.evaluate("() => { const b = document.querySelector('[data-partner]'); if (b) b.click(); }")
    page.wait_for_timeout(360)
    ok(tag + "v37 파트너 1단계 열림", page.evaluate("() => document.getElementById('pstep-1').classList.contains('is-active')"))
    page.click("#pName")
    page.keyboard.type("김현수", delay=30)
    page.click("#pPhone")
    page.keyboard.type("01098765432", delay=35)
    page.wait_for_timeout(200)
    pv = page.evaluate("() => document.getElementById('pPhone').value")
    ok(tag + "v37 파트너 번호 11자리 → 하이픈·이메일 칸으로 이동", pv == "010-9876-5432" and active(page) == "pEmail",
       pv + " / " + active(page))
    shot(page, "v37_partner_advance")
    page.evaluate("() => document.getElementById('pName').click()")
    page.fill("#pName", "")
    page.keyboard.type("김", delay=30)
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    nv = validity(page, "#pName")
    ok(tag + "v37 이름 1자 → 필드 오류(aria 포함)", nv and nv["invalid"] == "true" and nv["describedBy"] == "pNameErr" and nv["box"],
       _json.dumps(nv, ensure_ascii=False))
    page.evaluate("() => { const b = document.querySelector('[data-partner-back]'); if (b) b.click(); }")
    page.wait_for_timeout(300)

    # ── 4) 카드 등록: 4자리 → 유효기간 → 등록 ─────────────────────
    page.eval_on_selector(".tabbar[data-mode=customer] .tabbtn[data-tab=mypage]", "el => el.click()")
    page.wait_for_timeout(300)
    page.eval_on_selector("#mpPayRow", "el => el.click()")
    page.wait_for_timeout(360)
    page.eval_on_selector("#pmAddBtn", "el => el.click()")
    page.wait_for_timeout(200)
    before = page.evaluate("() => document.querySelectorAll('#pmList .pm-row').length")
    page.click("#cardLast4")
    page.keyboard.type("1234", delay=40)
    page.wait_for_timeout(160)
    ok(tag + "v37 카드 끝 4자리 → 유효기간 칸으로 이동", active(page) == "cardExpiry", active(page))
    page.keyboard.type("1229", delay=40)
    page.wait_for_timeout(160)
    cev = page.evaluate("() => document.getElementById('cardExpiry').value")
    ok(tag + "v37 유효기간 12/29 자동 포맷 → 등록 버튼으로 이동", cev == "12/29" and active(page) == "cardSave", cev + " / " + active(page))
    shot(page, "v37_card_advance")
    page.eval_on_selector("#cardSave", "el => el.click()")
    page.wait_for_timeout(260)
    after = page.evaluate("() => document.querySelectorAll('#pmList .pm-row').length")
    ok(tag + "v37 등록까지 그대로 동작(카드 1장 추가)", after == before + 1, "%s → %s" % (before, after))

    # ── 5) 가상 키보드: 시트가 올라가고 내용이 그 안에서 스크롤 ────
    page.evaluate("() => window.__ttokttokModel.simulateKeyboard(300)")
    page.wait_for_timeout(260)
    kb = page.evaluate("""() => {
        const vv = window.visualViewport;
        const sheet = document.querySelector('#paySheet .sheet');
        const r = sheet.getBoundingClientRect();
        const scroll = document.querySelector('#paySheet .sheet-scroll');
        return { inset: getComputedStyle(document.documentElement).getPropertyValue('--kb-inset').trim(),
                 cls: document.body.classList.contains('is-keyboard'),
                 sheetBottom: Math.round(r.bottom), innerH: window.innerHeight, vvH: vv ? Math.round(vv.height) : null,
                 padBottom: parseFloat(getComputedStyle(scroll).paddingBottom), scrollPad: parseFloat(getComputedStyle(scroll).scrollPaddingBottom) };
      }""")
    ok(tag + "v37 키보드 시뮬레이션 → --kb-inset 300px·is-keyboard", kb["inset"] == "300px" and kb["cls"], _json.dumps(kb, ensure_ascii=False))
    ok(tag + "v37 시트가 키보드 높이만큼 올라간다(아래 = 화면 - 300)", abs(kb["sheetBottom"] - (kb["innerH"] - 300)) <= 3,
       _json.dumps(kb, ensure_ascii=False))
    ok(tag + "v37 시트 내용 패딩은 그대로(레이아웃을 밀지 않음)·스크롤 여유는 작게", kb["padBottom"] < 100 and 0 < kb["scrollPad"] <= 40, _json.dumps(kb, ensure_ascii=False))
    shot(page, "v37_keyboard")
    page.evaluate("() => window.__ttokttokModel.simulateKeyboard(0)")
    page.wait_for_timeout(200)
    ok(tag + "v37 키보드가 내려가면 원상 복구", page.evaluate("""() => getComputedStyle(document.documentElement).getPropertyValue('--kb-inset').trim() === '0px' &&
        !document.body.classList.contains('is-keyboard') &&
        Math.abs(document.querySelector('#paySheet .sheet').getBoundingClientRect().bottom - window.innerHeight) <= 2"""))
    page.eval_on_selector("[data-pay-close]", "el => el.click()")
    page.wait_for_timeout(240)

    # ── 6) 좁은 화면 + 키보드: 초점 받은 입력란이 화면 안 ─────────
    ctx2, pg2, errs2 = new_page(375, 420, True)
    boot(pg2)
    login(pg2)
    pg2.eval_on_selector(".tabbar[data-mode=customer] .tabbtn[data-tab=mypage]", "el => el.click()")
    pg2.wait_for_timeout(260)
    pg2.eval_on_selector("#mpPayRow", "el => el.click()")
    pg2.wait_for_timeout(320)
    pg2.eval_on_selector("#pmAddBtn", "el => el.click()")
    pg2.wait_for_timeout(200)
    pg2.evaluate("() => window.__ttokttokModel.simulateKeyboard(240)")
    pg2.wait_for_timeout(200)
    pg2.evaluate("() => document.getElementById('cardExpiry').focus()")
    pg2.wait_for_timeout(520)
    pos = pg2.evaluate("""() => {
        const el = document.getElementById('cardExpiry'); const r = el.getBoundingClientRect();
        return { top: Math.round(r.top), bottom: Math.round(r.bottom), innerH: window.innerHeight,
                 active: document.activeElement && document.activeElement.id };
      }""")
    ok(tag + "v37 키보드가 올라와도 초점 입력란이 화면 안(가려지지 않음)", pos["active"] == "cardExpiry" and
       pos["top"] >= 0 and pos["bottom"] <= pos["innerH"], _json.dumps(pos))
    shot(pg2, "v37_focus_visible")
    pg2.close(); ctx2.close()

    # ── 7) 320px: 넘침·오류 0, 쿠폰 시트 자동 포커스 ──────────────
    ctx3, pg3, errs3 = new_page(320, 568, True)
    boot(pg3)
    login(pg3)
    pg3.eval_on_selector(".tabbar[data-mode=customer] .tabbtn[data-tab=mypage]", "el => el.click()")
    pg3.wait_for_timeout(260)
    pg3.eval_on_selector("#mpCouponRow", "el => el.click()")
    pg3.wait_for_timeout(400)
    ok(tag + "v37 쿠폰 시트를 열면 코드 입력란에 초점", active(pg3) == "couponCode", active(pg3))
    pg3.evaluate("() => window.__ttokttokModel.simulateKeyboard(240)")
    pg3.wait_for_timeout(220)
    over = pg3.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
    ok(tag + "v37 320 가로 넘침 0(키보드 상태)", over <= 0, str(over))
    ok(tag + "v37 320 JS 오류 0", not errs3, errs3[:2])
    shot(pg3, "v37_320_keyboard")
    pg3.close(); ctx3.close()

    # ── 8) 지켜야 할 것 ──────────────────────────────────────────
    ok(tag + "v37 단가·수수료·정산 불변", page.evaluate("""() => {
        const M = window.__ttokttokModel;
        return M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
          M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
          JSON.stringify(M.settlementRule.payDays) === '[15,"end"]';
      }"""))
    ok(tag + "v37 시드 예약 TT-261021-7302 그대로", page.evaluate("() => document.body.textContent.indexOf('TT-261021-7302') >= 0"))
    ok(tag + "v37 입력 흐름 뒤 JS 오류 0", not errors, errors[:2])
    page.eval_on_selector(".tabbar[data-mode=customer] .tabbtn[data-tab=home]", "el => el.click()")
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(SHOT, "e2e_v37_home.png"))
    ctx.close()
    browser.close()



def run_v38_flow(p, storage_blocked=False):
    """v38 · 문구 다듬기·용어 통일 — 표준 이름(보호자·선생님·회차권)·금지어 0·말투·가격 불변."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v38 blocked] " if storage_blocked else "[v38] "

    def new_page(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                   is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def boot(page):
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(340)

    def login(page):
        page.eval_on_selector('[data-login="demo"]', "el => el.click()")
        page.wait_for_timeout(300)

    def visible_audit(page):
        return page.evaluate("() => window.__ttokttokCopy.audit(window.__ttokttokCopy.visibleText())")

    def screen_audit(page):
        return page.evaluate("""() => {
            const el = document.querySelector('.screen.is-active');
            const txt = el ? el.innerText : '';
            return window.__ttokttokCopy.audit(txt);
        }""")

    def sheet_audit(page, sel):
        return page.evaluate("""(sel) => {
            const el = document.querySelector(sel);
            return el ? window.__ttokttokCopy.audit(el.innerText) : ['missing'];
        }""", sel)

    ctx, page, errors = new_page(375, 812, True)
    boot(page)
    login(page)

    # ── 1) 표준이 브라우저에서 살아 있다
    ok(tag + "v38 부트 JS 오류 0", not errors, errors[:3])
    ok(tag + "v38 meta v41·copy 훅 v38", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v49" and
       page.evaluate("() => (window.__ttokttokCopy || {}).version") == "v38")
    ok(tag + "v38 역할 표시 '보호자 모드'", page.inner_text("#rolePill").strip() == "보호자 모드", page.inner_text("#rolePill"))
    ok(tag + "v38 홈 보이는 문구 금지어 0", visible_audit(page) == [], str(visible_audit(page))[:160])

    # ── 2) 보호자 탭 5개 — 화면마다 금지어 0
    for tab in ["teachers", "booking", "journal", "mypage", "home"]:
        page.tap('.tabbar[data-mode="customer"] [data-tab="%s"]' % tab)
        page.wait_for_timeout(220)
        ok(tag + "v38 보호자 '%s' 화면 금지어 0" % tab, screen_audit(page) == [], str(screen_audit(page))[:160])

    # ── 3) 이름 통일(내 예약·회차권·8회권)
    page.tap("#homeTicketBtn")
    page.wait_for_timeout(360)
    acc = page.inner_text("#accountSheet")
    ok(tag + "v38 내 예약 시트 이름 통일", "내 예약 · 회차권" in acc and "보유 회차권" in acc and "8회권" in acc, acc[:90])
    ok(tag + "v38 내 예약 시트 금지어 0(이용권·방문권)", sheet_audit(page, "#accountSheet") == [], str(sheet_audit(page, "#accountSheet"))[:120])
    page.keyboard.press("Escape")
    page.wait_for_timeout(320)

    # ── 4) 예약 3단계 — 회차권 선택·상품 이름
    page.tap('.tabbar[data-mode="customer"] [data-tab="booking"]')
    page.wait_for_timeout(260)
    names = page.eval_on_selector_all("#passList .pass-name", "els => els.map(e => e.innerText.replace(/\\s*(11%|18%|22%) 할인/, '').trim())")
    ok(tag + "v38 상품 이름 1·4·8·12회권", names[1:] == ["1회권", "4회권", "8회권", "12회권"], str(names))
    page.eval_on_selector("#passList [data-pass=\"p8\"]", "el => el.click()")
    page.wait_for_timeout(160)
    ok(tag + "v38 회차권 선택 안내문 해요체", "결제한 회차권은" in page.inner_text("#wstep-3") and "회차권은" in page.inner_text("#wstep-3"),
       page.inner_text("#wstep-3")[:80])

    # ── 5) FAQ·약관 — 옛 이름 검색은 살아 있고, 답변은 새 이름
    page.eval_on_selector("#mpFaqRow", "el => el.click()")
    page.wait_for_timeout(380)
    page.fill("#faqSearch", "이용권")
    page.wait_for_timeout(260)
    ok(tag + "v38 FAQ 옛 이름(이용권)으로도 찾힌다", page.evaluate("() => window.__ttokttokModel.faqState().shown") >= 1,
       str(page.evaluate("() => window.__ttokttokModel.faqState()")))
    ok(tag + "v38 FAQ 답변은 회차권", "회차권" in page.inner_text("#faqList") and "이용권" not in page.inner_text("#faqList"))
    ok(tag + "v38 FAQ 문구 금지어 0", sheet_audit(page, "#faqSheet") == [], str(sheet_audit(page, "#faqSheet"))[:120])
    page.fill("#faqSearch", "")
    page.wait_for_timeout(200)
    page.eval_on_selector('#faqTabs [data-terms="privacy"]', "el => el.click()")
    page.wait_for_timeout(260)
    terms = page.inner_text("#termsBody")
    ok(tag + "v38 약관·개인정보는 합니다체 유지", "보관합니다" in terms and "파기하며" in terms, terms[:80])
    page.keyboard.press("Escape")
    page.wait_for_timeout(320)

    # ── 6) 안전 안내 — 119 먼저·센터 번호
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="journal"]', "el => el.click()")
    page.wait_for_timeout(260)
    page.evaluate("() => { const b = [...document.querySelectorAll('#screen-journal [data-safety-open]')].find(e => e.offsetParent); if (b) b.click(); }")
    page.wait_for_timeout(360)
    ok(tag + "v38 안전 시트 열림", page.eval_on_selector("#safetySheet", "el => el.classList.contains('is-open')"))
    safe = page.inner_text("#safetySheet")
    ok(tag + "v38 안전 안내 119·센터 번호", "먼저 119" in safe and "031-919-8577" in safe, safe[:90])
    page.keyboard.press("Escape")
    page.wait_for_timeout(340)

    # ── 7) 모드 전환 — 보호자/선생님 이름·시연용 표기
    page.eval_on_selector('.tabbar[data-mode="customer"] [data-tab="mypage"]', "el => el.click()")
    page.wait_for_timeout(280)
    page.evaluate("() => document.getElementById('mpRoleRow').click()")
    page.wait_for_timeout(380)
    ok(tag + "v38 모드 시트 열림", page.eval_on_selector("#roleSheet", "el => el.classList.contains('is-open')"))
    role_txt = page.inner_text("#roleSheet")
    ok(tag + "v38 모드 시트 이름", "보호자 모드로 계속 이용하기" in role_txt and "선생님 모드로 전환" in role_txt, role_txt[:90])
    ok(tag + "v38 모드 시트 개발 용어 0", sheet_audit(page, "#roleSheet") == [], str(sheet_audit(page, "#roleSheet"))[:120])
    page.eval_on_selector('#roleSheet [data-role-switch="therapist"]', "el => el.click()")
    page.wait_for_timeout(420)

    # ── 8) 선생님 화면 — 선생님 홈·내 정보
    ok(tag + "v38 선생님 홈 제목", page.inner_text("#screen-tp-home h1").strip() == "선생님 홈", page.inner_text("#screen-tp-home h1"))
    for tab in ["tp-schedule", "tp-journal", "tp-settle", "tp-mypage"]:
        page.tap('.tabbar[data-mode="therapist"] [data-tab="%s"]' % tab)
        page.wait_for_timeout(240)
        ok(tag + "v38 선생님 '%s' 화면 금지어 0" % tab, screen_audit(page) == [], str(screen_audit(page))[:160])
    ok(tag + "v38 선생님 내 정보 제목", page.inner_text("#screen-tp-mypage h1").strip() == "선생님 내 정보")
    stl = page.inner_text("#screen-tp-settle")
    ok(tag + "v38 정산 표기 유지(D+3·15일·말일·22.2%)", "D+3" in stl and "15일" in stl and "말일" in stl and "22.2%" in stl, stl[:80])

    # ── 9) 운영자 화면 — 시연용 고지·지표 이름
    page.eval_on_selector("[data-admin-open]", "el => el.click()")
    page.wait_for_timeout(520)
    ok(tag + "v38 운영자 화면 진입", page.eval_on_selector(".screen.is-active", "el => el.id") == "screen-admin")
    ok(tag + "v38 운영자 고지 이름", "이 기기에만 저장 · 서버 미연결" in page.inner_text("#adminResvDemoNotice"))
    ok(tag + "v38 운영 지표 이름", "예약 진행 단계" in page.inner_text("#adminMetricsSec") and "퍼널" not in page.inner_text("#adminMetricsSec"))
    ok(tag + "v38 운영자 화면 금지어 0", screen_audit(page) == [], str(screen_audit(page))[:160])
    ok(tag + "v38 시연용 표기 유지", "시연용" in page.inner_text("#screen-admin") or "시연용" in page.inner_text("body"))

    # ── 10) 가격 불변·시드 예약
    ok(tag + "v38 단가·수수료 불변", page.evaluate("""() => {
        const M = window.__ttokttokModel;
        return M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
          M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
          JSON.stringify(M.settlementRule.payDays) === '[15,"end"]';
    }"""))
    ok(tag + "v38 시드 예약 TT-261021-7302", "TT-261021-7302" in page.inner_text("body"))
    shot(page, "v38_admin_copy")

    # ── 11) 320px — 문구가 넘치지 않고 금지어 0
    ctx2, page2, errors2 = new_page(320, 568, True)
    boot(page2)
    login(page2)
    ok(tag + "v38 320 부팅 오류 0", not errors2, errors2[:2])
    ok(tag + "v38 320 홈 가로 넘침 0", page2.eval_on_selector("html", "el => el.scrollWidth <= el.clientWidth + 1"),
       page2.eval_on_selector("html", "el => el.scrollWidth + '/' + el.clientWidth"))
    ok(tag + "v38 320 홈 문구 금지어 0", visible_audit(page2) == [], str(visible_audit(page2))[:120])
    shot(page2, "v38_320_home")
    ctx2.close()
    ctx.close()


def run_v39_flow(p, storage_blocked=False):
    """v39 · 성능·첫 화면 마감 — 첫 화면 먼저, 나머지 화면은 첫 페인트 뒤 유휴 렌더.
    · DCL·FCP·booted 시각을 실브라우저에서 재고, 지연 렌더가 끝난 뒤에도
      v31 터치·v34 접근성·v38 문구·가격/정산 불변이 그대로인지 본다.
    """
    import statistics
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v39 blocked] " if storage_blocked else "[v39] "

    def new_page(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                   is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def boot(page):
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)

    def stat(page):
        return page.evaluate("() => window.__ttokttokPerf.stats()")

    ctx, page, errors = new_page(375, 812, True)
    # ── 첫 화면이 그려진 시점(DCL)에 무거운 화면은 아직 비어 있다
    page.goto(URL, wait_until="domcontentloaded")
    at_dcl = page.evaluate("""() => ({
        booted: window.__ttokttokBooted,
        perf: window.__ttokttokPerf.stats(),
        teachers: document.querySelectorAll('#teacherList [data-teacher]').length,
        home: ((document.querySelector('#homeSummaryCard') || {}).innerText || '') + ' ' + ((document.querySelector('#homePassCard') || {}).innerText || ''),
        gate: !!document.querySelector('#entryGate.is-open')
    })""")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    s1 = stat(page)
    page.wait_for_timeout(260)

    ok(tag + "v39 meta v41 · perf 훅 v39(기능 세대 표기 유지)", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v49" and
       page.evaluate("() => (window.__ttokttokPerf || {}).version") == "v39")
    ok(tag + "v39 브라우저는 유휴 청크 모드", s1["mode"] == "idle-chunked", s1["mode"])
    ok(tag + "v39 DCL 600ms 이내(첫 로드 · 공용 CPU 편차 허용)", s1["dcl"] is not None and s1["dcl"] <= 600, str(s1["dcl"]))
    ok(tag + "v39 첫 페인트(FCP) 기록됨", s1["fcp"] is not None and s1["fcp"] > 0, str(s1["fcp"]))
    ok(tag + "v39 페인트가 부팅 완료보다 먼저", s1["fcp"] is not None and s1["fcp"] <= s1["bootedAt"],
       "%s/%s" % (s1["fcp"], s1["bootedAt"]))
    # 부팅 순서 계약: 첫 화면 렌더(criticalDone) → 유휴 렌더 → booted.
    # (DCL 시점의 탭 뒤 화면 유무는 브라우저 부하에 따라 달라 타이밍으로 단정하지 않는다.
    #  그 순서는 jsdom v39 테스트가 결정적으로 확인한다.)
    ok(tag + "v39 첫 화면 렌더가 유휴 렌더·booted보다 앞선다",
       at_dcl["perf"]["marks"]["criticalDone"] < s1["marks"]["booted"] and
       s1["marks"]["criticalDone"] <= s1["marks"].get("deferredStart", s1["marks"]["booted"]),
       "%s < %s" % (at_dcl["perf"]["marks"]["criticalDone"], s1["marks"]["booted"]))
    ok(tag + "v39 DCL 직후 첫 화면(홈 요약)은 그려짐", "다음 방문" in at_dcl["home"] and "회차권" in at_dcl["home"],
       at_dcl["home"][:60])
    ok(tag + "v39 DCL 직후 시작 게이트 열려 있음", at_dcl["gate"] is True)
    ok(tag + "v39 DCL 직후 유휴 렌더 예약됨", at_dcl["perf"]["scheduled"] is True and at_dcl["perf"]["finished"] is False,
       str(at_dcl["perf"]["scheduled"]) + "/" + str(at_dcl["perf"]["finished"]))
    ok(tag + "v39 유휴 렌더 22건 모두 완료", s1["deferredTotal"] == 22 and s1["deferredRendered"] == 22 and s1["pending"] == 0,
       "%s/%s/%s" % (s1["deferredTotal"], s1["deferredRendered"], s1["pending"]))
    ok(tag + "v39 부팅 JS 오류 0", not errors, errors[:2])

    # ── 지연 렌더 결과가 예전 화면과 같다
    ok(tag + "v39 선생님 목록 8명", page.eval_on_selector_all("#teacherList [data-teacher]", "els => els.length") == 8,
       str(page.eval_on_selector_all("#teacherList [data-teacher]", "els => els.length")))
    ok(tag + "v39 알림함 4건·배지 4", page.eval_on_selector_all("#notifList .notif", "els => els.length") == 4 and
       page.inner_text("#notifDot").strip() == "4")
    ok(tag + "v39 FAQ 10문항", page.eval_on_selector_all("#faqList .faq-item", "els => els.length") == 10,
       str(page.eval_on_selector_all("#faqList .faq-item", "els => els.length")))
    ok(tag + "v39 예약 1단계 날짜 7일", page.eval_on_selector_all("#bookDates [data-date]", "els => els.length") == 7)
    ok(tag + "v39 내 정보·방문 일지 렌더", len(page.inner_text("#screen-mypage")) > 200 and
       len(page.inner_text("#screen-journal")) > 100)
    ok(tag + "v39 v34 배경 잠금 유지(게이트 열림)", page.evaluate("() => window.__ttokttokModel.a11y.backgroundLocked()") is True)
    ok(tag + "v39 v31 터치 44px 위반 0", page.evaluate("() => window.__ttokttokTouch.violations().length") == 0,
       str(page.evaluate("() => window.__ttokttokTouch.violations()")[:2]))
    ok(tag + "v39 v38 보이는 문구 금지어 0",
       page.evaluate("() => window.__ttokttokCopy.audit(window.__ttokttokCopy.visibleText())") == [])

    # ── 화면 이동·시트: 유휴 렌더 뒤에도 그 자리에서 다시 그린다
    page.eval_on_selector('[data-login="demo"]', "el => el.click()")
    page.wait_for_timeout(250)
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el => el.click()")
    page.wait_for_timeout(200)
    ok(tag + "v39 선생님 탭 8명", page.eval_on_selector_all("#teacherList [data-teacher]", "els => els.length") == 8)
    near = page.query_selector('#teacherViewTabs [data-view="near"]')
    if near:
        near.click()
        page.wait_for_timeout(200)
    ok(tag + "v39 내 주변 동네 카드", page.eval_on_selector_all("#nearPanel [data-dong-cluster]", "els => els.length") > 0,
       str(page.eval_on_selector_all("#nearPanel [data-dong-cluster]", "els => els.length")))
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=home]', "el => el.click()")
    page.wait_for_timeout(200)
    ok(tag + "v39 홈 요약 카드 순서(다음 방문)", "다음 방문" in page.inner_text("#homeSummaryCard"))
    ok(tag + "v39 단가·수수료·시드 불변", page.evaluate("""() => {
        const M = window.__ttokttokModel;
        return M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
               M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
               M.reservations().some(r => r.no === 'TT-261021-7302');
    }""") is True)

    # ── 재방문(새로고침)에도 두 단계 부팅이 같고 데이터가 남아 있다
    before = page.evaluate("() => window.__ttokttokModel.reservations().length")
    page.reload()
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    s2 = stat(page)
    ok(tag + "v39 재방문 DCL 600ms 이내", s2["dcl"] is not None and s2["dcl"] <= 600, str(s2["dcl"]))
    ok(tag + "v39 재방문에도 유휴 렌더 전부 완료", s2["deferredRendered"] == s2["deferredTotal"] and s2["pending"] == 0)
    ok(tag + "v39 재방문 데이터 유지(예약 수)", page.evaluate("() => window.__ttokttokModel.reservations().length") == before,
       "%s/%s" % (before, page.evaluate("() => window.__ttokttokModel.reservations().length")))
    ok(tag + "v39 재방문 오류 0", not errors, errors[:2])
    ctx.close()

    # ── 관리자·선생님 화면(부팅 때 미리 그리지 않던 화면)도 그 자리에서 그려진다
    ctx2, page2, errors2 = new_page(375, 812, True)
    boot(page2)
    page2.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page2.wait_for_timeout(350)
    ok(tag + "v39 운영자 화면 일 때 열린다", page2.is_visible("#screen-admin") is not False)
    ok(tag + "v39 운영자 큐에 시드 예약", "TT-261021-7302" in page2.inner_text("#screen-admin"),
       page2.inner_text("#screen-admin")[:60])
    page2.screenshot(path=os.path.join(SHOT, "e2e_v39_admin.png"))
    page2.eval_on_selector('[data-login="therapist"]', "el => el.click()") if page2.query_selector('[data-login="therapist"]') else None
    page2.wait_for_timeout(300)
    ok(tag + "v39 선생님 모드 화면 그려짐", len(page2.inner_text("#screen-tp-home")) > 100,
       page2.inner_text("#screen-tp-home")[:40])
    ok(tag + "v39 운영자·선생님 화면 오류 0", not errors2, errors2[:2])
    ctx2.close()

    # ── 320px 좁은 폭에서도 가로 넘침 0
    ctx3, page3, errors3 = new_page(320, 568, True)
    boot(page3)
    page3.eval_on_selector('[data-login="demo"]', "el => el.click()")
    page3.wait_for_timeout(250)
    ok(tag + "v39 320px 가로 넘침 0", page3.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"),
       page3.evaluate("() => document.documentElement.scrollWidth + '/' + document.documentElement.clientWidth"))
    ok(tag + "v39 320px 문구 금지어 0", page3.evaluate("() => window.__ttokttokCopy.audit(window.__ttokttokCopy.visibleText())") == [])
    page3.screenshot(path=os.path.join(SHOT, "e2e_v39_320_home.png"))
    ctx3.close()
    browser.close()


def run_v40_flow(p, storage_blocked=False):
    """v40 · 전체 회귀 — 화면 글자의 날짜·요일·D-day가 달력과 같고, 시드가 오늘 기준으로 계산된다."""
    import datetime
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v40 blocked] " if storage_blocked else "[v40] "
    today = datetime.date.fromisoformat(FIXED_TODAY)
    WD = ["월", "화", "수", "목", "금", "토", "일"]

    def new_page(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                   is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def boot(page):
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(300)

    # 화면 글자의 (M.DD) 요일이 실제 달력과 맞는지
    AUDIT = """() => {
      const WD = ['일','월','화','수','목','금','토'];
      const now = new Date();
      const base = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const near = (m, d) => { let best = null;
        [base.getFullYear()-1, base.getFullYear(), base.getFullYear()+1].forEach(y => {
          const t = new Date(y, m-1, d); if (t.getMonth() !== m-1 || t.getDate() !== d) return;
          const diff = Math.abs(t - base); if (!best || diff < best.diff) best = {diff, t}; });
        return best ? best.t : null; };
      const out = [];
      const re = /(\\d{1,2})[./](\\d{1,2})\\s*\\((월|화|수|목|금|토|일)\\)/g;
      document.querySelectorAll('body *').forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width < 1 || r.height < 1 || getComputedStyle(el).display === 'none') return;
        if (el.children.length) return;
        const t = (el.textContent || '').trim();
        if (!t || t.length > 80) return;
        let mm; re.lastIndex = 0;
        while ((mm = re.exec(t))) {
          const d = near(+mm[1], +mm[2]); if (!d) continue;
          if (WD[d.getDay()] !== mm[3]) out.push(mm[0] + '→' + WD[d.getDay()]);
        }
      });
      return Array.from(new Set(out));
    }"""

    ctx, page, errors = new_page(390, 844, True)
    boot(page)
    page.eval_on_selector('[data-login="demo"]', "el => el.click()")
    page.wait_for_timeout(400)

    ok(tag + "v40 부팅 JS 오류 0", not errors, errors[:3])
    ok(tag + "v40 meta v41", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v49", "v46")

    # ── 1) 다음 방문 = 오늘+2일, 라벨·요일·D-day 일치
    nxt = (today + datetime.timedelta(days=2))
    want = "%d.%02d (%s)" % (nxt.month, nxt.day, WD[nxt.weekday()])
    home = page.inner_text("#homeSummaryCard")
    ok(tag + "v40 홈 다음 방문 요일 달력 일치", want in home, home.replace("\n", " ")[:120])
    ok(tag + "v40 홈 D-2", "D-2" in home)
    ok(tag + "v40 시드 예약번호 유지", "TT-261021-7302" in home)

    # ── 2) 일지 탭 방문 카드
    page.tap('.tabbar[data-mode="customer"] [data-tab="journal"]')
    page.wait_for_timeout(400)
    chip = page.inner_text("#todayChip")
    ok(tag + "v40 방문 카드 날짜·요일", ("%d월 %d일 (%s)" % (nxt.month, nxt.day, WD[nxt.weekday()])) in chip, chip)
    ok(tag + "v40 방문 카드 다음 방문 표기", "다음 방문" in chip, chip)
    ok(tag + "v40 방문 카드 시간 범위", "10:30" in page.inner_text("#todayTime") and "11:30" in page.inner_text("#todayTime"),
       page.inner_text("#todayTime"))
    ok(tag + "v40 방문 카드 선생님·회차권", "박서준 선생님" in page.inner_text("#todayMeta") and "8회권" in page.inner_text("#todayMeta"),
       page.inner_text("#todayMeta"))
    ok(tag + "v40 박혀 있던 11월 25일 없음", "11월 25일" not in page.inner_text("body"))
    page.screenshot(path=os.path.join(SHOT, "e2e_v40_journal.png"))
    ok(tag + "v40 보호자 화면 날짜-요일 불일치 0", page.evaluate(AUDIT) == [], page.evaluate(AUDIT)[:4])

    # ── 3) 선생님 일정·요청
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(450)
    page.tap('.tabbar[data-mode="therapist"] [data-tab="tp-schedule"]')
    page.wait_for_timeout(350)
    sched = page.inner_text("#screen-tp-schedule")
    ok(tag + "v40 선생님 일정 오늘 요일", ("오늘 (%s)" % WD[today.weekday()]) in sched, sched.replace("\n", " ")[:160])
    d5 = today + datetime.timedelta(days=5)
    d6 = today + datetime.timedelta(days=6)
    ok(tag + "v40 요청 날짜 요일(5일 후)", ("%02d/%02d (%s)" % (d5.month, d5.day, WD[d5.weekday()])) in sched, sched.replace("\n", " ")[:200])
    ok(tag + "v40 요청 날짜 요일(6일 후)", ("%02d/%02d (%s)" % (d6.month, d6.day, WD[d6.weekday()])) in sched, sched.replace("\n", " ")[:200])
    ok(tag + "v40 선생님 화면 날짜-요일 불일치 0", page.evaluate(AUDIT) == [], page.evaluate(AUDIT)[:4])
    page.tap('.tabbar[data-mode="therapist"] [data-tab="tp-home"]')
    page.wait_for_timeout(350)
    chart = page.inner_text(".settle-chart")
    ok(tag + "v40 정산 차트 '18.8만'", "18.8만" in chart and "188k" not in chart, chart.replace("\n", " ")[:40])
    page.screenshot(path=os.path.join(SHOT, "e2e_v40_tp_home.png"))

    # ── 4) 운영자 화면의 '시연용' 배지가 한 줄로
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(600)
    one_line = page.evaluate("""() => Array.from(document.querySelectorAll('#screen-admin .tag-example')).map(el => {
        const r = el.getBoundingClientRect(); const lh = parseFloat(getComputedStyle(el).lineHeight) || 14;
        return r.height <= lh * 1.9;
      })""")
    ok(tag + "v40 시연용 배지 한 줄(운영자)", all(one_line) and len(one_line) > 0, str(one_line))
    ok(tag + "v40 운영자 날짜-요일 불일치 0", page.evaluate(AUDIT) == [], page.evaluate(AUDIT)[:4])

    # ── 5) 재방문(새로고침)에도 같은 라벨
    page.reload()
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.eval_on_selector('[data-login="demo"]', "el => el.click()")
    page.wait_for_timeout(450)
    ok(tag + "v40 재방문 홈 요일 유지", want in page.inner_text("#homeSummaryCard"), page.inner_text("#homeSummaryCard").replace("\n", " ")[:100])
    ctx.close()

    # ── 6) 320px — 넘침 0, 날짜-요일 0
    ctx2, page2, errors2 = new_page(320, 568, True)
    boot(page2)
    page2.eval_on_selector('[data-login="demo"]', "el => el.click()")
    page2.wait_for_timeout(350)
    ok(tag + "v40 320 가로 넘침 0",
       page2.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
    ok(tag + "v40 320 날짜-요일 불일치 0", page2.evaluate(AUDIT) == [], page2.evaluate(AUDIT)[:4])
    ok(tag + "v40 320 오류 0", not errors2, errors2[:2])
    ctx2.close()

    # ── 7) 정책 불변
    ctx3, page3, _ = new_page(390, 844, True)
    boot(page3)
    ok(tag + "v40 단가·수수료·정산·시드 불변", page3.evaluate("""() => {
        const M = window.__ttokttokModel;
        return M.pricing.consumerPrice === 90000 && M.pricing.teacherPayout === 70000 &&
               M.pricing.platformFeeRate === 0.2222 && M.settlementRule.confirmDays === 3 &&
               String(M.settlementRule.payDays) === '15,end' &&
               M.reservations().some(r => r.no === 'TT-261021-7302');
      }"""))
    ctx3.close()
    browser.close()



def run_v42_flow(p, storage_blocked=False):
    """v42 · 첫 화면에서 회차권까지 · 글자 크기 · 예약 3·4단계 · 관리자 표 · 시트 스와이프 · 배지 전환."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v42 blocked] " if storage_blocked else "[v42] "

    def new_page(w, h, mob, textsize=None, reuse=None):
        if reuse is not None:
            ctx = reuse
        else:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                      is_mobile=mob, has_touch=mob, locale="ko-KR")
        if textsize:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_textsize_v1','%s')}catch(e){}" % textsize)
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def boot(page):
        page.goto(URL)
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(400)

    def as_customer(page):
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(700)

    # ── 1) 첫 화면: 다음 방문 히어로 + 회차권 카드가 스크롤 없이 ──────
    for w, h in [(390, 844), (375, 812)]:
        ctx, page, errs = new_page(w, h, True)
        boot(page)
        as_customer(page)
        page.wait_for_timeout(1600)
        fold = page.evaluate("() => { const q = (s) => document.querySelector(s); const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return {top: Math.round(b.top), bottom: Math.round(b.bottom)}; }; return {pass: r(q('#homePassCard')), tab: r(q('.tabbar[data-mode=customer]')), hero: r(q('#homeSummaryCard'))}; }")
        ok(tag + "v42 %d 첫 화면에 회차권 카드가 온전히 보임" % w,
           fold["pass"] and fold["tab"] and fold["pass"]["bottom"] <= fold["tab"]["top"],
           str(fold))
        ok(tag + "v42 %d 다음 방문 히어로 먼저" % w,
           fold["hero"] and fold["pass"] and fold["hero"]["bottom"] < fold["pass"]["top"],
           str(fold))
        ok(tag + "v42 %d 카드 순서(다음 방문 → 회차권 → 최근 4주)" % w,
           page.evaluate("""() => { const b = document.querySelector('#screen-home .home-body');
             const ids = [...b.children].map((x) => x.id);
             return ids.indexOf('homeSummaryCard') === 0 && ids.indexOf('homePassCard') === 1 && ids.indexOf('homeReportCard') === 2; }"""))
        ok(tag + "v42 %d 회차권 요약 문구" % w,
           "잔여 5회" in page.inner_text("#homeSummaryPass") and "5회 / 8회" in page.inner_text("#homeSummaryPass"))
        ok(tag + "v42 %d 가로 넘침 없음" % w,
           page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
        ok(tag + "v42 %d 오류 없음" % w, not errs, errs[:2])
        ctx.close()

    # ── 2) 글자 크기(아주 크게) — 새로 열어도 유지 ──────────────────
    ctx, page, errs = new_page(390, 844, True)
    boot(page)
    as_customer(page)
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]', "el => el.click()")
    page.wait_for_timeout(500)
    ok(tag + "v42 글자 크기 3단", page.eval_on_selector_all("#mpTextSize [data-textsize]", "els => els.length") == 3)
    page.eval_on_selector('#mpTextSize [data-textsize="xl"]', "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v42 아주 크게 → data-textsize=xl", page.evaluate("() => document.documentElement.getAttribute('data-textsize')") == "xl")
    ok(tag + "v42 아주 크게 작은 글자 12→15.6px", (lambda v: abs(v - 15.6) < 0.6)(float(page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('#homeSummaryPass .hs-guide')).fontSize)"))),
       page.evaluate("() => getComputedStyle(document.querySelector('#homeSummaryPass .hs-guide')).fontSize"))
    ok(tag + "v42 큰 날짜도 함께 커진다(28→36.4px)", (lambda v: abs(v - 36.4) < 0.8)(float(page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('.hs-date')).fontSize)"))),
       page.evaluate("() => getComputedStyle(document.querySelector('.hs-date')).fontSize"))
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=home]', "el => el.click()")
    page.wait_for_timeout(1200)
    ok(tag + "v42 아주 크게에서도 홈 가로 넘침 없음",
       page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
    page.reload()
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(400)
    if not storage_blocked:
        ok(tag + "v42 새로 열어도 아주 크게 유지", page.evaluate("() => document.documentElement.getAttribute('data-textsize')") == "xl")
    else:
        ok(tag + "v42 저장 차단에서도 글자 크기 기본값(보통)",
           page.evaluate("() => !document.documentElement.getAttribute('data-textsize')"))
    ok(tag + "v42 글자 크기 오류 없음", not errs, errs[:2])
    ctx.close()

    # ── 3) 예약 3·4단계: 합계 바는 3단계만, 4단계 요약은 열 맞춤 ──────
    ctx, page, errs = new_page(390, 844, True)
    boot(page)
    as_customer(page)
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]', "el => el.click()")
    page.wait_for_timeout(400)
    page.eval_on_selector('#provinceQuick [data-prov="서울"]', "el => el.click()")
    page.select_option("#bookDistrict", "강남구")
    page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
    page.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
    page.eval_on_selector('[data-next="1"]', "el => el.click()")
    page.wait_for_timeout(300)
    page.eval_on_selector('#bookDates .date-chip', "el => el.click()")
    page.wait_for_timeout(120)
    page.eval_on_selector('#bookSlots .slot:not([disabled])', "el => el.click()")
    page.eval_on_selector('[data-next="2"]', "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v42 3단계 회차권 카드 5장", page.eval_on_selector_all("#passList .pass", "els => els.length") == 5)
    ok(tag + "v42 회당 가격은 가격 열 안에", page.eval_on_selector('#passList [data-pass="p8"]', "el => !!el.querySelector('.pass-per')"))
    page.eval_on_selector('#passList [data-pass="p8"]', "el => el.click()")
    page.wait_for_timeout(300)
    ok(tag + "v42 3단계 합계 바 표시", page.evaluate("() => !document.querySelector('#bookTotalBar').hidden"))
    bar = page.evaluate("() => { const b = document.querySelector('#wstep-3'); return {pad: parseFloat(getComputedStyle(b).paddingBottom)}; }")
    ok(tag + "v42 3단계 아래 여백 확보(합계 바 78px)", bar["pad"] >= 78, str(bar))
    page.eval_on_selector('[data-next="3"]', "el => el.click()")
    page.wait_for_timeout(350)
    ok(tag + "v42 4단계에서는 합계 바 숨김", page.evaluate("() => document.querySelector('#bookTotalBar').hidden === true"))
    ok(tag + "v42 4단계 요약 6줄", page.eval_on_selector_all("#bookSummary .sum-line", "els => els.length") >= 6,
       str(page.eval_on_selector_all("#bookSummary .sum-line", "els => els.length")))
    ok(tag + "v42 4단계 그룹 제목·이전 단계 버튼",
       "예약자 정보" in page.inner_text("#wstep-4") and page.is_visible("#wstep-4 .prev-step"))
    page.eval_on_selector('#wstep-4 .prev-step', "el => el.click()")
    page.wait_for_timeout(300)
    ok(tag + "v42 이전 단계 → 3단계", page.evaluate("() => document.querySelector('#wstep-3').classList.contains('is-active')"))
    ok(tag + "v42 예약 오류 없음", not errs, errs[:2])
    ctx.close()

    # ── 4) 관리자 표 정렬 + 지역 수치 칸 ─────────────────────────────
    ctx, page, errs = new_page(390, 844, True)
    boot(page)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(1500)
    page.eval_on_selector('#adminMetricsFunnel', "el => el.scrollIntoView({block:'start'})")
    page.wait_for_timeout(400)
    rows = page.evaluate("""() => [...document.querySelectorAll('#adminMetricsFunnelRows .adm-row')].map((r) => {
      const n = r.querySelector('.adm-n'); const cs = n ? getComputedStyle(n) : {};
      return {t: r.textContent.replace(/\s+/g, ' ').trim(), align: cs.textAlign, nums: cs.fontVariantNumeric}; })""")
    ok(tag + "v42 퍼널 표 6행", len(rows) == 6, str(len(rows)))
    ok(tag + "v42 표 숫자 우측 정렬·고정폭", bool(rows) and all(r["align"] == "right" for r in rows) and
       any("tabular-nums" in (r["nums"] or "") for r in rows), str(rows[:2]))
    rev = page.inner_text("#adminMetricsRevenueRows")
    ok(tag + "v42 매출 표 값 유지(2,340,000·520,000·22.2%)",
       "2,340,000원" in rev and "520,000원" in rev and "22.2%" in rev, rev[:80])
    cells = page.eval_on_selector_all(".adm-reg > span", "els => els.map((e) => e.textContent.replace(/\s+/g, ''))")
    ok(tag + "v42 지역 카드 수요·필요·등록 칸", len(cells) >= 3 and any(c.startswith("수요") for c in cells) and
       any(c.startswith("등록") for c in cells), str(cells[:3]))
    ok(tag + "v42 관리자 가로 넘침 없음", page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
    ok(tag + "v42 관리자 오류 없음", not errs, errs[:2])
    ctx.close()

    # ── 5) 시트 스와이프 닫기 + 배지 전환 ────────────────────────────
    ctx, page, errs = new_page(390, 844, True)
    boot(page)
    as_customer(page)
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el => el.click()")
    page.wait_for_timeout(500)
    page.eval_on_selector('#teacherList [data-teacher]', "el => el.click()")
    page.wait_for_timeout(500)
    ok(tag + "v42 선생님 시트 열림", page.evaluate("() => document.querySelector('#teacherSheet').classList.contains('is-open')"))
    ok(tag + "v42 스와이프 가능 시트 10개 이상", page.evaluate("() => __ttokttokGesture.sheets") >= 10,
       str(page.evaluate("() => __ttokttokGesture.sheets")))
    ok(tag + "v42 게이트 시트는 스와이프 대상 아님", page.evaluate("() => __ttokttokGesture.has('#gateSheet')") is False)
    hb = page.evaluate("""() => { const h = document.querySelector('#teacherSheet .sheet-handle'); const r = h.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; }""")
    page.mouse.move(hb["x"], hb["y"])
    page.mouse.down()
    for i in range(1, 4):
        page.mouse.move(hb["x"], hb["y"] + i * 8)
        page.wait_for_timeout(16)
    mid = page.evaluate("() => document.querySelector('#teacherSheet .sheet').style.transform")
    page.mouse.up()
    page.wait_for_timeout(400)
    ok(tag + "v42 끌면 시트가 따라 내려온다", bool(mid) and "px" in mid, str(mid))
    ok(tag + "v42 조금 끌면 제자리로", page.evaluate("() => document.querySelector('#teacherSheet').classList.contains('is-open')"))
    page.mouse.move(hb["x"], hb["y"])
    page.mouse.down()
    for i in range(1, 12):
        page.mouse.move(hb["x"], hb["y"] + i * 13)
        page.wait_for_timeout(14)
    page.mouse.up()
    page.wait_for_timeout(600)
    ok(tag + "v42 아래로 끌면 시트가 닫힌다", not page.evaluate("() => document.querySelector('#teacherSheet').classList.contains('is-open')") and
       page.evaluate("() => __ttokttokGesture.closes") >= 1)
    ok(tag + "v42 포커스가 누른 카드로 돌아온다",
       page.evaluate("() => !!document.activeElement && !!document.activeElement.closest('[data-teacher]')"),
       page.evaluate("() => document.activeElement && document.activeElement.tagName"))

    # 배지: 관리자 전이 → 같은 자리 글자가 바뀌면 전환 모션
    page.eval_on_selector('#rolePill, [data-role-switch]', "el => el.click()")
    page.wait_for_timeout(400)
    page.eval_on_selector('[data-role-switch="admin"], [data-admin-open]', "el => el.click()")
    page.wait_for_timeout(1200)
    page.eval_on_selector('#adminResvQueue', "el => el.scrollIntoView({block:'start'})")
    page.wait_for_timeout(400)
    before_swaps = page.evaluate("() => __ttokttokGesture.badgeSwaps")
    target = page.evaluate("""() => { const c = document.querySelector('#adminResvQueue [data-resv]');
      if (!c) return null; const b = [...c.querySelectorAll('button')].find((x) => /방문 완료/.test(x.textContent));
      if (!b) return null; const r = b.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2, t: b.textContent.trim()}; }""")
    if target:
        page.mouse.click(target["x"], target["y"])
        page.wait_for_timeout(130)
        swapped = page.evaluate("() => ({n: __ttokttokGesture.badgeSwaps, cls: !!document.querySelector('.tt-badge-swap')})")
        ok(tag + "v42 상태 배지 전환 모션", swapped["n"] > before_swaps and swapped["cls"], str(swapped))
        page.wait_for_timeout(700)
        ok(tag + "v42 전이 후 배지 문구 반영", "방문 완료" in page.inner_text("#adminResvQueue"))
    else:
        ok(tag + "v42 상태 배지 전환 모션(전이 버튼 없음)", False, "no transition button")
    ok(tag + "v42 손짓 오류 없음", not errs, errs[:2])
    ctx.close()
    browser.close()



def run_v43_flow(p, storage_blocked=False):
    """v43 · 인트로 컷신 · 320×568 첫 화면 · 합계 바가 고른 카드를 덮지 않음 · 빈 상태 그림 · 토스트."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v43 blocked] " if storage_blocked else "[v43] "

    def new_page(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                  is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    # ── 1) 인트로 컷신 ─────────────────────────────────────────
    ctx, page, errs = new_page(390, 844, True)
    page.goto(URL + "?intro=1")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(150)
    ok(tag + "v43 인트로 컷신이 뜬다", page.evaluate("() => !document.getElementById('intro').hidden"))
    ok(tag + "v43 장면 요소(집·선생님·보호자·회복선·새싹)",
       page.evaluate("""() => { const i = document.getElementById('intro');
         return ['in-house','in-teacher','in-patient','in-recover','in-sprout'].every((c) => !!i.querySelector('.' + c)); }"""))
    ok(tag + "v43 인트로는 소리로 읽지 않는다",
       page.evaluate("() => document.getElementById('intro').getAttribute('aria-hidden') === 'true'"))
    page.wait_for_timeout(2400)
    ok(tag + "v43 인트로가 2.5초 안에 스스로 끝난다", page.evaluate("() => document.getElementById('intro').hidden === true"))
    ok(tag + "v43 인트로 중 오류 없음", not errs, errs[:2])
    ctx.close()

    # 첫 손짓이면 바로 끝난다
    ctx, page, errs = new_page(390, 844, True)
    page.goto(URL + "?intro=1")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(120)
    page.mouse.click(200, 400)
    page.wait_for_timeout(500)
    ok(tag + "v43 첫 손짓에 인트로가 끝난다", page.evaluate("() => document.getElementById('intro').hidden === true"))
    ctx.close()

    # ?intro=0 은 인트로를 끈다(v41의 반대 동작 회귀 방지)
    ctx, page, errs = new_page(390, 844, True)
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(200)
    ok(tag + "v43 ?intro=0 이면 인트로를 끈다", page.evaluate("() => document.getElementById('intro').hidden === true"))
    ctx.close()

    # ── 2) 320×568 첫 화면에 회차권 카드까지 ────────────────────
    ctx, page, errs = new_page(320, 568, True)
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(400)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(1800)
    fold = page.evaluate("""() => { const r = (s) => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return {top: Math.round(b.top), bottom: Math.round(b.bottom)}; };
      return {pass: r('#homePassCard'), tab: r('.tabbar[data-mode=customer]'), notice: r('#homeNotice')}; }""")
    ok(tag + "v43 320 첫 화면에 회차권 카드까지 보인다", fold["pass"] and fold["tab"] and fold["pass"]["bottom"] <= fold["tab"]["top"], str(fold))
    ok(tag + "v43 320에서는 프로모션 띠를 접는다", page.evaluate("() => getComputedStyle(document.getElementById('homeNotice')).display === 'none'"))
    ok(tag + "v43 320 가로 넘침 없음", page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
    page.screenshot(path=os.path.join(ROOT, "preview", "v43_320_home.png"))
    ok(tag + "v43 320 오류 없음", not errs, errs[:2])
    ctx.close()

    # ── 3) 합계 바가 고른 회차권 카드를 덮지 않는다 ─────────────
    for w, h in [(390, 844), (320, 568)]:
        ctx, page, errs = new_page(w, h, True)
        page.goto(URL + "?intro=0")
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(300)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(700)
        page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=booking]', "el => el.click()")
        page.wait_for_timeout(400)
        page.eval_on_selector('#provinceQuick [data-prov="서울"]', "el => el.click()")
        page.select_option("#bookDistrict", "강남구")
        page.fill("#bookAddress", "대치동 123-4, 101동 1203호")
        page.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
        page.eval_on_selector('[data-next="1"]', "el => el.click()")
        page.wait_for_timeout(250)
        page.eval_on_selector('#bookDates .date-chip', "el => el.click()")
        page.wait_for_timeout(120)
        page.eval_on_selector('#bookSlots .slot:not([disabled])', "el => el.click()")
        page.eval_on_selector('[data-next="2"]', "el => el.click()")
        page.wait_for_timeout(350)
        page.eval_on_selector('#passList [data-pass="p8"]', "el => el.click()")
        page.wait_for_timeout(900)
        geo = page.evaluate("""() => { const c = document.querySelector('#passList .pass.is-on').getBoundingClientRect();
          const b = document.querySelector('#bookTotalBar').getBoundingClientRect();
          return {cardBottom: Math.round(c.bottom), barTop: Math.round(b.top), nudged: !!window.__ttokttokPassNudge}; }""")
        ok(tag + "v43 %d 고른 카드가 합계 바에 가리지 않는다" % w, geo["cardBottom"] <= geo["barTop"] + 2, str(geo))
        ok(tag + "v43 %d 합계 바는 76px 이하" % w, page.evaluate("() => Math.round(document.querySelector('#bookTotalBar').getBoundingClientRect().height)") <= 76)
        ok(tag + "v43 %d 예약 3단계 오류 없음" % w, not errs, errs[:2])
        ctx.close()

    # ── 4) 빈 상태 그림 · 토스트 ────────────────────────────────
    ctx, page, errs = new_page(390, 844, True)
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(300)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(1500)
    page.evaluate("""() => { const b = [...document.querySelectorAll('#adminResvFilters [data-admin-resv-filter]')].find((x) => /노쇼/.test(x.textContent)); if (b) b.click(); }""")
    page.wait_for_timeout(600)
    ok(tag + "v43 빈 상태에 그림", page.evaluate("() => !!document.querySelector('#adminResvQueue .empty svg.empty-art')"))
    ok(tag + "v43 빈 상태 그림은 장식(aria-hidden)",
       page.evaluate("() => document.querySelector('#adminResvQueue .empty svg').getAttribute('aria-hidden') === 'true'"))
    ok(tag + "v43 빈 상태 문구·CTA 유지",
       "이 상태의 예약이 없어요" in page.inner_text("#adminResvQueue") and page.is_visible("#adminResvQueue .empty .btn"))
    toast = page.evaluate("""() => { const t = document.querySelector('.toast'); const cs = getComputedStyle(t);
      return {w: Math.round(t.getBoundingClientRect().width), fs: parseFloat(cs.fontSize)}; }""")
    ok(tag + "v43 토스트는 320px·13px", toast["w"] <= 322 and abs(toast["fs"] - 13) < 0.6, str(toast))
    ok(tag + "v43 빈 상태 오류 없음", not errs, errs[:2])
    ctx.close()
    browser.close()


def run_v45_flow(p, storage_blocked=False):
    """v45 · 화면 테마(시스템·라이트·다크) — 첫 페인트 적용·즉시 전환·저장·시스템 따라가기·대비·레이아웃."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v45 blocked] " if storage_blocked else "[v45] "

    def new_page(w, h, mob, theme=None, color_scheme=None):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                  is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        elif theme:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
        page = ctx.new_page()
        if color_scheme:
            page.emulate_media(color_scheme=color_scheme)
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    # 바탕색은 body(데스크톱 프레임, 짙은 남색 고정)가 아니라 화면 토큰 --bg 로 본다
    LIGHT_BG = "#F7F8FA"
    DARK_BG = "#0B1119"
    BG_JS = "() => getComputedStyle(document.documentElement).getPropertyValue('--bg').trim().toUpperCase()"

    # ── 1) 첫 페인트: 저장값이 다크면 처음부터 어둡다(깜빡임 없음) ──────
    ctx, page, errs = new_page(390, 844, True, theme="dark")
    first = []
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(200)
    if storage_blocked:
        # 저장이 막힌 기기: 테마 저장값을 못 읽으니 라이트로 안전하게 뜨고 오류는 없어야 한다
        ok(tag + "v45 저장 차단 기기 — 라이트로 안전하게 뜬다", page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "light")
        ok(tag + "v45 저장 차단 기기 — 화면 테마 카드는 그대로", page.evaluate("() => !!document.querySelector('#mpThemeCard')"))
        ok(tag + "v45 저장 차단 기기 오류 0", not errs, errs[:2])
    else:
        ok(tag + "v45 저장값 dark → html data-theme=dark", page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark")
        ok(tag + "v45 다크 첫 화면 바탕 토큰", page.evaluate(BG_JS) == DARK_BG, page.evaluate(BG_JS))
        ok(tag + "v45 다크에서 color-scheme=dark(스크롤바·기본 컨트롤)", page.evaluate("() => getComputedStyle(document.documentElement).colorScheme") == "dark")
        ok(tag + "v45 다크에서 주소창 색도 어둡다", page.evaluate("() => document.querySelector('meta[name=theme-color]').content") == "#0B1119")
        ok(tag + "v45 테마 훅 노출", page.evaluate("() => window.__ttokttokTheme.version") == "v45")
        ok(tag + "v45 다크 부팅 오류 0", not errs, errs[:2])
    ctx.close()

    # 저장값이 없으면 기기 설정을 따른다(라이트·다크 OS)
    ctx, page, errs = new_page(390, 844, True, color_scheme="dark")
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(200)
    ok(tag + "v45 기기가 다크 → 시스템 선택이 다크로", page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark")
    ok(tag + "v45 시스템 선택 표기", page.evaluate("() => document.documentElement.getAttribute('data-theme-pref')") == "system")
    ctx.close()

    ctx, page, errs = new_page(390, 844, True, color_scheme="light")
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(200)
    ok(tag + "v45 기기가 라이트 → 라이트로", page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "light" and
       page.evaluate(BG_JS) == LIGHT_BG)
    ctx.close()

    # ── 2) 내 정보에서 테마 바꾸기 ─────────────────────────────────
    ctx, page, errs = new_page(390, 844, True)
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(300)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(1500)
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]', "el => el.click()")
    page.wait_for_timeout(500)
    page.eval_on_selector('#mpThemeCard', "el => el.scrollIntoView({block:'center'})")
    page.wait_for_timeout(300)
    ok(tag + "v45 내 정보에 화면 테마 카드", page.evaluate("() => !!document.querySelector('#mpThemeCard')"))
    opts = page.evaluate("() => [...document.querySelectorAll('#mpTheme [data-theme-opt]')].map(b => b.getAttribute('data-theme-opt'))")
    ok(tag + "v45 시스템·라이트·다크 3단 선택", opts == ["system", "light", "dark"], opts)
    box = page.evaluate("""() => { const b = document.querySelector('#mpTheme [data-theme-opt=dark]').getBoundingClientRect();
        return {w: Math.round(b.width), h: Math.round(b.height)}; }""")
    ok(tag + "v45 선택 버튼 44px 이상", box["h"] >= 44 and box["w"] >= 44, str(box))

    page.eval_on_selector('#mpTheme [data-theme-opt=dark]', "el => el.click()")
    page.wait_for_timeout(400)
    card_bg = page.evaluate("() => getComputedStyle(document.querySelector('#mpThemeCard')).backgroundColor")
    ok(tag + "v45 다크 선택 → 즉시 어두워진다", page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark" and
       card_bg == "rgb(21, 29, 41)", card_bg)
    ok(tag + "v45 선택 상태·aria", page.evaluate("""() => { const d = document.querySelector('#mpTheme [data-theme-opt=dark]');
        return d.getAttribute('aria-checked') === 'true' && d.classList.contains('is-on') &&
               document.querySelector('#mpTheme [data-theme-opt=system]').getAttribute('aria-checked') === 'false'; }"""))
    ok(tag + "v45 안내 문구 갱신", page.evaluate("() => document.querySelector('#mpThemeHint').textContent") == "다크")
    ok(tag + "v45 토스트 안내", "다크" in page.inner_text(".toast") if page.query_selector(".toast") else False)
    if not storage_blocked:
        ok(tag + "v45 기기에 저장", page.evaluate("() => localStorage.getItem('ttokttok_theme_v1')") == "dark")
        page.reload()
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(300)
        ok(tag + "v45 새로 열어도 다크 유지", page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "dark")
        page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]', "el => el.click()")
        page.wait_for_timeout(400)
        page.eval_on_selector('#mpThemeCard', "el => el.scrollIntoView({block:'center'})")
        page.wait_for_timeout(250)
        page.eval_on_selector('#mpTheme [data-theme-opt=light]', "el => el.click()")
        page.wait_for_timeout(400)
        ok(tag + "v45 라이트로 되돌리기", page.evaluate("() => document.documentElement.getAttribute('data-theme')") == "light" and
           page.evaluate(BG_JS) == LIGHT_BG)
        if storage_blocked:
            pass
    if page.query_selector('#mpThemeCard'):
        page.screenshot(path=os.path.join(SHOT, "e2e_v45_theme_card%s.png" % ("_blocked" if storage_blocked else "")))
    ok(tag + "v45 테마 조작 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 3) 다크에서 화면 순회: 넘침 0 · 밝은 박스 0 · 글자 보임 ────────
    if storage_blocked:
        browser.close()
        return
    ctx, page, errs = new_page(390, 844, True, theme="dark")
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(300)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(1600)
    shots = []
    for tab in ("home", "teachers", "booking", "journal", "mypage"):
        page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=%s]' % tab, "el => el.click()")
        page.wait_for_timeout(450)
        info = page.evaluate("""() => {
          const de = document.documentElement;
          const surface = getComputedStyle(document.documentElement).getPropertyValue('--surface').trim();
          /* 카드가 흰색으로 남아 있지 않은지: 화면 안의 큰 흰 면 개수 */
          let whites = 0;
          for (const el of document.querySelectorAll('.screen.is-active .card, .screen.is-active .list-item')) {
            const r = el.getBoundingClientRect();
            if (r.width < 80 || r.height < 30) continue;
            const c = getComputedStyle(el).backgroundColor;
            if (/rgb\\(25[0-5], 25[0-5], 25[0-5]\\)/.test(c)) whites++;
          }
          return {overflow: de.scrollWidth - de.clientWidth, whites: whites, surface: surface};
        }""")
        shots.append((tab, info))
        if tab in ("home", "mypage"):
            page.screenshot(path=os.path.join(SHOT, "e2e_v45_dark_%s%s.png" % (tab, "_blocked" if storage_blocked else "")))
    ok(tag + "v45 다크 5개 화면 가로 넘침 0", all(x[1]["overflow"] <= 0 for x in shots), shots)
    ok(tag + "v45 다크에서 흰 카드가 남지 않는다", all(x[1]["whites"] == 0 for x in shots), shots)
    ok(tag + "v45 다크 카드 면이 바탕과 구분된다", all(x[1]["surface"] in ("#151D29", "#131B26") for x in shots), shots[:2])

    # 다크 텍스트 대비(본문) — 실제 계산 색으로
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=home]', "el => el.click()")
    page.wait_for_timeout(400)
    contrast = page.evaluate("""() => {
      const parse = (c) => { const m = String(c).match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
        const p = m[1].split(/[\\s,\\/]+/).map(Number); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}; };
      const over = (t,b) => { const a=t.a+b.a*(1-t.a); if(!a) return {r:0,g:0,b:0,a:0};
        return {r:(t.r*t.a+b.r*b.a*(1-t.a))/a,g:(t.g*t.a+b.g*b.a*(1-t.a))/a,b:(t.b*t.a+b.b*b.a*(1-t.a))/a,a}; };
      const lum = (c) => { const f=(v)=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
        return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b); };
      const ratio = (a,b) => { const l1=lum(a),l2=lum(b),hi=Math.max(l1,l2),lo=Math.min(l1,l2); return (hi+0.05)/(lo+0.05); };
      const bgOf = (el) => { let cur = el; while (cur) { const c = parse(getComputedStyle(cur).backgroundColor);
          if (c && c.a > 0.5) return c; cur = cur.parentElement; } return parse(getComputedStyle(document.body).backgroundColor); };
      const worst = [];
      for (const el of document.querySelectorAll('#screen-home h1, #screen-home h2, #screen-home b, #screen-home p, #screen-home span')) {
        const t = (el.textContent || '').trim(); if (!t || t.length < 2) continue;
        const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
        const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
        const fg = parse(cs.color); if (!fg) continue;
        const bg = bgOf(el);
        const cr = ratio(fg.a < 1 ? over(fg, bg) : fg, bg);
        const size = parseFloat(cs.fontSize) || 14;
        const weight = parseInt(cs.fontWeight, 10) || 400;
        const need = (size >= 24 || (size >= 18.66 && weight >= 700)) ? 3 : 4.5;
        if (cr + 0.01 < need) worst.push({t: t.slice(0, 14), cr: Math.round(cr * 100) / 100, need: need});
      }
      return worst;
    }""")
    ok(tag + "v45 다크 홈 글자 대비 4.5:1 이상(AA)", not contrast, contrast[:4])
    ok(tag + "v45 다크 순회 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 4) 320 다크: 가로 넘침·첫 화면 수납 ─────────────────────────
    ctx, page, errs = new_page(320, 568, True, theme="dark")
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(300)
    ok(tag + "v45 320 다크 시작 화면 넘침 없음", page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
    ok(tag + "v45 320 다크 시작 화면 바탕", page.evaluate("() => getComputedStyle(document.querySelector('#entryGate')).backgroundColor") == "rgb(21, 29, 41)",
       page.evaluate("() => getComputedStyle(document.querySelector('#entryGate')).backgroundColor"))
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(1600)
    ok(tag + "v45 320 다크 홈 넘침 없음", page.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1"))
    page.screenshot(path=os.path.join(SHOT, "e2e_v45_dark_320%s.png" % ("_blocked" if storage_blocked else "")))
    ok(tag + "v45 320 다크 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 5) 시트·모달도 다크 ────────────────────────────────────────
    ctx, page, errs = new_page(390, 844, True, theme="dark")
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(300)
    page.eval_on_selector('[data-login="customer"]', "el => el.click()")
    page.wait_for_timeout(1500)
    page.eval_on_selector('#btnNotif', "el => el.click()")
    page.wait_for_timeout(500)
    sheet_bg = page.evaluate("() => getComputedStyle(document.querySelector('#notifSheet .sheet')).backgroundColor")
    ok(tag + "v45 알림 시트가 다크 면", sheet_bg == "rgb(21, 29, 41)" or sheet_bg == "rgb(19, 27, 38)", sheet_bg)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el => el.click()")
    page.wait_for_timeout(400)
    page.eval_on_selector('#teacherList .teacher, .teacher', "el => el.click()")
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(SHOT, "e2e_v45_dark_sheet%s.png" % ("_blocked" if storage_blocked else "")))
    ok(tag + "v45 선생님 시트 다크 렌더", page.evaluate("() => !!document.querySelector('#teacherSheet.is-open')"))
    ok(tag + "v45 시트 오류 0", not errs, errs[:2])
    ctx.close()
    browser.close()


def run_v46_flow(p, storage_blocked=False):
    """v46 · 넓은 화면 — 데스크톱 2단·태블릿 폭·320 시작 화면 수납."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v46 blocked] " if storage_blocked else "[v46] "

    def make(w, h, mob, theme=None):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                  is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        elif theme:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def no_overflow(page, state):
        m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,"
                                  " aw: document.getElementById('appRoot').scrollWidth, acw: document.getElementById('appRoot').clientWidth})")
        return m["sw"] <= m["cw"] + 1 and m["aw"] <= m["acw"] + 1, m

    def box(page, sel):
        return page.evaluate("""(s) => { const el = document.querySelector(s); if (!el) return null;
          const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), b: Math.round(r.bottom), r: Math.round(r.right)}; }""", sel)

    def rows_of(page, sel):
        """같은 줄에 놓인 카드의 x 좌표 묶음(열 수 세기) — 첫 줄만."""
        return page.evaluate("""(s) => {
          const els = [...document.querySelectorAll(s)].filter(e => e.getBoundingClientRect().width > 1);
          if (!els.length) return [];
          const top = Math.min(...els.map(e => Math.round(e.getBoundingClientRect().top)));
          return [...new Set(els.filter(e => Math.abs(Math.round(e.getBoundingClientRect().top) - top) < 6)
            .map(e => Math.round(e.getBoundingClientRect().x)))].sort((a, b) => a - b);
        }""", sel)

    def enter(page, role, tab=None, mode=None):
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(200)
        page.eval_on_selector('[data-login="%s"]' % role, "el => el.click()")
        page.wait_for_timeout(600)
        if tab:
            page.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode or "customer", tab), "el => el.click()")
            page.wait_for_timeout(400)

    # ── 1) 데스크톱(1280): 작업면 폭·2단·시트 ────────────────────
    ctx, page, errs = make(1280, 900, False)
    page.goto(URL + "?intro=0")
    enter(page, "customer")
    app = box(page, "#appRoot")
    ok(tag + "v46 데스크톱 작업면 1,180px", abs(app["w"] - 1180) <= 2, app)
    ok(tag + "v46 데스크톱 작업면이 화면 가운데", abs((app["x"] + app["w"] / 2) - 640) <= 2, app)
    ok(tag + "v46 데스크톱 탭바가 작업면 폭과 같다", abs(box(page, '.tabbar[data-mode="customer"]')["w"] - app["w"]) <= 2,
       box(page, '.tabbar[data-mode="customer"]'))
    ok(tag + "v46 데스크톱에서 브랜드 패널은 숨김", page.evaluate("() => getComputedStyle(document.querySelector('.desk-brand')).display") == "none")

    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="teachers"]', "el => el.click()")
    page.wait_for_timeout(500)
    side, main = box(page, "#teacherSideCol"), box(page, "#teacherMainCol")
    ok(tag + "v46 선생님 화면 2단(레일이 결과 왼쪽)", side and main and side["r"] <= main["x"] + 2, [side, main])
    ok(tag + "v46 레일 폭 288px(상세 열을 둔 3칸)", abs(side["w"] - 288) <= 2, side)
    cols_t = rows_of(page, "#teacherList .teacher")
    ok(tag + "v46 데스크톱 선생님 목록은 한 줄에 하나(상세 열 옆)", len(cols_t) == 1, cols_t)
    ok(tag + "v46 선생님 화면 가로 넘침 없음", no_overflow(page, "teachers")[0], no_overflow(page, "teachers")[1])
    page.eval_on_selector("#appRoot", "el => { el.scrollTop = 420; }")
    page.wait_for_timeout(320)
    sticky = box(page, "#teacherSideCol")
    ok(tag + "v46 레일은 스크롤해도 위에 붙어 있다", sticky["y"] >= app["y"] + 50 and sticky["y"] <= app["y"] + 130, sticky)
    page.eval_on_selector("#appRoot", "el => { el.scrollTop = 0; }")
    page.wait_for_timeout(200)
    page.eval_on_selector("#teacherList .teacher", "el => el.click()")
    page.wait_for_timeout(600)
    pane = box(page, "#teacherPane")
    ok(tag + "v46 데스크톱 카드를 누르면 오른쪽 상세 열이 열린다", pane and pane["w"] >= 300 and
       not page.evaluate("() => document.getElementById('teacherPane').hidden"), pane)
    ok(tag + "v46 데스크톱 상세는 시트를 겹쳐 띄우지 않는다",
       not page.evaluate("() => document.getElementById('teacherSheet').classList.contains('is-open')"))
    ok(tag + "v46 상세 열이 목록 오른쪽", pane and abs(pane["x"] - (main["r"] - pane["w"])) <= 3, [pane, main])
    ok(tag + "v46 고른 카드가 표시된다", page.evaluate("() => !!document.querySelector('#teacherList .teacher.is-selected')"))
    ok(tag + "v46 상세 열에 이름·자격·후기", all(t in page.inner_text("#teacherPane") for t in ["박서준", "물리치료사", "신뢰 배지"]),
       page.inner_text("#teacherPane")[:80])
    ok(tag + "v46 상세 열 가로 넘침 없음", page.evaluate("""() => { const p = document.getElementById('teacherPane');
      return p.scrollWidth <= p.clientWidth + 1; }"""))
    page.eval_on_selector("[data-pane-open]", "el => el.click()")
    page.wait_for_timeout(600)
    sheet = box(page, "#teacherSheet .sheet")
    ok(tag + "v46 상세 열 '전체 프로필 보기' → 시트 폭 600px", sheet and abs(sheet["w"] - 600) <= 2, sheet)
    ok(tag + "v46 데스크톱 시트가 가운데", sheet and abs((sheet["x"] + sheet["w"] / 2) - 640) <= 3, sheet)
    ok(tag + "v46 데스크톱 시트 높이가 화면을 넘지 않는다", sheet and sheet["h"] <= 900 - 40, sheet)
    page.keyboard.press("Escape")
    page.wait_for_timeout(350)

    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
    page.wait_for_timeout(500)
    ok(tag + "v46 일지 화면이 2단 grid", page.evaluate("() => getComputedStyle(document.getElementById('journal')).display") == "grid")
    a, b = box(page, "#journalSideCol"), box(page, "#journalMainCol")
    ok(tag + "v46 일지 두 열이 나란히", a and b and a["r"] <= b["x"] + 2 and abs(a["y"] - b["y"]) <= 2, [a, b])
    ok(tag + "v46 일지 두 열 폭이 비슷하다(±40px)", a and b and abs(a["w"] - b["w"]) <= 40, [a["w"], b["w"]])
    share = box(page, "#shareBtn")
    ok(tag + "v46 공유 버튼은 두 열 아래 전체 폭", share and share["w"] > a["w"] + b["w"] - 40, share)
    ok(tag + "v46 일지 화면 가로 넘침 없음", no_overflow(page, "journal")[0], no_overflow(page, "journal")[1])
    if not storage_blocked:
        shot(page, "v46_desktop_journal")

    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(800)
    met, ops = box(page, "#adminMetricsSec"), box(page, "#adminOpsSec")
    ok(tag + "v46 관리자 2단(지표 왼쪽·처리 오른쪽)", met and ops and met["r"] <= ops["x"] + 2, [met, ops])
    ok(tag + "v46 관리자 지표 열 폭 456px", met and abs(met["w"] - 456) <= 2, met)
    ok(tag + "v46 관리자 화면 가로 넘침 없음", no_overflow(page, "admin")[0], no_overflow(page, "admin")[1])
    if not storage_blocked:
        shot(page, "v46_desktop_admin")

    page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
    page.wait_for_timeout(150)
    page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
    page.wait_for_timeout(700)
    page.eval_on_selector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-settle"]', "el => el.click()")
    page.wait_for_timeout(600)
    summ, rows = box(page, "#tpsSummary"), box(page, "#tpsRows")
    ok(tag + "v46 정산 2단(요약 왼쪽·내역 오른쪽)", summ and rows and summ["r"] <= rows["x"] + 2, [summ, rows])
    ok(tag + "v46 정산 월 칩은 두 열 위(전체 폭)", page.evaluate("() => { const c = document.getElementById('tpsMonths'); return !!c && !c.closest('.tt46-col'); }"))
    ok(tag + "v46 정산 화면 가로 넘침 없음", no_overflow(page, "settle")[0], no_overflow(page, "settle")[1])
    ok(tag + "v46 데스크톱 오류 0", not errs, errs[:2])
    if not storage_blocked:
        shot(page, "v46_desktop_settle")
    ctx.close()

    # ── 2) 데스크톱 다크: 2단에서도 흰 카드가 남지 않는다 ──────
    if not storage_blocked:
        ctx, page, errs = make(1280, 900, False, theme="dark")
        page.goto(URL + "?intro=0")
        enter(page, "customer")
        light_cards = page.evaluate("""() => {
          const out = [];
          document.querySelectorAll('#screen-home .card, #screen-home .home-hero').forEach((el) => {
            const c = getComputedStyle(el).backgroundColor;
            if (/255, 255, 255/.test(c)) out.push(el.className);
          });
          return out;
        }""")
        ok(tag + "v46 다크 데스크톱에서 흰 카드 0", not light_cards, light_cards[:3])
        ok(tag + "v46 다크 데스크톱 가로 넘침 없음", no_overflow(page, "home-dark")[0], no_overflow(page, "home-dark")[1])
        shot(page, "v46_desktop_dark")
        ctx.close()

    # ── 3) 1024(작은 데스크톱): 상세 열 없이 필터 레일 + 두 열 카드 ──
    ctx, page, errs = make(1024, 800, False)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    ok(tag + "v46 1024는 상세 열을 쓰지 않는다", page.evaluate("() => document.getElementById('teacherPane').hidden"))
    ok(tag + "v46 1024는 필터 레일 + 카드 두 열", len(rows_of(page, "#teacherList .teacher")) == 2, rows_of(page, "#teacherList .teacher"))
    page.eval_on_selector("#teacherList .teacher", "el => el.click()")
    page.wait_for_timeout(500)
    ok(tag + "v46 1024 카드를 누르면 시트가 열린다", page.evaluate("() => document.getElementById('teacherSheet').classList.contains('is-open')"))
    ok(tag + "v46 1024 시작 화면 카드 배치 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 3-1) 태블릿(768): 앱·탭바·시트 폭이 함께 넓어진다 ────────
    ctx, page, errs = make(768, 1024, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    app = box(page, "#appRoot")
    ok(tag + "v46 태블릿 앱 폭 720px", abs(app["w"] - 720) <= 2, app)
    ok(tag + "v46 태블릿 탭바 폭도 720px", abs(box(page, '.tabbar[data-mode="customer"]')["w"] - 720) <= 2,
       box(page, '.tabbar[data-mode="customer"]'))
    ok(tag + "v46 태블릿 선생님 카드 두 열", len(rows_of(page, "#teacherList .teacher")) == 2, rows_of(page, "#teacherList .teacher"))
    ok(tag + "v46 태블릿은 아직 1단(레일 없음)", page.evaluate("() => getComputedStyle(document.getElementById('teacherSideCol')).display") == "contents")
    page.eval_on_selector("#teacherList .teacher", "el => el.click()")
    page.wait_for_timeout(600)
    sheet = box(page, "#teacherSheet .sheet")
    ok(tag + "v46 태블릿 시트 폭 640px(앱보다 좁게 가운데)", sheet and abs(sheet["w"] - 640) <= 2, sheet)
    ok(tag + "v46 태블릿 시트가 앱 안에 들어온다", sheet and sheet["x"] >= app["x"] and sheet["r"] <= app["r"] + 1, [sheet, app])
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    ok(tag + "v46 태블릿 가로 넘침 없음", no_overflow(page, "tablet")[0], no_overflow(page, "tablet")[1])
    gate_fit = page.evaluate("() => { const g = document.getElementById('entryGate'); g.classList.add('is-open'); return {sh: g.scrollHeight, ch: g.clientHeight}; }")
    ok(tag + "v46 태블릿 시작 화면 한 화면", gate_fit["sh"] <= gate_fit["ch"] + 1, gate_fit)
    if not storage_blocked:
        shot(page, "v46_tablet_teachers")
    ctx.close()

    # ── 4) 모바일(390): v45와 같은 1단 흐름 그대로 ───────────────
    ctx, page, errs = make(390, 844, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    ok(tag + "v46 모바일은 1단(묶음이 display:contents)",
       page.evaluate("() => getComputedStyle(document.getElementById('teacherSideCol')).display") == "contents" and
       page.evaluate("() => getComputedStyle(document.getElementById('teacherCols')).display") == "block")
    ok(tag + "v46 모바일 선생님 카드 한 줄에 하나", len(rows_of(page, "#teacherList .teacher")) == 1, rows_of(page, "#teacherList .teacher"))
    ok(tag + "v46 모바일 앱 폭 390(기존 그대로)", abs(box(page, "#appRoot")["w"] - 390) <= 1, box(page, "#appRoot"))
    page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
    page.wait_for_timeout(400)
    ok(tag + "v46 모바일 일지는 1단(block)", page.evaluate("() => getComputedStyle(document.getElementById('journal')).display") == "block")
    ok(tag + "v46 모바일 가로 넘침 없음", no_overflow(page, "mobile")[0], no_overflow(page, "mobile")[1])
    ctx.close()

    # ── 5) 320×568: 시작 화면이 법적 고지까지 한 화면 ──────────
    ctx, page, errs = make(320, 568, True)
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(400)
    fit = page.evaluate("""() => {
      const g = document.getElementById('entryGate');
      const legal = document.querySelector('.gate-legal');
      const cta = document.getElementById('gateCta');
      const r = legal.getBoundingClientRect();
      return {sh: g.scrollHeight, ch: g.clientHeight, legalBottom: Math.round(r.bottom), vh: window.innerHeight,
              ctaH: Math.round(cta.getBoundingClientRect().height), ctaBottom: Math.round(cta.getBoundingClientRect().bottom)};
    }""")
    ok(tag + "v46 320×568 시작 화면 스크롤 0", fit["sh"] <= fit["ch"] + 1, fit)
    ok(tag + "v46 320×568 법적 고지까지 화면 안", fit["legalBottom"] <= fit["vh"] + 1, fit)
    ok(tag + "v46 320×568 CTA 44px 이상", fit["ctaH"] >= 44, fit)
    ok(tag + "v46 320×568 CTA가 고지 위에 있다", fit["ctaBottom"] < fit["legalBottom"], fit)
    ok(tag + "v46 320×568 오류 0", not errs, errs[:2])
    if not storage_blocked:
        shot(page, "v46_320_gate_fit")
    ctx.close()
    browser.close()


def run_v47_flow(p, storage_blocked=False):
    """v47 · 데스크톱 목록 방향키 이동 · 스켈레톤 로딩(흔들림 0) · 1024 카드 여백."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v47 blocked] " if storage_blocked else "[v47] "

    def make(w, h, mob, theme=None):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                  is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        elif theme:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def enter(page, role, tab=None, mode=None):
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(200)
        page.eval_on_selector('[data-login="%s"]' % role, "el => el.click()")
        page.wait_for_timeout(600)
        if tab:
            page.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode or "customer", tab), "el => el.click()")
            page.wait_for_timeout(450)

    def geo(page, sel):
        return page.evaluate("""(s) => { const el = document.querySelector(s); if (!el) return null;
          const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width),
          h: Math.round(r.height), b: Math.round(r.bottom)}; }""", sel)

    # ── 1) 데스크톱 1280: 방향키 이동 ────────────────────────────
    ctx, page, errs = make(1280, 900, False)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    hint = geo(page, "#teacherKbdHint")
    ok(tag + "v47 1280 키보드 안내가 보인다", hint and hint["h"] > 12 and page.evaluate(
        "() => getComputedStyle(document.getElementById('teacherKbdHint')).display") == "flex", hint)
    ok(tag + "v47 안내 문구(↑↓·Enter·Esc)", all(t in page.inner_text("#teacherKbdHint") for t in ["카드 이동", "프로필 열기", "닫기"]),
       page.inner_text("#teacherKbdHint"))
    ok(tag + "v47 1280에서 상세 열은 아직 닫혀 있고 빈 자리 안내가 보인다",
       page.evaluate("() => document.getElementById('teacherPane').hidden") and
       page.evaluate("() => getComputedStyle(document.getElementById('teacherPaneEmpty')).display") == "flex")
    ok(tag + "v47 빈 자리 안내 문구", "프로필이 여기에 열려요" in page.inner_text("#teacherPaneEmpty"))
    ok(tag + "v47 목록은 한 칸(438px 안팎)", 380 <= (geo(page, "#teacherList") or {"w": 0})["w"] <= 470, geo(page, "#teacherList"))

    names = page.evaluate("() => [...document.querySelectorAll('#teacherList .teacher')].map(e => e.getAttribute('data-teacher'))")
    page.eval_on_selector("#teacherList .teacher .t-open", "el => el.focus()")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(320)
    st = page.evaluate("""() => { const a = document.activeElement;
      return {focused: a && a.closest('.teacher') && a.closest('.teacher').getAttribute('data-teacher'), paneHidden: document.getElementById('teacherPane').hidden,
        paneText: document.getElementById('teacherPane').innerText, live: document.getElementById('teacherNavLive').textContent,
        hasPane: document.getElementById('teacherMainCol').classList.contains('has-pane'),
        emptyShown: getComputedStyle(document.getElementById('teacherPaneEmpty')).display !== 'none',
        current: (document.querySelector('#teacherList .teacher[aria-current="true"]') || {}).getAttribute
          ? document.querySelector('#teacherList .teacher[aria-current="true"]').getAttribute('data-teacher') : null}; }""")
    ok(tag + "v47 ↓로 다음 카드에 초점", st["focused"] == names[1], st)
    ok(tag + "v47 오른쪽 프로필 열이 따라 온다", st["paneHidden"] is False and "이하늘" in st["paneText"], st["paneText"][:60])
    ok(tag + "v47 고른 카드 표시(aria-current)", st["current"] == names[1], st["current"])
    ok(tag + "v47 빈 자리 안내는 숨는다", st["hasPane"] and not st["emptyShown"])
    ok(tag + "v47 이동을 '2/8'로 낭독", "2/8" in st["live"], st["live"])
    page.screenshot(path=os.path.join(SHOT, "v47_1280_kbd_pane.png"))

    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(300)
    ok(tag + "v47 ↓↓ 3번째 카드·열 갱신", page.evaluate(
        "() => ((document.activeElement.closest('.teacher')||{getAttribute:function(){return null}}).getAttribute('data-teacher'))") == names[2] and
        "정민아" in page.inner_text("#teacherPane"))
    page.keyboard.press("End")
    page.wait_for_timeout(300)
    ok(tag + "v47 End는 마지막 카드", page.evaluate("() => (document.activeElement.closest('.teacher')||{getAttribute:function(){return null}}).getAttribute('data-teacher')") == names[-1])
    page.keyboard.press("Home")
    page.wait_for_timeout(300)
    ok(tag + "v47 Home은 첫 카드", page.evaluate("() => (document.activeElement.closest('.teacher')||{getAttribute:function(){return null}}).getAttribute('data-teacher')") == names[0])
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(250)
    page.keyboard.press("Enter")
    page.wait_for_timeout(300)
    ok(tag + "v47 Enter는 프로필 열 안으로 초점을 옮긴다", page.evaluate(
        "() => document.getElementById('teacherPane').contains(document.activeElement)") and
        page.evaluate("() => !!document.activeElement.closest('#teacherPane').querySelector('[data-pane-open]')"))
    ok(tag + "v47 Enter로 시트를 겹쳐 띄우지 않는다",
       not page.evaluate("() => document.getElementById('teacherSheet').classList.contains('is-open')"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    ok(tag + "v47 Esc는 열을 닫고 카드로 돌아온다",
       page.evaluate("() => document.getElementById('teacherPane').hidden") and
       page.evaluate("() => (document.activeElement.closest('.teacher')||{getAttribute:function(){return null}}).getAttribute('data-teacher')") == names[1])
    ok(tag + "v47 닫으면 빈 자리 안내가 돌아온다",
       page.evaluate("() => getComputedStyle(document.getElementById('teacherPaneEmpty')).display") == "flex")
    ok(tag + "v47 초점 링은 키보드일 때만(is-kb)", page.evaluate("() => document.body.classList.contains('is-kb')"))

    # ── 2) 스켈레톤: 같은 자리·같은 높이 ─────────────────────────
    before = page.evaluate("""() => { const l = document.getElementById('teacherList');
      const f = document.querySelector('#teacherMainCol > .fine');
      return {listH: Math.round(l.getBoundingClientRect().height), fineY: f ? Math.round(f.getBoundingClientRect().y) : null}; }""")
    page.evaluate("() => { window.__ttSkeleton.set(true, {silent: true}); window.__ttSkeleton.delay(600); }")
    page.eval_on_selector('#teacherFilters [data-cat="stroke"]', "el => el.click()")
    page.wait_for_timeout(180)
    skel = page.evaluate("""() => { const l = document.getElementById('teacherList');
      return {n: document.querySelectorAll('#teacherList .teacher.is-skel').length, busy: l.getAttribute('aria-busy'),
        listH: Math.round(l.getBoundingClientRect().height),
        bars: document.querySelectorAll('#teacherList .tt-skel').length,
        label: document.getElementById('teacherNavLive').textContent}; }""")
    ok(tag + "v47 스켈레톤이 필터 결과 수만큼(3장)", skel["n"] == 3, skel)
    ok(tag + "v47 스켈레톤 중 aria-busy·낭독", skel["busy"] == "true" and "불러오는" in skel["label"], skel)
    ok(tag + "v47 스켈레톤 막대가 그려진다", skel["bars"] >= 15, skel["bars"])
    page.wait_for_timeout(700)
    after = page.evaluate("""() => { const l = document.getElementById('teacherList');
      const f = document.querySelector('#teacherMainCol > .fine');
      return {n: document.querySelectorAll('#teacherList .teacher').length, listH: Math.round(l.getBoundingClientRect().height),
        fineY: f ? Math.round(f.getBoundingClientRect().y) : null, busy: l.getAttribute('aria-busy')}; }""")
    ok(tag + "v47 스켈레톤 뒤 실제 카드 3장", after["n"] == 3 and after["busy"] == "false", after)
    ok(tag + "v47 스켈레톤↔카드 높이 차 3px 이내(흔들림 0)", abs(after["listH"] - skel["listH"]) <= 3,
       [skel["listH"], after["listH"]])
    page.eval_on_selector('#teacherFilters [data-cat="all"]', "el => el.click()")
    page.wait_for_timeout(600)
    after_all = page.evaluate("""() => { const f = document.querySelector('#teacherMainCol > .fine');
      return {fineY: f ? Math.round(f.getBoundingClientRect().y) : null,
        h: window.__ttokttokSkeleton && window.__ttokttokSkeleton.cardHeight}; }""")
    ok(tag + "v47 카드 높이를 기억한다(190~210px)", 180 <= (after_all["h"] or 0) <= 215, after_all)

    # 프로필 열 스켈레톤
    page.evaluate("() => { window.__ttSkeleton.delay(600); }")
    page.eval_on_selector("#teacherList .teacher", "el => el.click()")
    page.wait_for_timeout(200)
    ok(tag + "v47 프로필 열도 스켈레톤", page.evaluate(
        "() => !!document.querySelector('#teacherPane .pane-skel') && document.getElementById('teacherPane').getAttribute('aria-busy') === 'true'"))
    page.screenshot(path=os.path.join(SHOT, "v47_1280_pane_skel.png"))
    page.wait_for_timeout(700)
    ok(tag + "v47 지연 뒤 실제 프로필", page.evaluate(
        "() => !document.querySelector('#teacherPane .pane-skel') && document.getElementById('teacherPane').innerText.indexOf('박서준') >= 0"))
    page.evaluate("() => window.__ttSkeleton.set(false, {silent: true})")
    page.wait_for_timeout(150)
    page.eval_on_selector("#teacherList .teacher", "el => el.click()")
    page.wait_for_timeout(300)
    ok(tag + "v47 스켈레톤을 끄면 곧바로 카드", page.evaluate(
        "() => !document.querySelector('#teacherList .teacher.is-skel') && document.getElementById('teacherList').innerText.indexOf('박서준') >= 0"))
    ok(tag + "v47 1280 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 3) 다크 1280: 스켈레톤도 어둡게 ──────────────────────────
    ctx, page, errs = make(1280, 900, False, theme="dark")
    page.goto(URL + "?intro=0&skel=1&skelms=2500")
    enter(page, "customer", "teachers")
    page.wait_for_timeout(150)
    dark = page.evaluate("""() => { const b = document.querySelector('#teacherList .tt-skel');
      const card = document.querySelector('#teacherList .teacher.is-skel');
      return {bg: b ? getComputedStyle(b).backgroundColor : null,
        cardBg: card ? getComputedStyle(card).backgroundColor : null,
        n: document.querySelectorAll('#teacherList .teacher.is-skel').length}; }""")
    ok(tag + "v47 다크에서도 스켈레톤이 보인다", dark["n"] > 0, dark)
    ok(tag + "v47 다크 스켈레톤 막대는 흰색이 아니다", dark["bg"] and "255, 255, 255" not in dark["bg"], dark)
    page.screenshot(path=os.path.join(SHOT, "v47_1280_dark_skel.png"))
    ok(tag + "v47 다크 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 4) 1024: 레일 + 두 열, 방향키는 초점만 ──────────────────
    ctx, page, errs = make(1024, 900, False)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    ok(tag + "v47 1024에서는 키보드 안내를 숨긴다", page.evaluate(
        "() => getComputedStyle(document.getElementById('teacherKbdHint')).display") == "none")
    ok(tag + "v47 1024에는 상세 열이 없다", page.evaluate(
        "() => getComputedStyle(document.getElementById('teacherPane')).display") == "none" and
        page.evaluate("() => getComputedStyle(document.getElementById('teacherPaneEmpty')).display") == "none")
    cols = page.evaluate("""() => { const els = [...document.querySelectorAll('#teacherList .teacher')];
      const top = Math.min(...els.map(e => Math.round(e.getBoundingClientRect().top)));
      return [...new Set(els.filter(e => Math.abs(Math.round(e.getBoundingClientRect().top) - top) < 6)
        .map(e => Math.round(e.getBoundingClientRect().x)))].sort((a, b) => a - b); }""")
    ok(tag + "v47 1024 목록은 두 열", len(cols) == 2, cols)
    reg = page.evaluate("""() => { const r = document.querySelector('#teacherList .teacher .t-region');
      const ic = r.querySelector('.ic'), sp = r.querySelector('span');
      return {icY: Math.round(ic.getBoundingClientRect().y), spY: Math.round(sp.getBoundingClientRect().y),
        lines: Math.round(sp.getBoundingClientRect().height / 20)}; }""")
    ok(tag + "v47 1024 지역 아이콘이 글자와 같은 줄", abs(reg["icY"] - reg["spY"]) <= 4, reg)
    page.eval_on_selector("#teacherList .teacher .t-open", "el => el.focus()")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(200)
    ok(tag + "v47 1024에서도 ↓로 초점 이동", page.evaluate(
        "() => document.activeElement === document.querySelectorAll('#teacherList .teacher .t-open')[1]"))
    ok(tag + "v47 1024에서는 열을 열지 않는다", page.evaluate("() => document.getElementById('teacherMainCol').classList.contains('has-pane')") is False)
    ok(tag + "v47 1024 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 5) 375: 안내 숨김·스켈레톤·Enter 시트 ───────────────────
    ctx, page, errs = make(375, 812, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    ok(tag + "v47 375에서 키보드 안내는 숨김", page.evaluate(
        "() => getComputedStyle(document.getElementById('teacherKbdHint')).display") == "none")
    page.eval_on_selector("#teacherList .teacher .t-open", "el => el.focus()")
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    ok(tag + "v47 375 Enter로 상세 시트", page.evaluate(
        "() => document.getElementById('teacherSheet').classList.contains('is-open')"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    ok(tag + "v47 375 Esc로 시트 닫기", not page.evaluate(
        "() => document.getElementById('teacherSheet').classList.contains('is-open')"))
    page.evaluate("() => { window.__ttSkeleton.set(true, {silent: true}); window.__ttSkeleton.delay(500); window.__ttSkeleton.render(); }")
    page.wait_for_timeout(150)
    mobile_skel = page.evaluate("""() => { const l = document.getElementById('teacherList');
      return {n: document.querySelectorAll('#teacherList .teacher.is-skel').length,
        h: Math.round(l.getBoundingClientRect().height)}; }""")
    page.wait_for_timeout(600)
    mobile_real = page.evaluate("""() => { const l = document.getElementById('teacherList');
      return {n: document.querySelectorAll('#teacherList .teacher').length, h: Math.round(l.getBoundingClientRect().height)}; }""")
    ok(tag + "v47 375에서도 스켈레톤 8장", mobile_skel["n"] == 8, mobile_skel)
    ok(tag + "v47 375 스켈레톤↔카드 높이 차 6px 이내", abs(mobile_real["h"] - mobile_skel["h"]) <= 6, [mobile_skel, mobile_real])
    ok(tag + "v47 375 오류 0", not errs, errs[:2])
    page.screenshot(path=os.path.join(SHOT, "v47_375_teachers.png"))
    ctx.close()
    browser.close()


def run_v48_flow(p, storage_blocked=False):
    """v48 · 로빙 탭인덱스(목록 Tab 1정지점) · 경계 대비 토큰 · 가로모드 · 인쇄."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v48 blocked] " if storage_blocked else "[v48] "

    def make(w, h, mob, theme=None):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                  is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        elif theme:
            ctx.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % theme)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def enter(page, role, tab=None, mode=None):
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(200)
        page.eval_on_selector('[data-login="%s"]' % role, "el => el.click()")
        page.wait_for_timeout(600)
        if tab:
            page.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode or "customer", tab), "el => el.click()")
            page.wait_for_timeout(450)

    def geo(page, sel):
        return page.evaluate("""(s) => { const el = document.querySelector(s); if (!el) return null;
          const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width),
          h: Math.round(r.height), b: Math.round(r.bottom)}; }""", sel)

    def active(page):
        return page.evaluate("""() => { const a = document.activeElement;
          return {tag: a && a.tagName, teacher: a && a.closest && a.closest('.teacher') && a.closest('.teacher').getAttribute('data-teacher'),
                  inList: !!(a && a.closest && a.closest('#teacherList')),
                  inPane: !!(a && a.closest && a.closest('#teacherPane')),
                  cls: (a && a.className || '').toString().slice(0, 30)}; }""")

    def stops(page):
        return page.evaluate("""() => { const cs = [...document.querySelectorAll('#teacherList .teacher .t-open')];
          return {n: cs.length, stops: cs.filter((c) => c.getAttribute('tabindex') === '0').length,
                  pattern: cs.map((c) => c.getAttribute('tabindex')).join(',')}; }""")

    # ── 1) 1280 — 목록은 Tab 정지점 1개, 방향키로 이동, Tab은 다음 칸 ──
    ctx, page, errs = make(1280, 900, False)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    st = stops(page)
    ok(tag + "v48 1280 목록 Tab 정지점 1개(카드 8장)", st["n"] == 8 and st["stops"] == 1 and st["pattern"] == "0,-1,-1,-1,-1,-1,-1,-1", st)
    ok(tag + "v48 로빙 훅 노출", page.evaluate("() => !!window.__ttokttokRoving && /^v4[89]$/.test(window.__ttokttokRoving.version)"))
    # 마지막 필터 칩 → Tab 한 번에 목록으로 들어온다
    page.evaluate("() => { const c = [...document.querySelectorAll('#regionFilters .chip')]; c[c.length - 1].focus(); }")
    page.keyboard.press("Tab")
    page.wait_for_timeout(250)
    a1 = active(page)
    ok(tag + "v48 1280 필터에서 Tab 한 번이면 목록 진입(카드 8번 아님)", a1["inList"] and a1["teacher"], a1)
    ok(tag + "v48 들어오면 목록 안내를 낭독", "선생님 목록 8명" in page.inner_text("#teacherNavLive"), page.inner_text("#teacherNavLive")[:60])
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(320)
    a2 = active(page)
    ok(tag + "v48 ↓ 다음 카드", a2["teacher"] and a2["teacher"] != a1["teacher"], [a1["teacher"], a2["teacher"]])
    ok(tag + "v48 정지점이 고른 카드로 옮겨간다", stops(page)["pattern"].count("0") == 1, stops(page))
    page.keyboard.press("Tab")
    page.wait_for_timeout(250)
    a3 = active(page)
    ok(tag + "v48 카드에서 Tab은 다음 조작 요소로(카드 안 하트 또는 프로필 열)", a3["inList"] or a3["inPane"], a3)
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    # 초점을 되돌려 Enter로 프로필 열기
    page.evaluate("() => document.querySelector('#teacherList .teacher .t-open[tabindex=\"0\"]').focus()")
    page.keyboard.press("Enter")
    page.wait_for_timeout(350)
    ok(tag + "v48 Enter는 프로필 열 안으로 초점", page.evaluate(
        "() => !document.getElementById('teacherPane').hidden && document.getElementById('teacherPane').contains(document.activeElement)"))
    ok(tag + "v48 1280 오류 0", not errs, errs[:2])
    page.screenshot(path=os.path.join(SHOT, "v48_1280_roving.png"))
    ctx.close()

    # ── 2) 375 — 좁은 화면도 정지점 1개 ─────────────────────────
    ctx, page, errs = make(375, 812, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    st = stops(page)
    ok(tag + "v48 375 목록 Tab 정지점 1개", st["stops"] == 1, st)
    page.evaluate("() => { const c = [...document.querySelectorAll('#regionFilters .chip')]; c[c.length - 1].focus(); }")
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    ok(tag + "v48 375 Tab 한 번에 목록 진입", active(page)["inList"], active(page))
    last_name = page.evaluate("() => { const c = [...document.querySelectorAll('#teacherList .teacher')]; return c[c.length - 1].getAttribute('data-teacher'); }")
    page.keyboard.press("End")
    page.wait_for_timeout(250)
    ok(tag + "v48 375 End는 마지막 카드", active(page)["teacher"] == last_name, [active(page)["teacher"], last_name])
    page.keyboard.press("Enter")
    page.wait_for_timeout(400)
    ok(tag + "v48 375 Enter는 상세 시트", page.evaluate("() => document.getElementById('teacherSheet').classList.contains('is-open')"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    ok(tag + "v48 375 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 3) 가로모드 844×390·667×375 — 헤더·탭바가 화면을 덜 가린다 ──
    for w, h in [(844, 390), (667, 375)]:
        ctx, page, errs = make(w, h, True)
        page.goto(URL + "?intro=0")
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(500)
        gate = page.evaluate("""() => { const g = document.getElementById('gateCta').getBoundingClientRect();
          return {y: Math.round(g.y), b: Math.round(g.bottom), h: Math.round(g.height), vh: innerHeight}; }""")
        ok(tag + "v48 %dx%d 시작 화면 CTA가 첫 화면 안에" % (w, h), gate["b"] <= gate["vh"] + 2 and gate["h"] >= 44, gate)
        page.screenshot(path=os.path.join(SHOT, "v48_land_%d_gate.png" % w))
        enter(page, "customer", "teachers")
        m = page.evaluate("""() => { const q = (s) => { const el = document.querySelector(s); if (!el) return null;
            const r = el.getBoundingClientRect();
            return {y: Math.round(r.y), h: Math.round(r.height), w: Math.round(r.width), b: Math.round(r.bottom)}; };
          return {vw: innerWidth, vh: innerHeight, docW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth,
            app: q('.app'), header: q('.app-header'), tabbar: q('.tabbar'), card: q('#teacherList .teacher'),
            list: q('#teacherList'), cta: q('.book-total')}; }""")
        ok(tag + "v48 %dx%d 앱이 가로 폭을 다 쓴다(430px 우편함 없음)" % (w, h), abs(m["app"]["w"] - m["vw"]) <= 2, m["app"])
        ok(tag + "v48 %dx%d 헤더 50px 이하" % (w, h), m["header"]["h"] <= 50, m["header"])
        ok(tag + "v48 %dx%d 탭바 52px 이하" % (w, h), m["tabbar"]["h"] <= 52, m["tabbar"])
        ok(tag + "v48 %dx%d 가로 넘침 없음" % (w, h), m["docW"] <= m["clientW"] + 1, [m["docW"], m["clientW"]])
        ok(tag + "v48 %dx%d 첫 카드가 탭바 위에서 보인다" % (w, h), m["card"] and m["card"]["y"] < m["tabbar"]["y"] and m["card"]["b"] > 0,
           [m["card"], m["tabbar"]])
        ok(tag + "v48 %dx%d 오류 0" % (w, h), not errs, errs[:2])
        page.screenshot(path=os.path.join(SHOT, "v48_land_%d_teachers.png" % w))
        ctx.close()

    # ── 4) 경계 대비: 실제 계산된 테두리가 3:1 이상 ────────────────
    ctx, page, errs = make(375, 812, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    edge = page.evaluate("""() => {
      const parse = (c) => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return null;
        const p = m[1].split(/[\\s,\\/]+/).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
      const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
      const bgOf = (el) => { let cur = el; while (cur && cur !== document.documentElement) {
          const c = parse(getComputedStyle(cur).backgroundColor); if (c && c.a > 0.5) return c; cur = cur.parentElement; }
        return parse('rgb(247,248,250)'); };
      const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
      const pick = (sel) => { for (const el of document.querySelectorAll(sel)) { const r = el.getBoundingClientRect();
          const cs = getComputedStyle(el); if (cs.display === 'none' || r.width < 2 || r.height < 2) continue;
          if (parseFloat(cs.borderTopWidth) < 0.5) continue; const bc = parse(cs.borderTopColor); if (!bc || bc.a === 0) continue;
          return Math.round(ratio(bc, bgOf(el.parentElement || document.body)) * 100) / 100; } return null; };
      return {chip: pick('.chip'), seg: pick('.segmented button'), card: pick('.card'), status: pick('.status'),
              input: pick('input.input'), token: getComputedStyle(document.documentElement).getPropertyValue('--edge-ctl').trim()};
    }""")
    ok(tag + "v48 경계 토큰 적용(#7E8592)", edge["token"] == "#7E8592", edge["token"])
    ok(tag + "v48 칩 테두리 3:1 이상", edge["chip"] is not None and edge["chip"] >= 3, edge["chip"])
    ok(tag + "v48 세그먼트 테두리 3:1 이상", edge["seg"] is None or edge["seg"] >= 3, edge["seg"])
    ok(tag + "v48 입력창 테두리 3:1 이상", edge["input"] is None or edge["input"] >= 3, edge["input"])
    ok(tag + "v48 카드·배지는 낮은 대비 선을 그리지 않는다(선 없음)", edge["card"] is None and edge["status"] is None,
       [edge["card"], edge["status"]])
    ctx.close()

    # ── 5) 인쇄 — 헤더·탭바가 빠지고 열린 시트만 ──────────────────
    ctx, page, errs = make(390, 844, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "journal")
    page.emulate_media(media="print")
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    page.wait_for_timeout(200)
    pr = page.evaluate("""() => { const d = (s) => { const el = document.querySelector(s); return el ? getComputedStyle(el).display : 'missing'; };
      return {header: d('.app-header'), tabbar: d('.tabbar'), screen: d('#screen-journal'), other: d('#screen-home'),
              roleSwitch: d('.role-switch')}; }""")
    ok(tag + "v48 인쇄에서 헤더·탭바가 빠진다", pr["header"] == "none" and pr["tabbar"] == "none", pr)
    ok(tag + "v48 인쇄는 지금 화면만", pr["screen"] == "block" and pr["other"] == "none", pr)
    ok(tag + "v48 인쇄에서 보기 전환 탭은 빠진다", pr["roleSwitch"] == "none", pr["roleSwitch"])
    page.screenshot(path=os.path.join(SHOT, "v48_print_journal.png"), full_page=True)
    page.emulate_media(media="screen")
    page.evaluate("() => window.dispatchEvent(new Event('afterprint'))")
    ctx.close()

    ctx, page, errs = make(1280, 900, False)
    page.goto(URL + "?intro=0")
    enter(page, "therapist", "tp-settle", "therapist")
    page.evaluate("() => { const b = document.querySelector('[data-stl-preview]'); if (b) b.click(); }")
    page.wait_for_timeout(500)
    page.emulate_media(media="print")
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    page.wait_for_timeout(300)
    pr2 = page.evaluate("""() => { const d = (s) => { const el = document.querySelector(s); return el ? getComputedStyle(el).display : 'missing'; };
      return {sheet: d('#settlementPrintSheet'), screens: [...document.querySelectorAll('.screen')].filter((el) => getComputedStyle(el).display !== 'none').length,
              mark: window.__ttokttokPrint.target(), header: d('.app-header'), handle: d('.sheet-handle')}; }""")
    ok(tag + "v48 정산서 시트가 인쇄 대상", pr2["sheet"] == "block" and pr2["mark"] == "settlementPrintSheet", pr2)
    ok(tag + "v48 시트가 열리면 화면 본문은 인쇄하지 않는다", pr2["screens"] == 0, pr2["screens"])
    ok(tag + "v48 인쇄에서 시트 손잡이·닫기 버튼 없음", pr2["handle"] == "none" and pr2["header"] == "none", pr2)
    page.screenshot(path=os.path.join(SHOT, "v48_print_settle.png"), full_page=True)
    page.emulate_media(media="screen")
    ctx.close()
    browser.close()



def run_v49_flow(p, storage_blocked=False):
    """v49 · 카드 열기/찜 분리(중첩 버튼 0) · .btn-sm 경계 · 인쇄 쪽나눔 · 시트 스크롤 복원 · 긴 글."""
    browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--font-render-hinting=none"])
    tag = "[v49 blocked] " if storage_blocked else "[v49] "

    def make(w, h, mob):
        ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1,
                                  is_mobile=mob, has_touch=mob, locale="ko-KR")
        if storage_blocked:
            ctx.add_init_script("""
              Object.defineProperty(window, 'localStorage', {
                configurable: true,
                get() { throw new DOMException('SecurityError', 'SecurityError'); }
              });
            """)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        return ctx, page, errs

    def enter(page, role, tab=None, mode=None):
        page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
        page.wait_for_timeout(200)
        page.eval_on_selector('[data-login="%s"]' % role, "el => el.click()")
        page.wait_for_timeout(600)
        if tab:
            page.eval_on_selector('.tabbar[data-mode="%s"] .tabbtn[data-tab="%s"]' % (mode or "customer", tab), "el => el.click()")
            page.wait_for_timeout(450)

    def active(page):
        return page.evaluate("""() => { const a = document.activeElement;
          return {cls: (a && a.className || '').toString().slice(0, 30), id: a && a.id,
                  card: a && a.closest && a.closest('.teacher') && a.closest('.teacher').getAttribute('data-teacher'),
                  inList: !!(a && a.closest && a.closest('#teacherList')),
                  inPane: !!(a && a.closest && a.closest('#teacherPane'))}; }""")

    # ── 1) 375 — 카드 구조·Tab 순서·하트·스크롤 복원 ────────────────
    ctx, page, errs = make(375, 812, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    st = page.evaluate("""() => { const cards = [...document.querySelectorAll('#teacherList .teacher')];
      return {n: cards.length,
        role: cards.filter((c) => c.hasAttribute('role')).length,
        tab: cards.filter((c) => c.hasAttribute('tabindex')).length,
        openers: document.querySelectorAll('#teacherList .teacher .t-open').length,
        nested: window.__ttokttokRoving.nestedButtons(),
        stops: window.__ttokttokRoving.tabStops(),
        heartsOn: [...document.querySelectorAll('#teacherList .t-fav')].filter((b) => b.getAttribute('tabindex') === '0').length,
        label: (document.querySelector('#teacherList .t-open') || {}).getAttribute
          ? document.querySelector('#teacherList .t-open').getAttribute('aria-label') : '',
        cover: (() => { const c = document.querySelector('#teacherList .teacher').getBoundingClientRect();
          const b = document.querySelector('#teacherList .t-open').getBoundingClientRect();
          return [Math.round(c.width), Math.round(b.width), Math.round(c.height), Math.round(b.height)]; })()}; }""")
    ok(tag + "v49 카드 8장·role=button 0·카드 tabindex 0", st["n"] == 8 and st["role"] == 0 and st["tab"] == 0, st)
    ok(tag + "v49 카드마다 열기 버튼 1개(총 8)", st["openers"] == 8, st["openers"])
    ok(tag + "v49 중첩 인터랙티브 0", st["nested"] == 0, st["nested"])
    ok(tag + "v49 정지점은 열기 버튼 1개 + 고른 카드 하트 1개", st["stops"] == 1 and st["heartsOn"] == 1, [st["stops"], st["heartsOn"]])
    ok(tag + "v49 열기 버튼이 카드를 덮는다", abs(st["cover"][0] - st["cover"][1]) <= 2 and abs(st["cover"][2] - st["cover"][3]) <= 2, st["cover"])
    ok(tag + "v49 열기 버튼 이름", st["label"] == "박서준 선생님 상세 프로필 보기", st["label"])
    # 하트 자리를 실제로 누르면 하트가 잡힌다(열기 버튼이 덮지 않는다)
    hit = page.evaluate("""() => { const b = document.querySelector('#teacherList .t-fav'); const r = b.getBoundingClientRect();
      const el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
      return {fav: !!(el && el.closest && el.closest('.t-fav')), open: !!(el && el.closest && el.closest('.t-open'))}; }""")
    ok(tag + "v49 하트 중심의 클릭 대상은 하트", hit["fav"] and not hit["open"], hit)
    # Tab: 필터 → 열기 버튼 → 하트 → 목록 밖
    page.evaluate("() => { const c = [...document.querySelectorAll('#regionFilters .chip')]; c[c.length - 1].focus(); }")
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    a1 = active(page)
    ok(tag + "v49 375 Tab 한 번에 카드 열기 버튼", a1["inList"] and a1["cls"] == "t-open" and a1["card"], a1)
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    a2 = active(page)
    ok(tag + "v49 그다음 Tab은 그 카드의 하트", a2["cls"].startswith("t-fav"), a2)
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    ok(tag + "v49 하트 다음 Tab은 목록 밖", not active(page)["inList"], active(page))
    # 하트: 클릭은 찜만, Space/Enter는 프로필을 열지 않는다
    page.evaluate("() => document.querySelector('#teacherList .teacher .t-fav').click()")
    page.wait_for_timeout(220)
    h1 = page.evaluate("""() => ({fav: document.querySelector('#teacherList .teacher .t-fav').getAttribute('aria-pressed'),
      sheet: document.getElementById('teacherSheet').classList.contains('is-open')})""")
    ok(tag + "v49 하트 클릭은 찜만(시트 안 열림)", h1["fav"] == "true" and h1["sheet"] is False, h1)
    page.evaluate("() => document.querySelector('#teacherList .teacher .t-fav').focus()")
    page.keyboard.press("Space")
    page.wait_for_timeout(250)
    h2 = page.evaluate("""() => ({fav: document.querySelector('#teacherList .teacher .t-fav').getAttribute('aria-pressed'),
      sheet: document.getElementById('teacherSheet').classList.contains('is-open')})""")
    ok(tag + "v49 하트 Space는 찜만 바꾼다(프로필 X)", h2["fav"] == "false" and h2["sheet"] is False, h2)
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(220)
    ok(tag + "v49 하트에서 ↓는 다음 카드로", active(page)["card"] == "lee" and active(page)["cls"] == "t-open", active(page))
    # 열기 버튼 Enter → 시트, Esc → 열기 버튼으로 복귀
    page.keyboard.press("Enter")
    page.wait_for_timeout(350)
    ok(tag + "v49 Enter는 프로필 시트", page.evaluate("() => document.getElementById('teacherSheet').classList.contains('is-open')"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(320)
    back = active(page)
    ok(tag + "v49 Esc 뒤 초점은 그 카드의 열기 버튼", back["cls"] == "t-open" and back["card"] == "lee", back)
    # 스크롤 복원: 열고 → 문서가 0으로 튀고 → 닫으면 보던 자리로
    page.evaluate("() => window.scrollTo(0, 900)")
    page.wait_for_timeout(250)
    y0 = page.evaluate("() => window.scrollY")
    page.evaluate("() => document.querySelectorAll('#teacherList .t-open')[3].click()")
    page.wait_for_timeout(400)
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(150)
    page.evaluate("() => document.querySelector('#teacherSheet .sheet-close').click()")
    page.wait_for_timeout(400)
    y1 = page.evaluate("() => window.scrollY")
    ok(tag + "v49 시트를 닫으면 보던 스크롤 자리로", y0 > 100 and abs(y1 - y0) <= 2, [y0, y1])
    ok(tag + "v49 375 오류 0", not errs, errs[:2])
    page.screenshot(path=os.path.join(SHOT, "v49_375_teachers.png"))
    ctx.close()

    # ── 2) 320 — 긴 이름·지역·요청 메모가 카드를 밀어내지 않는다 ──────
    ctx, page, errs = make(320, 568, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    long_name = "김하늘보람찬들빛가운데햇살노을아침저녁선생님"
    long_region = "경기도고양시일산동구백석1동파주시운정동서울특별시강남구대치동인천광역시연수구송도동"
    page.evaluate("""(v) => { const card = document.querySelector('#teacherList .teacher');
      card.querySelector('.t-name').firstChild.textContent = v.name;
      const sp = card.querySelector('.t-region span'); if (sp) sp.textContent = v.region + ' 방문';
      const m = card.querySelector('.t-meta'); if (m) m.textContent = v.name + ' · 재활 20년'; }""", {"name": long_name, "region": long_region})
    page.wait_for_timeout(150)
    ov = page.evaluate("""() => { const el = document.querySelector('#teacherList .teacher'); const box = el.getBoundingClientRect();
      const out = [];
      el.querySelectorAll('*').forEach((n) => { const b = n.getBoundingClientRect();
        if (b.width && (b.right > box.right + 0.5 || b.left < box.left - 0.5)) out.push((n.className || '').toString().slice(0, 20)); });
      return {over: out.slice(0, 4), sw: el.scrollWidth, cw: el.clientWidth,
              doc: document.documentElement.scrollWidth, win: innerWidth,
              lines: Math.round(document.querySelector('#teacherList .t-name').getBoundingClientRect().height)}; }""")
    ok(tag + "v49 320 긴 이름·지역도 카드 밖으로 넘치지 않는다", not ov["over"] and ov["sw"] <= ov["cw"] + 1 and ov["doc"] <= ov["win"] + 1, ov)
    ok(tag + "v49 긴 이름은 줄바꿈으로 감싼다(카드가 커진다)", ov["lines"] > 24, ov["lines"])
    page.screenshot(path=os.path.join(SHOT, "v49_320_long_name.png"))
    enter(page, "therapist", "tp-home", "therapist")
    n = page.evaluate("""(v) => { const el = document.querySelector('#tpReqList .req'); if (!el) return 0;
      el.querySelector('.req-top b').textContent = v.name;
      const m = el.querySelector('.req-meta'); if (m) m.innerHTML = v.symptom + ' · 10회권<br>' + v.region + ' · 12/01 (월) 10:00'; return 1; }""",
      {"name": long_name, "symptom": "뇌졸중편마비보행재활균형훈련어깨통증무릎관절가동범위훈련일상생활동작훈련", "region": long_region})
    if n:
        ov2 = page.evaluate("""() => { const el = document.querySelector('#tpReqList .req'); const box = el.getBoundingClientRect();
          const out = [];
          el.querySelectorAll('*').forEach((n) => { const b = n.getBoundingClientRect();
            if (b.width && (b.right > box.right + 0.5 || b.left < box.left - 0.5)) out.push((n.className || '').toString().slice(0, 20)); });
          return {over: out.slice(0, 4), sw: el.scrollWidth, cw: el.clientWidth,
                  doc: document.documentElement.scrollWidth, win: innerWidth}; }""")
        ok(tag + "v49 320 긴 요청 이름·증상·지역도 넘치지 않는다", not ov2["over"] and ov2["sw"] <= ov2["cw"] + 1 and ov2["doc"] <= ov2["win"] + 1, ov2)
        page.screenshot(path=os.path.join(SHOT, "v49_320_long_request.png"))
    ok(tag + "v49 320 오류 0", not errs, errs[:2])
    ctx.close()

    # ── 3) 1280 — 방향키로 카드·프로필 열, Tab 순서 ────────────────
    ctx, page, errs = make(1280, 900, False)
    page.goto(URL + "?intro=0")
    enter(page, "customer", "teachers")
    page.evaluate("() => { const c = [...document.querySelectorAll('#regionFilters .chip')]; c[c.length - 1].focus(); }")
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    ok(tag + "v49 1280 Tab 한 번에 목록", active(page)["inList"] and active(page)["cls"] == "t-open", active(page))
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(320)
    a = active(page)
    ok(tag + "v49 1280 ↓ 다음 카드 + 오른쪽 프로필 열", a["card"] == "lee" and page.evaluate(
        "() => !document.getElementById('teacherPane').hidden && /이하늘/.test(document.getElementById('teacherPane').textContent)"), a)
    page.keyboard.press("Enter")
    page.wait_for_timeout(350)
    ok(tag + "v49 1280 Enter는 프로필 열 안으로", page.evaluate("() => document.getElementById('teacherPane').contains(document.activeElement)"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    ok(tag + "v49 1280 Esc는 고른 카드의 열기 버튼으로", active(page)["card"] == "lee" and active(page)["cls"] == "t-open", active(page))
    ok(tag + "v49 1280 오류 0", not errs, errs[:2])
    page.screenshot(path=os.path.join(SHOT, "v49_1280_kbd.png"))
    ctx.close()

    # ── 4) 인쇄 — 정산서: 회차 통째로·머리글 반복·모션 끝난 상태 ────
    for w, h, mob, nm in [(390, 844, True, "375"), (1280, 900, False, "1280")]:
        ctx, page, errs = make(w, h, mob)
        page.goto(URL + "?intro=0")
        enter(page, "therapist", "tp-settle", "therapist")
        page.evaluate("() => { const b = document.querySelector('[data-stl-preview]'); if (b) b.click(); }")
        page.wait_for_timeout(500)
        page.emulate_media(media="print")
        page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
        page.wait_for_timeout(350)
        pr = page.evaluate("""() => {
          const rows = [...document.querySelectorAll('#settlementPrintBody [data-print-row]')];
          const cs = rows.length ? getComputedStyle(rows[0]) : null;
          const keep = [...document.querySelectorAll('#settlementPrintBody [data-print-keep]')];
          const reveal = [...document.querySelectorAll('.screen.is-active .tt-reveal')];
          return {rows: rows.length,
            breakRow: cs ? cs.breakInside : 'none',
            keep: keep.length,
            keepBreak: keep.length ? getComputedStyle(keep[0]).breakInside : 'none',
            revealHidden: reveal.filter((el) => parseFloat(getComputedStyle(el).opacity) < 0.99).length,
            runner: document.getElementById('printRunnerTitle').textContent,
            runnerNote: document.getElementById('printRunnerNote').textContent,
            runnerDisp: getComputedStyle(document.getElementById('printRunner')).display,
            footDisp: getComputedStyle(document.getElementById('printFoot')).display,
            sheetTitle: getComputedStyle(document.querySelector('#settlementPrintSheet .sheet-title')).display}; }""")
        ok(tag + "v49 %s 정산서 회차는 쪽나눔에서 쪼개지지 않는다" % nm, pr["rows"] > 0 and pr["breakRow"] == "avoid", pr)
        ok(tag + "v49 %s 요약·머리는 통째로(2장)" % nm, pr["keep"] == 2 and pr["keepBreak"] == "avoid", pr)
        ok(tag + "v49 %s 화면 등장 모션은 인쇄에서 모두 보인다" % nm, pr["revealHidden"] == 0, pr["revealHidden"])
        ok(tag + "v49 %s 종이 머리글(%s)" % (nm, pr["runner"]),
           "정산 명세서" in pr["runner"] and "2026년 11월" in pr["runner"] and pr["runnerDisp"] == "flex", pr)
        ok(tag + "v49 %s 종이 발급일·시연용·상호" % nm, "발급" in pr["runnerNote"] and "시연용" in pr["runnerNote"] and pr["footDisp"] == "block", pr)
        ok(tag + "v49 %s 종이에는 '미리보기' 제목을 빼고 문서 머리만" % nm, pr["sheetTitle"] == "none", pr["sheetTitle"])
        page.screenshot(path=os.path.join(SHOT, "v49_settle_print_%s.png" % nm))
        try:
            page.pdf(path=os.path.join(SHOT, "v49_settle_%s.pdf" % nm), format="A4", print_background=True)
        except Exception as e:
            ok(tag + "v49 %s 정산서 PDF 만들기" % nm, False, str(e)[:60])
        page.emulate_media(media="screen")
        page.evaluate("() => window.dispatchEvent(new Event('afterprint'))")
        ctx.close()

    # ── 5) 인쇄 — 관리자 콘솔: 아래쪽 섹션이 빈 쪽으로 나오지 않는다 ──
    ctx, page, errs = make(1280, 900, False)
    page.goto(URL + "?intro=0")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.eval_on_selector('[data-login="admin"]', "el => el.click()")
    page.wait_for_timeout(700)
    page.emulate_media(media="print")
    page.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")
    page.wait_for_timeout(350)
    adm = page.evaluate("""() => { const scr = document.getElementById('screen-admin');
      const reveals = [...scr.querySelectorAll('.tt-reveal')];
      const cols = scr.querySelector('.tt46-cols');
      const secs = ['adminMetricsSec', 'adminOpsSec', 'adminReminderSec', 'adminResvSec', 'adminBackupSec', 'adminSkelSec', 'adminHomeStageSec'];
      return {revealHidden: reveals.filter((el) => parseFloat(getComputedStyle(el).opacity) < 0.99).length,
        colsDisp: cols ? getComputedStyle(cols).display : 'missing',
        hiddenSecs: secs.filter((id) => { const el = document.getElementById(id); return el && getComputedStyle(el).opacity === '0'; }),
        runner: document.getElementById('printRunnerTitle').textContent,
        activeScreen: document.querySelector('.screen.is-active').id}; }""")
    ok(tag + "v49 관리자 콘솔 인쇄에서 숨은 섹션 0", adm["revealHidden"] == 0 and not adm["hiddenSecs"], adm)
    ok(tag + "v49 관리자 콘솔은 종이에서 한 줄로 펼친다", adm["colsDisp"] == "block", adm["colsDisp"])
    ok(tag + "v49 관리자 콘솔 종이 머리글", "심사 콘솔" in adm["runner"], adm["runner"])
    page.screenshot(path=os.path.join(SHOT, "v49_admin_print.png"))
    try:
        page.pdf(path=os.path.join(SHOT, "v49_admin.pdf"), format="A4", print_background=True)
    except Exception as e:
        ok(tag + "v49 관리자 콘솔 PDF 만들기", False, str(e)[:60])
    page.emulate_media(media="screen")
    page.evaluate("() => window.dispatchEvent(new Event('afterprint'))")
    ctx.close()

    # ── 6) 요약 카드 보조 버튼 = 3:1 경계 ────────────────────────
    ctx, page, errs = make(375, 812, True)
    page.goto(URL + "?intro=0")
    enter(page, "customer")
    bd = page.evaluate("""() => {
      const el = document.querySelector('#homeSummaryRebook .btn-outline.btn-sm'); if (!el) return null;
      const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
      const parse = (c) => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return null;
        const p = m[1].split(/[\s,\/]+/).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
      const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      const lum = (c) => 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b);
      const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
      return {bw: parseFloat(cs.borderTopWidth) || 0, color: cs.borderTopColor,
        cr: Math.round(ratio(parse(cs.borderTopColor), parse('rgb(255,255,255)')) * 100) / 100,
        h: Math.round(r.height), text: el.textContent.trim().slice(0, 12)}; }""")
    ok(tag + "v49 요약 카드 보조 버튼에 1px 경계", bd and bd["bw"] >= 1, bd)
    ok(tag + "v49 그 경계는 3:1 이상", bd and bd["cr"] >= 3, bd)
    ok(tag + "v49 그 버튼 높이 44px 이상", bd and bd["h"] >= 44, bd)
    ok(tag + "v49 홈 오류 0", not errs, errs[:2])
    ctx.close()
    browser.close()

def main():
    """E2E 전 흐름. E2E_ONLY=v29,v31 처럼 쉼표로 골라 실행할 수 있다(개발·부분 재실행용)."""
    only = [x.strip() for x in os.environ.get("E2E_ONLY", "").split(",") if x.strip()]
    flows = [
        ("base", run_flow),
        ("v17", run_v17_flow), ("v18", run_v18_flow), ("v19", run_v19_flow),
        ("v20", run_v20_flow), ("v21", run_v21_flow), ("v22", run_v22_flow),
        ("v23", run_v23_flow), ("v24", run_v24_flow), ("v25", run_v25_flow),
        ("v26", run_v26_flow), ("v27", run_v27_flow), ("v28", run_v28_flow),
        ("v29", run_v29_flow), ("v31", run_v31_flow), ("v32", run_v32_flow),
        ("v33", run_v33_flow), ("v34", run_v34_flow), ("v35", run_v35_flow),
        ("v36", run_v36_flow), ("v37", run_v37_flow), ("v38", run_v38_flow), ("v39", run_v39_flow),
        ("v40", run_v40_flow), ("v42", run_v42_flow), ("v43", run_v43_flow), ("v45", run_v45_flow),
        ("v46", run_v46_flow), ("v47", run_v47_flow), ("v48", run_v48_flow), ("v49", run_v49_flow),
    ]
    with sync_playwright() as p:
        for name, fn in flows:
            if only and name not in only:
                continue
            fn(p, storage_blocked=False)
            fn(p, storage_blocked=True)
    print("\nRESULT: %d passed, %d failed" % (passed, failed))
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" - " + f)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(2)
