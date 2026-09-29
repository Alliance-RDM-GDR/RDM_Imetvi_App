# tests/test_manifest.py

import hashlib
import os

import pytest

from utils.manifest import (
    check_coverage, list_files, parse_manifest, sha256_file, total_size, verify_manifest,
)

REAL_RELEASE = r"D:\Alliance\FRDR\Curation\2026\1777\v1\O-shell-data-release"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def dataset(tmp_path):
    """Small release: nested folders, one file with a space in its name."""
    files = {
        "README.md": b"hello",
        "run/a.bin": b"\x00" * 3000,
        "run/sub/b.txt": b"beta",
        "run/sub/with space.dat": b"gamma",
    }
    for rel, data in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    manifest = "".join(f"{_sha(d)}  {rel}\n" for rel, d in files.items())
    (tmp_path / "MANIFEST.sha256").write_text(manifest)
    return tmp_path, files


def test_parse_manifest_reads_entries(dataset):
    folder, files = dataset
    entries, bad = parse_manifest(str(folder / "MANIFEST.sha256"))

    assert bad == []
    assert set(entries) == set(files)
    assert entries["run/sub/with space.dat"] == _sha(b"gamma")


def test_parse_manifest_tolerates_crlf_binary_marker_dot_slash_and_uppercase(tmp_path):
    digest = _sha(b"x")
    p = tmp_path / "MANIFEST.sha256"
    p.write_bytes(
        f"{digest.upper()} *./one.bin\r\n\r\n{digest}  two.bin\r\n".encode()
    )
    entries, bad = parse_manifest(str(p))

    assert bad == []
    assert entries == {"one.bin": digest, "two.bin": digest}


def test_parse_manifest_reports_bad_and_duplicate_lines(tmp_path):
    digest = _sha(b"x")
    p = tmp_path / "MANIFEST.sha256"
    p.write_text(
        f"{digest}  ok.bin\nnot a checksum line\n{digest[:-1]}  short.bin\n"
        f"\\{digest}  escaped.bin\n{_sha(b'y')}  ok.bin\n"
    )
    entries, bad = parse_manifest(str(p))

    assert list(entries) == ["ok.bin"]
    assert entries["ok.bin"] == _sha(b"y")           # last one wins
    assert [n for n, _ in bad] == [2, 3, 4, 5]
    assert "duplicate" in bad[-1][1]


def test_coverage_clean_dataset(dataset):
    folder, files = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    cov = check_coverage(str(folder), entries)

    assert cov == {"listed": 4, "on_disk": 4, "unlisted": [], "missing": []}


def test_coverage_reports_unlisted_and_missing_and_ignores_manifest(dataset):
    folder, _ = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    (folder / "run" / "stray.Rhistory").write_text("x")
    (folder / "run" / "sub" / "b.txt").unlink()
    cov = check_coverage(str(folder), entries)

    assert cov["unlisted"] == ["run/stray.Rhistory"]
    assert cov["missing"] == ["run/sub/b.txt"]
    assert "MANIFEST.sha256" not in cov["unlisted"]


def test_list_files_uses_forward_slashes(dataset):
    folder, files = dataset
    assert set(list_files(str(folder), exclude={"MANIFEST.sha256"})) == set(files)


def test_sha256_file_streams_in_chunks(tmp_path):
    p = tmp_path / "f.bin"
    data = os.urandom(10_000)
    p.write_bytes(data)
    seen = []
    digest = sha256_file(str(p), on_bytes=seen.append, chunk_size=1024)

    assert digest == _sha(data)
    assert max(seen) <= 1024 and sum(seen) == len(data)


def test_verify_all_ok(dataset):
    folder, files = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    result = verify_manifest(str(folder), entries)

    assert result["cancelled"] is False
    assert set(result["status"].values()) == {"OK"}
    assert len(result["status"]) == 4
    assert result["bytes_hashed"] == sum(len(d) for d in files.values())


def test_verify_detects_modified_and_missing(dataset):
    folder, _ = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    (folder / "run" / "sub" / "b.txt").write_bytes(b"BETA")
    (folder / "README.md").unlink()
    status = verify_manifest(str(folder), entries)["status"]

    assert status["run/sub/b.txt"] == "MODIFIED"
    assert status["README.md"] == "MISSING"
    assert status["run/a.bin"] == "OK"


def test_verify_subset_only_touches_requested_paths(dataset):
    folder, _ = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    (folder / "run" / "a.bin").write_bytes(b"corrupted")          # not in the subset
    result = verify_manifest(str(folder), entries, paths=["README.md", "not/in/manifest"])

    assert result["status"] == {"README.md": "OK"}


