#!/usr/bin/env python3
"""
lab_archive.py -- shared helpers for talking to the public Binance data archive.

What it does : HTTP GET with retries, S3 bucket listing (paginated), SHA-256,
               and an append-only download manifest.
Input        : nothing on disk; reads only from https://data.binance.vision
Output       : nothing on its own; imported by the numbered scripts.
Rules        : RULES 2  (record source URL, download time, SHA-256; verify the
                         archive's own .CHECKSUM companion)
               RULES 23 (clock is read from the system, never guessed)
               RULES 26 (resumable: callers checkpoint, this module never
                         re-downloads a file already present and verified)
               RULES 27 (documented addresses only; no guessed URLs)
               RULES 30 (append-only: writing different content under an
                         existing key stops the script)

Where the addresses come from
-----------------------------
DOWNLOAD_BASE  The archive's own download host. The URL pattern
               data/futures/um/monthly/klines/{SYMBOL}/{INTERVAL}/
               {SYMBOL}-{INTERVAL}-{YYYY}-{MM}.zip
               and the companion "{filename}.zip.CHECKSUM" are documented in
               https://github.com/binance/binance-public-data (linked from the
               archive's own front page), which also gives the verification
               command "sha256sum -c <file>.zip.CHECKSUM".

LIST_BASE      The archive's front page (https://data.binance.vision/) loads
               list.js, which builds its directory listing by calling the S3
               REST ListBucket interface of the bucket "data.binance.vision"
               with the query parameters ?delimiter=/&prefix=...&marker=...
               (see createS3QueryUrl() in that script). LIST_BASE is that same
               interface, reached at the bucket's regional S3 endpoint. It was
               not guessed: it was read out of the archive's own page script
               and then confirmed to return ListBucketResult XML.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# ---------------------------------------------------------------- constants --
DOWNLOAD_BASE = "https://data.binance.vision"
LIST_BASE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

# Network behaviour. Chosen here so no numbered script carries its own values.
HTTP_TIMEOUT_S = 60      # per-request socket timeout
HTTP_RETRIES = 5         # attempts per URL before it is recorded as a failure
HTTP_BACKOFF_S = 2.0     # first retry wait; doubles each attempt
USER_AGENT = "balikcil-lab/1.0 (research; public archive)"


def utc_now_iso() -> str:
    """System clock, UTC, second resolution (RULES 23)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def object_url(key: str) -> str:
    """Download URL for one archive object key.

    The key is percent-encoded because the archive holds contracts whose symbol
    is not ASCII (e.g. the Chinese-named meme contracts). Without this, urllib
    raises UnicodeEncodeError and the file looks absent when it is not
    (RULES 20: a client-side error is not "no data").
    """
    return DOWNLOAD_BASE + "/" + urllib.parse.quote(key, safe="/")


class FetchError(Exception):
    """Carries the last real error text so a failure is reported by name."""


