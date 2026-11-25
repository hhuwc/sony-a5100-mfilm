"""Compare actual saved body canvases at the camera surface's 640 × 480 geometry."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def display_frame(path):
    with Image.open(path) as original:
        if original.size!=(720,480):
            raise ValueError(f"Unexpected canvas {original.size}")
        image=original.convert("RGB").resize((640,426),Image.Resampling.NEAREST)
    output=Image.new("RGB",(640,480))
    output.paste(image,(0,27))
    return output


if __name__=="__main__":
    before,after,dest=map(Path,sys.argv[1:])
    output=Image.new("RGB",(640,218),"#181818")
    draw=ImageDraw.Draw(output)
    font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",15)
    for y,title,path in [(0,"Before",before),(109,"Port9",after)]:
        draw.text((9,y+2),title,fill="white",font=font)
        frame=display_frame(path)
        output.paste(frame.crop((0,27,640,56)),(0,y+26))
        output.paste(frame.crop((0,411,640,454)),(0,y+55))
    output.save(dest)
