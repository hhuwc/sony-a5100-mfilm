"""Run a complete 12/24/36-frame reprint in a private fixture on the physical camera."""
import argparse
import re
import time
from pathlib import Path

from PIL import Image
from scene_camera import SceneCamera


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("serial")
    p.add_argument("fixture",help="Source fixture produced by reprint_scene.py")
    p.add_argument("frames",type=int,choices=(12,24,36))
    p.add_argument("output",type=Path)
    p.add_argument("--collect",help="Resume collection from an already started private test roll")
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    source=SceneCamera(args.serial,args.fixture)
    cam=SceneCamera(args.serial,args.collect) if args.collect else SceneCamera(args.serial)
    print("Isolated roll",cam.card,flush=True)
    names=["DCIM/100MSDCF/DSC00001.ARW","ML/DATA/FOSFONT.BIN","ML/DATA/FOSFILMS.BIN",
           "ML/DARKROOM/LOOK04.LUT","ML/DARKROOM/LOOK05.LUT"]
    roll=args.output/"ROLL_001.TXT"
    header=f"film = superia400\nexposures = {args.frames}\nloaded = 2026-11-25 02:23\n"
    roll.write_text(header+"".join(f"{i}  DSC00001.ARW  2026-11-25 02:23:29  f/4.5\n" for i in range(1,args.frames+1)),encoding="ascii")
    commands=args.output/"scene.txt"
    commands.write_text("noroll\nopen darkroom\n1500 right\n2200 right\n3000 set\n4200 right\n5200 set\n1500000 end\n",encoding="ascii")
    settings="FOS_CARD=./ FOS_SIZE=1 FOS_FONT=ML/DATA/FOSFONT.BIN FOS_FILMS=ML/DATA/FOSFILMS.BIN"
    runner=cam.install_runner()
    if not args.collect:
        cam.shell(f"cd {cam.card} && mkdir DCIM && mkdir DCIM/100MSDCF && mkdir ML && mkdir ML/DATA && mkdir ML/DARKROOM && mkdir MFILM")
        for name in names:
            cam.shell(f"cat {source.card}/{name} > {cam.card}/{name}")
        cam.push(roll,cam.card+"/DCIM/100MSDCF/ROLL_001.TXT")
        cam.push(commands,cam.card+"/ROLL.TXT")
        (args.output/"fixture.txt").write_text(cam.token+"\n",encoding="ascii")
        cam.shell(f"cd {cam.card} && sh -c '({settings} FOS_WALL=1 {runner} ROLL.TXT - > RUN.LOG 2>&1; "
                  f"echo $? > EXIT.TXT) </dev/null >/dev/null 2>&1 &'")
    stop=time.monotonic()+1600
    while "EXIT.TXT" not in cam.shell(f"ls {cam.card}").splitlines():
        if time.monotonic()>stop:
            raise TimeoutError(f"Completion not observed. Reuse --collect {cam.token} to check the card.")
        time.sleep(10)
    log=cam.shell(f"cat {cam.card}/RUN.LOG")
    (args.output/"develop.log").write_text(log+"\n",encoding="utf8")
    times=re.findall(r"darkroom: roll 001 frame (\d+) developed in (\d+) ms, 2008 x 1341",log)
    assert [int(frame) for frame,ms in times]==list(range(1,args.frames+1)),log[-2200:]
    directory="MFILM/PRINTS/R001/P0001005/"
    listing=cam.shell(f"ls -l {cam.card}/{directory}")
    (args.output/"files.txt").write_text(listing+"\n",encoding="utf8")
    files={name:int(size) for size,name in re.findall(r"\s(\d+)\s+\d{4}-\d\d-\d\d\s+\d\d:\d\d\s+(\S+)",listing)}
    expected={f"F{i:02d}.{ext}" for i in range(1,args.frames+1) for ext in ("JPG","BMP","ZOM")}|{"SHEET.BMP"}
    assert files.keys()==expected,listing
    for i in range(1,args.frames+1):
        assert files[f"F{i:02d}.ZOM"]==16+2008*1341
        assert files[f"F{i:02d}.BMP"]==375542 and files[f"F{i:02d}.JPG"]>0
    cam.pull(directory+"SHEET.BMP",args.output/"sheet.bmp")
    cam.pull(directory+f"F{args.frames:02d}.JPG",args.output/"last.jpg")
    with Image.open(args.output/"last.jpg") as img:
        img.load()
        assert img.size==(2008,1341) and img.getexif().get(272)=="ILCE-5100"
    with Image.open(args.output/"sheet.bmp") as im:
        rgb=im.convert("RGB")
        assert rgb.size==(720,480)
        rows=(args.frames+5)//6
        for frame in range(args.frames):
            x=120*(frame%6)+60
            y=(480-80*rows)//2+80*(frame//6)+40
            assert any(rgb.getpixel((x,y))),frame
        rgb.save(args.output/"sheet.png")
    commands.write_text("noroll\nopen prints\n1500 snap\n2300 end\n",encoding="ascii")
    cam.push(commands,cam.card+"/VIEW.TXT")
    view=cam.shell(f"cd {cam.card} && {settings} {runner} VIEW.TXT - 2>&1")
    assert "read ./"+directory+"SHEET.BMP" in view
    (args.output/"prints.log").write_text(view+"\n",encoding="utf8")
    elapsed=re.search(r"job_ms=(\d+)",log)[1]
    highwater=re.search(r"VmHWM:\s+(\d+)",log)[1]
    result=(f"{args.frames} numbered test frames from one copy of DSC01126.ARW, Velvia 50, M, CPU 3.\n"
            f"{args.frames} decoded. {len(files)} published files. All contact sheet centers contain image pixels.\n"
            f"job_ms={elapsed} VmHWM_KiB={highwater} frame_ms="+",".join(ms for frame,ms in times)+
            f"\nReopened published contact sheet. Private fixture {cam.card}\n")
    (args.output/"results.txt").write_text(result,encoding="ascii")
    print(result)


if __name__=="__main__":
    main()
