import importlib.util, os, sys, time
spec = importlib.util.spec_from_file_location("e2e", os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e_chromium.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    for blocked in (False, True):
        m.run_v45_flow(p, storage_blocked=blocked)
print("\nV45 RESULT: %d passed, %d failed" % (m.passed, m.failed))
for f in m.failures: print(" - " + f)
sys.exit(1 if m.failed else 0)
