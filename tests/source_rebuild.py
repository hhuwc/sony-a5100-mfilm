"""Package the portable project sources, extract into a fresh path, and verify the signed APK."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("assets", "gradle", "native", "res", "src", "tests")
FILES = ("AndroidManifest.xml", "build.gradle", "build.py", "fonts.py", "gradlew", "gradlew.bat",
         "LICENSE", "navigation.py", "OFL.txt", "prepare.py", "README.md", "reprints.py",
         "settings.gradle", "setup.py", "THIRD_PARTY.md", ".gitignore")


def source_archive(archive):
    paths = [ROOT / f for f in FILES]
    paths.extend(p for folder in FOLDERS for p in (ROOT / folder).rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts)
    with zipfile.ZipFile(archive, "w") as stream:
        for path in sorted(paths):
            item = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = (0o100755 if path.name == "gradlew" else 0o100644) << 16
            stream.writestr(item, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)


def main(apk):
    reference = apk.read_bytes()
    archive = apk.with_name(apk.stem + "-source.zip")
    source_archive(archive)
    # A sibling uses the same pinned SDK and clones without copying build outputs.
    with tempfile.TemporaryDirectory(prefix="mfilm-check-", dir=ROOT.parent) as tmp:
        check = Path(tmp).resolve()
        assert check.parent == ROOT.parent and check.name.startswith("mfilm-check-")
        with zipfile.ZipFile(archive) as src:
            src.extractall(check)
        log = ROOT / "build/port-relocated.log"
        with log.open("wb") as output:
            subprocess.run([sys.executable, "build.py", "--signing-dir", ROOT / ".signing"],
                           cwd=check, stdout=output, stderr=subprocess.STDOUT, check=True)
        rebuilt = check / "dist" / apk.name
        if rebuilt.read_bytes() != reference:
            with zipfile.ZipFile(apk) as a, zipfile.ZipFile(rebuilt) as b:
                for name in sorted(set(a.namelist()) | set(b.namelist())):
                    if name not in a.namelist() or name not in b.namelist() or a.read(name) != b.read(name):
                        print("Different entry", name)
            raise RuntimeError("The relocated APK differs")
    print("PASS unpacked source archive at a different path, clean objects, same signer and identical APK")
    print("APK SHA256", hashlib.sha256(reference).hexdigest())
    print("Source SHA256", hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    main(parser.parse_args().apk.resolve())
