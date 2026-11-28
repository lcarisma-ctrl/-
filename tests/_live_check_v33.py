import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

URL = "https://lcarisma-ctrl.github.io/-/?v=33"
SHOT = os.path.join(ROOT, "preview")
EMPTY = json.dumps({"passes": [], "bookings": [], "receipts": [], "sessions": [], "myReviews": [], "profile": {"name": "현수"}}, ensure_ascii=False)
passed, failed, fails = 0, 0, []


def ok(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print("  ✓ " + name)
    else:
        failed += 1
        fails.append(name + (" :: " + str(extra) if extra else ""))
        print("  ✗ " + name + ((" :: " + str(extra)) if extra else ""))


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
        # ── 1) 첫 방문 전 홈 (빈 계정) 320/375/1280
        for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                      is_mobile=mob, has_touch=mob, locale="ko-KR")
            ctx.add_init_script("try{localStorage.setItem('ttokttok_account_v3', %s);}catch(e){}" % json.dumps(EMPTY))
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
            page.goto(URL, wait_until="load")
            page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
            page.wait_for_timeout(500)
            ok("live %d 앱 버전 v33" % w, page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v33")
            ok("live %d 홈 분기 모델 v33" % w,
               page.evaluate("() => window.__ttokttokModel.guardianHomeVersion") == "v33" and
               page.evaluate("() => window.__ttokttokModel.qaVersion") == "v33")
            page.eval_on_selector('[data-login="customer"]', "el => el.click()")
            page.wait_for_timeout(520)
            st = page.evaluate("() => window.__ttokttokModel.homeStageState()")
            ok("live %d 첫 방문 안내가 첫 카드(요약은 접힘)" % w,
               st["firstCardVisible"] and not st["summaryVisible"] and st["firstElement"] == "homeFirstVisitCard",
               json.dumps(st, ensure_ascii=False)[:110])
            ok("live %d 안내 카드 내용(가치 3·순서·CTA 2)" % w,
               len(st["points"]) == 3 and "15분 평가" in st["steps"] and st["ctas"] == ["무료 평가 신청", "선생님 둘러보기"])
            ok("live %d 중복 공지 접힘" % w, page.eval_on_selector("#homeNotice", "el => el.hidden"))
            m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
            ok("live %d 가로 넘침 없음" % w, m["sw"] <= m["cw"] + 1, m)
            ok("live %d 감사 위반 0" % w, page.evaluate("() => window.__ttokttokUI.audit().length") == 0)
            ok("live %d JS 오류 없음" % w, not errors, errors[:2])
            page.screenshot(path=os.path.join(SHOT, "live_v33_%d_first_visit.png" % w))
            page.eval_on_selector('#homeFirstVisitCard [data-book="eval"]', "el => el.click()")
            page.wait_for_timeout(420)
            ok("live %d 무료 평가 신청 → 예약 1단계" % w,
               page.evaluate("() => document.querySelector('#screen-booking').classList.contains('is-active')") and
               page.evaluate("() => window.__ttokttokModel.bookingFormState().passId") == "eval")
            ctx.close()

        # ── 2) 이용 중(기본 시드) + 관리자 미리보기
        ctx = browser.new_context(viewport={"width": 375, "height": 812}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True, locale="ko-KR")
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
        page.goto(URL, wait_until="load")
        page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
        page.wait_for_timeout(500)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(480)
        st = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok("live 375 이용 중 — 요약 카드가 첫 카드", st["summaryVisible"] and not st["firstCardVisible"] and
           st["firstElement"] == "homeSummaryCard")
        ok("live 375 시드 예약 요약 유지", "TT-261021-7302" in page.evaluate("() => document.querySelector('#homeSummaryNext').innerText"))
        page.screenshot(path=os.path.join(SHOT, "live_v33_375_active_home.png"))
        page.evaluate("() => { const g = document.getElementById('entryGate'); if (g) g.classList.add('is-open'); }")
        page.wait_for_timeout(200)
        page.eval_on_selector('[data-login="admin"]', "el => el.click()")
        page.wait_for_timeout(520)
        ok("live 375 관리자 「홈 화면 미리보기」 카드",
           page.is_visible("#adminHomeStageSec") and "이용 중" in page.inner_text("#adminHomeStageNow"))
        page.eval_on_selector("#adminStageFirst", "el => el.click()")
        page.wait_for_timeout(560)
        st2 = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok("live 375 미리보기 — 첫 방문 안내 + 데이터 그대로",
           st2["firstCardVisible"] and st2["noteVisible"] and st2["preview"] == "first" and
           page.evaluate("() => window.__ttokttokModel.guardianHome().counts.bookings") == 2)
        page.screenshot(path=os.path.join(SHOT, "live_v33_375_preview_first.png"))
        page.eval_on_selector("#homeStagePreviewNote", "el => el.click()")
        page.wait_for_timeout(420)
        st3 = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok("live 375 미리보기 끄기 → 이용 중 홈", st3["summaryVisible"] and not st3["noteVisible"])
        ok("live 375 JS 오류 없음", not errors, errors[:2])
        ctx.close()

        # ── 3) ?stage=first 주소 미리보기
        ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True, locale="ko-KR")
        page = ctx.new_page()
        page.goto(URL + "&stage=first", wait_until="load")
        page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
        page.wait_for_timeout(460)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(420)
        st = page.evaluate("() => window.__ttokttokModel.homeStageState()")
        ok("live ?stage=first — 미리보기 분기", st["preview"] == "first" and st["firstCardVisible"] and
           page.evaluate("() => window.__ttokttokModel.guardianHome().actualStage") == "active")
        ctx.close()
        browser.close()
    print("\nLIVE V33 RESULT: %d passed, %d failed" % (passed, failed))
    for f in fails:
        print(" - " + f)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
