"""Headless test: exercise WorkflowExecutor directly without GUI."""
import sys
import os
import time
import traceback

os.chdir(r"d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted")
sys.path.insert(0, ".")

# Minimal Qt app (no window needed)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

app = QApplication.instance() or QApplication(sys.argv)

LOG = open("workflow_headless_test.log", "w", encoding="utf-8")

def log(msg):
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()

log("=" * 60)
log("HEADLESS WORKFLOW EXECUTOR TEST")
log("=" * 60)

# Import and setup
from models.database import Database
from ui.workflow.executor import WorkflowExecutor, _task_manager_available
from ui.workflow.models import serialize_workflow, WorkflowData, NodeData, ConnectionData

log(f"_task_manager_available: {_task_manager_available}")

db = Database()
db.connect()
log(f"DB connected. Enabled accounts: {len(db.get_accounts(enabled_only=True))}")

# Create a mock main_win with the essential attributes
class MockMainWin:
    def __init__(self, db):
        self.db = db
        self.task_manager = None
        self._task_manager = None
        self.browser_manager = None
    
    def _get_task_manager(self):
        if self.task_manager is None:
            try:
                from automation.browser_manager import BrowserManager
                self.browser_manager = BrowserManager()
            except ImportError as e:
                log(f"  BrowserManager import failed: {e}")
                self.browser_manager = None
            try:
                from workers.task_manager import TaskManager
                self.task_manager = TaskManager(self.db, self.browser_manager)
            except TypeError:
                from workers.task_manager import TaskManager
                self.task_manager = TaskManager(self.db)
            except Exception as e:
                log(f"  TaskManager creation failed: {e}")
                self.task_manager = None
        return self.task_manager

mock_main = MockMainWin(db)
log(f"MockMainWin created")

# Setup workflow
wf = WorkflowData(name="Headless Test")
wf.nodes = [
    NodeData(id="n1", node_type="text_prompt", x=0, y=0,
             config={"prompt": "t?o ?nh con chó con chibi, t? l? 9:16"}),
    NodeData(id="n2", node_type="generate_image", x=200, y=0,
             config={"model": "Nano Banana 2", "count": 3, "aspect_ratio": "16:9"}),
]
wf.connections = [
    ConnectionData(id="c1", source_node="n1", source_port="prompt",
                   target_node="n2", target_port="prompt"),
]
wf_data = serialize_workflow(wf)
log(f"Workflow serialized. Nodes: {len(wf_data['nodes'])}, Connections: {len(wf_data['connections'])}")

# Verify node_type field is correct
for n in wf_data["nodes"]:
    nt = n.get("node_type") or n.get("type", "")
    log(f"  Node {n['id']}: node_type='{nt}'")

# Build configs
configs = {n["id"]: n.get("config", {}) for n in wf_data["nodes"]}
log(f"Configs: {configs}")

# Create executor
executor = WorkflowExecutor(main_win=mock_main)
log(f"Executor created: {executor}")

# Connect signals
def on_log(nid, msg):
    log(f"  [LOG] {nid[:8]}: {msg}")

def on_start(nid):
    log(f"  [START] {nid}")

def on_done(nid, state):
    log(f"  [DONE] {nid}: {state}")

def on_exec_done(success):
    log(f"  [EXEC_DONE] success={success}")

def on_task_req(task_id):
    log(f"  [TASK_REQ] task_id={task_id}")
    # Simulate _on_task_requested from workflow_page
    vtask = mock_main.db.get_task(task_id)
    manager = mock_main._get_task_manager()
    if manager and vtask:
        log(f"  [TASK_REQ] Starting task via TaskManager...")
        manager.start_task(vtask)
    else:
        log(f"  [TASK_REQ] FAIL: manager={manager}, vtask={vtask}")

executor.log_message.connect(on_log)
executor.node_started.connect(on_start)
executor.node_finished.connect(on_done)
executor.execution_finished.connect(on_exec_done)
executor.task_requested.connect(on_task_req)

# RUN!
log("\n--- EXECUTING WORKFLOW ---")
try:
    executor.run_all(wf_data, configs)
    log("run_all() called OK")
except Exception as e:
    log(f"run_all() FAILED: {e}")
    traceback.print_exc(file=LOG)

# Process events for 60 seconds
log("\nProcessing events for 60s...")
start = time.time()
last_status = -1
while time.time() - start < 60:
    app.processEvents()
    time.sleep(0.2)
    
    elapsed = int(time.time() - start)
    if elapsed % 5 == 0 and elapsed != last_status:
        last_status = elapsed
        log(f"  [{elapsed}s] running={executor.is_running}, data_store_keys={list(executor.data_store.keys())}")
        
    if not executor.is_running and executor.data_store:
        log(f"  Executor finished early at {elapsed}s")
        break

log("\n--- FINAL RESULTS ---")
log(f"Running: {executor.is_running}")
for k, v in executor.data_store.items():
    log(f"  {k}: {v}")

log("\n" + "=" * 60)
log("TEST COMPLETE")
log("=" * 60)
LOG.close()
sys.exit(0)
