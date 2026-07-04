"""Final test: confirm executor stops + returns results after image generated"""
import sys, os, time
os.chdir(r"d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted")
sys.path.insert(0, ".")
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from models.database import Database
from ui.workflow.executor import WorkflowExecutor
from ui.workflow.models import serialize_workflow, WorkflowData, NodeData, ConnectionData

db = Database()
db.connect()

class MockMainWin:
    def __init__(self, db):
        self.db = db
        self.task_manager = None
        self.browser_manager = None
    def _get_task_manager(self):
        if self.task_manager is None:
            from automation.browser_manager import BrowserManager
            self.browser_manager = BrowserManager()
            from workers.task_manager import TaskManager
            self.task_manager = TaskManager(self.db, self.browser_manager)
        return self.task_manager

mock = MockMainWin(db)

wf = WorkflowData(name="Final Test")
wf.nodes = [
    NodeData(id="p1", node_type="text_prompt", x=0, y=0,
             config={"prompt": "cute chibi pig eating rice bowl"}),
    NodeData(id="g1", node_type="generate_image", x=300, y=0,
             config={"model": "Nano Banana 2", "count": "1", "ratio": "16:9"}),
]
wf.connections = [
    ConnectionData(id="c1", source_node="p1", source_port="output",
                   target_node="g1", target_port="input"),
]

wf_data = serialize_workflow(wf)
configs = {n["id"]: n.get("config", {}) for n in wf_data["nodes"]}

executor = WorkflowExecutor(main_win=mock)

results = {"done": False, "success": None, "output": None}

def on_start(nid):
    print(f"[START] {nid}", flush=True)
def on_done(nid, state):
    print(f"[DONE] {nid}: {state}", flush=True)
    if nid == "g1":
        data = executor.data_store.get("g1", {})
        results["output"] = data.get("output", [])
        print(f"[OUTPUT] {results['output']}", flush=True)
def on_exec_done(success):
    print(f"[EXEC_DONE] success={success}", flush=True)
    results["done"] = True
    results["success"] = success
def on_task_req(task_id):
    print(f"[TASK_REQ] task_id={task_id}", flush=True)
    vtask = mock.db.get_task(task_id)
    manager = mock._get_task_manager()
    if manager and vtask:
        manager.start_task(vtask)

executor.node_started.connect(on_start)
executor.node_finished.connect(on_done)
executor.execution_finished.connect(on_exec_done)
executor.task_requested.connect(on_task_req)

print("--- STARTING ---", flush=True)
executor.run_all(wf_data, configs)

start = time.time()
while time.time() - start < 180:
    app.processEvents()
    time.sleep(0.3)
    elapsed = int(time.time() - start)
    if elapsed % 15 == 0 and elapsed > 0:
        print(f"[{elapsed}s] running={executor.is_running} done={results['done']} keys={list(executor.data_store.keys())}", flush=True)
    if results["done"]:
        break

print("\n--- FINAL RESULTS ---", flush=True)
print(f"Success: {results['success']}", flush=True)
print(f"Output files: {results['output']}", flush=True)
for k, v in executor.data_store.items():
    out = v.get("output", "N/A")
    print(f"  {k}: {out}", flush=True)

if results["output"] and isinstance(results["output"], list):
    for f in results["output"]:
        if os.path.exists(f):
            size = os.path.getsize(f)
            print(f"  FILE OK: {f} ({size} bytes)", flush=True)

print("TEST COMPLETE", flush=True)
sys.exit(0)
