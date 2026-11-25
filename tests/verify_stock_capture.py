"""Compare a real camera RAW and its paired JPEG with the settings of the logged M-Film stock."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def exiftool():
    exe=shutil.which("exiftool")
    if exe:
        return [exe]
    script=Path(__file__).resolve().parents[2]/"toolchain/exiftool/exiftool"
    perl=shutil.which("perl")
    git=shutil.which("git")
    if not perl and git:
        perl=Path(git).resolve().parents[1]/"usr/bin/perl.exe"
    if script.is_file() and perl and Path(perl).is_file():
        return [str(perl),script.as_posix()]
    raise SystemExit("Install ExifTool on PATH or supply --exiftool.")


def verify(stocks, roll, raw, jpeg, cli):
    text=roll.read_text(encoding="utf8")
    stock=re.search(r"^film\s*=\s*(\w+)\s*$",text,re.M)
    frame=re.search(r"^\s*(\d+)\s+"+re.escape(raw.name)+r"\s",text,re.I|re.M)
    if not stock or not frame:
        raise ValueError("The ARW must occur in the selected camera roll log.")
    if raw.suffix.upper()!=".ARW" or jpeg.suffix.upper()!=".JPG" or raw.stem.upper()!=jpeg.stem.upper():
        raise ValueError("Select the original ARW and same-shutter camera JPG.")
    with stocks.open(encoding="ascii") as stream:
        row=next(row for row in csv.reader(stream,delimiter="\t") if row[0]==stock[1])
    box,iso,kelvin,style,con,sat,sharp,ab,gm=map(int,row[1:])
    clamp=lambda value:max(-3,min(3,value))
    expected={"IFD0:Model":"ILCE-5100","ExifIFD:ISO":iso,"Sony:ColorTemperature":kelvin,
              "Sony:WBShiftAB_GM":f"{ab} {-gm}","Sony:CreativeStyle":{129:"Standard",131:"Landscape",134:"B&W"}[style],
              "Sony:Contrast":clamp(con),"Sony:Sharpness":clamp(sharp-3)}
    if style!=134:expected["Sony:Saturation"]=clamp(sat)
    keys=[*expected,"ExifIFD:ExposureCompensation","ExifIFD:DateTimeOriginal","ExifIFD:LensModel"]
    data=json.loads(subprocess.check_output([*cli,"-j","-G1",*["-"+k for k in keys],
                                             raw.resolve().as_posix(),jpeg.resolve().as_posix()],text=True,encoding="utf8"))
    if len(data)!=2 or not data[0].get("ExifIFD:DateTimeOriginal") or data[0].get("ExifIFD:DateTimeOriginal")!=data[1].get("ExifIFD:DateTimeOriginal"):
        raise ValueError("RAW and JPEG must report the same original capture time.")
    checks=[]
    for path,seen in zip((raw,jpeg),data):
        with path.open("rb") as f:digest=hashlib.file_digest(f,"sha256").hexdigest()
        diff={}
        for key, requested in expected.items():
            recorded=seen.get(key)
            # ExifTool displays positive Sony style adjustments with an explicit plus sign.
            if isinstance(requested,int) and isinstance(recorded,str) and re.fullmatch(r"[+-]?\d+",recorded):
                recorded=int(recorded)
            if recorded!=requested:
                diff[key]={"requested":requested,"recorded":seen.get(key)}
        checks.append({"file":path.name,"sha256":digest,"recorded":{k:seen.get(k) for k in keys},
                       "differences":diff})
    return {"roll":roll.name,"frame":int(frame[1]),"stock":stock[1],"box_iso":box,"expected":expected,
            "files":checks,"passed":all(not record["differences"] for record in checks)}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ["stocks","roll","raw","jpeg","output"]:p.add_argument(name,type=Path)
    p.add_argument("--exiftool",type=Path)
    args=p.parse_args()
    report=verify(args.stocks,args.roll,args.raw,args.jpeg,[str(args.exiftool)] if args.exiftool else exiftool())
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    for record in report["files"]:
        print(record["file"],record["differences"] or "matches the stock")
    raise SystemExit(0 if report["passed"] else 1)
