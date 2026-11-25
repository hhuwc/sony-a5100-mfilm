"""Exercise the staged C menus with a private desktop card and check the state after each key sequence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image
from build_darkroom_scene import port


def at(keys, **state):
    return keys.split(), state


def run(output, raw):
    binary = port / "build/menu-scene/menu.exe"
    assets = port / "build/assets/ML"
    output.mkdir(parents=True, exist_ok=True)
    report = {}

    def scene(name, opening, steps, *, fixture="empty", config=None, forbidden=()):
        with tempfile.TemporaryDirectory(prefix="key-test-", dir=port/"build") as work:
            card = Path(work)
            capture = card/"DCIM/100MSDCF"
            capture.mkdir(parents=True)
            (card/"MFILM").mkdir()
            (card/"ML/DARKROOM").mkdir(parents=True)
            if fixture=="samples":
                shutil.copytree(assets/"SAMPLES", card/"ML/SAMPLES")
            elif fixture in ("negative", "prints"):
                (capture/"ROLL_001.TXT").write_text(
                    "film = superia400\nexposures = 36\nloaded = 2026-11-25 10:11\n"
                    "1  DSC00001.ARW  2026-11-25 10:23:30  f/4.5\n", encoding="ascii")
                if raw:
                    shutil.copyfile(raw, capture/"DSC00001.ARW")
                else:
                    (capture/"DSC00001.ARW").write_bytes(b"original file for navigation fixture")
                shutil.copyfile(assets/"DARKROOM/LOOK04.LUT",card/"ML/DARKROOM/LOOK04.LUT")
                if fixture=="prints" and not raw:
                    folder = card/"ML/DARKROOM/R001"
                    folder.mkdir()
                    sample=bytearray((assets/"SAMPLES/F004.BMP").read_bytes())
                    sample[1078:1082]=b"FOP2"
                    for number,file in enumerate(("SHEET.BMP","F01.BMP")):
                        sample[1084:1086]=number.to_bytes(2,"little")
                        (folder/file).write_bytes(sample)
                    jpegs=card/"DCIM/NOV1125"
                    jpegs.mkdir()
                    (jpegs/"ROLL001.TXT").touch()
                    Image.new("RGB",(720,480)).save(jpegs/"DSC00001.JPG")
            if (capture/"DSC00001.ARW").exists():
                (capture/"DSC00001.JPG").write_bytes(b"camera JPEG to preserve")
            before={p:hashlib.sha256(p.read_bytes()).digest() for p in capture.glob("DSC00001.*")}
            lines = [opening]
            checks, pictures = [], []
            time = 1200
            for keys, expected in steps:
                for key in keys:
                    lines.append(f"{time} {key}")
                    time += 580
                label = expected.get("picture")
                if label:
                    lines.append(f"{time} snap")
                    pictures.append(label)
                    time += 100
                checks.append({k:str(v) for k,v in expected.items() if k!="picture"})
                lines.append(f"{time} state")
                time += 200
            lines.append(f"{time} end")
            if sum(2 if line.split()[-1] in ("up","down","left","right") else 1 for line in lines)>250:
                raise ValueError("Scene exceeds upstream event table")
            script = card/"SCENE.TXT"
            script.write_text("\n".join(lines)+"\n", encoding="ascii")
            env = {k:v for k,v in os.environ.items() if not k.startswith("FOS_")}
            env.update(FOS_CARD="./",FOS_FONT=str(assets/"DATA/FOSFONT.BIN"),
                       FOS_FILMS=str(assets/"DATA/FOSFILMS.BIN"),FOS_SIZE="1")
            env.update(config or {})
            if fixture=="prints" and raw:
                develop=card/"DEVELOP.TXT"
                develop.write_text("noroll\nopen darkroom\n1500 set\n2400 info\n3400 set\n"
                                   "68000 state\n68500 snap\n70000 end\n",encoding="ascii")
                job=subprocess.run([str(binary),develop.name,"-"],cwd=card,env=env,
                                   capture_output=True,text=True,timeout=120,check=True)
                (output/"develop-original.log").write_text(job.stderr,encoding="utf8")
                assert "done=1" in job.stderr and (card/"ML/DARKROOM/R001/F01.ZOM").is_file(),job.stderr[-1800:]
                with Image.open(card/"SCR01.PPM") as frame:
                    frame.save(output/"developing-done.png")
            result = subprocess.run([str(binary),script.name,"-"],cwd=card,env=env,
                                    capture_output=True,text=True,timeout=60)
            log = result.stderr
            (output/(name+".log")).write_text(script.read_text()+"\n"+log,encoding="utf8")
            result.check_returncode()
            states = [dict(field.split("=",1) for field in line[6:].split("|"))
                      for line in log.splitlines() if line.startswith("STATE ")]
            assert len(states)==len(checks), (name,len(states),len(checks),log[-1200:])
            for i,(state,check) in enumerate(zip(states,checks)):
                for key,val in check.items():
                    assert state[key]==val,(name,i,key,val,state[key],state)
            for item in forbidden:
                assert item not in log,(name,item)
            for original,digest in before.items():
                assert digest==hashlib.sha256(original.read_bytes()).digest(), (name,original.name)
            for i,label in enumerate(pictures,1):
                with Image.open(card/f"SCR{i:02}.PPM") as frame:
                    frame.save(output/(label+".png"))
            report[name]=len(checks)
            print(f"{name}: {len(checks)} checkpoints", flush=True)

    scene("shelf","roll 0 5 36 3\nopen shelf",[
        at("",screen=2,film=0,picture="shelf"),at("right",film=2),at("left",film=0),
        at("up right",tabs=1),at("down",tabs=0),at("down",bar="Frames"),
        at("tele wide",bar="Frames"),at("set",bar="-",exp=1),
        at("play",sample=3,picture="sample"),at("menu",sample=0),at("set",ask=1),
        at("right",ask=1,sheet=1),at("set",ask=0,loading=0),
    ],fixture="samples",forbidden=("action 0 (","action 1 ("))
    scene("load","noroll\nopen shelf",[at("right set",screen=2,loading=1)])
    scene("settings","noroll\nopen home",[
        at("right",screen=3,home=0,picture="home"),at("down down set",screen=4,row="Viewfinder",picture="settings"),
        at("down set right",row="Print size",edit=1,value=2,size=1),
        at("down right set",edit=0,size=1),at("set right menu",edit=0,size=1),
        at("set right set",edit=0,size=2),at("down down down set",page=1,row="Lens"),
        at("down set",row="Aperture",edit=0,picture="lens"),at("play",screen=8),at("menu",screen=4,page=1,row="Aperture"),
        at("menu down set",page=2,row="LEDs on half-press",picture="advanced"),
        at("down down down down down down down set",page=3,row="Conversion",picture="screen"),
        at("menu",page=2,row="Screen colour"),at("menu",page=0,row="Advanced"),
        at("menu",screen=3,home=2)
    ], config={"FOS_ELECTRONIC_LENS":"1"})
    scene("legacy-setting","noroll\nopen home",[
        at("down down set down set",edit=1,value=2,size=99),at("set",edit=0,size=2)
    ],config={"FOS_SIZE":"99"})
    scene("advanced","noroll\nopen home",[
        at("down down set down down down down down set",page=2),
        at("down down down down down down down set",page=3,row="Conversion"),
        at("set right set",stored=1),
        at("down set right down left set",row="Colour",stored=1),
        at("down set left set",row="Warmth",stored=-1),
        at("down set right down right set",row="Brightness",stored=0),
        at("down set menu",row="Screen colour"),at("down set",row="Playback",edit=0),
        at("down down",row="Debug log"),at("set",row="Debug log",stored=0)
    ])
    scene("finish-cancel","roll 0 5 36 3\nopen end",[
        at("info",screen=5,rewind=1,sheet=0),
        at("right info",screen=5,rewind=1,sheet=1,picture="finish-new-roll"),
        at("right set",screen=5,rewind=0),at("set menu",rewind=0)
    ],forbidden=("action 1 (",))
    scene("finish-confirm","roll 0 36 36 3\nopen end",[
        at("right set",screen=2,loading=0),
    ])
    scene("darkroom","noroll\nopen darkroom",[
        at("set",marked=1,picture="darkroom"),at("right",bar="Unmark"),
        at("right",bar="Recipe"),at("set",ask=20,stock=4),
        at("right",ask=20,stock=5),at("down right",sheet=1,stock=5),
        at("set",screen=6,ask=0),at("right right right set",ask=4,size=1),
        at("right info",sheet=1,size=1,picture="develop-size"),at("set",ask=4,size=2),
        at("menu",ask=0),at("right right right right set",ask=3,sheet=1),
        at("set",ask=0,rolls=1)
    ], fixture="negative")
    scene("delete-prints","noroll\nopen darkroom",[
        at("right",bar="Prints"),at("right right",bar="Delete"),at("set",ask=1),
        at("set",ask=2,sheet=1),at("set",ask=0,rolls=1),at("right right right set",ask=1),
        at("right set",ask=3,sheet=1,picture="keep-roll"),at("menu",ask=0,rolls=1),
        at("play",screen=8,picture="prints-sheet"),at("set",mode=1,zoom=0,picture="prints-frame"),at("up right",mode=1,zoom=0),
        *([at("tele",mode=1,zoom=1,picture="prints-zoom"),at("left",mode=1,zoom=1),at("wide",mode=1,zoom=0)] if raw else []),
        at("menu",mode=0),at("menu",screen=6),
        at("right right right set right set left set",ask=0,rolls=0)
    ],fixture="prints")
    if raw:
        scene("stop-develop","noroll\nopen darkroom",[
            at("set info set",screen=7,done=0),at("menu",stop=1),
            at("right set",stop=0,done=0),at("menu menu",stop=0,done=0),
            at("menu set",screen=6)
        ],fixture="negative")
    (output/"checkpoints.json").write_text(json.dumps(report,indent=2)+"\n",encoding="ascii")
    print(sum(report.values()),"verified checkpoints")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    parser.add_argument("--raw",type=Path)
    args=parser.parse_args()
    run(args.output.resolve(),args.raw.resolve() if args.raw else None)
