import re

with open(r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\workers\task_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
with open(r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\workers\execute_new.py', 'r', encoding='utf-8') as f:
    new_content = f.read()

# Extract _async_execute and _async_process_batch from new_content
async_execute_match = re.search(r'    async def _async_execute\(self\):.*?(?=    async def _async_process_batch)', new_content, re.DOTALL)
async_process_match = re.search(r'    async def _async_process_batch\(self, batch, local_browser_manager, account\):.*', new_content, re.DOTALL)

if not async_execute_match or not async_process_match:
    print("Could not parse execute_new.py")
    exit(1)
    
new_async_execute = async_execute_match.group(0)
new_async_process = async_process_match.group(0)

# Replace in task_manager.py
# 1. Replace _async_execute
content = re.sub(r'    async def _async_execute\(self\):.*?(?=    def _execute\(self\):)', new_async_execute, content, flags=re.DOTALL)

# 2. Replace _async_process_batch
content = re.sub(r'    async def _async_process_batch\(self, batch, local_browser_manager\):.*?(?=class UpscaleSignals\(QObject\):)', new_async_process + '\n\n', content, flags=re.DOTALL)

with open(r'd:\Downloads\NAVTools.exe_extracted\NAVTools.exe_extracted\workers\task_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched task_manager.py")
