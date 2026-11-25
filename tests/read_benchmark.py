"""Run ordered RAW decoding trials on the connected camera's foreground-equivalent CPU."""
import argparse
import hashlib
from pathlib import Path
import subprocess


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("serial")
    cli.add_argument("arw")
    cli.add_argument("output",type=Path)
    args=cli.parse_args()
    if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./-" for c in args.arw):
        raise ValueError("Expected a Sony DCIM file path")
    adb=["adb","-s",args.serial]
    work="/data/local/tmp/mfilm-perf6"
    card="/mnt/sdcard/MFILM/VERIFY"
    libs=Path(__file__).resolve().parents[1]/"build/libs/armeabi-v7a"
    def shell(cmd):
        return subprocess.check_output(adb+["shell",cmd],text=True,timeout=120).strip()
    shell(f"mkdir -p {work}")
    shell(f"chmod 777 {work}")
    for name in ("libfilmos.so","mfilm_devtest"):
        blob=f"/data/local/tmp/bench-{name}.bin"
        subprocess.run(adb+["push",str(libs/name),blob],check=True)
        dest="runner" if name=="mfilm_devtest" else "libfilmos.so"
        # The Android sync service writes as system. Create shell-owned executable files.
        shell(f"cat {blob} > {work}/new-{dest} && chmod 755 {work}/new-{dest} && mv {work}/new-{dest} {work}/{dest}")
    shell(f"chmod 755 {work}")
    logs=[]
    for mode in ("0","p","p","0","1","2"):
        prefix=f"{card}/PERF{mode}"
        result=shell(f"LD_LIBRARY_PATH={work} MFILM_CPU3=1 MFILM_THREADS={mode} "
                     f"{work}/runner {args.arw} {prefix} 0")
        if "progress 1000" not in result or "Cpus_allowed_list:" not in result:
            raise RuntimeError(result)
        jpeg=args.output.parent/f"read-{mode}.jpg"
        subprocess.run(adb+["pull",prefix+".jpg",str(jpeg)],check=True)
        msg=f"mode={mode}\n{result}\nSHA256 {hashlib.sha256(jpeg.read_bytes()).hexdigest()}\n"
        logs.append(msg)
        args.output.write_text("\n".join(logs), encoding="utf8")
        print(msg,flush=True)


if __name__=="__main__":
    main()