def http_get(url: str) -> bytes:
    """GET with retries. Raises FetchError carrying the last error text.

    A 404 is not retried: the archive uses it to mean "this file does not
    exist", which is an answer, not a failure.
    """
    last = None
    for attempt in range(HTTP_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last = "HTTP %s %s" % (exc.code, exc.reason)
            if exc.code == 404:
                raise FetchError(last) from exc
        except Exception as exc:  # noqa: BLE001 - recorded verbatim, not swallowed
            last = "%s: %s" % (type(exc).__name__, exc)
        if attempt < HTTP_RETRIES - 1:
            time.sleep(HTTP_BACKOFF_S * (2 ** attempt))
    raise FetchError(last or "unknown error")


def list_prefix(prefix: str) -> dict:
    """List one bucket prefix with delimiter='/'.

    Returns {"dirs": [...], "files": [{"key","size","last_modified"}, ...]}
    following the NextMarker/marker pagination the archive's own list.js uses.
    """
    dirs, files, marker = [], [], ""
    while True:
        query = {"delimiter": "/", "prefix": prefix, "max-keys": "1000"}
        if marker:
            query["marker"] = marker
        url = LIST_BASE + "?" + urllib.parse.urlencode(query)
        root = ET.fromstring(http_get(url))
        page_dirs = [p.findtext(S3_NS + "Prefix") for p in root.findall(S3_NS + "CommonPrefixes")]
        dirs.extend(page_dirs)
        page_keys = []
        for c in root.findall(S3_NS + "Contents"):
            key = c.findtext(S3_NS + "Key")
            page_keys.append(key)
            files.append({
                "key": key,
                "size": int(c.findtext(S3_NS + "Size")),
                "last_modified": c.findtext(S3_NS + "LastModified"),
            })
        if root.findtext(S3_NS + "IsTruncated") != "true":
            break
        nxt = root.findtext(S3_NS + "NextMarker")
        if not nxt:
            tail = page_keys or page_dirs
            if not tail:
                break
            nxt = tail[-1]
        marker = nxt
    return {"dirs": dirs, "files": files}


# -------------------------------------------------------------- manifest ----
class Manifest:
    """Append-only JSONL record of every downloaded file (RULES 2, 30).

    One line per file: relative path, source URL, download time, SHA-256,
    checksum-verification result. If a line already exists for a path with
    *different* content, the script stops instead of overwriting (RULES 30).
    """

    def __init__(self, path: str):
        self.path = path
        self.rows = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        row = json.loads(line)
                        self.rows[row["path"]] = row

    def has_verified(self, rel_path: str) -> bool:
        row = self.rows.get(rel_path)
        return bool(row) and row.get("checksum_verified") is True

    def get(self, rel_path: str):
        return self.rows.get(rel_path)

    def add(self, row: dict) -> None:
        key = row["path"]
        old = self.rows.get(key)
        if old is not None:
            if old.get("sha256") is None:
                # The earlier line recorded a *failed* fetch: no bytes were ever
                # recorded under this path, so this is a retry, not a rewrite.
                # The failure line stays in the file; the new line is appended
                # after it, so the history stays complete (RULES 20, 30).
                pass
            elif old.get("sha256") != row.get("sha256"):
                raise SystemExit(
                    "STOP (RULES 30): manifest already holds %s with sha256 %s, "
                    "refusing to overwrite with %s"
                    % (key, old.get("sha256"), row.get("sha256"))
                )
            else:
                return  # identical content: nothing to append
        self.rows[key] = row
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())


def download_verified(key: str, dest_path: str, manifest: Manifest) -> dict:
    """Download one archive object and verify it against its own .CHECKSUM.

    Returns the manifest row. Never raises on a verification mismatch: the
    mismatch is recorded as a named failure (RULES 20, 21) and the bad file is
    kept next to the record with a .FAILED suffix so it can be inspected.
    """
    rel = os.path.relpath(dest_path, os.path.dirname(manifest.path))
    if manifest.has_verified(rel) and os.path.exists(dest_path):
        return manifest.get(rel)

    zip_url = object_url(key)
    sum_url = zip_url + ".CHECKSUM"
    row = {
        "path": rel,
        "source_url": zip_url,
        "checksum_url": sum_url,
        "downloaded_at_utc": None,
        "sha256": None,
        "expected_sha256": None,
        "checksum_verified": False,
        "error": None,
    }

    try:
        blob = http_get(zip_url)
    except FetchError as exc:
        row["downloaded_at_utc"] = utc_now_iso()
        row["error"] = "zip fetch failed: %s" % exc
        manifest.add(row)
        return row

    row["downloaded_at_utc"] = utc_now_iso()
    row["sha256"] = sha256_bytes(blob)

    try:
        sum_blob = http_get(sum_url)
        # documented form: "<sha256>  <filename>"
        row["expected_sha256"] = sum_blob.decode("utf-8", "replace").split()[0].lower()
    except FetchError as exc:
        row["error"] = "checksum fetch failed: %s" % exc

    if row["expected_sha256"] is not None:
        row["checksum_verified"] = (row["sha256"] == row["expected_sha256"])
        if not row["checksum_verified"]:
            row["error"] = "CHECKSUM MISMATCH: computed %s, archive says %s" % (
                row["sha256"], row["expected_sha256"])

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    out = dest_path if row["checksum_verified"] else dest_path + ".FAILED"
    with open(out, "wb") as fh:
        fh.write(blob)
    manifest.add(row)
    return row
