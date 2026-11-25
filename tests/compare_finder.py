"""Compare the pinned Canon renderer with the APK's HUD adapter on an identical viewfinder image."""
import argparse
import os
from pathlib import Path
import subprocess
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

port = Path(__file__).resolve().parents[1]
work = port / "build/finder-tests"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--background", type=Path, help="optional photograph for the common 720x480 backdrop")
parser.add_argument("--output", type=Path, default=work)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
size = (720, 480)
bg = Image.open(args.background).convert("RGB").resize(size, Image.Resampling.LANCZOS) if args.background else Image.new("RGB", size, "#778799")
bg.save(work / "background.ppm")
marker = (255, 0, 255)
Image.new("RGB", size, marker).save(work / "mask.ppm")
font_file = work / "upstream-font.bin"
with zipfile.ZipFile(port.parent / "toolchain/mfilm-release.zip") as release:
    entry = next(n for n in release.namelist() if n.upper()=="ML/DATA/FOSFONT.BIN")
    font_file.write_bytes(release.read(entry))

def canonical(style, source):
    filename = work / "canonical.ppm"
    env = dict(os.environ, HUD_STYLE=str(style), HUD_OUT=str(filename), FOS_FONT=str(font_file))
    subprocess.run([work / "upstream.exe", "1", source], cwd=work, env=env, check=True)
    with Image.open(filename) as im:
        return im.convert("RGB")

up = port.parent / "mfilm-canon-film-simulation/ml-dev/filmos/preview"
names = ("Classic", "Minimal", "Rangefinder", "Clean")
originals = ("hud", "hud-minimal", "hud-rangefinder", "hud-clean")
sheet = Image.new("RGB", (1112, 1124), "#1a1a1a")
draw = ImageDraw.Draw(sheet)
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
for x, label in enumerate(("EOS M 原版发布预览", "EOS M 原版 C · 同一背景", "α5100 移植 C · 同一背景")):
    draw.text((10 + 370*x, 8), label, font=font, fill="white")
lines = ["Controlled desktop render, panel 720x480. No camera preview, Sony callback or physical LCD was exercised.",
         "Same frame 12/36, f/4, shutter 1/125, EV +2/3, battery 82%, half press, blink on, count window active.",
         "Manual focus screen enabled. Wind reminder enabled only for Classic, matching upstream hudtest.c.",
         "Coverage is the nontransparent pixel mask. Bright-red pixels cover the lit indicators and digits.",
         "style         Canon pixels   Sony pixels    coverage IoU   Canon red  Sony red   red IoU    mask bounds"]
for style, name in enumerate(names):
    fixture = Image.frombytes("RGBA", size, (work / f"style{style}.rgba").read_bytes())
    port_mask = np.asarray(fixture.getchannel("A")) > 0
    canon_rgb = np.asarray(canonical(style, work/"mask.ppm"))
    canon_mask = np.any(canon_rgb != marker, axis=2)
    canon_red = np.all(canon_rgb == (240,30,30), axis=2)
    sony_red = np.all(np.asarray(fixture) == (255,52,36,255), axis=2)
    box1 = Image.fromarray(canon_mask).getbbox()
    box2 = Image.fromarray(port_mask).getbbox()
    overlap = (port_mask & canon_mask).sum() / (port_mask | canon_mask).sum()
    assert box1 == box2 and np.array_equal(port_mask,canon_mask), (name, box1, box2, overlap)
    red_iou = (canon_red & sony_red).sum() / (canon_red | sony_red).sum()
    assert red_iou >= .96, (name, red_iou)
    sony = Image.alpha_composite(bg.convert("RGBA"), fixture).convert("RGB")
    canon = canonical(style, work/"background.ppm")
    lines.append(f"{name:12} {canon_mask.sum():12} {port_mask.sum():12} {overlap:14.5f} {canon_red.sum():10} {sony_red.sum():9} {red_iou:10.5f}   {box1}")
    with Image.open(up / (originals[style]+".png")) as published:
        for col, im in enumerate((published, canon, sony)):
            sheet.paste(im.resize((360,240), Image.Resampling.LANCZOS), (10+370*col, 66+style*270))
    draw.text((10, 38+style*270), name, font=font, fill="#e7bd75")
sheet.save(args.output / "comparison.jpg", quality=94, subsampling=0)
(args.output / "geometry.txt").write_text("\n".join(lines)+"\n", encoding="utf8")
print("\n".join(lines[-4:]))
