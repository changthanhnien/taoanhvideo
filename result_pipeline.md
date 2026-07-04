# Kết quả Trace Runtime Pipeline Result

## Kết quả kiểm tra từng bước
- **Process Button**: PASS (Kích hoạt sự kiện chính xác).
- **main.js fetch("/api/process")**: PASS (Gửi yêu cầu hợp lệ).
- **Flask /api/process**: FAIL
- **video output path**: FAIL (File sinh ra không tương thích trình duyệt).
- **JSON response**: PASS (Trả status và url đúng).
- **main.js success callback**: PASS (Gọi tới hàm build giao diện).
- **setResultVideo()**: PASS (Cập nhật thành công DOM player bên phải).
- **HTML <video>**: PASS (Cấu trúc HTML hiển thị đủ player).
- **video.load()**: FAIL (File video hỏng định dạng trình duyệt).
- **video.play()**: FAIL (Màn hình đen, báo 0:00).

## Thông tin lỗi tầng FAIL
- **Tầng lỗi**: `source/app.py` và `static/main.js`.
- **Nguyên nhân chính**: Tại `app.py`, cấu hình FFmpeg Writer để xuất file video (`libx264`) đã bỏ quên cờ cấu hình format điểm ảnh. Vì dữ liệu đầu vào pipe là `bgr24`, bộ nén `libx264` tự động xuất file thành định dạng `yuv444p`. Tuy nhiên, trình duyệt web / thẻ `<video>` HTML5 **không hỗ trợ** đọc `yuv444p`. Kết quả là FFmpeg vẫn ghi thành công, file có dung lượng > 0, mở bằng OpenCV hay VLC đều được, nhưng trình duyệt từ chối đọc, dẫn đến player hiển thị `0:00` và màn hình đen.
- **Nguyên nhân phụ**: Hàm render giao diện ở `main.js` chỉ thay đổi `innerHTML` của vùng chứa mà chưa chủ động fetch/load file video vào bộ đệm của trình duyệt sau khi thay đổi đường dẫn DOM.

## Khắc phục
1. Ở tầng Python (`app.py`): Đã bổ sung thông số `-pix_fmt yuv420p` vào danh sách lệnh subprocess của bộ ghi FFmpeg. Việc này đảm bảo file xuất ra tuân thủ chuẩn màu tương thích tối đa với HTML5.
2. Ở tầng Javascript (`main.js`): Đã lấy ra đối tượng video node và gọi trực tiếp `video.load()` cùng `video.play()` ngay khi kết thúc callback cập nhật giao diện.

Video kết quả hiện tại đã có thể play mượt mà trên QtWebEngine, duration và nút tải xuống hoàn toàn khả dụng. Dừng kiểm tra.
