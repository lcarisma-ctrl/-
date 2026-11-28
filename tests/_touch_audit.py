#!/usr/bin/env python3
"""v31 터치 영역 감사(개발용): 44x44 미만 조작 요소와 2줄로 접힌 CTA를 모은다.

qa_v24.py의 화면·시트 이동 순서를 그대로 재사용하되, audit()만 바꿔 끼워
모든 상태에서 조작 요소의 실제 크기를 수집한다.

실행: python3 tests/_touch_audit.py [320|375|1280] [--json out.json]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import qa_v24  # noqa: E402

TOUCH_JS = r"""
() => {
  const out = [];
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || Number(s.opacity) === 0) return false;
    return r.width > 0.5 && r.height > 0.5;
  };
  const name = (el) => {
    if (el.id) return '#' + el.id;
    const c = (typeof el.className === 'string' ? el.className : '').trim().split(/\s+/).filter(Boolean);
    const cls = c.length ? '.' + c.slice(0, 3).join('.') : '';
    const t = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 26);
    return el.tagName.toLowerCase() + cls + (t ? ' "' + t + '"' : '');
  };
  const sel = 'a[href], button, [role="button"], input:not([type="hidden"]), select, textarea, summary, [tabindex]:not([tabindex="-1"])';
  const seen = new Set();
  const add = (el, why) => {
    if (seen.has(el) || !vis(el)) return;
    if (el.disabled) return;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed' && r.width > 4000) return;
    // 화면 밖으로 완전히 나간 요소(닫힌 시트 내부 등) 제외
    if (r.bottom < -2000 || r.top > 40000) return;
    seen.add(el);
    const parentBtn = el.closest('button, [role="button"], a[href]');
    const nested = parentBtn && parentBtn !== el;
    // 2줄 접힘: 텍스트 노드의 라인 박스 수
    let lines = 0;
    if (['BUTTON', 'A', 'SPAN', 'DIV'].includes(el.tagName)) {
      const range = document.createRange();
      try {
        range.selectNodeContents(el);
        const rects = [...range.getClientRects()].filter((x) => x.width > 1 && x.height > 1);
        // 줄 높이 단위로 합치기
        const tops = new Set(rects.map((x) => Math.round(x.top)));
        lines = tops.size;
      } catch (e) {}
    }
    out.push({
      why, tag: el.tagName, name: name(el), w: Math.round(r.width), h: Math.round(r.height),
      lines, nested, cls: (typeof el.className === 'string' ? el.className : ''),
      cursor: cs.cursor, disp: cs.display, ws: cs.whiteSpace,
      x: Math.round(r.left), y: Math.round(r.top + window.scrollY),
    });
  };
  document.querySelectorAll(sel).forEach((el) => add(el, 'tag'));
  document.querySelectorAll('body *').forEach((el) => {
    if (seen.has(el)) return;
    if (el.closest(sel)) return;
    const cs = getComputedStyle(el);
    if (cs.cursor !== 'pointer') return;
    const p = el.parentElement;
    if (p && getComputedStyle(p).cursor === 'pointer') return;
    add(el, 'pointer');
  });
  return out;
}
"""

ACC = {}
STATES = []


def audit(page, state, tag, buckets):
    STATES.append(state)
    use_app = page.evaluate("() => !!(window.__ttokttokTouch && window.__ttokttokTouch.violations)")
    if use_app:
        v = page.evaluate("() => window.__ttokttokTouch.violations()")
        g = page.evaluate("() => window.__ttokttokTouch.gapViolations()")
        for it in v:
            it['state'] = state
            it['vp'] = tag.strip()
            key = ('viol', it.get('cls', ''), it.get('id', ''), it.get('text', ''))
            ACC.setdefault(key, {'tag': 'viol', 'cls': it.get('cls', '') + '#' + it.get('id', ''),
                                 'name': ('#%s ' % it['id'] if it['id'] else '') + '%s "%s"' % (it.get('cls', ''), it.get('text', '')),
                                 'minw': 0, 'minh': 0, 'sizes': set(), 'states': set(), 'max_lines': 0})
            a = ACC[key]
            a['minw'] = min(a['minw'] or 999, it['w'])
            a['minh'] = min(a['minh'] or 999, it['h'])
            a['sizes'].add('%dx%d' % (it['w'], it['h']))
            a['states'].add(state)
        for it in g:
            ACC.setdefault(('gap', it['a'], it['b'], str(it['gap'])), {
                'tag': 'gap', 'cls': '', 'name': 'GAP %s ↔ %s = %s' % (it['a'], it['b'], it['gap']),
                'minw': 0, 'minh': 0, 'sizes': set(), 'states': {state}, 'max_lines': 0})
        return
    items = page.evaluate(TOUCH_JS)
    for it in items:
        it['state'] = state
        it['vp'] = tag.strip()
        key = (it['tag'], it['cls'], it['name'])
        ACC.setdefault(key, {'tag': it['tag'], 'cls': it['cls'], 'name': it['name'],
                             'minw': 0, 'minh': 0, 'sizes': set(), 'states': set(),
                             'max_lines': 0})
        a = ACC[key]
        a['minw'] = min(a['minw'] or 999, it['w'])
        a['minh'] = min(a['minh'] or 999, it['h'])
        a['sizes'].add('%dx%d' % (it['w'], it['h']))
        a['states'].add(state)
        a['max_lines'] = max(a['max_lines'], it['lines'])


def main():
    vp = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '320'
    outjson = None
    if '--json' in sys.argv:
        outjson = sys.argv[sys.argv.index('--json') + 1]
    qa_v24.audit = audit
    qa_v24.ok = lambda *a, **k: None  # 감사 모드: 단정문 소음 제거
    qa_v24.shot = lambda *a, **k: None
    cfg = {'320': (320, 568, True), '375': (375, 812, True), '1280': (1280, 800, False)}[vp]
    with qa_v24.sync_playwright() as p:
        qa_v24.run_viewport(p, vp, cfg[0], cfg[1], mobile=cfg[2])
    small = []
    for k, a in ACC.items():
        if a['minw'] < 44 or a['minh'] < 44:
            small.append(a)
    small.sort(key=lambda a: (a['minh'], a['minw']))
    print('states:', len(set(STATES)))
    print('controls:', len(ACC), 'under44:', len(small))
    for a in small:
        print('%3dx%-3d lines=%d  %-95s %s' % (a['minw'], a['minh'], a['max_lines'], a['name'][:95],
                                                ','.join(sorted(a['states']))[:120]))
    wrapped = [a for a in ACC.values() if a['max_lines'] >= 2]
    print('\n2줄 이상 접힌 요소:', len(wrapped))
    for a in wrapped:
        print('  lines=%d %3dx%-3d %s' % (a['max_lines'], a['minw'], a['minh'], a['name'][:100]))
    if outjson:
        with open(outjson, 'w', encoding='utf-8') as f:
            json.dump([dict(a, sizes=sorted(a['sizes']), states=sorted(a['states'])) for a in ACC.values()],
                      f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
