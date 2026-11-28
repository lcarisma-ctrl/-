#!/usr/bin/env python3
"""
똑똑쌤 v39 성능 측정 (Chromium, 로컬 file://)
─────────────────────────────────────────
· DOMContentLoaded / load / FCP / __ttokttokBooted(첫 화면 조작 가능)까지 시간
· 부팅 중 메인 스레드 차단(long task) 합계·최장
· DOM 노드 수, index.html 크기
· 5회 반복 → 중앙값. 선택: --runs N --json path
실행: python3 tests/_perf_v39.py
"""
import os
import sys
import json
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")

from playwright.sync_api import sync_playwright

URL = os.environ.get("TT_PERF_URL") or ("file://" + os.path.join(ROOT, "index.html"))

INIT_JS = """
(function () {
  window.__perf = { long: [], firstPaint: null };
  try {
    let booted = false;
    Object.defineProperty(window, '__ttokttokBooted', {
      configurable: true,
      get() { return booted; },
      set(v) { if (v && !booted) { booted = true; window.__ttPerfBootedAt = performance.now(); } }
    });
  } catch (e) {}
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__perf.long.push(Math.round(e.duration));
    }).observe({ type: 'longtask', buffered: true });
  } catch (e) {}
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) {
        if (e.name === 'first-contentful-paint' && window.__perf.firstPaint == null) {
          window.__perf.firstPaint = Math.round(e.startTime);
        }
      }
    }).observe({ type: 'paint', buffered: true });
  } catch (e) {}
})();
"""

READ_JS = """
() => {
  const n = performance.getEntriesByType('navigation')[0] || {};
  const p = performance.getEntriesByType('paint') || [];
  const fcp = p.find((x) => x.name === 'first-contentful-paint');
  const booted = window.__ttPerfBootedAt || null;
  const long = (window.__perf && window.__perf.long) || [];
  return {
    dcl: Math.round(n.domContentLoadedEventEnd || 0),
    load: Math.round(n.loadEventEnd || 0),
    responseEnd: Math.round(n.responseEnd || 0),
    fcp: fcp ? Math.round(fcp.startTime) : null,
    booted: booted == null ? null : Math.round(booted),
    longCount: long.length,
    longTotal: long.reduce((a, b) => a + b, 0),
    longMax: long.length ? Math.max.apply(null, long) : 0,
    nodes: document.getElementsByTagName('*').length,
    size: (() => { try { return document.documentElement.outerHTML.length; } catch (e) { return 0; } })()
  };
}
"""


def run_once(browser, blocked=False):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    if blocked:
        ctx.add_init_script("""
          Object.defineProperty(window, 'localStorage', { configurable: true,
            get() { throw new DOMException('SecurityError', 'SecurityError'); } });
        """)
    page = ctx.new_page()
    page.add_init_script(INIT_JS)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(URL, wait_until="load")
    page.wait_for_function("window.__ttokttokBooted === true", timeout=15000)
    page.wait_for_timeout(400)  # idle work (rIC) settles
    m = page.evaluate(READ_JS)
    m["errors"] = errors
    # 눈에 보이는 첫 화면 텍스트(체감 확인)
    m["homeText"] = page.evaluate("() => (document.querySelector('#screen-home')||{}).innerText ? document.querySelector('#screen-home').innerText.slice(0,80) : ''")
    ctx.close()
    return m


def main():
    runs = 5
    args = sys.argv[1:]
    if "--runs" in args:
        runs = int(args[args.index("--runs") + 1])
    out = {"url": URL, "runs": []}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        run_once(browser)  # warm-up (파일 캐시·브라우저 준비) — 측정에서 제외
        for i in range(runs):
            m = run_once(browser)
            m["i"] = i + 1
            out["runs"].append(m)
            print("run %d: DCL %sms · load %sms · FCP %sms · booted %sms · long %d/%dms(max %d) · nodes %d · errors %d"
                  % (i + 1, m["dcl"], m["load"], m["fcp"], m["booted"], m["longCount"], m["longTotal"], m["longMax"], m["nodes"], len(m["errors"])))
        blocked = run_once(browser, blocked=True)
        out["blocked"] = blocked
        print("storage-blocked: DCL %sms · booted %sms · errors %d" % (blocked["dcl"], blocked["booted"], len(blocked["errors"])))
        browser.close()

    def med(key):
        vals = [r[key] for r in out["runs"] if r.get(key) is not None]
        return statistics.median(vals) if vals else None

    summary = {
        "runs": runs,
        "dclMedian": med("dcl"), "loadMedian": med("load"), "fcpMedian": med("fcp"),
        "bootedMedian": med("booted"),
        "longTotalMedian": med("longTotal"), "longMaxMedian": med("longMax"),
        "nodes": out["runs"][0]["nodes"],
        "bytes": os.path.getsize(os.path.join(ROOT, "index.html")),
        "errors": sum(len(r["errors"]) for r in out["runs"]),
        "blocked": {"dcl": blocked["dcl"], "booted": blocked["booted"], "errors": blocked["errors"]},
    }
    out["summary"] = summary
    print("\n== 중앙값 ==")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    path = os.path.join(ROOT, "tests", "perf-v39.json")
    if "--json" in args:
        path = args[args.index("--json") + 1]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("saved:", path)


if __name__ == "__main__":
    main()
