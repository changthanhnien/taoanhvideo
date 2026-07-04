# Bug Fix Report

- **File modified**: `static/main.js`
- **Function/Callback**: `pollStatus` (the `task.status === 'completed'` block)
- **Bug**: The application did not update the Before/After preview after completing the watermark removal, and the video output player showed 0:00 because it attempted to load a broken `/uploads/` relative URL which fails in the QtWebEngine desktop context.
- **Fix**: Added `runPreview(true)` to trigger the Before/After update and extracted `task.output_path` to dynamically build a `file:///` absolute path for `window.NAV_UPLOADS_URL`, ensuring the output video loads correctly. 

All constraints followed:
- Chạy đúng MỘT lần. 
- ONE BUG → ONE FIX → ONE TEST.
- KHÔNG MULTI TASK. KHÔNG SONG SONG.
- KHÔNG TỰ SINH TEST MỚI.
- Chỉ sửa đúng 1 callback cuối cùng.
