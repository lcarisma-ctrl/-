#!/usr/bin/env python3
"""v34 라이브 확인 — 배경 inert·Tab 트랩·초점 복귀·이름 전수·aria-live(실서비스 URL)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright  # noqa: E402

URL = "https://lcarisma-ctrl.github.io/-/?v=34"
SHOT = os.path.join(ROOT, "preview")
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
        for (w, h, mob) in [(320, 568, True), (375, 812, True), (1280, 800, False)]:
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mob else 1,
                                      is_mobile=mob, has_touch=mob, locale="ko-KR")
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
            page.goto(URL, wait_until="load")
            page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
            page.wait_for_timeout(500)
            A = lambda expr: page.evaluate("() => window.__ttokttokModel.a11y." + expr)  # noqa: E731
            ok("live %d 앱 버전 v34" % w, page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v34")
            ok("live %d 게이트 열림 — 최상위·배경 잠금" % w,
               A("topDialog()") == "#entryGate" and A("backgroundLocked()") is True)
            ok("live %d 배경 #appRoot inert+aria-hidden" % w,
               page.evaluate("() => { const a = document.getElementById('appRoot'); return a.hasAttribute('inert') && a.getAttribute('aria-hidden') === 'true'; }"))
            for _ in range(9):
                page.keyboard.press("Tab")
            ok("live %d 게이트 안에서 Tab 순환" % w,
               page.evaluate("() => document.getElementById('entryGate').contains(document.activeElement)"))
            page.screenshot(path=os.path.join(SHOT, "live_v34_%d_gate.png" % w))
            page.eval_on_selector('[data-login="customer"]', "el => el.click()")
            page.wait_for_timeout(520)
            ok("live %d 로그인 뒤 잠금 해제" % w,
               A("backgroundLocked()") is False and page.evaluate("() => document.getElementById('appRoot').getAttribute('aria-hidden')") is None)
            aud = A("auditAll()")
            ok("live %d 조작 요소 %d개 이름 누락 0" % (w, aud["total"]),
               aud["blank"] == [] and aud["iconNoLabel"] == [] and aud["unlabeledFields"] == [], str(aud)[:120])
            # 선생님 시트 → 트랩 → 닫고 초점 복귀
            page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el => el.click()")
            page.wait_for_timeout(400)
            page.eval_on_selector("#teacherList .teacher", "el => el.click()")
            page.wait_for_timeout(460)
            ok("live %d 선생님 시트 — 최상위·배경 잠금" % w,
               A("topDialog()") == "#teacherSheet" and A("backgroundLocked()") is True)
            seq = []
            for _ in range(10):
                page.keyboard.press("Tab")
                seq.append(page.evaluate("() => document.getElementById('teacherSheet').contains(document.activeElement)"))
            ok("live %d 시트 안에서 Tab 순환(10회)" % w, all(seq), seq)
            page.keyboard.press("Shift+Tab")
            ok("live %d Shift+Tab도 시트 안" % w,
               page.evaluate("() => document.getElementById('teacherSheet').contains(document.activeElement)"))
            ok("live %d 시트 이름 감사 0" % w, A("auditAll()")["blank"] == [] and A("auditAll()")["iconNoLabel"] == [])
            page.screenshot(path=os.path.join(SHOT, "live_v34_%d_teacher_sheet.png" % w))
            page.keyboard.press("Escape")
            page.wait_for_timeout(420)
            ok("live %d Escape → 닫힘·잠금 해제" % w,
               A("backgroundLocked()") is False and
               page.evaluate("() => !document.getElementById('teacherSheet').classList.contains('is-open')"))
            ok("live %d 닫힌 뒤 초점이 카드로" % w,
               page.evaluate("() => !!document.activeElement && document.activeElement.classList.contains('teacher')"),
               page.evaluate("() => document.activeElement && (document.activeElement.id || document.activeElement.className)"))
            m = page.evaluate("() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})")
            ok("live %d 가로 넘침 없음" % w, m["sw"] <= m["cw"] + 1, m)
            ok("live %d JS 오류 없음" % w, not errors, errors[:2])
            page.screenshot(path=os.path.join(SHOT, "live_v34_%d_home.png" % w))
            ctx.close()

        # ara-live 정리 확인(375)
        ctx = browser.new_context(viewport={"width": 375, "height": 812}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True, locale="ko-KR")
        page = ctx.new_page()
        page.goto(URL, wait_until="load")
        page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
        page.wait_for_timeout(500)
        page.eval_on_selector('[data-login="customer"]', "el => el.click()")
        page.wait_for_timeout(460)
        ok("live 알림 띠 컨테이너 aria-live 없음",
           page.evaluate("() => { const h = document.getElementById('ttAlertHost'); return h.getAttribute('aria-live') === null && h.getAttribute('role') === null; }"))
        r = page.evaluate("""() => {
          document.getElementById('homeGuideBtn').click();
          return new Promise((res) => setTimeout(() => {
            const V = window.__ttokttokV32;
            V.simulateStorageFailure(true); V.saveAccountNow();
            setTimeout(() => {
              const out = {live: document.getElementById('a11yLive').textContent,
                           bandInert: !!document.getElementById('ttAlertHost').closest('[inert]')};
              V.simulateStorageFailure(false);
              res(out);
            }, 160);
          }, 260));
        }""")
        ok("live 시트 열림 → 저장 실패가 낭독 영역으로 1회", r["bandInert"] and "저장하지 못했어요" in r["live"], r["live"][:40])
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        ok("live 낭독 영역은 잠금 밖", page.evaluate("() => !document.getElementById('a11yLive').closest('[inert]')"))
        ok("live <style> 144,471자 유지", page.evaluate("() => { const m = document.documentElement.innerHTML.match(/<style>([\\s\\S]*?)<\\/style>/); return m ? m[1].length : -1; }") == 144471)
        ctx.close()
        browser.close()

    print("\nLIVE RESULT: %d passed, %d failed" % (passed, failed))
    for f in fails:
        print(" - " + f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
