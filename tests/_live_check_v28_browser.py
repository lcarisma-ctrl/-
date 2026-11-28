#!/usr/bin/env python3
"""똑똑쌤 v28 라이브(GitHub Pages) 실브라우저 점검 — 관리자 운영 지표 대시보드.
실행: python3 tests/_live_check_v28_browser.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright

LIVE = "https://lcarisma-ctrl.github.io/-/?v=28"
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

        ok("v28 라이브 앱 버전", page.evaluate("() => document.querySelector('meta[name=app-version]').content") == "v28")
        ok("v28 라이브 부팅 오류 0", not errors, errors[:3])
        ok("v28 지표 모델 노출", page.evaluate("() => window.__ttokttokModel.adminMetricsVersion") == "v28" and
           page.evaluate("() => window.__ttokttokModel.metricsPeriods().length") == 3)

        page.evaluate("() => document.getElementById('entryGate').classList.add('is-open')")
        page.wait_for_timeout(150)
        page.eval_on_selector('[data-login="admin"]', "el => el.click()")
        page.wait_for_timeout(700)
        st = page.evaluate("() => window.__ttokttokModel.adminMetricsState()")
        ok("v28 운영 지표 섹션 렌더", page.is_visible("#adminMetricsSec") and st["kpiCards"] == 6, st["kpiCards"])
        ok("v28 기간 칩 3개(기본 전체)", len(st["chips"]) == 3 and st["period"] == "all", [c["text"] for c in st["chips"]])
        ok("v28 KPI 문구", "완료 전환율" in st["kpiText"] and "취소·노쇼율" in st["kpiText"] and
           "24시간 초과 미배정" in st["kpiText"] and "예상 플랫폼 마진" in st["kpiText"])
        ok("v28 퍼널·매출 렌더", "전체 신청" in st["funnelText"] and "보호자 결제" in st["revenueText"] and
           "플랫폼 마진" in st["revenueText"], [st["funnelText"][:40], st["revenueText"][:40]])
        ok("v28 지역·SLA 렌더", st["regionCards"] >= 1 and "매칭 대기 시간" in st["slaText"], st["regionText"][:60])
        ok("v28 로컬 데모 고지", "로컬 데모 계산" in st["noteText"], st["noteText"][:60])
        okk, why = overflow("metrics390")
        ok("v28 운영 지표 390px 넘침 없음", okk, why)
        page.screenshot(path=os.path.join(SHOT, "live_v28_admin_metrics.png"))

        all_sessions = st["sessions"]
        page.tap('#adminMetricsPeriods [data-metrics-period="7d"]')
        page.wait_for_timeout(420)
        st7 = page.evaluate("() => window.__ttokttokModel.adminMetricsState()")
        ok("v28 7일 칩 전환", st7["period"] == "7d" and "최근 7일" in st7["captionText"] and
           st7["sessions"] < all_sessions, [st7["sessions"], all_sessions])
        page.screenshot(path=os.path.join(SHOT, "live_v28_admin_metrics_7d.png"))
        page.tap('#adminMetricsPeriods [data-metrics-period="30d"]')
        page.wait_for_timeout(420)
        st30 = page.evaluate("() => window.__ttokttokModel.adminMetricsState()")
        ok("v28 30일 칩 전환", st30["period"] == "30d" and st7["sessions"] < st30["sessions"] < all_sessions,
           [st7["sessions"], st30["sessions"], all_sessions])
        page.tap('#adminMetricsPeriods [data-metrics-period="all"]')
        page.wait_for_timeout(320)

        page.tap("#adminMetricsCopyText")
        page.wait_for_timeout(320)
        hook = page.evaluate("() => window.__ttokttokMetricsCopy || {}")
        ok("v28 요약 텍스트 복사", hook.get("kind") == "text" and "[똑똑쌤 운영 지표]" in (hook.get("text") or ""))
        ok("v28 요약에 퍼널·지역 포함", "■ 예약 퍼널" in (hook.get("text") or "") and "■ 지역 수요·공급" in (hook.get("text") or ""))
        page.tap("#adminMetricsCopyCsv")
        page.wait_for_timeout(320)
        hook = page.evaluate("() => window.__ttokttokMetricsCopy || {}")
        ok("v28 지역 표 CSV 복사", hook.get("kind") == "csv" and (hook.get("text") or "").startswith("지표,값"))

        page.set_viewport_size({"width": 320, "height": 568})
        page.wait_for_timeout(420)
        okk, why = overflow("metrics320")
        ok("v28 운영 지표 320px 넘침 없음", okk, why)
        page.screenshot(path=os.path.join(SHOT, "live_v28_320_admin_metrics.png"))

        ok("v28 라이브 콘솔·페이지 오류 0", not errors, errors[:3])
        browser.close()

    print("\nLIVE v28 RESULT: %d passed, %d failed" % (passed, failed))
    for f in failures:
        print(" - " + f)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
