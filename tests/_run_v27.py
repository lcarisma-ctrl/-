import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e_chromium as E
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    E.run_v27_flow(p, storage_blocked=False)
    E.run_v27_flow(p, storage_blocked=True)
print("\nRESULT: %d passed, %d failed" % (E.passed, E.failed))
for f in E.failures:
    print(" - " + f)
sys.exit(1 if E.failed else 0)
