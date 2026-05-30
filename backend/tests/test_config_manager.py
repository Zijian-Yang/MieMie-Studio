import concurrent.futures
import threading

from app.config import ConfigManager


def test_config_manager_concurrent_writes_do_not_share_temp_path(tmp_path, monkeypatch):
    """独立 manager 并发写同一配置目录时，不应因共享 config.tmp 互相删除。"""

    managers = [ConfigManager(str(tmp_path)) for _ in range(2)]
    replace_barrier = threading.Barrier(2)
    original_replace = __import__("os").replace

    def synchronized_replace(src, dst):
        replace_barrier.wait(timeout=5)
        return original_replace(src, dst)

    monkeypatch.setattr("app.config.os.replace", synchronized_replace)

    def write_config(index):
        managers[index]._write_with_lock({"writer": index})

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write_config, index) for index in range(2)]
        for future in futures:
            future.result(timeout=5)

    assert (tmp_path / "config.json").exists()
