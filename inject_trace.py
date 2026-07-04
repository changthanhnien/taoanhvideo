import os
path = r'D:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\features\watermark_remove\source\app.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

old_code = '''    cap = cv2.VideoCapture(path)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))'''

new_code = '''    print("[TRACE] BƯỚC 5: Backend nhận request /api/process", flush=True)
    print("[TRACE] BƯỚC 5.1: Chuẩn bị gọi cv2.VideoCapture", flush=True)
    cap = cv2.VideoCapture(path)
    print("[TRACE] BƯỚC 5.2: cv2.VideoCapture đã xong", flush=True)
    fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))'''

if old_code in code:
    code = code.replace(old_code, new_code)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    print("Injected tracing into api_process")
else:
    print("Could not inject tracing")
