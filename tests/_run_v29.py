import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("e2e", os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e_chromium.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    m.run_v29_flow(p, storage_blocked=False)
    m.run_v29_flow(p, storage_blocked=True)
print("\nV29 RESULT: %d passed, %d failed" % (m.passed, m.failed))
for f in m.failures: print(" - " + f)
sys.exit(1 if m.failed else 0)
