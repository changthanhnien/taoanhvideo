# Kết quả Trace Runtime Upload

## Pipeline Trace (thứ tự kiểm tra thực tế)
1. **Click nút "Tải File Lên"** -> PASS
2. **<input type="file"> Có nhận event change không?** -> N/A (Bỏ qua do chạy native QtBridge)
3. **Qt File Dialog Có trả về đường dẫn thật không?** -> PASS (Dialog hiện lên, người dùng chọn file và Qt backend xử lý, trả về JSON string hợp lệ)
4. **QWebEngine chooseFiles() Có trả selectedFiles không?** -> N/A (Không dùng HTML5 input file)
5. **api_shim.js Có intercept fetch upload không?** -> N/A (Bỏ qua, không dùng fetch)
6. **QtBridge.dispatch() Có được gọi không?** -> PASS (JS gọi thành công hàm `/api/open_file_dialog`)
7. **/api/upload Có nhận request không?** -> N/A
8. **Response HTTP code JSON** -> **FAIL** (Dừng tại đây)

## Thông tin lỗi tầng FAIL
- **File**: `static/main.js`
- **Function**: `btnUpload.addEventListener('click', async () => {...})`
- **Line**: `const data = JSON.parse(resStr);`
- **Exception**: `SyntaxError: "undefined" is not valid JSON` (Exception bị catch ở khối `catch(e)` in ra `Native upload error`).
- **Callback chết**: Lỗi do `window.qtBridge.dispatch` không hoạt động dưới dạng Promise. `qwebchannel.js` yêu cầu truyền hàm callback ở tham số thứ 3, nếu không kết quả trả về luôn là `undefined`, khiến JS lập tức đi tiếp mà không chờ kết quả từ Python, dẫn đến parse JSON hỏng và tiến trình bị dừng.

## Khắc phục
Bọc lại lời gọi hàm thành Promise tại vị trí fail:
```javascript
const resStr = await new Promise(resolve => {
    window.qtBridge.dispatch('/api/open_file_dialog', '{}', resolve);
});
```
Ứng dụng đã chạy upload thành công 1 lần sau khi fix. Dừng kiểm tra theo đúng quy định.
