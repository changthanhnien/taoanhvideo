"""Real end-to-end test: open UI, navigate to Workflow Studio, load workflow, press Run."""
import sys
import os
import time
import traceback

os.chdir(r"d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted")
sys.path.insert(0, ".")

LOG = open("workflow_e2e_test.log", "w", encoding="utf-8")

def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()

log("=" * 60)
log("WORKFLOW E2E TEST")
log("=" * 60)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt

app = QApplication.instance() or QApplication(sys.argv)

from ui.main_window import MainWindow
from models.database import Database

db = Database()
main_win = MainWindow(db)
main_win.show()
main_win.resize(1280, 720)
app.processEvents()

# Navigate to workflow studio page
log("\n[1] Navigating to Workflow Studio page...")
main_win._navigate("workflow_studio")
app.processEvents()
time.sleep(0.5)
app.processEvents()

# Get the actual page from the lazy wrapper
lazy = main_win.pages.get("workflow_studio")
log(f"  LazyPage: {lazy}")
log(f"  LazyPage type: {type(lazy)}")

# The LazyPage should have loaded the real page as its child
page = None
if hasattr(lazy, "_inner"):
    page = lazy._inner
elif hasattr(lazy, "page"):
    page = lazy.page
else:
    # Try finding child WorkflowStudioPage
    from ui.workflow.workflow_page import WorkflowStudioPage
    for child in lazy.findChildren(WorkflowStudioPage):
        page = child
        break

log(f"  Inner page: {page}")
log(f"  Inner page type: {type(page)}")

if not page:
    log("  FAIL: Could not find WorkflowStudioPage instance!")
    # Let's inspect what the lazy page contains
    log(f"  lazy.__dict__: {[k for k in lazy.__dict__.keys()]}")
    for child in lazy.children():
        log(f"    child: {type(child).__name__}: {child}")
    LOG.close()
    sys.exit(1)

log(f"  page.window() = {page.window()}")
log(f"  page.window() is main_win: {page.window() is main_win}")

# Load workflow data
log("\n[2] Loading workflow data...")
from ui.workflow.models import WorkflowData, NodeData, ConnectionData
wf = WorkflowData(name="E2E Test Workflow")
wf.nodes = [
    NodeData(id="n1", node_type="text_prompt", x=100, y=100,
             config={"prompt": "A cute dog eating a banana, digital art, vibrant colors"}),
    NodeData(id="n2", node_type="generate_image", x=400, y=100,
             config={"model": "Nano Banana 2", "count": 1, "ratio": "16:9"}),
]
wf.connections = [
    ConnectionData(id="c1", source_node="n1", source_port="prompt",
                   target_node="n2", target_port="prompt"),
]
page._load_wf(wf)
app.processEvents()
log("  Workflow loaded.")

# Hook signals before run
log("\n[3] Setting up signal hooks...")

def on_log(nid, msg):
    log(f"  [EXEC_LOG] {nid[:8]}: {msg}")

def on_node_start(nid):
    log(f"  [NODE_START] {nid}")

def on_node_done(nid, state):
    log(f"  [NODE_DONE] {nid}: {state}")

def on_exec_done(success):
    log(f"  [EXEC_DONE] success={success}")

def on_task_req(task_id):
    log(f"  [TASK_REQUESTED] task_id={task_id}")

# Run!
log("\n[4] Pressing Run...")
try:
    page._on_run_all()
    log("  _on_run_all() returned OK")
except Exception as e:
    log(f"  FAIL: {e}")
    traceback.print_exc(file=LOG)
    LOG.close()
    sys.exit(1)

app.processEvents()

if hasattr(page, "_executor") and page._executor:
    page._executor.log_message.connect(on_log)
    page._executor.node_started.connect(on_node_start)
    page._executor.node_finished.connect(on_node_done)
    page._executor.execution_finished.connect(on_exec_done)
    page._executor.task_requested.connect(on_task_req)
    log(f"  Executor: {page._executor}")
    log(f"  Thread running: {page._executor.is_running}")
else:
    log("  WARNING: No executor was created!")

# Wait and process events
log("\n[5] Waiting 30 seconds for execution...")
start = time.time()
last_status = ""
while time.time() - start < 30:
    app.processEvents()
    time.sleep(0.2)
    
    # Check progress every 5 seconds
    elapsed = time.time() - start
    status_key = f"{int(elapsed) // 5}"
    if status_key != last_status:
        last_status = status_key
        if hasattr(page, "_executor") and page._executor:
            log(f"  [{int(elapsed)}s] running={page._executor.is_running}, data_store keys={list(page._executor.data_store.keys())}")
            for k, v in page._executor.data_store.items():
                if isinstance(v, dict):
                    summary = {kk: (str(vv)[:50] if isinstance(vv, str) else vv) for kk, vv in v.items()}
                    log(f"    {k}: {summary}")

log("\n[6] Final status:")
if hasattr(page, "_executor") and page._executor:
    log(f"  running: {page._executor.is_running}")
    log(f"  data_store: {page._executor.data_store}")

log("\n" + "=" * 60)
log("E2E TEST COMPLETE")
log("=" * 60)
LOG.close()
app.quit()
sys.exit(0)
