import re

with open('ui/dialogs/settings_dialog.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_dlg = '''        btn_layout = QHBoxLayout()
        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        self.layout.addLayout(btn_layout)'''

new_dlg = '''        btn_layout = QHBoxLayout()
        self.btn_fix = QPushButton("Mở trình duyệt để Đăng nhập / Cấp quyền Video FX")
        self.btn_fix.setStyleSheet("background-color: #3b82f6; color: white; padding: 5px 15px; font-weight: bold; border-radius: 4px;")
        self.btn_fix.clicked.connect(lambda: [self.accept(), parent._edit_account(account)] if parent and hasattr(parent, '_edit_account') else None)
        
        self.btn_close = QPushButton("Đóng")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_fix)
        btn_layout.addWidget(self.btn_close)
        self.layout.addLayout(btn_layout)'''

if old_dlg in content:
    content = content.replace(old_dlg, new_dlg)
else:
    print('WARNING: Could not find old_dlg')

with open('ui/dialogs/settings_dialog.py', 'w', encoding='utf-8') as f:
    f.write(content)
