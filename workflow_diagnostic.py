"""Diagnostic script: trace the entire workflow execution chain."""
import sys
import os
import time
import traceback

os.chdir(r"d:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted")
sys.path.insert(0, ".")

LOG = open("workflow_diagnostic.log", "w", encoding="utf-8")

def log(msg):
    print(msg)
    LOG.write(msg + "\n")
    LOG.flush()

log("=" * 60)
log("WORKFLOW DIAGNOSTIC TEST")
log("=" * 60)

# 1. Check imports
log("\n[1] Checking imports...")
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    log("  OK: PySide6")
except Exception as e:
    log(f"  FAIL: PySide6 - {e}")
    sys.exit(1)

try:
    from workers.task_manager import TaskManager
    log("  OK: TaskManager")
except Exception as e:
    log(f"  FAIL: TaskManager - {e}")

try:
    from automation.browser_manager import BrowserManager
    log("  OK: BrowserManager")
except Exception as e:
    log(f"  FAIL: BrowserManager - {e}")

try:
    from ui.workflow.executor import ExecutionThread, WorkflowExecutor, _task_manager_available
    log(f"  OK: Executor (_task_manager_available={_task_manager_available})")
except Exception as e:
    log(f"  FAIL: Executor - {e}")

try:
    from ui.workflow.models import serialize_workflow, WorkflowData, NodeData, ConnectionData
    log("  OK: Models")
except Exception as e:
    log(f"  FAIL: Models - {e}")

# 2. Check serialize_workflow field names
log("\n[2] Checking serialize_workflow field names...")
wf = WorkflowData(name="Test")
wf.nodes = [
    NodeData(id="n1", node_type="text_prompt", x=0, y=0, config={"prompt": "test"}),
    NodeData(id="n2", node_type="generate_image", x=100, y=100, config={"model": "Nano Banana 2"}),
]
wf.connections = [
    ConnectionData(id="c1", source_node="n1", source_port="prompt", target_node="n2", target_port="prompt"),
]
data = serialize_workflow(wf)
node_dict = data["nodes"][0]
log(f"  Node dict keys: {list(node_dict.keys())}")
log(f"  Has 'node_type': {'node_type' in node_dict}")
log(f"  Has 'type': {'type' in node_dict}")
log(f"  node_type value: {node_dict.get('node_type', 'MISSING!')}")

# 3. Check executor dispatcher
log("\n[3] Checking executor dispatcher...")
from ui.workflow.executor import ExecutionThread
et = ExecutionThread.__new__(ExecutionThread)
for nt in ["text_prompt", "generate_image", "generate_video"]:
    method_name = et._EXECUTORS.get(nt)
    log(f"  {nt} -> {method_name} -> hasattr={hasattr(et, method_name) if method_name else 'N/A'}")

# Check: will _execute_node find the type?
node_type_from_data = data["nodes"][0].get("node_type") or data["nodes"][0].get("type", "")
log(f"  Resolved node_type from serialized data: '{node_type_from_data}'")
log(f"  Will dispatcher match? {node_type_from_data in et._EXECUTORS}")

# 4. Check database + accounts
log("\n[4] Checking database...")
app = QApplication.instance() or QApplication(sys.argv)

from models.database import Database
db = Database()
db.connect()
log(f"  DB connected: {db._db_path}")

accounts = db.get_accounts(enabled_only=True)
log(f"  Enabled accounts: {len(accounts)}")
for acc in accounts:
    log(f"    - id={acc.id}, email={acc.email}, enabled={acc.enabled}, cookie_path={acc.cookie_path}")

if not accounts:
    log("  ⚠ WARNING: No enabled accounts! TaskWorker will DEADLOCK waiting for account_pool.acquire()!")

# 5. Check MainWindow + _get_task_manager
log("\n[5] Checking MainWindow...")
from ui.main_window import MainWindow
main_win = MainWindow(db)
log(f"  main_win.task_manager = {main_win.task_manager}")
log(f"  main_win._task_manager = {main_win._task_manager}")
log(f"  hasattr _get_task_manager: {hasattr(main_win, '_get_task_manager')}")

log("  Calling _get_task_manager()...")
try:
    mgr = main_win._get_task_manager()
    log(f"  Result: {mgr}")
    log(f"  Type: {type(mgr)}")
    if mgr:
        log(f"  mgr.account_pool: {mgr.account_pool}")
        log(f"  mgr.account_pool.available_count(): {mgr.account_pool.available_count()}")
except Exception as e:
    log(f"  FAIL: {e}")
    traceback.print_exc(file=LOG)

# 6. Check workflow_page attribute
log("\n[6] Checking workflow_page...")
main_win.show()
app.processEvents()

page = getattr(main_win, "workflow_page", None)
log(f"  workflow_page: {page}")
log(f"  type: {type(page)}")

if page:
    log(f"  page.window() == main_win: {page.window() == main_win}")

# 7. Simulate run
log("\n[7] Simulating _on_run_all...")
if page:
    page._load_wf(wf)
    app.processEvents()
    
    # Hook into signals
    def on_log(nid, msg):
        log(f"  [LOG] {nid[:8]}: {msg}")
    
    def on_node_start(nid):
        log(f"  [START] {nid}")
    
    def on_node_done(nid, state):
        log(f"  [DONE] {nid}: {state}")
    
    def on_exec_done(success):
        log(f"  [EXEC_DONE] success={success}")
    
    def on_task_req(task_id):
        log(f"  [TASK_REQUESTED] task_id={task_id}")
    
    log("  Calling _on_run_all()...")
    try:
        page._on_run_all()
        log("  _on_run_all() returned without exception")
        
        # Hook signals after executor is created
        if hasattr(page, "_executor") and page._executor:
            page._executor.log_message.connect(on_log)
            page._executor.node_started.connect(on_node_start)
            page._executor.node_finished.connect(on_node_done)
            page._executor.execution_finished.connect(on_exec_done)
            page._executor.task_requested.connect(on_task_req)
            log(f"  Executor created: {page._executor}")
            log(f"  Thread running: {page._executor.is_running}")
        else:
            log("  WARNING: No executor created!")
    except Exception as e:
        log(f"  FAIL: {e}")
        traceback.print_exc(file=LOG)
    
    # Process events for 15 seconds
    log("\n[8] Processing events for 15 seconds...")
    start = time.time()
    while time.time() - start < 15:
        app.processEvents()
        time.sleep(0.1)
    
    log("  15s elapsed.")
    if hasattr(page, "_executor") and page._executor:
        log(f"  Executor still running: {page._executor.is_running}")
        log(f"  Data store: {page._executor.data_store}")

log("\n" + "=" * 60)
log("DIAGNOSTIC COMPLETE")
log("=" * 60)
LOG.close()
sys.exit(0)
