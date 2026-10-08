"""Testes de scripts/download_assets — FIX-19b (sha256 + path traversal) e FIX-19c (pin)."""
import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from scripts import download_assets as da

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_tar(tmp_path: Path, members: list) -> Path:
    tar_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        for member in members:
            info, data = member
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return tar_path


def _file_member(name: str, data: bytes = b"ok") -> tuple:
    return tarfile.TarInfo(name=name), data


def test_extract_rejects_path_traversal(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    tar_path = _build_tar(tmp_path, [_file_member("../evil.txt", b"pwned")])
    with tarfile.open(tar_path, "r:gz") as tar:
        with pytest.raises(RuntimeError, match="Unsafe path"):
            da._extract_safely(tar, dest)
    assert not (tmp_path / "evil.txt").exists()


def test_extract_rejects_absolute_path(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    tar_path = _build_tar(tmp_path, [_file_member("/abs/evil.txt")])
    with tarfile.open(tar_path, "r:gz") as tar:
        with pytest.raises(RuntimeError, match="Unsafe path"):
            da._extract_safely(tar, dest)


def test_extract_rejects_symlink(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    link = tarfile.TarInfo(name="evil-link")
    link.type = tarfile.SYMTYPE
    link.linkname = "../../outside"
    tar_path = _build_tar(tmp_path, [(link, b"")])
    with tarfile.open(tar_path, "r:gz") as tar:
        with pytest.raises(RuntimeError, match="unsupported member"):
            da._extract_safely(tar, dest)


def test_extract_allows_normal_members(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    tar_path = _build_tar(tmp_path, [_file_member("assets/ok.bin", b"data")])
    with tarfile.open(tar_path, "r:gz") as tar:
        da._extract_safely(tar, dest)
    assert (dest / "assets" / "ok.bin").read_bytes() == b"data"


def test_sha256_mismatch_aborts(monkeypatch, tmp_path):
    payload = b"tampered payload"

    def fake_download(url, dest_path):
        Path(dest_path).write_bytes(payload)

    monkeypatch.setattr(da, "_download", fake_download)
    monkeypatch.setattr(da, "_fetch_expected_sha256", lambda version: "0" * 64)
    target = tmp_path / "bundle.tar.gz"
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        da.download_and_verify("https://example.invalid/bundle.tar.gz", str(target))


def test_sha256_match_proceeds(monkeypatch, tmp_path):
    payload = b"good payload"
    expected = hashlib.sha256(payload).hexdigest()

    def fake_download(url, dest_path):
        Path(dest_path).write_bytes(payload)

    monkeypatch.setattr(da, "_download", fake_download)
    monkeypatch.setattr(da, "_fetch_expected_sha256", lambda version: expected)
    target = tmp_path / "bundle.tar.gz"
    da.download_and_verify("https://example.invalid/bundle.tar.gz", str(target))
    assert target.read_bytes() == payload


def test_sha256_unavailable_is_documented_not_fatal(monkeypatch, tmp_path, capsys):
    payload = b"no digest published"

    def fake_download(url, dest_path):
        Path(dest_path).write_bytes(payload)

    monkeypatch.setattr(da, "_download", fake_download)
    monkeypatch.setattr(da, "_fetch_expected_sha256", lambda version: None)
    target = tmp_path / "bundle.tar.gz"
    da.download_and_verify("https://example.invalid/bundle.tar.gz", str(target))
    out = capsys.readouterr().out
    assert "SHA-256" in out
    assert "disponivel" in out
    assert target.read_bytes() == payload


class _FakeApiResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_fetch_expected_sha256_sends_token_when_env_set(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = req.headers
        return _FakeApiResponse(b'{"assets": []}')

    monkeypatch.setattr(da.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_example")
    da._fetch_expected_sha256("5.6.0")

    assert captured["headers"].get("Authorization") == "Bearer ghp_example"


def test_fetch_expected_sha256_without_token_has_no_auth_header(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = req.headers
        return _FakeApiResponse(b'{"assets": []}')

    monkeypatch.setattr(da.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    da._fetch_expected_sha256("5.6.0")

    assert "Authorization" not in captured["headers"]


def test_requirements_pins_geniuslib():
    """FIX-19c: geniuslib pinado; demais linhas permanecem como estavam."""
    req = _REPO_ROOT / "requirements.txt"
    parsed = []
    for line in req.read_text(encoding="utf-8").splitlines():
        spec = line.split("#", 1)[0].strip()
        if spec:
            parsed.append(spec)
    assert "geniuslib==5.6.0" in parsed
