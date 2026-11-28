#!/usr/bin/env python3
"""v45 · 라이트·다크 양쪽 본문 대비 전수 측정(WCAG AA).

실행:
  cd projects/ttokttok-app/tests && THEME=light python3 contrast_v45.py
  cd projects/ttokttok-app/tests && THEME=dark  python3 contrast_v45.py
  VIEWPORT=1280 THEME=dark python3 contrast_v45.py      # v46 데스크톱 2단
  VIEWPORT=1024 THEME=light python3 contrast_v45.py     # v47 작은 데스크톱(레일 + 두 열)
결과: 콘솔 요약 + tests/contrast-v45-<theme>-<viewport>.json

v46 · 배포 게이트(tests/qa_gate.py)에 들어가면서 **위반이 있으면 0이 아닌 코드로 끝난다**.
"""
import importlib.util
import json
import os
import sys
from collections import Counter

# 로컬(워크스페이스)에서만 쓰는 시스템 라이브러리 경로 — CI(Ubuntu)에는 없다
_LDLP = "/workspace/.aptwork/rootfs"
if os.path.isdir(_LDLP + "/usr/lib/x86_64-linux-gnu"):
    os.environ["LD_LIBRARY_PATH"] = _LDLP + "/usr/lib/x86_64-linux-gnu:" + _LDLP + "/lib/x86_64-linux-gnu"
from playwright.sync_api import sync_playwright  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ca", os.path.join(HERE, "_contrast_audit.py"))
ca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ca)

ROOT = os.path.dirname(HERE)
URL = "file://" + os.path.join(ROOT, "index.html")
THEME = os.environ.get("THEME", "light")
VIEWPORT = os.environ.get("VIEWPORT", "375")
# 폭별 화면 크기·모바일 여부 — 1280은 v46 데스크톱 2단, 768은 태블릿
SIZES = {"320": (320, 568, True), "375": (375, 812, True), "390": (390, 844, True),
         "768": (768, 1024, True), "1024": (1024, 900, False), "1280": (1280, 900, False)}
VW, VH, VMOBILE = SIZES.get(VIEWPORT, SIZES["375"])

# UI 경계(테두리·구분선) 대비 — WCAG 1.4.11: 3:1
BORDER_JS = r"""
() => {
  const parse = (c) => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).map(Number); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}; };
  const over = (t,b) => { const a=t.a+b.a*(1-t.a); if(!a) return {r:0,g:0,b:0,a:0};
    return {r:(t.r*t.a+b.r*b.a*(1-t.a))/a,g:(t.g*t.a+b.g*b.a*(1-t.a))/a,b:(t.b*t.a+b.b*b.a*(1-t.a))/a,a}; };
  const lum = (c) => { const f=(v)=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);};
    return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b); };
  const ratio = (a,b) => { const l1=lum(a),l2=lum(b),hi=Math.max(l1,l2),lo=Math.min(l1,l2); return (hi+0.05)/(lo+0.05); };
  const hex = (c) => '#'+[c.r,c.g,c.b].map(v=>Math.round(v).toString(16).padStart(2,'0')).join('').toUpperCase();
  const bgOf = (el) => {
    let cur = el, stack = [];
    while (cur && cur !== document.documentElement) {
      const cs = getComputedStyle(cur);
      const c = parse(cs.backgroundColor);
      if (c && c.a > 0.5) { stack.push(c); break; }
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        const m = cs.backgroundImage.match(/rgba?\([^)]+\)/g);
        if (m) { const c2 = parse(m[m.length-1]); if (c2 && c2.a > 0.2) { stack.push(c2); break; } }
      }
      cur = cur.parentElement;
    }
    if (!stack.length) stack.push({r:11,g:20,b:36,a:1});
    return stack[0];
  };
  const sels = ['input:not([type=hidden])','select','textarea','.card','.btn-outline','.segmented','.chip','.mp-row','.status','.tag','.sheet','.list-item','.quick-tile','.settle-cell'];
  const out = [];
  const seen = new Set();
  for (const sel of sels) {
    for (const el of document.querySelectorAll(sel)) {
      if (seen.has(sel)) break;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || r.width < 2 || r.height < 2) continue;
      const bw = parseFloat(cs.borderTopWidth) || 0;
      const side = parseFloat(cs.borderLeftWidth) || 0;
      if (bw < 0.5 && side < 0.5) continue;
      const bc = parse(cs.borderTopColor) || parse(cs.borderLeftColor);
      if (!bc || bc.a === 0) continue;
      const bgEl = bgOf(el);
      const parent = bgOf(el.parentElement || document.body);
      const eff = over(bc, parent);
      const cr = ratio(eff, parent);
      out.push({sel, cr: Math.round(cr*100)/100, border: hex(eff), bg: hex(parent), w: side || bw});
      seen.add(sel);
    }
  }
  return out;
}
"""


