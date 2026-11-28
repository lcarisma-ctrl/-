#!/usr/bin/env python3
"""
똑똑쌤 v39 라이브 확인 (Chromium)
· https://lcarisma-ctrl.github.io/-/?v=39 이 v39 빌드를 실제로 서빙하는지
  (HTTP 200 · 바이트 수 · md5 · meta app-version), 첫 화면·지연 렌더·성능 수치를 본다.
· 실행: python3 tests/live_check_v39.py
"""
import os
import sys
import json
import hashlib
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")

from playwright.sync_api import sync_playwright

LIVE = "https://lcarisma-ctrl.github.io/-/?v=39"
SHOT = os.path.join(ROOT, "preview")
LOCAL = os.path.join(ROOT, "index.html")

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


def http(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ttokttok-live-check/v39"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


def main():
    local = open(LOCAL, "rb").read()
    local_md5 = hashlib.md5(local).hexdigest()
    print("local index.html: %d bytes · md5 %s" % (len(local), local_md5))

    st, body = http(LIVE)
    ok("v39 HTTP 200", st == 200, st)
    ok("v39 바이트 수가 로컬과 같다", len(body) == len(local), "%d/%d" % (len(body), len(local)))
    ok("v39 md5가 로컬과 같다", hashlib.md5(body).hexdigest() == local_md5, hashlib.md5(body).hexdigest())
    ok("v39 meta app-version", b'<meta name="app-version" content="v39">' in body)
    ok("v39 일지 사진 lazy/async", body.count(b'loading="lazy" decoding="async"') == 4,
       str(body.count(b'loading="lazy" decoding="async"')))
    for v in ("38", "37", "36", "25", "10"):
        try:
            s2, _ = http("https://lcarisma-ctrl.github.io/-/?v=" + v)
        except Exception as e:
            s2 = "err:" + str(e)
        ok("이전 ?v=%s도 열린다" % v, s2 == 200, s2)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
        results = {}
        for label, w, h in (("390", 390, 844), ("320", 320, 568), ("1280", 1280, 800)):
            ctx = browser.new_context(viewport={"width": w, "height": h}, locale="ko-KR",
                                      is_mobile=(w < 700), has_touch=(w < 700),
                                      device_scale_factor=2 if w < 700 else 1)
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
            page.goto(LIVE)
            page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
            page.wait_for_timeout(300)
            s = page.evaluate("() => window.__ttokttokPerf.stats()")
            results[label] = s
            ok("[%s] 부트 완료·유휴 렌더 22/22" % label,
               s["deferredTotal"] == 22 and s["deferredRendered"] == 22 and s["pending"] == 0, json.dumps(s["deferredTotal"]))
            ok("[%s] 유휴 청크 모드" % label, s["mode"] == "idle-chunked", s["mode"])
            ok("[%s] DCL 기록·부팅 완료 시각" % label, s["dcl"] and s["bootedAt"] and s["dcl"] <= 1200,
               "%s/%s" % (s["dcl"], s["bootedAt"]))
            ok("[%s] 첫 화면(게이트·홈 요약)" % label,
               page.evaluate("() => !!document.querySelector('#entryGate.is-open')") and
               "다음 방문" in page.inner_text("#homeSummaryCard"))
            ok("[%s] 선생님 목록 8명" % label,
               page.eval_on_selector_all("#teacherList [data-teacher]", "els => els.length") == 8)
            ok("[%s] 오류 0" % label, not errs, errs[:2])
            if label == "390":
                page.eval_on_selector('[data-login="demo"]', "el => el.click()")
                page.wait_for_timeout(300)
                page.screenshot(path=os.path.join(SHOT, "live_v39_390_home.png"))
                page.eval_on_selector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]', "el => el.click()")
                page.wait_for_timeout(250)
                page.screenshot(path=os.path.join(SHOT, "live_v39_390_teachers.png"))
                ok("v39 라이브 선생님 탭 8명",
                   page.eval_on_selector_all("#teacherList [data-teacher]", "els => els.length") == 8)
            elif label == "320":
                page.screenshot(path=os.path.join(SHOT, "live_v39_320_gate.png"))
            else:
                page.screenshot(path=os.path.join(SHOT, "live_v39_1280_gate.png"))
            ctx.close()
        browser.close()

    print("\n성능(라이브): " + " · ".join(
        "%s DCL %sms FCP %sms" % (k, v["dcl"], v["fcp"]) for k, v in results.items()))
    print("\nRESULT: %d passed, %d failed" % (passed, failed))
    for f in failures:
        print(" - " + f)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
