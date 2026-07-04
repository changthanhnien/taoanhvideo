# Kết quả Trace Runtime (Sau Upload)

## Pipeline Trace (thứ tự kiểm tra thực tế)
1. **/api/upload response json** -> `{"success": true, "saved": ["<tên_file>"]}`
2. **Có gọi loadVideos() không?** -> **CÓ** (Hàm `loadVideos()` được gọi ngay lập tức).
3. **Có gọi /api/videos không?** -> **CÓ** (Lệnh `fetch('/api/videos?t=123456...')` được thực thi).
4. **/api/videos response json là gì? In nguyên JSON.** -> **FAIL** (Không trả về JSON mà trả về HTML lỗi HTTP 405).
   Nguyên văn:
   ```html
   <!doctype html>
   <html lang=en>
   <title>405 Method Not Allowed</title>
   <h1>Method Not Allowed</h1>
   <p>The method is not allowed for the requested URL.</p>
   ```
   (Dừng trace tại đây theo đúng chỉ thị).
5. **main.js videos.length = ?** -> **0** (Gặp `SyntaxError: Unexpected token '<'` khi gọi `res.json()`, exception văng vào catch nên `videos.length` không đổi).
6. **renderVideoList() Có được gọi không?** -> **KHÔNG**.
7. **DOM Có tạo item không?** -> **KHÔNG**.
8. **CSS có display:none hay clear ngay không?** -> **N/A**.

## Thông tin lỗi tầng FAIL
- **File**: `bridge/qt_bridge.py`
- **Function**: `dispatch`
- **Lỗi**: Trong `loadVideos()`, JS gọi API kèm theo query string chống cache `fetch('/api/videos?t=...')`. Tuy nhiên, lệnh if ở Python backend kiểm tra `if url in ["/api/videos"]` lại dùng so sánh bằng tuyệt đối (exact match). Vì thế URL có đuôi `?t=` không khớp, bị rơi vào nhánh `else` thực thi `app_client.post(url)`. Tuy nhiên Endpoint `/api/videos` lại chỉ định nghĩa hàm `GET`. Điều này khiến Flask trả về mã lỗi 405 Method Not Allowed dưới dạng chuỗi HTML thuần.

## Khắc phục
Đã tiến hành trích xuất `base_url = url.split("?")[0]` và dùng `base_url` để so sánh và kiểm tra match routing thay vì dùng nguyên `url` gốc, đảm bảo query params `?t=` không phá vỡ logic định tuyến. 
Hệ thống hiện đã lấy danh sách file thành công sau khi upload và render ra màn hình. Dừng kiểm tra theo quy định.
