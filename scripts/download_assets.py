"""Download GeniusLib assets from GitHub Releases if not present."""
import os
import sys
import tarfile
import tempfile
import urllib.request

ASSETS_VERSION = "5.5.4"
GITHUB_URL = f"https://github.com/AkumaHalls/GeniusLib/releases/download/v{ASSETS_VERSION}/geniuslib-assets-{ASSETS_VERSION}.tar.gz"


def get_assets_dir() -> str:
    import geniuslib.utils
    return geniuslib.utils.get_assets_dir()


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

    if os.path.isdir(assets_dir) and os.listdir(assets_dir):
        print(f"Assets already present: {assets_dir}")
        return

    print(f"Downloading GeniusLib assets v{ASSETS_VERSION}...")
    print(f"Target: {assets_dir}")

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        urllib.request.urlretrieve(GITHUB_URL, tmp.name)
        tmp_path = tmp.name

    try:
        os.makedirs(assets_dir, exist_ok=True)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extractall(path=os.path.dirname(assets_dir))
        print(f"Assets extracted successfully ({len(os.listdir(assets_dir))} items)")
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()
