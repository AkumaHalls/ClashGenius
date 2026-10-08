"""Download GeniusLib assets from GitHub Releases if not present.

A integridade e verificada por SHA-256 **quando o digest esta disponivel** na
API de releases do GitHub (fail-closed em divergencia); sem digest, o download
segue com aviso. A API usa ``GITHUB_TOKEN`` (se definido) para elevar o rate limit.
"""
import hashlib
import json
import os
import posixpath
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlsplit

# FIX-19b/FIX-19c: alinhado a geniuslib==5.6.0 (pin em requirements.txt).
# Verificado em 2026-10-08: HEAD
#   https://github.com/AkumaHalls/GeniusLib/releases/download/v5.6.0/geniuslib-assets-5.6.0.tar.gz
# -> HTTP 200 (387676665 bytes) e a API de releases publica digest sha256 do asset.
ASSETS_VERSION = "5.6.0"
REPO = "AkumaHalls/GeniusLib"
GITHUB_URL = f"https://github.com/{REPO}/releases/download/v{ASSETS_VERSION}/geniuslib-assets-{ASSETS_VERSION}.tar.gz"
RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/tags/v{ASSETS_VERSION}"

# Mesmos hosts confiaveis do script irmao (GeniusLib/scripts/download_assets.py).
ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "api.github.com",
    }
)

# Teto generoso para um bundle de ~0.4GB (fonte maliciosa nao pode streamar infinito).
MAX_DOWNLOAD_BYTES = 1 << 30


def get_assets_dir() -> str:
    import geniuslib.utils
    return geniuslib.utils.get_assets_dir()


def _is_allowed_download_host(host: Optional[str]) -> bool:
    return ((host or "").lower().rstrip(".")) in ALLOWED_DOWNLOAD_HOSTS


def _download(url: str, dest_path: str) -> None:
    """Baixa ``url`` para ``dest_path`` com host permitido, redirect validado e teto de bytes."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not _is_allowed_download_host(parsed.hostname):
        raise RuntimeError(f"Refusing to download from untrusted host: {url}")
    total = 0
    with urllib.request.urlopen(url, timeout=60) as resp, open(dest_path, "wb") as out:
        final_host = urlsplit(resp.geturl()).hostname
        if not _is_allowed_download_host(final_host):
            raise RuntimeError(f"Redirected to untrusted host: {resp.geturl()}")
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise RuntimeError(f"Download exceeded {MAX_DOWNLOAD_BYTES} bytes; aborting.")
            out.write(chunk)


def _fetch_expected_sha256(version: str) -> Optional[str]:
    """Retorna o digest sha256 publicado pela API do GitHub, ou None se indisponivel.

    Usa ``GITHUB_TOKEN`` no header Authorization quando presente, elevando o
    rate limit da API (o digest so existe em respostas nao truncadas).
    """
    url = f"https://api.github.com/repos/{REPO}/releases/tags/v{version}"
    asset_name = f"geniuslib-assets-{version}.tar.gz"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "clashgenius-download-assets",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.load(resp)
    except Exception:
        return None
    for asset in release.get("assets", []):
        if asset.get("name") == asset_name:
            digest = asset.get("digest") or ""
            return digest.split(":", 1)[1] if ":" in digest else (digest or None)
    return None


def _sha256_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download_and_verify(url: str, dest_path: str, version: Optional[str] = None) -> None:
    """Baixa o tarball e verifica o SHA-256 **quando o digest esta disponivel**.

    Host allowlist + HTTPS sao sempre exigidos no download. Quando a API publica
    o digest, divergencia e fail-closed (aborta); sem digest, segue com aviso.
    """
    _download(url, dest_path)
    expected = _fetch_expected_sha256(version or ASSETS_VERSION)
    if not expected:
        print(
            "Aviso: digest SHA-256 indisponivel na API do GitHub; seguindo sem "
            "verificacao de integridade (a verificacao ocorre quando o digest esta disponivel)."
        )
        return
    actual = _sha256_file(dest_path)
    if actual.lower() != expected.lower():
        raise RuntimeError(f"SHA-256 mismatch: esperado {expected}, obtido {actual}. Recusando extrair.")
    print(f"SHA-256 verificado: {expected}")


def _validate_dest(assets_dir: str) -> str:
    """O destino precisa ser absoluto e a pasta ``assets`` do pacote geniuslib."""
    assets_dir = os.path.abspath(assets_dir)
    if os.path.basename(assets_dir) != "assets":
        raise RuntimeError(f"Destino invalido para assets: {assets_dir}")
    return assets_dir


def _extract_root(assets_dir: str, member_names: List[str]) -> str:
    """Escolhe o diretorio de extracao conforme o layout do tarball.

    geniuslib-assets <=5.5.4 empacota membros como ``assets/...`` (extrair no pai);
    a partir de 5.6.0 o conteudo vem na raiz (extrair dentro de ``assets_dir``).
    """
    tops = set()
    for name in member_names:
        norm = posixpath.normpath(name)
        if norm == "." or norm == ".." or norm.startswith("../"):
            continue  # _extract_safely rejeita depois
        tops.add(norm.split("/", 1)[0])
    if tops == {"assets"}:
        return os.path.dirname(assets_dir)
    return assets_dir


def _extract_safely(tar: tarfile.TarFile, dest) -> None:
    """Extrai apenas arquivos/dirs normais, sem sair de ``dest`` (path traversal/symlink)."""
    dest = Path(dest)
    base = dest.resolve()
    for member in tar.getmembers():
        # Apenas arquivos e diretorios: symlink/hardlink com alvo fora de dest
        # fariam a extracao escrita atraves dele, fora do destino.
        if not (member.isfile() or member.isdir()):
            raise RuntimeError(f"Refusing to extract unsupported member {member.name!r}")
        target = (dest / member.name).resolve()
        if not target.is_relative_to(base):
            raise RuntimeError(f"Unsafe path in archive: {member.name}")
        try:
            tar.extract(member, dest, filter="data")
        except TypeError:
            # Python < 3.12 nao tem o data filter; as checagens acima ja bastam.
            tar.extract(member, dest)


def main():
    try:
        assets_dir = get_assets_dir()
    except Exception:
        # Fallback: resolve from installed package
        import importlib
        spec = importlib.util.find_spec("geniuslib")
        if spec is None or spec.origin is None:
            print("geniuslib not installed", file=sys.stderr)
            sys.exit(1)
        assets_dir = os.path.join(os.path.dirname(spec.origin), "static", "assets")

    assets_dir = _validate_dest(assets_dir)

    if os.path.isdir(assets_dir) and os.listdir(assets_dir):
        print(f"Assets already present: {assets_dir}")
        return

    print(f"Downloading GeniusLib assets v{ASSETS_VERSION}...")
    print(f"Target: {assets_dir}")

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        download_and_verify(GITHUB_URL, tmp_path)
        os.makedirs(assets_dir, exist_ok=True)
        with tarfile.open(tmp_path, "r:gz") as tar:
            names = [m.name for m in tar.getmembers()]
            extract_root = _extract_root(assets_dir, names)
            os.makedirs(extract_root, exist_ok=True)
            _extract_safely(tar, extract_root)
        if not os.path.isdir(assets_dir) or not os.listdir(assets_dir):
            raise RuntimeError(f"Extracao concluida mas {assets_dir} continua vazio.")
        print(f"Assets extracted successfully ({len(os.listdir(assets_dir))} items)")
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()
