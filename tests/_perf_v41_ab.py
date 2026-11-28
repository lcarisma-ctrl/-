#!/usr/bin/env python3
"""v42 A/B 성능 — v41(대조군) vs v42(현재) DCL·부팅·long task를 번갈아 3회 측정해 중앙값 비교."""
import os, json, statistics
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = {"v41": os.path.join(ROOT, ".work", "index_v41.html"), "v42": os.path.join(ROOT, "index.html")}

INIT = """
(function(){
  try{ new PerformanceObserver((l)=>{ for(const e of l.getEntries()) (window.__lt=window.__lt||[]).push(Math.round(e.duration)); })
    .observe({type:'longtask', buffered:true}); }catch(e){}
})();
"""

JS = """() => {
  const n = performance.getEntriesByType('navigation')[0] || {};
  return {dcl: Math.round(n.domContentLoadedEventEnd||0), load: Math.round(n.loadEventEnd||0),
          booted: Math.round(window.__ttPerfBootedAt||0), long: (window.__lt||[]).reduce((a,b)=>a+b,0)};
}"""

res = {"v41": [], "v42": []}
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
    for _ in range(7):
        for k, path in FILES.items():
            ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, locale="ko-KR")
            ctx.add_init_script(INIT)
            ctx.add_init_script("""
              (function(){ let b=false; Object.defineProperty(window,'__ttokttokBooted',{configurable:true,
                get(){return b;}, set(v){ if(v&&!b){b=true; window.__ttPerfBootedAt=performance.now();} }}); })();
            """)
            pg = ctx.new_page()
            pg.goto("file://" + path)
            pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000)
            pg.wait_for_timeout(200)
            res[k].append(pg.evaluate(JS))
            pg.close(); ctx.close()
    b.close()

med = lambda k, f: round(statistics.median([r[f] for r in res[k]]))
out = {k: {f: med(k, f) for f in ("dcl", "load", "booted", "long")} for k in res}
out["runs"] = res
print(json.dumps(out, ensure_ascii=False, indent=2))
open(os.path.join(ROOT, "tests", "perf-v42.json"), "w").write(json.dumps(out, ensure_ascii=False, indent=2))
