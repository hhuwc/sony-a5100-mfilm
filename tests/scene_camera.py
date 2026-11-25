"""Deploy the scripted C UI outside the real Android activity on a private card fixture."""
import re
import subprocess
import uuid
from pathlib import Path


class SceneCamera:
    def __init__(self, serial, fixture=None):
        self.adb = ["adb", "-s", serial]
        self.token = fixture if fixture is not None else "R" + uuid.uuid4().hex[:7].upper()
        if not re.fullmatch(r"R[0-9A-F]{7}", self.token):
            raise ValueError("Use the R directory created by reprint_scene.py")
        self.card = "/mnt/sdcard/MFILM/VERIFY/" + self.token
        if fixture is None:
            self.shell(f"(cd /mnt/sdcard/MFILM/VERIFY || mkdir /mnt/sdcard/MFILM/VERIFY) && mkdir {self.card}")
        else:
            log = self.shell(f"cat {self.card}/DCIM/100MSDCF/ROLL_001.TXT")
            if "film = superia400" not in log or "1  DSC00001.ARW" not in log:
                raise RuntimeError("Expected the one-frame darkroom regression fixture")

    def shell(self, command, timeout=240):
        raw = subprocess.check_output(self.adb + ["shell", command + " && echo SCENE_OK"], timeout=timeout)
        text = raw.decode("utf8", "replace").replace("\r", "").strip()
        if not text.endswith("SCENE_OK"):
            raise RuntimeError(text[-2200:])
        return text[:-8].strip()

    def push(self, path, target):
        subprocess.run(self.adb + ["push", str(path), target], check=True, capture_output=True)

    def pull(self, relative, local):
        subprocess.run(self.adb + ["pull", self.card + "/" + relative, str(local)], check=True, capture_output=True)

    def install_runner(self, binary=None):
        if binary is None:
            binary = Path(__file__).resolve().parents[1] / "build/darkroom-scene/libs/armeabi-v7a/darkroom_scene"
        work = "/data/local/tmp/S" + uuid.uuid4().hex[:7].upper()
        self.shell(f"mkdir {work} && chmod 777 {work}")
        try:
            self.push(binary, work + "/TEST.BIN")
            self.shell(f"cat {work}/TEST.BIN > {work}/run && chmod 755 {work}/run")
        finally:
            self.shell(f"chmod 755 {work}")
        return work + "/run"
