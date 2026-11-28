#!/usr/bin/env python3
"""v34 · 본문 글자 대비 전수 측정(WCAG AA) — 개발·리포트용.

화면·시트(게이트 포함)를 열어 보이는 모든 텍스트 요소의 실제 계산 색(전경/배경)과
글자 크기·굵기를 읽어 대비율을 계산한다. 기준: 일반 텍스트 4.5:1, 큰 텍스트 3:1
(큰 텍스트 = 24px 이상, 또는 18.66px 이상 + 굵기 700 이상).

<결과물>
  - 콘솔: 위반 목록 + 색상(토큰)별 집계
  - 파일: tests/contrast-v35.json (기계 판독용; CONTRAST_OUT 으로 이름 변경)

실행: cd projects/ttokttok-app/tests && python3 _contrast_audit.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
# 로컬(워크스페이스)에서만 쓰는 시스템 라이브러리 경로 — CI(Ubuntu)에는 없다
_LDLP_OK = os.path.isdir("/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu")
if _LDLP_OK:
    os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")

# 화면·시트: (라벨, 준비 스크립트). 각 항목은 새 페이지에서 실행한다.
AUDIT_JS = r"""
() => {
  const parse = (c) => {
    const m = String(c).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,\/]+/).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (top, bottom) => {
    const a = top.a + bottom.a * (1 - top.a);
    if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
    return {
      r: (top.r * top.a + bottom.r * bottom.a * (1 - top.a)) / a,
      g: (top.g * top.a + bottom.g * bottom.a * (1 - top.a)) / a,
      b: (top.b * top.a + bottom.b * bottom.a * (1 - top.a)) / a,
      a
    };
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
  const hex = (c) => '#' + [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();

  /* 배경 그라디언트의 색 정지점 — 흰 글자가 진한 그라디언트 위에 있는 경우를
     '배경 없음'으로 잘못 읽지 않도록, 정지점 색을 모두 모아 가장 불리한(대비 최저) 색으로 판정한다. */
  function gradientStops(cs) {
    const img = cs.backgroundImage || '';
    if (!img || img === 'none') return null;
    const found = img.match(/rgba?\([^)]+\)/g);
    if (!found) return null;
    return found.map(parse).filter(function (c) { return c && c.a > 0.2; });
  }
  const bgCache = new Map();
  function bgCandidates(el) {
    if (bgCache.has(el)) return bgCache.get(el);
    let below;
    if (el === document.documentElement || el === document.body) {
      below = { r: 11, g: 20, b: 36, a: 1 };   /* body{background:#0B1424} */
    } else {
      const up = bgCandidates(el.parentElement || document.documentElement);
      below = up[0];
    }
    const cs = getComputedStyle(el);
    const own = parse(cs.backgroundColor) || { r: 0, g: 0, b: 0, a: 0 };
    const stops = gradientStops(cs);
    let result;
    if (stops && stops.length) {
      /* 그라디언트가 칠해진 면 → 정지점 색들을 후보로(가장 불리한 대조) */
      result = stops.map(function (s) { return over(s, below); });
    } else if (own.a > 0) {
      result = [over(own, below)];
    } else {
      result = [below];
    }
    bgCache.set(el, result);
    return result;
  }

  const out = [];
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
  let n;
  while ((n = walker.nextNode())) {
    const text = String(n.nodeValue || '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const el = n.parentElement;
    if (!el || seen.has(el)) { if (el) { /* 같은 요소의 두 번째 텍스트 노드는 첫 결과에 합친다 */ } }
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    if (el.closest('.sprite, [aria-hidden="true"], script, style, noscript')) continue;
    const op = parseFloat(cs.opacity);
    if (!isNaN(op) && op < 0.05) continue;
    const fg0 = parse(cs.color);
    if (!fg0) continue;
    let fgBase = fg0;
    if (op < 1) fgBase = { r: fgBase.r, g: fgBase.g, b: fgBase.b, a: fgBase.a * op };
    const layers = bgCandidates(el);
    const size = parseFloat(cs.fontSize) || 14;
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const need = large ? 3.0 : 4.5;
    /* 배경 후보(그라디언트 정지점·단색)마다 대조해 가장 불리한 값을 쓴다 */
    let bg = layers[0], cr = 0, worst = 99, worstBg = layers[0];
    for (let li = 0; li < layers.length; li++) {
      const b = layers[li];
      let f = fgBase;
      if (f.a < 1) f = over(f, b);
      const c2 = ratio(f, b);
      if (c2 < worst) { worst = c2; worstBg = b; }
    }
    fg = fgBase.a < 1 ? over(fgBase, worstBg) : fgBase;
    bg = worstBg;
    cr = worst;
    const inlineColor = /(^|;)\s*color\s*:/.test(el.getAttribute('style') || '');
    if (cr + 0.005 < need) {
      const key = el;
      if (seen.has(key)) continue;
      seen.add(key);
      let path = [];
      let cur = el;
      for (let i = 0; i < 4 && cur && cur !== document.body; i++) {
        let seg = cur.tagName.toLowerCase();
        if (cur.id) seg += '#' + cur.id;
        else if (typeof cur.className === 'string' && cur.className.trim()) seg += '.' + cur.className.trim().split(/\s+/).slice(0, 2).join('.');
        path.unshift(seg);
        cur = cur.parentElement;
      }
      out.push({
        sel: path.join(' > '),
        text: text.slice(0, 34),
        fg: hex(fg), bg: hex(bg), cr: Math.round(cr * 100) / 100,
        size: Math.round(size * 10) / 10, weight: weight, need: need,
        inlineColor: inlineColor, isGradient: !!gradientStops(cs),
        color: cs.color, bgRaw: cs.backgroundColor
      });
    }
  }
  return out;
}
"""

TOKENS_JS = r"""
() => {
  const map = {};
  const cs = getComputedStyle(document.documentElement);
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
    if (!rules) continue;
    for (const rule of rules) {
      if (rule.selectorText === ':root') {
        for (const prop of rule.style) {
          if (prop.startsWith('--')) map[prop] = rule.style.getPropertyValue(prop).trim();
        }
      }
    }
  }
  return map;
}
"""


def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def nearest_tokens(tokens, hexcolor):
    try:
        r, g, b = hex_to_rgb(hexcolor)
    except Exception:
        return ""
    best, bestd = "", 10 ** 9
    for name, val in tokens.items():
        v = val.strip()
        if not v.startswith("#"):
            continue
        try:
            rr, gg, bb = hex_to_rgb(v)
        except Exception:
            continue
        d = (r - rr) ** 2 + (g - gg) ** 2 + (b - bb) ** 2
        if d < bestd:
            best, bestd = name, d
    return best if bestd <= 12 else ""


STATES = [
    ("gate", "() => {}", "nologin"),
    ("customer-home", "() => {}"),
    ("customer-teachers", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click()"),
    ("customer-booking", "() => document.querySelector('#homeBookBtn, #homeFirstVisitCard [data-book=eval]').click()"),
    ("customer-journal", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click()"),
    ("customer-mypage", "() => document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]').click()"),
    ("sheet-guide", "() => document.querySelector('#homeGuideBtn').click()"),
    ("sheet-faq", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=mypage]').click(); setTimeout(() => { const b = document.querySelector('#mpFaqRow'); if (b) b.click(); }, 200); }"),
    ("sheet-safety", "() => { const b = document.querySelector('[data-safety-open]'); if (b) b.click(); }"),
    ("sheet-weekly", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=journal]').click(); setTimeout(() => { const b = document.querySelector('#weeklyOpen'); if (b) b.click(); }, 220); }"),
    ("sheet-notif", "() => document.querySelector('#btnNotif').click()"),
    ("sheet-account", "() => document.querySelector('#homeTicketBtn').click()"),
    ("pane-teacher", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click(); setTimeout(() => document.querySelector('#teacherList .teacher, .teacher').click(), 120); }"),
    # v47 · 스켈레톤 로딩 화면(회색 막대·빈 자리 안내·키보드 안내)의 색도 함께 본다
    ("teachers-skeleton", "() => { const t = document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]'); if (t) t.click(); if (window.__ttSkeleton) { window.__ttSkeleton.delay(6000); window.__ttSkeleton.set(true, {silent: true}); } setTimeout(() => { if (window.__ttSkeleton) window.__ttSkeleton.render(); }, 80); }"),
    # v46 · 데스크톱은 카드를 누르면 오른쪽 상세 열, 시트는 '전체 프로필 보기'에서. 그래도 시트 색은 검사한다.
    ("sheet-teacher", "() => { document.querySelector('.tabbar[data-mode=customer] .tabbtn[data-tab=teachers]').click(); setTimeout(() => { const c = document.querySelector('#teacherList .teacher, .teacher'); if (c) c.click(); setTimeout(() => { const s = document.getElementById('teacherSheet'); if (s && !s.classList.contains('is-open')) s.classList.add('is-open'); }, 260); }, 120); }"),
    ("sheet-region", "() => document.querySelector('#homeRegionBtn').click()"),
    ("sheet-role", "() => document.querySelector('#rolePill').click()"),
    ("partner-home", "() => { document.querySelector('#rolePill').click(); setTimeout(() => { document.querySelector('[data-role-switch=therapist]').click(); }, 180); }"),
    ("partner-schedule", "() => { document.querySelector('#rolePill').click(); setTimeout(() => { document.querySelector('[data-role-switch=therapist]').click(); setTimeout(() => { const t = document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-schedule]'); if (t) t.click(); }, 240); }, 180); }"),
    ("partner-journal", "() => { document.querySelector('#rolePill').click(); setTimeout(() => { document.querySelector('[data-role-switch=therapist]').click(); setTimeout(() => { const t = document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-journal]'); if (t) t.click(); }, 240); }, 180); }"),
    ("partner-settle", "() => { document.querySelector('#rolePill').click(); setTimeout(() => { document.querySelector('[data-role-switch=therapist]').click(); setTimeout(() => { const t = document.querySelector('.tabbar[data-mode=therapist] .tabbtn[data-tab=tp-settle]'); if (t) t.click(); }, 240); }, 180); }"),
    ("admin-console", "() => { document.querySelector('#rolePill').click(); setTimeout(() => { const b = document.querySelector('[data-admin-open]'); if (b) b.click(); }, 180); }"),
]


def run():
    report = {}
    tokens = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
        for state in STATES:
            label, prep = state[0], state[1]
            nologin = len(state) > 2 and state[2] == "nologin"
            ctx = browser.new_context(viewport={"width": 375, "height": 812}, device_scale_factor=2,
                                      is_mobile=True, has_touch=True, locale="ko-KR")
            page = ctx.new_page()
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))
            page.goto(URL)
            page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
            page.wait_for_timeout(320)
            if not nologin:
                page.eval_on_selector('[data-login="customer"]', "el => el.click()")
                page.wait_for_timeout(420)
            if not tokens:
                tokens = page.evaluate(TOKENS_JS)
            try:
                page.evaluate(prep)
            except Exception as e:
                report[label] = {"error": str(e)[:120]}
                ctx.close()
                continue
            page.wait_for_timeout(420)
            try:
                page.evaluate("() => window.__ttokttokTouch && window.__ttokttokTouch.apply()")
            except Exception:
                pass
            items = page.evaluate(AUDIT_JS)
            for it in items:
                it["token"] = nearest_tokens(tokens, it["fg"])
                it["bgToken"] = nearest_tokens(tokens, it["bg"])
            report[label] = items
            ctx.close()
        browser.close()

    allfail = []
    for label, items in report.items():
        if isinstance(items, dict):
            continue
        for it in items:
            it["state"] = label
            allfail.append(it)

    print("TOKENS:", json.dumps(tokens, ensure_ascii=False))
    print("\n=== 위반 %d건 / 상태 %d ===" % (len(allfail), len([k for k, v in report.items() if not isinstance(v, dict)])))
    by_color = Counter((it["fg"] + "/" + it["bg"] + "/" + str(it["size"])) for it in allfail)
    for (key, cnt) in by_color.most_common(40):
        sample = next(it for it in allfail if it["fg"] + "/" + it["bg"] + "/" + str(it["size"]) == key)
        print("  %3d  %s on %s  %.2f:1  %spx/%s  %s%s  e.g. %s | %s" % (
            cnt, sample["fg"], sample["bg"], sample["cr"], sample["size"], sample["weight"],
            sample["token"], ("/" + sample["bgToken"]) if sample["bgToken"] else "", sample["sel"][-70:], sample["text"]))
    out_name = os.environ.get("CONTRAST_OUT", "contrast-v35.json")
    with open(os.path.join(ROOT, "tests", out_name), "w", encoding="utf-8") as f:
        json.dump({"tokens": tokens, "violations": allfail, "byState": {k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}}, f, ensure_ascii=False, indent=1)
    print("\n저장: tests/" + out_name)
    return 0


if __name__ == "__main__":
    sys.exit(run())
