"""Request the current menu canvas from a traced Film OS session on the camera."""
import argparse
import subprocess
import time
from pathlib import Path
from PIL import Image

def capture(serial, destination):
    adb=["adb","-s",serial] if serial else ["adb"]
    folder="/mnt/sdcard/MFILM/VERIFY/"
    def shell(command):
        return subprocess.check_output(adb+["shell",command],timeout=8,text=True).strip()
    def exists(path):
        return any(line.startswith("-") for line in shell("ls -l "+path).splitlines())
    if not exists("/mnt/sdcard/MFILM/TEST.ON"):
        raise RuntimeError("This session needs MFILM/TEST.ON at launch.")
    shell("echo 1 > "+folder+"CAPTURE.REQ")
    for _ in range(32):
        time.sleep(.4)
        if not exists(folder+"CAPTURE.REQ"):
            ppm=destination.with_suffix(".ppm")
            subprocess.run(adb+["pull",folder+"CURRENT.PPM",str(ppm)],check=True,timeout=25)
            with Image.open(ppm) as frame:
                frame.load()
                if frame.size!=(720,480):raise ValueError(frame.size)
                frame.save(destination)
            return
    raise RuntimeError("No canvas response. Confirm that a Film OS menu is in the foreground.")

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("output",type=Path)
    cli.add_argument("--serial")
    args=cli.parse_args()
    capture(args.serial,args.output)

