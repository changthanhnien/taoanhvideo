"""Headless test: 2 prompts - dog running + pig eating rice chibi"""
import sys
import os
import time
import traceback

os.chdir(r"d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted")
sys.path.insert(0, ".")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PYTHONIOENCODING"] = "utf-8"

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

LOG = open("workflow_2prompt_test.log", "w", encoding="utf-8")

def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("utf-8"), flush=True)
    LOG.write(msg + "\n")
    LOG.flush()

log("=" * 60)
log("2-PROMPT WORKFLOW TEST")
log("=" * 60)

from models.database import Database
from ui.workflow.executor import WorkflowExecutor
from ui.workflow.models import serialize_workflow, WorkflowData, NodeData, ConnectionData

db = Database()
db.connect()
log(f"Enabled accounts: {len(db.get_accounts(enabled_only=True))}")

class MockMainWin:
    def __init__(self, db):
        self.db = db
        self.task_manager = None
        self.browser_manager = None
    def _get_task_manager(self):
        if self.task_manager is None:
            try:
                from automation.browser_manager import BrowserManager
                self.browser_manager = BrowserManager()
            except Exception as e:
                log(f"  BrowserManager: {e}")
                self.browser_manager = None
            try:
                from workers.task_manager import TaskManager
                self.task_manager = TaskManager(self.db, self.browser_manager)
            except TypeError:
                from workers.task_manager import TaskManager
                self.task_manager = TaskManager(self.db)
        return self.task_manager

mock = MockMainWin(db)

# Workflow: 2 text prompts -> 2 generate_image nodes
wf = WorkflowData(name="2 Prompt Test")
wf.nodes = [
    NodeData(id="prompt1", node_type="text_prompt", x=0, y=0,
             config={"prompt": "tao anh con cho dang chay"}),
    NodeData(id="prompt2", node_type="text_prompt", x=0, y=200,
             config={"prompt": "tao anh con heo dang an com chibi"}),
    NodeData(id="gen1", node_type="generate_image", x=300, y=0,
             config={"model": "Nano Banana 2", "count": 1, "aspect_ratio": "16:9"}),
    NodeData(id="gen2", node_type="generate_image", x=300, y=200,
             config={"model": "Nano Banana 2", "count": 1, "aspect_ratio": "16:9"}),
]
wf.connections = [
    ConnectionData(id="c1", source_node="prompt1", source_port="output",
                   target_node="gen1", target_port="input"),
    ConnectionData(id="c2", source_node="prompt2", source_port="output",
                   target_node="gen2", target_port="input"),
]

wf_data = serialize_workflow(wf)
configs = {n["id"]: n.get("config", {}) for n in wf_data["nodes"]}

executor = WorkflowExecutor(main_win=mock)

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
    vtask = mock.db.get_task(task_id)
    manager = mock._get_task_manager()
    if manager and vtask:
        log(f"  [TASK_REQ] Starting task with TaskManager...")
        manager.start_task(vtask)

executor.log_message.connect(on_log)
executor.node_started.connect(on_start)
executor.node_finished.connect(on_done)
executor.execution_finished.connect(on_exec_done)
executor.task_requested.connect(on_task_req)

log("\n--- EXECUTING ---")
executor.run_all(wf_data, configs)
log("run_all() OK")

start = time.time()
while time.time() - start < 120:
    app.processEvents()
    time.sleep(0.3)
    elapsed = int(time.time() - start)
    if elapsed % 10 == 0 and elapsed > 0:
        keys = list(executor.data_store.keys())
        log(f"  [{elapsed}s] running={executor.is_running} data_keys={keys}")
    if not executor.is_running and len(executor.data_store) >= 4:
        break

log("\n--- RESULTS ---")
for k, v in executor.data_store.items():
    out = v.get("output", "N/A")
    if isinstance(out, str) and len(out) > 80:
        out = out[:80] + "..."
    log(f"  {k}: output={out}")

log("DONE")
LOG.close()
sys.exit(0)
