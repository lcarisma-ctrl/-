#!/usr/bin/env python3
"""
똑똑쌤 v40 라이브 확인 (Chromium)
· https://lcarisma-ctrl.github.io/-/?v=40 이 v40 빌드를 실제로 서빙하는지
  (HTTP 200 · 바이트 수 · md5 · meta app-version)를 보고,
· 라이브에서 날짜·요일·방문 카드·390/320/1280 레이아웃·오류를 확인한다.
· 실행: python3 tests/live_check_v40.py
"""
import os
import sys
import json
import hashlib
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ.get("LD_LIBRARY_PATH", ""))

from playwright.sync_api import sync_playwright

LIVE = "https://lcarisma-ctrl.github.io/-/?v=40"
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
    req = urllib.request.Request(url, headers={"User-Agent": "ttokttok-live-check/v40", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


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
    if (r.width < 1 || r.height < 1 || getComputedStyle(el).display === 'none' || el.children.length) return;
    const t = (el.textContent || '').trim();
    if (!t || t.length > 80) return;
    let mm; re.lastIndex = 0;
    while ((mm = re.exec(t))) { const d = near(+mm[1], +mm[2]); if (!d) continue;
      if (WD[d.getDay()] !== mm[3]) out.push(mm[0] + '→' + WD[d.getDay()]); }
  });
  return Array.from(new Set(out));
}"""


def main():
    local = open(LOCAL, "rb").read()
    local_md5 = hashlib.md5(local).hexdigest()
    print("local index.html: %d bytes · md5 %s" % (len(local), local_md5))

    st, body = http(LIVE)
    ok("v40 HTTP 200", st == 200, st)
    ok("v40 바이트 수가 로컬과 같다", len(body) == len(local), "%d/%d" % (len(body), len(local)))
    ok("v40 md5가 로컬과 같다", hashlib.md5(body).hexdigest() == local_md5, hashlib.md5(body).hexdigest())
    ok("v40 meta app-version", b'<meta name="app-version" content="v40">' in body)
    for v in ("39", "38", "37", "36", "25", "10"):
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
            page.wait_for_function("window.__ttokttokBooted === true", timeout=30000)
            page.wait_for_timeout(400)
            s = page.evaluate("() => window.__ttokttokPerf.stats()")
            results[label] = s
            ok("[%s] 부트 완료·유휴 렌더 22/22" % label,
               s["deferredTotal"] == 22 and s["deferredRendered"] == 22 and s["pending"] == 0, s["deferredTotal"])
            ok("[%s] 첫 화면(게이트·홈 요약)" % label,
               page.evaluate("() => !!document.querySelector('#entryGate.is-open')") and
               "다음 방문" in page.inner_text("#homeSummaryCard"))
            ok("[%s] 가로 넘침 0" % label,
               page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"))

            # 오늘 +2일 = 다음 방문 (라이브는 실제 오늘이 기준)
            nx = page.evaluate("""() => { const d = new Date(); d.setDate(d.getDate() + 2);
                const WD = ['일','월','화','수','목','금','토'];
                const p2 = n => (n < 10 ? '0' + n : '' + n);
                return {label: (d.getMonth() + 1) + '.' + p2(d.getDate()), wd: WD[d.getDay()],
                        long: (d.getMonth() + 1) + '월 ' + d.getDate() + '일 (' + WD[d.getDay()] + ')'}; }""")
            home = page.inner_text("#homeSummaryCard")
            ok("[%s] 홈 다음 방문 요일 달력 일치" % label, ("%s (%s)" % (nx["label"], nx["wd"])) in home,
               home.replace("\n", " ")[:100])

            page.eval_on_selector('[data-login="demo"]', "el => el.click()")
            page.wait_for_timeout(400)
            page.eval_on_selector('.tabbar[data-mode="customer"] .tabbtn[data-tab="journal"]', "el => el.click()")
            page.wait_for_timeout(450)
            chip = page.inner_text("#todayChip")
            ok("[%s] 일지 방문 카드 날짜·요일" % label, nx["long"] in chip, chip)
            ok("[%s] 일지 카드 다음 방문 표기" % label, "다음 방문" in chip, chip)
            ok("[%s] 보호자 날짜-요일 불일치 0" % label, page.evaluate(AUDIT) == [], page.evaluate(AUDIT)[:4])
            if label == "390":
                page.screenshot(path=os.path.join(SHOT, "live_v40_390_journal.png"))
                page.eval_on_selector('[data-login="therapist"]', "el => el.click()")
                page.wait_for_timeout(500)
                page.eval_on_selector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-schedule"]', "el => el.click()")
                page.wait_for_timeout(400)
                sched = page.inner_text("#screen-tp-schedule")
                today_wd = page.evaluate("() => ['일','월','화','수','목','금','토'][new Date().getDay()]")
                ok("[390] 선생님 일정 오늘 요일", ("오늘 (%s)" % today_wd) in sched, sched.replace("\n", " ")[:120])
                ok("[390] 선생님 날짜-요일 불일치 0", page.evaluate(AUDIT) == [], page.evaluate(AUDIT)[:4])
                page.screenshot(path=os.path.join(SHOT, "live_v40_390_tp_schedule.png"))
                page.eval_on_selector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-home"]', "el => el.click()")
                page.wait_for_timeout(350)
                ok("[390] 정산 차트 18.8만", "18.8만" in page.inner_text(".settle-chart"))
                page.eval_on_selector('.tabbar[data-mode="therapist"] .tabbtn[data-tab="tp-home"]', "el => el.click()")
                page.wait_for_timeout(200)
                page.screenshot(path=os.path.join(SHOT, "live_v40_390_tp_home.png"))
            elif label == "320":
                page.screenshot(path=os.path.join(SHOT, "live_v40_320_journal.png"))
            else:
                page.screenshot(path=os.path.join(SHOT, "live_v40_1280_home.png"))
            ok("[%s] 오류 0" % label, not errs, errs[:2])
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
