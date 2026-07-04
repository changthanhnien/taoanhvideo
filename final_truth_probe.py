import sys, os, json, time, shutil, hashlib
os.environ['QT_API'] = 'pyside6'
from pathlib import Path

ARTIFACTS_DIR = Path(r"C:\Users\ASUS\.gemini\antigravity\brain\9228e2ba-62b3-49c8-8df9-e48ecb1067de")
test_img = ARTIFACTS_DIR / "test_input.jpg"

import cv2
import numpy as np

# Create a real 500x500 test image if not exists
if not os.path.exists(test_img):
    img = np.random.randint(0, 255, (500, 500, 3), dtype=np.uint8)
    cv2.imwrite(str(test_img), img)

sys.path.insert(0, os.path.abspath(r'features\watermark_remove\source'))
from app import app as flask_app

client = flask_app.test_client()

output_verify = {
    "preview_output_exists": False,
    "preview_size_bytes": 0,
    "process_output_exists": False,
    "process_size_bytes": 0,
    "export_exists": False,
    "export_size_bytes": 0,
    "sha256": ""
}

runtime_verify = {
    "upload_ms": 0,
    "preview_ms": 0,
    "process_ms": 0,
    "export_ms": 0
}

output_compare = {
    "same_resolution": False,
    "same_duration": True, # It's an image
    "same_file_created": False
}

try:
    # 1. UPLOAD
    t0 = time.time()
    uploads_dir = os.path.abspath(r'features\watermark_remove\source\uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    # Simulate upload by copying since api doesn't expose raw file upload easily in test_client without multipart data
    # Actually we can do multipart upload:
    with open(test_img, 'rb') as f:
        data = {
            'file': (f, 'test_input.jpg')
        }
        res_up = client.post('/api/upload', data=data, content_type='multipart/form-data')
    runtime_verify["upload_ms"] = int((time.time() - t0) * 1000)
    
    # 2. PREVIEW
    t0 = time.time()
    payload_prev = {'video_name': 'test_input.jpg', 'method': 'inpaint', 'x': 0, 'y': 0, 'width': 100, 'height': 100}
    res_prev = client.post('/api/preview', data=json.dumps(payload_prev), content_type='application/json')
    d_prev = res_prev.get_json()
    runtime_verify["preview_ms"] = int((time.time() - t0) * 1000)
    
    if d_prev and d_prev.get('success'):
        prev_path = os.path.join(os.path.abspath(r'features\watermark_remove\source'), d_prev.get('after_url', '').lstrip('/'))
        if os.path.exists(prev_path):
            output_verify["preview_output_exists"] = True
            output_verify["preview_size_bytes"] = os.path.getsize(prev_path)

    # 3. PROCESS
    t0 = time.time()
    payload_proc = {'video_name': 'test_input.jpg', 'method': 'inpaint', 'x': 0, 'y': 0, 'width': 100, 'height': 100}
    res_proc = client.post('/api/process', data=json.dumps(payload_proc), content_type='application/json')
    d_proc = res_proc.get_json()
    
    if d_proc and d_proc.get('success'):
        task_id = d_proc['task_id']
        while True:
            res_stat = client.get(f'/api/status/{task_id}')
            d_stat = res_stat.get_json()
            if d_stat and 'task' in d_stat:
                t_stat = d_stat['task']['status']
                if t_stat in ('completed', 'error'):
                    break
            time.sleep(0.1)
            
        runtime_verify["process_ms"] = int((time.time() - t0) * 1000)
        
        if d_stat['task']['status'] == 'completed':
            # Check if output exists
            out_name = d_stat['task']['output_name']
            out_path = os.path.join(uploads_dir, out_name)
            if os.path.exists(out_path):
                output_verify["process_output_exists"] = True
                output_verify["process_size_bytes"] = os.path.getsize(out_path)
                
                # 4. EXPORT
                t0 = time.time()
                export_path = ARTIFACTS_DIR / out_name
                shutil.copy(out_path, export_path)
                runtime_verify["export_ms"] = int((time.time() - t0) * 1000)
                
                output_verify["export_exists"] = True
                output_verify["export_size_bytes"] = os.path.getsize(export_path)
                
                with open(export_path, 'rb') as f:
                    output_verify["sha256"] = hashlib.sha256(f.read()).hexdigest()
                    
                # Compare
                im_in = cv2.imread(str(test_img))
                im_out = cv2.imread(str(export_path))
                if im_in is not None and im_out is not None:
                    output_compare["same_resolution"] = (im_in.shape == im_out.shape)
                    output_compare["same_file_created"] = True

except Exception as e:
    pass

with open(ARTIFACTS_DIR / "output_verify.json", "w", encoding="utf-8") as f:
    json.dump(output_verify, f, indent=4)
    
with open(ARTIFACTS_DIR / "runtime_verify.json", "w", encoding="utf-8") as f:
    json.dump(runtime_verify, f, indent=4)

with open(ARTIFACTS_DIR / "output_compare.json", "w", encoding="utf-8") as f:
    json.dump(output_compare, f, indent=4)

print("DONE")
