# 🎬 NAV TOOLS — Desktop AI Video/Image Generator

<p align="center">
  <img src="assets/logo.png" alt="NAVTools Logo" width="128" height="128">
</p>

**NAV Tools** là một ứng dụng desktop toàn diện và mạnh mẽ giúp tự động hóa quy trình tạo video và hình ảnh bằng trí tuệ nhân tạo (AI) sử dụng các nền t gian tiên tiến hàng đầu hiện nay như **Google Labs (Flow - Video-FX, Image-FX)** và **X.com Grok AI**. Ứng dụng được xây dựng trên nền tảng Python, giao diện đồ họa hiện đại với **PySide6** và lõi tự động hóa trình duyệt **Playwright** kết hợp công nghệ ẩn danh CDP chống phát hiện bot.

---

## 📸 Giao diện & Các tính năng nổi bật của từng Tab

### 1. Tạo Ảnh Flow (Image-FX)
* **Mô tả**: Tự động hóa quy trình tạo ảnh nghệ thuật sử dụng model thế hệ mới nhất của Google (**Nano Banana 2 / Imagen 3**). Hỗ trợ tính năng **Tạo hàng loạt (Batch Generation)**, tự động lấy token và tải ảnh sạch về máy mà không cần thao tác tay.
* **Giao diện**:
![Tạo ảnh Flow](assets/flow_image.png)

---

### 2. Tạo Video Flow (Video-FX)
* **Mô tả**: Tạo video chất lượng cao với model cao cấp nhất (**Veo 3.1 - Fast**). Hỗ trợ cấu hình tỷ lệ khung hình (16:9, 9:16, 1:1), thời lượng (6s, 8s). Tự động điền prompt, bấm tạo và theo dõi tiến trình trực quan trên giao diện ứng dụng.
* **Giao diện**:
![Tạo video Flow](assets/flow_video.png)

---

### 3. Video to Video (Character Video)
* **Mô tả**: Chuyển đổi phong cách hoặc nhân vật từ một video nguồn đầu vào thành một video mới nhưng vẫn giữ nguyên chuyển động vật lý, biểu cảm và nhịp độ gốc.
* **Giao diện**:
![Video to Video](assets/char_video.png)

---

### 4. Nối Khung Hình (Long Video / Frame to Video)
* **Mô tả**: Tạo các video dài và mượt mà hơn bằng cách nối ghép và thiết lập hiệu ứng chuyển cảnh mềm mại giữa các khung ảnh tĩnh hoặc các đoạn video ngắn khác nhau.
* **Giao diện**:
![Nối khung hình](assets/frame_video.png)

---

### 5. Tạo Ảnh Grok (Grok Image)
* **Mô tả**: Kết nối trực tiếp với tài khoản X Premium của bạn để tạo hình ảnh nghệ thuật từ văn bản sử dụng mô hình Grok AI thế hệ mới với hai chế độ: Tối ưu tốc độ (Speed) hoặc Tối ưu chất lượng (Quality).
* **Giao diện**:
![Tạo ảnh Grok](assets/grok_image.png)

---

### 6. Tạo Video Grok (Grok Video)
* **Mô tả**: Tạo các clip chuyển động ngắn độc đáo trực tiếp từ mô tả văn bản thông qua tích hợp API tự động hóa tài khoản Grok AI.
* **Giao diện**:
![Tạo video Grok](assets/grok_video.png)

---

### 7. Xóa Logo (Watermark Remove)
* **Mô tả**: Sử dụng công nghệ học sâu (Inpainting - LaMa, Telea, Smart Engine) để tự động dò quét và xóa bỏ các watermark, logo hoặc vật thể thừa trên hình ảnh/video một cách tự nhiên nhất mà không làm mờ nhoè vùng xung quanh.
* **Giao diện**:
![Xóa logo](assets/watermark_remove.png)

---

### 8. Workflow Studio (Node-based Editor)
* **Mô tả**: Không gian làm việc kéo thả trực quan giúp bạn liên kết nhiều tác vụ tạo ảnh, tạo video, chuyển văn bản thành giọng nói (TTS), dịch thuật thành một quy trình tự động hóa liên tục từ đầu đến cuối (Pipeline).
* **Giao diện**:
![Workflow Studio](assets/workflow_studio.png)

---

### 9. Lịch Sử Tạo (History)
* **Mô tả**: Trình quản lý lưu trữ tất cả các tác vụ đã thực hiện. Bạn có thể xem lại hình ảnh/video kết quả, kiểm tra lại prompt đã sử dụng, tải lại file hoặc chạy lại tác vụ bị lỗi chỉ với một nút bấm.
* **Giao diện**:
![Lịch sử tạo](assets/history.png)

---