def test_verify_never_opens_paths_outside_the_folder(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret")
    inner = tmp_path / "inner"
    inner.mkdir()
    entries = {"../outside.txt": _sha(b"secret"), "/etc/passwd": _sha(b"x")}
    result = verify_manifest(str(inner), entries)

    assert result["status"] == {"../outside.txt": "UNSAFE_PATH", "/etc/passwd": "UNSAFE_PATH"}
    assert result["bytes_hashed"] == 0


def test_verify_cancel_between_files_keeps_partial_results(dataset):
    folder, _ = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > 3     # let a couple of files through, then stop

    result = verify_manifest(str(folder), entries, cancel=cancel)

    assert result["cancelled"] is True
    assert 0 < len(result["status"]) < 4


def test_cancel_mid_file_stops_reading_and_returns_none(tmp_path):
    p = tmp_path / "big.bin"
    p.write_bytes(b"\x00" * 100_000)
    chunks = []

    digest = sha256_file(str(p), cancel=lambda: len(chunks) >= 2, on_bytes=chunks.append, chunk_size=1000)

    assert digest is None
    assert len(chunks) == 2                       # stopped long before the 100 chunks


def test_verify_cancelled_before_start_hashes_nothing(tmp_path):
    (tmp_path / "f.bin").write_bytes(b"abc")
    result = verify_manifest(str(tmp_path), {"f.bin": _sha(b"abc")}, cancel=lambda: True)

    assert result["cancelled"] is True and result["status"] == {} and result["bytes_hashed"] == 0


def test_progress_reports_files_and_bytes(dataset):
    folder, files = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    events = []
    verify_manifest(str(folder), entries, progress=lambda *a: events.append(a))

    total = sum(len(d) for d in files.values())
    assert events[0][0] == 0 and events[0][1] == 4 and events[0][4] == total
    assert events[-1][0] == 4 and events[-1][3] == total          # final event: all done


def test_total_size(dataset):
    folder, files = dataset
    assert total_size(str(folder), list(files) + ["gone.bin", "../x"]) == sum(len(d) for d in files.values())


def test_verify_unreadable_directory_entry_does_not_raise(tmp_path):
    (tmp_path / "adir").mkdir()
    result = verify_manifest(str(tmp_path), {"adir": _sha(b"")})

    assert result["status"]["adir"] == "UNREADABLE"
    assert "adir" in result["errors"]


@pytest.mark.skipif(not os.path.isfile(os.path.join(REAL_RELEASE, "MANIFEST.sha256")),
                    reason="FRDR 1777 release not available on this machine")
def test_real_release_coverage_only_never_hashes():
    """Names only: the release is 878 GB, so this must not open any data file."""
    entries, bad = parse_manifest(os.path.join(REAL_RELEASE, "MANIFEST.sha256"))
    cov = check_coverage(REAL_RELEASE, entries)

    assert bad == [] and len(entries) == 25591
    assert cov["missing"] == []
    assert cov["unlisted"] == [".Rhistory", "O28/prfs/frombqavs/Oshell25mix-BQav0841.rprof"]


# ── ManifestVerifyWorker (the QThread wrapper used by the UI) ────────────
# run() is called directly: signals connect straight to a list, so no event
# loop or QApplication is needed.

def _run_worker(folder, entries, mode, cancel_first=False):
    from main import ManifestVerifyWorker
    worker = ManifestVerifyWorker(str(folder), entries, "MANIFEST.sha256", mode)
    if cancel_first:
        worker.cancel()
    out, progress = [], []
    worker.done.connect(out.append)
    worker.progress.connect(lambda *a: progress.append(a))
    worker.run()
    return out[0], progress


def test_worker_coverage_mode_does_not_hash(dataset):
    folder, files = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    (folder / "extra.txt").write_text("x")
    out, progress = _run_worker(folder, entries, "coverage")

    assert out["error"] is None and out["verify"] is None and progress == []
    assert out["coverage"]["unlisted"] == ["extra.txt"]
    assert out["bytes_total"] == sum(len(d) for d in files.values())


def test_worker_full_mode_reports_status_and_progress(dataset):
    folder, _ = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    (folder / "README.md").write_bytes(b"HELLO")
    out, progress = _run_worker(folder, entries, "full")

    assert out["verify"]["status"]["README.md"] == "MODIFIED"
    assert progress and progress[-1][0] == 4


def test_worker_cancel_returns_partial_result_instead_of_dying(dataset):
    folder, _ = dataset
    entries, _ = parse_manifest(str(folder / "MANIFEST.sha256"))
    out, _ = _run_worker(folder, entries, "full", cancel_first=True)

    assert out["verify"]["cancelled"] is True and out["verify"]["status"] == {}
    assert out["coverage"] is not None


def test_worker_missing_folder_reports_everything_missing_without_raising(tmp_path):
    out, _ = _run_worker(tmp_path / "does_not_exist", {"a": "0" * 64}, "coverage")

    assert out["error"] is None
    assert out["coverage"]["missing"] == ["a"] and out["bytes_total"] == 0


def test_format_bytes():
    from utils.manifest import format_bytes
    assert format_bytes(0) == "0 B"
    assert format_bytes(1536) == "1.5 KiB"
    assert format_bytes(878 * 1024 ** 3) == "878.0 GiB"
    assert format_bytes(3 * 1024 ** 4) == "3.0 TiB"
