import time
import sys
import os

log_path = r"C:\Users\ASUS\.gemini\antigravity\brain\2bdbf117-1650-4c3d-bea6-84464b270760\.system_generated\tasks\task-3420.log"

start = time.time()
while time.time() - start < 80:
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
            if "ALL TESTS PASSED" in content or "QUALITY FAILED" in content or "Traceback" in content:
                print("DONE")
                sys.exit(0)
    time.sleep(2)

print("WAITING")
sys.exit(1)
