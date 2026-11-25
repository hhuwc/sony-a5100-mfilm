"""Exercise the release C screens in a separate process on an ILCE-5100 and a private test roll."""
import argparse
import hashlib
import re
from pathlib import Path

from PIL import Image

from scene_camera import SceneCamera


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("serial")
    p.add_argument("raw", help="Existing camera DCIM ARW to copy into the test roll")
    p.add_argument("output", type=Path)
    args = p.parse_args()
    if not re.fullmatch(r"/mnt/sdcard/DCIM/[0-9A-Za-z_]+/DSC[0-9]{5}\.ARW", args.raw):
        p.error("Provide a Sony DCIM ARW path")
    args.output.mkdir(parents=True, exist_ok=True)
    port = Path(__file__).resolve().parents[1]
    camera = SceneCamera(args.serial)
    card, token = camera.card, camera.token
    push, pull, shell = camera.push, camera.pull, camera.shell
    runner = camera.install_runner()
    print("Isolated test card", card, flush=True)

    def snapshot(label):
        dest = args.output / (label + ".ppm")
        pull("SCR01.PPM", dest)
        with Image.open(dest) as image:
            image.save(args.output / (label + ".png"))
        dest.unlink()

    def scene(name, actions, extra=""):
        path = args.output / (name + ".txt")
        path.write_text("noroll\nopen " + ("prints" if name == "reopen" else "darkroom") + "\n"
                        + "\n".join(str(t) + " " + key for t, key in actions) + "\n", encoding="ascii")
        push(path, card + "/SCENE.TXT")
        result = shell(f"cd {card} && FOS_CARD=./ FOS_SIZE=1 FOS_FONT=ML/DATA/FOSFONT.BIN "
                       f"FOS_FILMS=ML/DATA/FOSFILMS.BIN {extra} {runner} SCENE.TXT - 2>&1")
        (args.output / (name + ".log")).write_text(result + "\n", encoding="utf8")
        print(name, result.splitlines()[-1], flush=True)
        return result

    shell(f"cd {card} && mkdir DCIM && mkdir DCIM/100MSDCF && mkdir ML && mkdir ML/DARKROOM && mkdir ML/DATA && mkdir MFILM")
    shell(f"cat {args.raw} > {card}/DCIM/100MSDCF/DSC00001.ARW")
    log = args.output / "ROLL_001.TXT"
    log.write_text("film = superia400\nexposures = 36\nloaded = 2026-11-25 10:11\n"
                   "1  DSC00001.ARW  2026-11-25 10:23:30  f/4.5\n", encoding="ascii")
    push(log, card + "/DCIM/100MSDCF/ROLL_001.TXT")
    for path in ["DATA/FOSFONT.BIN", "DATA/FOSFILMS.BIN", "DARKROOM/LOOK04.LUT", "DARKROOM/LOOK05.LUT"]:
        push(port / "build/assets/ML" / path, card + "/ML/" + path)
    after = [(48000, "set"), (50500, "set"), (52500, "tele"), (54000, "snap"), (55000, "wide"), (56000, "end")]
    normal = scene("original", [(1500, "set"), (2400, "info"), (3400, "set")] + after)
    master = "ML/DARKROOM/R001/"
    assert "read ./" + master + "F01.ZOM" in normal, normal[-2000:]
    match = re.search(r"write (\./DCIM/[^\n]+/DSC00001\.JPG)", normal)
    assert match, normal[-2000:]
    original = {name: master + name for name in ["F01.BMP", "F01.ZOM", "SHEET.BMP"]}
    original.update({"F01.JPG": match.group(1)[2:], "RAW": "DCIM/100MSDCF/DSC00001.ARW"})

    def hashes(label, files):
        result = {}
        for name, remote in files.items():
            file = port / "build/darkroom-scene" / (token + "-" + label + "-" + name)
            pull(remote, file)
            result[name] = digest(file)
            if name.endswith(".BMP"):
                bmp = file.read_bytes()
                meta = bmp.index(b"FOP2")
                assert bmp[meta + 4] == (5 if label.startswith("edition") else 4)
            file.unlink()
        return result

    before = hashes("original", original)
    snapshot("original-zoom")
    recipe = [(1500, "right"), (2200, "right"), (3000, "set"), (4200, "right"), (5200, "set")]
    result = scene("alternate", recipe + after)
    edition = "MFILM/PRINTS/R001/P0001005/"
    for name in ["SHEET.BMP", "F01.BMP", "F01.ZOM"]:
        assert "read ./" + edition + name in result, result[-2000:]
    snapshot("alternate-zoom")
    reread = scene("reopen", [(1500, "down"), (2300, "right"), (3000, "right"), (3700, "right"),
                              (4500, "set"), (6100, "set"), (7700, "tele"), (9100, "snap"),
                              (9900, "wide"), (11000, "end")])
    assert "read ./" + master + "SHEET.BMP" in reread
    assert "read ./" + edition + "F01.ZOM" in reread, reread[-2000:]
    snapshot("reopened-zoom")
    edition_files = {name: edition + name for name in original if name != "RAW"}
    alternate = hashes("edition", edition_files)
    assert all(before[key] != value for key, value in alternate.items())
    assert hashes("master-after", original) == before
    assert digest(args.output / "alternate-zoom.png") == digest(args.output / "reopened-zoom.png")
    assert digest(args.output / "original-zoom.png") != digest(args.output / "alternate-zoom.png")
    result = scene("write-failure", recipe + [(48000, "set"), (50500, "end")], "FOS_FAIL_ZOOM=1")
    assert "Incomplete reprint files" in result and "screen 6" in result.split("screen 7")[-1], result[-2000:]
    cancelled = scene("cancel", recipe + [(7300, "menu"), (8200, "set"), (9800, "end")])
    assert "screen 6" in cancelled.split("screen 7")[-1] and "write ./MFILM/PRINTS/R001/T" in cancelled
    listing = shell(f"ls {card}/MFILM/PRINTS/R001").splitlines()
    assert listing == ["P0001005"], listing
    assert hashes("edition-after-failure", edition_files) == alternate
    assert hashes("master-after-failure", original) == before
    lines = [f"Camera {args.serial}, fixture {card}, source {args.raw}, size M",
             "Original + reopen: " + str(before), "Alternate + failed-write recovery: " + str(alternate),
             "On reopening the roll, Version selected the same rendered W/T zoom pixels.",
             "Incomplete zoom sidecar rejected; cancellation discarded an in-progress set.",
             "Original files, raw copy and first edition match previous SHA-256."]
    (args.output / "results.txt").write_text("\n".join(lines) + "\n", encoding="utf8")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
