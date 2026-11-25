"""Check the packaged 32-bit library against the saved ILCE-5100 system libraries."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT.parent / "toolchain/android-ndk-r16b/toolchains/arm-linux-androideabi-4.9/prebuilt/windows-x86_64/bin"
READELF = TOOLS / "arm-linux-androideabi-readelf.exe"
BODY_LIBS = ROOT.parent / "validation/device-libs"


def readelf(path, flag):
    return subprocess.check_output([READELF, flag, "--wide", path], text=True, encoding="utf8")


def symbols(path):
    imported, exported = set(), set()
    for line in readelf(path, "--dyn-syms").splitlines():
        fields = line.split()
        if len(fields) < 8 or not fields[0][:-1].isdigit() or fields[4] not in ("GLOBAL", "WEAK"):
            continue
        name = fields[7].split("@")[0]
        if fields[6] == "UND":
            if fields[4] == "GLOBAL":
                imported.add(name)
        elif fields[5] in ("DEFAULT", "PROTECTED"):
            exported.add(name)
    return imported, exported


def main(apk):
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(apk) as archive:
        assert archive.read("classes.dex")[:8] == b"dex\n035\0"
        lib = Path(tmp) / "libfilmos.so"
        lib.write_bytes(archive.read("lib/armeabi-v7a/libfilmos.so"))
        header = readelf(lib, "--file-header")
        assert "ELF32" in header and re.search(r"Machine:\s+ARM\b", header)
        required, exports = symbols(lib)
        needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", readelf(lib, "--dynamic"))
        assert needed and required
        provided = {}
        for name in needed:
            body = BODY_LIBS / name
            for symbol in symbols(body)[1]:
                provided.setdefault(symbol, name)
        assert not required - provided.keys(), sorted(required - provided.keys())
        declared = set()
        for src in (ROOT / "src/org/mfilm/sony").glob("*.java"):
            for method in re.findall(r"\bnative\s+\w+(?:\[\])*\s+(\w+)\s*\(", src.read_text(encoding="utf8")):
                declared.add(f"Java_org_mfilm_sony_{src.stem}_{method}")
        assert declared and not declared - exports, sorted(declared - exports)
        print(f"{apk.name}: DEX 035, ELF32 ARM, {len(declared)} JNI declarations exported")
        print(f"{len(required)} strong dynamic imports found in captured firmware 3.10 libraries: {', '.join(needed)}")
        for item in ("fsync", "fileno", "rename", "fflush", "ferror", "memchr"):
            if item in required:
                print(f"  {item} -> {provided[item]}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
