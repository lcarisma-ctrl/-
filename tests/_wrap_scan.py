import os, sys
os.environ.setdefault("LD_LIBRARY_PATH","/workspace/.aptwork/rootfs/usr/lib/x86_64-linux-gnu:/workspace/.aptwork/rootfs/lib/x86_64-linux-gnu")
from playwright.sync_api import sync_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL="file://"+os.path.join(ROOT,"index.html")
VP=int(sys.argv[1]) if len(sys.argv)>1 else 320
WRAP = r"""
() => {
  const out = [];
  const cls = (el) => (el.id ? '#'+el.id+' ' : '') + (typeof el.className==='string'?el.className:'');
  document.querySelectorAll('.btn, #homeGuideBtn, #homeRegionBtn, #homeTicketBtn, button[data-next], .wiz-nav button, .sheet-foot button, [data-summary], .sec-link, .admin-actions .btn, .req-btns .btn').forEach((el)=>{
    const cs = getComputedStyle(el);
    if (cs.display==='none'||cs.visibility==='hidden') return;
    const r = el.getBoundingClientRect();
    if (r.width<1||r.height<1) return;
    const range = document.createRange(); range.selectNodeContents(el);
    const rects=[...range.getClientRects()].filter(x=>x.width>1&&x.height>1);
    const tops=[]; rects.forEach(x=>{ const t=x.top; if(!tops.some(y=>Math.abs(y-t)<7)) tops.push(t); });
    if (tops.length>=2) out.push({cls: cls(el), w: Math.round(r.width), h: Math.round(r.height),
      lines: tops.length, ws: cs.whiteSpace, text: el.textContent.replace(/\s+/g,' ').trim().slice(0,40)});
  });
  return out;
}
"""
out=[]
def scan(pg,label):
    for it in pg.evaluate(WRAP):
        it['state']=label; out.append(it)

with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--allow-file-access-from-files"])
    pg=b.new_page(viewport={"width":VP,"height":812 if VP<500 else 800},is_mobile=VP<500,has_touch=VP<500)
    pg.goto(URL); pg.wait_for_function("window.__ttokttokBooted === true", timeout=8000)
    scan(pg,"gate")
    pg.eval_on_selector('[data-login="customer"]', "el => el.click()"); pg.wait_for_timeout(300)
    for t in ["home","teachers","booking","journal","mypage"]:
        pg.eval_on_selector('.tabbar .tabbtn[data-tab="%s"]'%t, "el => el.click()"); pg.wait_for_timeout(250); scan(pg,"customer/"+t)
    pg.eval_on_selector('.tabbar .tabbtn[data-tab="booking"]', "el => el.click()"); pg.wait_for_timeout(250)
    pg.eval_on_selector('#provinceQuick [data-prov="서울"]', "el => el.click()")
    pg.select_option("#bookDistrict","강남구"); pg.fill("#bookAddress","대치동 123-4")
    pg.eval_on_selector('#bookSyms [data-val="뇌졸중·편마비"]', "el => el.click()")
    pg.eval_on_selector('[data-next="1"]', "el => el.click()"); pg.wait_for_timeout(300); scan(pg,"booking/2")
    pg.eval_on_selector("#bookDates .date-chip", "el => el.click()")
    pg.eval_on_selector("#bookSlots .slot:not([disabled])", "el => el.click()")
    pg.eval_on_selector('[data-next="2"]', "el => el.click()"); pg.wait_for_timeout(300); scan(pg,"booking/3")
    pg.eval_on_selector('[data-next="3"]', "el => el.click()"); pg.wait_for_timeout(300); scan(pg,"booking/4")
    # 시트들
    pg.eval_on_selector('.tabbar .tabbtn[data-tab="mypage"]', "el => el.click()"); pg.wait_for_timeout(250)
    for openjs,label in [("#mpBookLink","accountSheet"),("#mpNotifRow","notifSheet"),("#mpCouponRow","couponSheet"),
                         ("#mpGuideLink","guideSheet"),("#mpRoleRow","roleSheet"),("#mpPayRow","paySheet")]:
        pg.eval_on_selector(openjs, "el => el.click()"); pg.wait_for_timeout(300); scan(pg,label)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    # 파트너·관리자
    pg.eval_on_selector('[data-login="demo"]', "el => el.click()"); pg.wait_for_timeout(300)
    try:
        pg.eval_on_selector('#roleSheet [data-role-switch]', "el => el.click()"); pg.wait_for_timeout(500)
    except Exception as e: print("role switch fail", e)
    for tab in ["tp-home","tp-schedule","tp-journal","tp-settle","tp-mypage"]:
        try:
            pg.eval_on_selector('.tabbar .tabbtn[data-tab="%s"]'%tab, "el => el.click()"); pg.wait_for_timeout(300); scan(pg,"partner/"+tab)
        except Exception as e: print("skip",tab,type(e).__name__)
    try:
        pg.eval_on_selector('[data-admin-open]', "el => el.click()"); pg.wait_for_timeout(500); scan(pg,"admin")
    except Exception as e: print("admin fail", type(e).__name__)
    for st in out:
        print('%-22s %3dx%-3d lines=%d ws=%s %-30s %s' % (st['state'],st['w'],st['h'],st['lines'],st['ws'],st['cls'][:30],st['text']))
    print('total', len(out))
    b.close()
