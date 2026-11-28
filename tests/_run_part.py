import importlib.util, os, sys, time
spec = importlib.util.spec_from_file_location("e2e", os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e_chromium.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from playwright.sync_api import sync_playwright
names = sys.argv[1:]
t0 = time.time()
with sync_playwright() as p:
    for n in names:
        fn = getattr(m, n)
        for blocked in (False, True):
            fn(p, storage_blocked=blocked)
            print("  .. %s blocked=%s (%.0fs)" % (n, blocked, time.time()-t0), flush=True)
print("\nPART RESULT: %d passed, %d failed (%.0fs)" % (m.passed, m.failed, time.time()-t0))
for f in m.failures: print(" - " + f)
sys.exit(1 if m.failed else 0)