### 10. Cài Đặt Hệ Thống (Settings)
* **Mô tả**: Nơi quản lý danh sách tài khoản Google và Grok (thêm, sửa, xóa, đồng bộ hóa cookie), cấu hình đường dẫn lưu kết quả mặc định, tùy chọn phông chữ giao diện và chế độ hiển thị sáng/tối (Light/Dark mode).
* **Giao diện**:
![Cài đặt hệ thống](assets/settings.png)

---

## 🛠️ Yêu cầu hệ thống

* **Hệ điều hành**: Windows 10 / 11 (64-bit).
* **Python**: Phiên bản 3.10 hoặc 3.11.
* **Trình duyệt**: Google Chrome bản chính thức đã được cài đặt trên máy.

---

## 🚀 Hướng dẫn Cài đặt & Khởi chạy

### Bước 1: Tải mã nguồn về máy
Bạn có thể clone repository này bằng Git:
```bash
git clone https://github.com/changthanhnien/taoanhvideo.git
cd taoanhvideo
```
Hoặc chọn **Code** -> **Download ZIP** trên GitHub, sau đó giải nén thư mục ra máy tính.

### Bước 2: Cài đặt các thư viện phụ thuộc
Mở Command Prompt (cmd) hoặc PowerShell tại thư mục dự án và chạy lệnh sau để cài đặt các gói thư viện Python cần thiết:
```bash
pip install -r requirements.txt
```

### Bước 3: Cài đặt trình điều khiển trình duyệt Playwright
Chạy lệnh sau để Playwright tải và đăng ký các browser driver trên hệ thống:
```bash
playwright install chromium
```

### Bước 3.5: Cấu hình FFmpeg (Bắt buộc cho xử lý Video)
Để sử dụng các tính năng ghép nối video hoặc chỉnh sửa video nâng cao, bạn cần đặt tệp tin `ffmpeg.exe` vào thư mục `ffmpeg/` ở thư mục gốc của dự án.
1. Tạo thư mục tên `ffmpeg` trong thư mục dự án (nếu chưa có).
2. Tải `ffmpeg.exe` dành cho Windows (Ví dụ từ: https://github.com/GyanD/codexffmpeg/releases hoặc trang chủ FFmpeg).
3. Sao chép tệp tin `ffmpeg.exe` vào thư mục `ffmpeg/` vừa tạo.

### Bước 4: Khởi chạy phần mềm
Chạy tệp tin chính `main.py` để khởi động ứng dụng:
```bash
python main.py
```

---

## 📖 Hướng dẫn Sử dụng

### 1. Đăng nhập và cấu hình tài khoản
1. Mở phần mềm, nhấn vào biểu tượng **Cài đặt** (Settings) ở góc dưới bên trái (hoặc chọn tab Cài đặt hệ thống).
2. Tại bảng **Tài khoản Google** hoặc **Tài khoản Grok**, nhấn nút **Thêm tài khoản**.
3. Một cửa sổ Chrome thực tế sẽ hiện lên. Bạn chỉ cần thực hiện đăng nhập vào tài khoản Google hoặc X (Grok) của mình như bình thường.
4. Sau khi đăng nhập thành công, cửa sổ Chrome sẽ tự động đóng lại. Hệ thống sẽ đồng bộ hóa cookie và hiển thị trạng thái tài khoản là **Đã kết nối** (Connected).

### 2. Thiết lập tác vụ tạo ảnh / video hàng loạt
1. Tại tab **Tạo ảnh Flow** hoặc **Tạo video Flow**, điền nội dung mô tả vào khung **Prompt**.
2. Thiết lập các thông số: Tỷ lệ ảnh/video, số lượng (Quantity) cần tạo hàng loạt (Ví dụ: tạo 10 ảnh).
3. Nhấn nút **Bắt đầu tạo**. Tiến trình chạy ẩn sẽ tự động kích hoạt Chrome dưới giao thức CDP, tự động lấy token và gửi yêu cầu tạo.
4. Kết quả sau khi được tạo xong sẽ được tự động tải về thư mục máy tính của bạn và cập nhật trạng thái trên bảng theo dõi tác vụ.

### 3. Thư mục lưu trữ kết quả tạo ảnh/video
Mặc định kết quả ảnh và video sẽ được tự động tải về thư mục:
* Ảnh: `C:\Users\<Tên_User>\.vidgen\output\images`
* Video: `C:\Users\<Tên_User>\.vidgen\output\videos`
*(Bạn có thể tùy chỉnh lại đường dẫn lưu trữ này trong phần **Cài đặt**)*

---

## 📦 Đóng gói phần mềm thành tệp tin chạy trực tiếp (.EXE)

Nếu muốn đóng gói toàn bộ mã nguồn thành một tệp tin duy nhất `NAVTools.exe` để chạy trực tiếp không cần cài đặt Python, bạn có thể sử dụng PyInstaller với file cấu hình `.spec` đi kèm:
```bash
pyinstaller NAVTools.spec
```
Tệp tin chạy được sau khi đóng gói sẽ nằm trong thư mục `dist/`.
