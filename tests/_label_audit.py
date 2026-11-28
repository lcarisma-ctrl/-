#!/usr/bin/env python3
"""v34 · 아이콘 버튼 이름 전수 감사 — 숨은 시트·모달·동적 화면까지 이름이 있는지 본다."""
import json
import os

LIB = "/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu"
os.environ["LD_LIBRARY_PATH"] = LIB + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file://" + os.path.join(ROOT, "index.html")

JS = r"""
() => {
  const nameOf = (el) => {
    let n = String(el.getAttribute('aria-label') || '').trim();
    if (!n && el.getAttribute('aria-labelledby')) {
      n = el.getAttribute('aria-labelledby').split(/\s+/).map((id) => { const t = document.getElementById(id); return t ? t.textContent : ''; }).join('').replace(/\s+/g, ' ').trim();
    }
    if (!n) n = String(el.getAttribute('title') || '').trim();
    if (!n) n = String(el.getAttribute('alt') || '').trim();
    if (!n) n = String(el.textContent || '').replace(/\s+/g, ' ').trim();
    return n;
  };
  const isIcon = (el) => {
    const t = String(el.textContent || '').replace(/\s+/g, '').trim();
    return !t && !!el.querySelector('svg,img');
  };
  const out = { blank: [], iconNoLabel: [], total: 0, icons: 0 };
  document.querySelectorAll('button,[role="button"],a[href],input[type="submit"],input[type="button"],summary').forEach((el) => {
    out.total++;
    const n = nameOf(el);
    if (isIcon(el)) out.icons++;
    if (!n) out.blank.push((el.id || '') + '.' + (typeof el.className === 'string' ? el.className : '') + '|' + (el.tagName));
    else if (isIcon(el) && !String(el.getAttribute('aria-label') || '').trim() && !el.getAttribute('aria-labelledby')) out.iconNoLabel.push((el.id || '') + '.' + (typeof el.className === 'string' ? el.className : '') + '|' + n);
  });
  return out;
}
"""

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox", "--allow-file-access-from-files"])
    page = b.new_page(viewport={"width": 375, "height": 812})
    page.goto(URL)
    page.wait_for_function("window.__ttokttokBooted === true", timeout=20000)
    page.wait_for_timeout(400)
    r = page.evaluate(JS)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    b.close()