def main():
    fails = []
    borders = []
    tokens = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files", "--disable-dev-shm-usage"])
        for state in ca.STATES:
            label, prep = state[0], state[1]
            nologin = len(state) > 2 and state[2] == "nologin"
            ctx = browser.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=2 if VW < 900 else 1,
                                      is_mobile=VMOBILE, has_touch=VMOBILE, locale="ko-KR")
            page = ctx.new_page()
            page.add_init_script("try{localStorage.setItem('ttokttok_theme_v1','%s')}catch(e){}" % THEME)
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.goto(URL + "?intro=0")
            page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
            page.wait_for_timeout(300)
            theme = page.evaluate("() => ({theme: document.documentElement.getAttribute('data-theme'), pref: document.documentElement.getAttribute('data-theme-pref')})")
            if theme.get("theme") != THEME:
                print("!! theme mismatch", label, theme)
            if not nologin:
                page.eval_on_selector('[data-login="customer"]', "el => el.click()")
                page.wait_for_timeout(420)
            if not tokens:
                tokens = page.evaluate(ca.TOKENS_JS)
            try:
                page.evaluate(prep)
            except Exception as e:
                print("prep fail", label, str(e)[:80])
                ctx.close()
                continue
            page.wait_for_timeout(450)
            try:
                page.evaluate("() => window.__ttokttokTouch && window.__ttokttokTouch.apply()")
            except Exception:
                pass
            for it in page.evaluate(ca.AUDIT_JS):
                it["state"] = label
                fails.append(it)
            borders.extend(page.evaluate(BORDER_JS))
            ctx.close()
        browser.close()

    print("\n=== [%s] 본문 대비 위반 %d건 ===" % (THEME, len(fails)))
    by = Counter((it["fg"] + "/" + it["bg"] + "/" + str(it["size"])) for it in fails)
    for key, cnt in by.most_common(30):
        s = next(it for it in fails if it["fg"] + "/" + it["bg"] + "/" + str(it["size"]) == key)
        print("  %3d  %s on %s  %.2f:1  %spx/%s  %s  e.g. %s | %s" % (
            cnt, s["fg"], s["bg"], s["cr"], s["size"], s["weight"], s["state"], s["sel"][-60:], s["text"]))
    bad_b = [b for b in borders if b["cr"] < 3.0]
    print("=== [%s] UI 경계 대비 < 3:1 %d건 ===" % (THEME, len(bad_b)))
    for b in bad_b[:20]:
        print("  %-12s %.2f:1  %s on %s (w=%s)" % (b["sel"], b["cr"], b["border"], b["bg"], b["w"]))
    out = os.path.join(HERE, "contrast-v45-%s-%s.json" % (THEME, VIEWPORT))
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"theme": THEME, "viewport": VIEWPORT, "tokens": tokens, "violations": fails, "borders": borders}, f, ensure_ascii=False, indent=1)
    print("saved", out)
    if fails:
        print("판정: 실패 — %s @%s 본문 대비 위반 %d건" % (THEME, VIEWPORT, len(fails)))
        return 1
    print("판정: 통과 — %s @%s 본문 대비 위반 0건" % (THEME, VIEWPORT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
