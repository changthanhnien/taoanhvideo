import json
import os

ARTIFACT_DIR = r"C:\Users\ASUS\.gemini\antigravity\brain\2bdbf117-1650-4c3d-bea6-84464b270760"

files = [
    "phase4_execution_trace.json",
    "phase4_strategy_samples.json",
    "phase4_pipeline_benchmark.json",
    "phase4_quality_regression.json",
    "phase4_final_summary.json"
]

content = "# Phase 4 Direct Artifact Outputs\n\n"

for f in files:
    path = os.path.join(ARTIFACT_DIR, f)
    content += f"## {f}\n```json\n"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
                content += json.dumps(data, indent=2)
            except:
                file.seek(0)
                content += file.read()
    else:
        content += "FILE NOT FOUND"
    content += "\n```\n\n"

out_path = os.path.join(ARTIFACT_DIR, "phase4_artifact_dump.md")
with open(out_path, "w", encoding="utf-8") as out_file:
    out_file.write(content)
