#!/usr/bin/env python3
"""v24 접근성 탐침: 화면별 누락 항목을 빠르게 모아 본다(개발용, 결과는 참고)."""
import os
LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

URL = "file://" + os.path.join(ROOT, "index.html")

A11Y = r"""
() => {
  const out = {unnamed:[], unlabeled:[], noalt:[], dialogs:[], live:[]};
  const vis = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const nameOf = (el) => (el.getAttribute('aria-label') || '').trim() ||
    (el.getAttribute('aria-labelledby') ? (document.getElementById(el.getAttribute('aria-labelledby')) || {}).textContent || '' : '').trim() ||
    (el.getAttribute('title') || '').trim() || (el.textContent || '').replace(/\s+/g,' ').trim();
  document.querySelectorAll('button, [role="button"], a[href], input[type="submit"]').forEach((el) => {
    if (!vis(el)) return;
    if (!nameOf(el)) out.unnamed.push((el.id || el.className || el.tagName) + '|' + (el.getAttribute('type')||''));
  });
  document.querySelectorAll('input:not([type="hidden"]), select, textarea').forEach((el) => {
    if (!vis(el)) return;
    const id = el.id;
    const hasLabel = (id && document.querySelector('label[for="' + id + '"]')) || el.closest('label') ||
      el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title');
    if (!hasLabel) out.unlabeled.push(id || el.name || el.type);
  });
  document.querySelectorAll('img').forEach((el) => {
    if (!el.hasAttribute('alt')) out.noalt.push(el.id || el.className || el.src.slice(0,40));
  });
  document.querySelectorAll('[role="dialog"]').forEach((el) => {
    if (!el.getAttribute('aria-modal') || !(el.getAttribute('aria-labelledby') || el.getAttribute('aria-label'))) {
      out.dialogs.push(el.id + '|' + (el.getAttribute('aria-modal')||'-') + '|' + (el.getAttribute('aria-labelledby')||'-'));
    }
  });
  document.querySelectorAll('[aria-live], [role="status"], [role="alert"]').forEach((el) => {
    out.live.push(el.id || el.className);
  });
  return out;
}
"""

def probe(page, label, buckets):
    r = page.evaluate(A11Y)
    for k, v in r.items():
        if k == 'live':
            continue
        for item in v:
            buckets.setdefault(k, set()).add(label + ' :: ' + item)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    page = b.new_page(viewport={"width": 320, "height": 568})
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    buckets = {}
    probe(page, 'gate', buckets)
    page.eval_on_selector('[data-login="customer"]', 'el => el.click()')
    page.wait_for_timeout(300)
    for tab in ['home', 'teachers', 'booking', 'journal', 'mypage']:
        page.eval_on_selector('[data-tab="%s"]' % tab, 'el => el.click()')
        page.wait_for_timeout(250)
        probe(page, 'customer/%s' % tab, buckets)
    # sheets
    for sid in ['teacherSheet','accountSheet','paySheet','notifSheet','couponSheet','faqSheet','safetySheet','guideSheet','roleSheet','weeklySheet','reportSheet','manageSheet','chatSheet','reviewSheet','appSheet','rejectSheet','gateSheet','regionSheet','receiptModal']:
        page.evaluate("(id) => { const s=document.getElementById(id); if(s){s.classList.add('is-open');} }", sid)
        page.wait_for_timeout(150)
        probe(page, 'sheet/'+sid, buckets)
        page.evaluate("(id) => { const s=document.getElementById(id); if(s){s.classList.remove('is-open');} }", sid)
    page.eval_on_selector('[data-login="therapist"]', 'el => el.click()') if page.is_visible('[data-login="therapist"]') else None
    page.evaluate("() => { document.getElementById('entryGate').classList.add('is-open'); }")
    page.eval_on_selector('[data-login="therapist"]', 'el => el.click()')
    page.wait_for_timeout(300)
    for tab in ['tp-home', 'tp-schedule', 'tp-journal', 'tp-mypage']:
        page.eval_on_selector('[data-tab="%s"]' % tab, 'el => el.click()')
        page.wait_for_timeout(250)
        probe(page, 'partner/%s' % tab, buckets)
    page.evaluate("() => { document.getElementById('entryGate').classList.add('is-open'); }")
    page.eval_on_selector('[data-login="admin"]', 'el => el.click()')
    page.wait_for_timeout(400)
    probe(page, 'admin', buckets)
    b.close()

for k in ['unnamed', 'unlabeled', 'noalt', 'dialogs']:
    print('\n== %s (%d)' % (k, len(buckets.get(k, []))))
    for i in sorted(buckets.get(k, []))[:60]:
        print('  ' + i)
