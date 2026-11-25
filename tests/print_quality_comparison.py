"""Compare the daylight building frame DSC01127, its Film OS prints and a fixed LibRaw reference."""
import argparse
import json
from pathlib import Path

import numpy as np
import rawpy
from PIL import Image, ImageDraw, ImageFont, ImageOps


def run(raw, camera, prints, output, alternatives):
    output.mkdir(parents=True, exist_ok=True)
    with rawpy.imread(str(raw)) as sensor:
        ref = sensor.postprocess(use_camera_wb=True, use_auto_wb=False, no_auto_bright=True,
                                 demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD, gamma=(2.4,12.92),
                                 output_color=rawpy.ColorSpace.sRGB, highlight_mode=rawpy.HighlightMode.Clip)
        white = sensor.camera_white_level_per_channel
        pixels = sensor.raw_image_visible
        summary = {"raw":raw.name,"rawpy":rawpy.__version__, "libraw_white_level":sensor.white_level,
                   "camera_white":white, "black":sensor.black_level_per_channel,
                   "wb":sensor.camera_whitebalance, "photosites":int(pixels.size)}
        if white and len(set(white))==1:
            summary["sites_at_or_above_camera_white_percent"] = float(100*np.mean(pixels>=white[0]))
    with Image.open(camera) as jpeg:
        sources = {"Sony JPEG":ImageOps.exif_transpose(jpeg).convert("RGB")}
    sources["LibRaw AHD"] = Image.fromarray(ref)
    for size in "SML":
        with Image.open(prints/size/(raw.stem+".JPG")) as frame:
            sources["MFilm "+size] = ImageOps.exif_transpose(frame).convert("RGB")
    lanczos = Image.Resampling.LANCZOS
    common = (720,480)
    small = {name:np.asarray(im.resize(common,lanczos),dtype=np.int16) for name,im in sources.items()}
    # These coordinates apply to DSC01127's sky, building and shaded trees.
    regions = {"sky":(425,6,490,20), "facade":(45,73,113,122), "trees":(332,414,372,447)}
    summary["regions_xyxy_on_720x480"] = regions
    for name, arr in small.items():
        regions_rgb = {key:arr[t:b,l:r].mean(axis=(0,1)).round(2).tolist() for key,(l,t,r,b) in regions.items()}
        summary[name] = {"dimensions":sources[name].size, "region_mean_rgb":regions_rgb,
                         "rgb_ge250_all_percent":round(100*float(np.all(arr>=250,axis=2).mean()),3)}
    summary["mean_absolute_rgb_S_to_downsampled_M"] = float(np.abs(small["MFilm M"]-small["MFilm S"]).mean())
    (output/"daylight-metrics.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf8")
    font = ImageFont.truetype("arial.ttf",18)
    width = 292
    canvas = Image.new("RGB",(5*width,476),"#1a1a1a")
    draw = ImageDraw.Draw(canvas)
    crop = (720,340,943,508)  # balcony details, in the Medium file's coordinates
    for index,(name,im) in enumerate(sources.items()):
        x=index*width+5
        draw.text((x,4),name+"  "+str(im.width)+" x "+str(im.height),font=font,fill="white")
        canvas.paste(im.resize((width-10,188),lanczos),(x,36))
        scaled = tuple(round(v*im.size[i%2]/(2008,1341)[i%2]) for i,v in enumerate(crop))
        crop_im = im.crop(scaled).resize((width-10,212),lanczos)
        canvas.paste(crop_im,(x,249))
        draw.text((x,225),"Same balcony crop",font=font,fill="#ddd")
    canvas.save(output/"daylight-comparison.jpg",quality=95,subsampling=0)
    if alternatives:
        grades = {"Ektar 100":sources["MFilm M"]}
        for label, path in alternatives:
            with Image.open(path) as im:
                if im.size!=grades["Ektar 100"].size:
                    raise ValueError(f"Use the same Medium size for {label}")
                grades[label]=im.convert("RGB")
        strip=Image.new("RGB",(450*len(grades),335),"#1a1a1a")
        pen=ImageDraw.Draw(strip)
        for i,(label,im) in enumerate(grades.items()):
            pen.text((450*i+8,5),label,font=font,fill="white")
            strip.paste(im.resize((450,300),lanczos),(450*i,35))
        strip.save(output/"daylight-stocks.jpg",quality=95,subsampling=0)
    return summary


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ("raw","camera","prints","output"):
        p.add_argument(arg,type=Path)
    p.add_argument("--alternate",action="append",nargs=2,metavar=("STOCK","JPEG"))
    a=p.parse_args()
    run(a.raw,a.camera,a.prints,a.output,a.alternate)
