import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e_chromium as E
from playwright.sync_api import sync_playwright

FLOWS = {
    "base": [("run_flow", None)],
    "v17": [("run_v17_flow", None)], "v18": [("run_v18_flow", None)], "v19": [("run_v19_flow", None)],
    "v20": [("run_v20_flow", None)], "v21": [("run_v21_flow", None)], "v22": [("run_v22_flow", None)],
    "v23": [("run_v23_flow", None)], "v24": [("run_v24_flow", None)], "v25": [("run_v25_flow", None)],
    "v26": [("run_v26_flow", None)], "v27": [("run_v27_flow", None)],
}

names = sys.argv[1:] or list(FLOWS.keys())
with sync_playwright() as p:
    for name in names:
        fn = getattr(E, FLOWS[name][0][0])
        fn(p, storage_blocked=False)
        fn(p, storage_blocked=True)
print("\nRESULT: %d passed, %d failed" % (E.passed, E.failed))
for f in E.failures:
    print(" - " + f)
sys.exit(1 if E.failed else 0)
