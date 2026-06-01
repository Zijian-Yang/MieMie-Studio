import concurrent.futures
import threading

from app.services.storage import StorageService


def test_storage_service_concurrent_writes_do_not_share_temp_path(tmp_path, monkeypatch):
    """独立 storage 实例并发写同一 JSON 时，不应因共享 .tmp 互相删除。"""

    services = [StorageService(str(tmp_path / f"service-{index}")) for index in range(2)]
    target = tmp_path / "shared" / "task.json"
    target.parent.mkdir(parents=True)
    replace_barrier = threading.Barrier(2)
    original_replace = __import__("os").replace

    def synchronized_replace(src, dst):
        replace_barrier.wait(timeout=5)
        return original_replace(src, dst)

    monkeypatch.setattr("app.services.storage.os.replace", synchronized_replace)

    def write_json(index):
        services[index]._write_json_with_lock(target, {"writer": index})

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write_json, index) for index in range(2)]
        for future in futures:
            future.result(timeout=5)

    assert target.exists()
