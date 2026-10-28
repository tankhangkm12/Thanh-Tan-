import hashlib

from thanhtan.fsutil import file_sha256, write_bytes_atomic, write_text_atomic


def test_write_text_atomic_replaces_and_leaves_no_temp(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text("old", encoding="utf-8")
    write_text_atomic(path, "mới\n")
    assert path.read_bytes() == "mới\n".encode("utf-8")
    assert [p.name for p in tmp_path.iterdir()] == ["f.txt"]


def test_file_sha256_matches_hashlib(tmp_path):
    path = tmp_path / "b.bin"
    write_bytes_atomic(path, b"\x00\x01data")
    assert file_sha256(path) == hashlib.sha256(b"\x00\x01data").hexdigest()
