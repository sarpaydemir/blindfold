"""Verified downloads and the append-only manifest (scripts/lab_archive.py).

RULES 2: every file is checked against the archive's own .CHECKSUM.
RULES 20-21: a failure is recorded by name, never read as "no data".
RULES 30: different content under an existing path stops the script.
No network: http_get is replaced with a stub.
"""

import hashlib
import json

import pytest

from helpers import load_script

la = load_script("lab_archive.py")


def row(path, sha, verified=True):
    return {"path": path, "sha256": sha, "checksum_verified": verified}


def lines(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def test_identical_content_is_not_appended_twice(tmp_path):
    m = la.Manifest(str(tmp_path / "manifest.jsonl"))
    m.add(row("a.zip", "aa"))
    m.add(row("a.zip", "aa"))
    assert len(lines(tmp_path / "manifest.jsonl")) == 1


def test_different_content_under_an_existing_path_stops(tmp_path):
    m = la.Manifest(str(tmp_path / "manifest.jsonl"))
    m.add(row("a.zip", "aa"))
    with pytest.raises(SystemExit, match="RULES 30"):
        m.add(row("a.zip", "bb"))


def test_a_failed_fetch_stays_on_record_when_the_retry_succeeds(tmp_path):
    path = tmp_path / "manifest.jsonl"
    m = la.Manifest(str(path))
    m.add(row("a.zip", None, verified=False))
    m.add(row("a.zip", "aa"))
    assert [r["sha256"] for r in lines(path)] == [None, "aa"]
    assert la.Manifest(str(path)).has_verified("a.zip")


@pytest.fixture
def archive(monkeypatch):
    served = {}

    def fake_get(url):
        if url not in served:
            raise la.FetchError("HTTP 404 Not Found")
        return served[url]

    monkeypatch.setattr(la, "http_get", fake_get)
    return served


def serve(served, key, blob, checksum=None):
    url = la.object_url(key)
    served[url] = blob
    digest = checksum or hashlib.sha256(blob).hexdigest()
    served[url + ".CHECKSUM"] = ("%s  %s\n" % (digest, key.rsplit("/", 1)[-1])).encode()


def test_a_verified_download_is_written_and_recorded(archive, tmp_path):
    key = "data/futures/um/monthly/klines/XUSDT/1h/XUSDT-1h-2026-01.zip"
    serve(archive, key, b"zip bytes")
    m = la.Manifest(str(tmp_path / "manifest.jsonl"))
    dest = tmp_path / "klines" / "XUSDT-1h-2026-01.zip"
    r = la.download_verified(key, str(dest), m)
    assert r["checksum_verified"] is True and r["error"] is None
    assert dest.read_bytes() == b"zip bytes"
    archive.clear()                     # a verified file is never fetched again
    assert la.download_verified(key, str(dest), m)["checksum_verified"] is True


def test_a_checksum_mismatch_is_kept_aside_and_named(archive, tmp_path):
    key = "data/x/XUSDT-1h-2026-02.zip"
    serve(archive, key, b"zip bytes", checksum="0" * 64)
    m = la.Manifest(str(tmp_path / "manifest.jsonl"))
    dest = tmp_path / "XUSDT-1h-2026-02.zip"
    r = la.download_verified(key, str(dest), m)
    assert r["checksum_verified"] is False
    assert r["error"].startswith("CHECKSUM MISMATCH")
    assert not dest.exists()
    assert (tmp_path / "XUSDT-1h-2026-02.zip.FAILED").read_bytes() == b"zip bytes"


def test_a_missing_file_is_a_named_failure_not_an_empty_result(archive, tmp_path):
    m = la.Manifest(str(tmp_path / "manifest.jsonl"))
    r = la.download_verified("data/x/NOPE.zip", str(tmp_path / "NOPE.zip"), m)
    assert r["sha256"] is None
    assert r["error"] == "zip fetch failed: HTTP 404 Not Found"


def test_non_ascii_symbols_are_percent_encoded():
    assert la.object_url("data/futures/um/币安人生USDT/x.zip").isascii()
