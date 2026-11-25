"""Develop the same on-card ARW at S/M/L on the camera using the release library."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serial")
    parser.add_argument("arw")
    parser.add_argument("film", type=int)
    parser.add_argument("output", type=Path)
    parser.add_argument("--apk", type=Path, help="signed APK containing the native library to test")
    args = parser.parse_args()
    if not re.fullmatch(r"/mnt/sdcard/DCIM/[0-9A-Za-z_]+/DSC[0-9]{5}\.ARW", args.arw):
        parser.error("Expected a Sony DCIM ARW path")
    root = Path(__file__).resolve().parents[1]
    libs = root / "build/libs/armeabi-v7a"
    with zipfile.ZipFile(args.apk or root / "dist/M-Film-0.2.4-ILCE5100.apk") as apk:
        assert apk.read("lib/armeabi-v7a/libfilmos.so") == (libs / "libfilmos.so").read_bytes()
    args.output.mkdir(parents=True, exist_ok=True)
    adb = ["adb", "-s", args.serial]
    work = "/data/local/tmp/mfilm-size11"
    card = "/mnt/sdcard/MFILM/VERIFY"

    def shell(cmd):
        return subprocess.check_output(adb + ["shell", cmd], text=True, timeout=180).strip()

    # The Gingerbread toolbox mkdir has no -p. A remote shell's exit status is
    # unavailable with this version of adbd, so check for each command's marker.
    for directory in (work, card):
        if shell(f"(cd {directory} 2>/dev/null || mkdir {directory}) && echo READY").splitlines()[-1:] != ["READY"]:
            raise RuntimeError(f"Could not prepare {directory}")
    # The sync service and shell redirections use different accounts on this body.
    shell(f"chmod 777 {work}")
    try:
        for src, target in (("mfilm_devtest", "run"), ("libfilmos.so", "libfilmos.so")):
            blob = f"/data/local/tmp/size11-{src}.bin"
            subprocess.run(adb + ["push", str(libs / src), blob], check=True)
            result = shell(f"cat {blob} > {work}/new-{target} && chmod 755 {work}/new-{target} "
                           f"&& mv {work}/new-{target} {work}/{target} && echo READY")
            if result.splitlines()[-1:] != ["READY"]:
                raise RuntimeError(result)
    finally:
        shell(f"chmod 755 {work}")
    with (args.output / "results.txt").open("w", encoding="utf8") as log:
        for size in "SML":
            # Sony's card writer accepts an 8.3 filename.
            prefix = f"{card}/V{Path(args.arw).stem[-5:]}{size}"
            result = shell(f"LD_LIBRARY_PATH={work} MFILM_CPU3=1 MFILM_THREADS=p "
                           f"{work}/run {args.arw} {prefix} {args.film} {size}")
            print(result, file=log, flush=True)
            if "progress 1000" not in result:
                raise RuntimeError(result)
            jpeg = args.output / f"{size}.jpg"
            subprocess.run(adb + ["pull", prefix + ".jpg", str(jpeg)], check=True)
            print(f"SHA256 {hashlib.sha256(jpeg.read_bytes()).hexdigest()}", file=log, flush=True)
            print(result, flush=True)


if __name__ == "__main__":
    main()
