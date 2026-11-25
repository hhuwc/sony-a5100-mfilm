"""Render a copied Sony roll at S, M and L with the desktop Film OS darkroom."""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from PIL import Image

PORT = Path(__file__).resolve().parents[1]


def render(roll, output, search, frames):
    lines = roll.read_text(encoding="ascii").splitlines()
    frame_line = re.compile(r"^\s*(\d+)\s+(DSC\d{5}\.ARW)\s")
    if frames:
        numbers = {int(m[1]) for line in lines if (m := frame_line.match(line))}
        if not set(frames) <= numbers:
            raise ValueError("Selected frame is absent from the roll manifest")
        lines = [line for line in lines if not (m := frame_line.match(line)) or int(m[1]) in frames]
    entries = [m[2] for line in lines if (m := frame_line.match(line))]
    if not entries or len(entries) != len(set(entries)):
        raise ValueError("Expected unique ARW filenames in the roll")
    selected = {int(m[1]) for line in lines if (m := frame_line.match(line))}
    # Film OS visits every ordinal through the last selected frame. Keep original
    # frame numbers for the grain seed, and verify any intentional gaps by number.
    gaps = set(range(1,max(selected)+1)) - selected
    if gaps and not frames:
        raise ValueError("Roll has missing frame numbers; specify the frames to render")
    assets = PORT/"build/assets/ML"
    runner = PORT/"build/menu-scene/menu.exe"
    for size, label in enumerate("SML"):
        with tempfile.TemporaryDirectory(dir=PORT/"build") as tmp:
            card = Path(tmp)
            dcim = card/"DCIM/100MSDCF"
            dcim.mkdir(parents=True)
            (card/"MFILM").mkdir()
            shutil.copytree(assets/"DARKROOM", card/"ML/DARKROOM")
            (dcim/roll.name).write_text("\n".join(lines)+"\n", encoding="ascii")
            for name in entries:
                source = next((folder/name for folder in [roll.parent, *search] if (folder/name).is_file()), None)
                if source is None:
                    raise FileNotFoundError(name)
                shutil.copyfile(source, dcim/name)
            end = 80000*len(entries)
            scene = card/"SCENE.TXT"
            scene.write_text("noroll\nopen darkroom\n1500 set\n2400 info\n3400 set\n"
                             f"{end} state\n{end+300} end\n", encoding="ascii")
            env = {k:v for k,v in os.environ.items() if not k.startswith("FOS_")}
            env.update(FOS_CARD="./", FOS_FONT=str(assets/"DATA/FOSFONT.BIN"),
                       FOS_FILMS=str(assets/"DATA/FOSFILMS.BIN"), FOS_SIZE=str(size))
            job = subprocess.run([runner, scene.name, "-"], cwd=card, env=env,
                                 capture_output=True, text=True, check=True, timeout=120*len(entries))
            dest = output/label
            dest.mkdir(parents=True, exist_ok=True)
            (dest/"darkroom.log").write_text(job.stderr, encoding="utf8")
            developed = set(map(int, re.findall(r"darkroom: roll \d+ frame (\d+) developed in", job.stderr)))
            missing = set(map(int, re.findall(r"darkroom: roll \d+ frame (\d+): no RAW file", job.stderr)))
            if developed!=selected or missing!=gaps or f"done=1|failed={len(gaps)}|sheet_errors=0" not in job.stderr:
                raise RuntimeError(f"Selected frames failed to render; see {dest/'darkroom.log'}")
            jpegs = next((card/"DCIM").glob("*/ROLL"+roll.stem[-3:]+".TXT")).parent
            for name in entries:
                jpg = jpegs/Path(name).with_suffix(".JPG")
                with Image.open(jpg) as im:
                    im.load()
                    if max(im.size) != (720,2008,3012)[size]:
                        raise ValueError((name,label,im.size))
                shutil.copyfile(jpg,dest/jpg.name)
            print(f"{roll.name} {label}: {len(entries)} JPEGs in {dest}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roll", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--raw-dir", type=Path, action="append", default=[])
    parser.add_argument("--frames", type=int, nargs="+", help="optional original frame numbers to render")
    args = parser.parse_args()
    render(args.roll.resolve(), args.output.resolve(), args.raw_dir, args.frames)
