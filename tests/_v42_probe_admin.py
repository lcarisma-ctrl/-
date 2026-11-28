#!/usr/bin/env python3
import os
os.environ["LD_LIBRARY_PATH"] = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage"])
    for w,h,mob in [(390,844,True),(320,568,True)]:
        ctx = b.new_context(viewport={"width":w,"height":h}, device_scale_factor=2, is_mobile=mob, has_touch=mob, locale="ko-KR")
        pg = ctx.new_page(); pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted===true", timeout=20000); pg.wait_for_timeout(300)
        pg.eval_on_selector('[data-login="admin"]', "el=>el.click()"); pg.wait_for_timeout(1200)
        pg.evaluate("()=>{const e=document.querySelector('#adminMetricsKpiCard'); e.scrollIntoView({block:'start'});}")
        pg.wait_for_timeout(700)
        pg.screenshot(path=os.path.join(ROOT,"preview","v42-audit","adm_%d_kpi.png"%w))
        pg.evaluate("()=>{const e=document.querySelector('#adminMetricsFunnel'); e.scrollIntoView({block:'start'});}")
        pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(ROOT,"preview","v42-audit","adm_%d_tbl.png"%w))
        pg.evaluate("()=>{const e=document.querySelector('#adminMetricsRegions'); e.scrollIntoView({block:'start'});}")
        pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(ROOT,"preview","v42-audit","adm_%d_region.png"%w))
        print(w, pg.evaluate("""()=>{const r=document.querySelector('.adm-row'); if(!r) return null; const cs=getComputedStyle(r); return {cols:cs.gridTemplateColumns, h:Math.round(r.getBoundingClientRect().height)};}"""))
        ctx.close()
    b.close()
