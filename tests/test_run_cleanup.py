import os, time
from orbitlab_backend.api.run_cleanup import cleanup_old_run_dirs, get_run_root

def test_cleanup_deletes_only_old_dirs(tmp_path):
    old = tmp_path / "oldjob"
    new = tmp_path / "newjob"
    old.mkdir(); new.mkdir()
    (old / "f.txt").write_text("x")
    ancient = time.time() - 30 * 3600
    os.utime(old, (ancient, ancient))
    n = cleanup_old_run_dirs(tmp_path, 24.0)
    assert n == 1
    assert not old.exists()
    assert new.exists()

def test_cleanup_missing_root_returns_zero(tmp_path):
    assert cleanup_old_run_dirs(tmp_path / "nope", 24.0) == 0
