import re

with open("workers/task_manager.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update AccountPool
old_account_pool = """class AccountPool:
    def __init__(self, db):
        self.db = db
        self._busy = set()

    def acquire(self):
        accounts = self.db.get_accounts(enabled_only=True) if self.db else []
        for account in accounts:
            if account.id not in self._busy:
                self._busy.add(account.id)
                return account
        return None

    def release(self, account):
        if account:
            self._busy.discard(account.id)

    def available_count(self):
        try:
            return len([a for a in self.db.get_accounts(enabled_only=True) if a.id not in self._busy])
        except Exception:
            return 0"""

new_account_pool = """class AccountPool:
    def __init__(self, db):
        self.db = db
        self._counts = {}

    def acquire(self, max_per_account: int = 1):
        accounts = self.db.get_accounts(enabled_only=True) if self.db else []
        for account in accounts:
            count = self._counts.get(account.id, 0)
            if count < max_per_account:
                self._counts[account.id] = count + 1
                return account
        return None

    def release(self, account):
        if account:
            count = self._counts.get(account.id, 0)
            if count > 0:
                self._counts[account.id] = count - 1

    def available_count(self):
        try:
            return len(self.db.get_accounts(enabled_only=True))
        except Exception:
            return 0"""

code = code.replace(old_account_pool, new_account_pool)

# 2. Update _async_execute
old_execute = """        try:
            for i, item in enumerate(items, 1):
                if self._cancelled:
                    break
                while self._paused and not self._cancelled:
                    await asyncio.sleep(0.2)
                try:
                    await self._async_process_item(item, local_browser_manager)
                except Exception as e:
                    item_id = getattr(item, "id", 0)
                    log.error(f"Error processing item {item_id}: {e}")
                    self.signals.item_error.emit(item_id, str(e))
                self.signals.task_progress.emit(task_id, i, total)
                # Delay between items to avoid spam
                if delay > 0 and i < total and not self._cancelled:
                    log.info(f"Delay {delay}s before next item...")
                    await asyncio.sleep(delay)
        finally:
            await local_browser_manager.stop()"""

new_execute = """        try:
            parallel = getattr(self.task, "parallel_per_account", 1) or 1
            if parallel <= 0: parallel = 1
            
            sem = asyncio.Semaphore(parallel)
            
            async def worker(index, item):
                async with sem:
                    if self._cancelled:
                        return
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.2)
                    try:
                        await self._async_process_item(item, local_browser_manager)
                    except Exception as e:
                        item_id = getattr(item, "id", 0)
                        log.error(f"Error processing item {item_id}: {e}")
                        self.signals.item_error.emit(item_id, str(e))
                    self.signals.task_progress.emit(task_id, index, total)
                    if delay > 0 and not self._cancelled:
                        log.info(f"Delay {delay}s before next item...")
                        await asyncio.sleep(delay)

            tasks = [asyncio.create_task(worker(i, item)) for i, item in enumerate(items, 1)]
            if tasks:
                await asyncio.gather(*tasks)
        finally:
            await local_browser_manager.stop()"""

code = code.replace(old_execute, new_execute)

# 3. Update acquire call in _async_process_item
old_acquire = """        account = self.account_pool.acquire()
        while not account and not self._cancelled:
            await asyncio.sleep(2)
            account = self.account_pool.acquire()"""

new_acquire = """        parallel = getattr(self.task, "parallel_per_account", 1) or 1
        account = self.account_pool.acquire(parallel)
        while not account and not self._cancelled:
            await asyncio.sleep(2)
            account = self.account_pool.acquire(parallel)"""

code = code.replace(old_acquire, new_acquire)

with open("workers/task_manager.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Updated task_manager.py")
