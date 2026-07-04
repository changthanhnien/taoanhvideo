import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

# First replace _on_sync_failed definition
old_failed = '''    @Slot(str)
    def _on_sync_failed(self, error: str):
        self._load_accounts()
        QMessageBox.warning(self, "Lỗi đồng bộ", f"Đồng bộ thất bại, có thể do trình duyệt bị kẹt hoặc mạng chậm.\\nChi tiết lỗi: {error}")'''

new_failed = '''    @Slot(int, str)
    def _on_sync_failed(self, account_id: int, error: str):
        self._load_accounts()
        if "cấp quyền Video FX" in error or "Đăng nhập lại" in error or "Sửa" in error:
            reply = QMessageBox.question(self, "Cần thao tác", f"{error}\\n\\nBạn có muốn MỞ TRÌNH DUYỆT ngay bây giờ để xử lý không?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                account = self.db.get_account(account_id)
                if account:
                    self._edit_account(account)
        else:
            QMessageBox.warning(self, "Lỗi đồng bộ", f"Đồng bộ thất bại.\\nChi tiết lỗi: {error}")'''

if old_failed in content:
    content = content.replace(old_failed, new_failed)
else:
    print('WARNING: Could not find old_failed')

# Second replace the invokeMethod
old_invoke = '''                QMetaObject.invokeMethod(self, '_on_sync_failed', Qt.QueuedConnection, Q_ARG(str, tier))'''
new_invoke = '''                QMetaObject.invokeMethod(self, '_on_sync_failed', Qt.QueuedConnection, Q_ARG(int, account.id), Q_ARG(str, tier))'''

if old_invoke in content:
    content = content.replace(old_invoke, new_invoke)
else:
    print('WARNING: Could not find old_invoke')

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
