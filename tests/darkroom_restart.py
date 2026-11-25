"""Interrupt the release C darkroom at each publication boundary on a private Windows test card."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from PIL import Image
from build_darkroom_scene import port


def hashes(files):
    result = {}
    for path in files:
        with path.open("rb") as stream:
            result[path.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return result


def main(raw, output, full_roll):
    output.mkdir(parents=True, exist_ok=True)
    assets = port / "build/assets/ML"
    runner = port / "build/menu-scene/menu.exe"
    env = {k:v for k,v in os.environ.items() if not k.startswith("FOS_")}
    env.update(FOS_CARD="./", FOS_FONT=str(assets/"DATA/FOSFONT.BIN"),
               FOS_FILMS=str(assets/"DATA/FOSFILMS.BIN"), FOS_SIZE="1")
    start = "1500 set\n2400 info\n3400 set\n"
    end = "125000 state\n126000 end\n"
    results = {}

    def scene(card, name, actions=start+end, expected=0, **options):
        script=card/"SCENE.TXT"
        script.write_text("noroll\nopen darkroom\n1000 state\n"+actions,encoding="ascii")
        run=subprocess.run([runner,script.name,"-"],cwd=card,env={**env,**options},
                           capture_output=True,text=True,timeout=150)
        (output/(name+".log")).write_text(script.read_text()+"\n"+run.stderr,encoding="utf8")
        assert run.returncode==expected,(name,run.returncode,run.stderr[-1800:])
        return run.stderr

    with tempfile.TemporaryDirectory(dir=port/"build",prefix="restart-card-") as tmp:
        card=Path(tmp)
        capture=card/"DCIM/100MSDCF"
        capture.mkdir(parents=True)
        (card/"MFILM").mkdir()
        lab=card/"ML/DARKROOM"
        lab.mkdir(parents=True)
        for number in [4,5]:
            shutil.copyfile(assets/f"DARKROOM/LOOK{number:02}.LUT",lab/f"LOOK{number:02}.LUT")
        lines=["film = superia400","exposures = 36","loaded = 2026-11-25 10:11"]
        for frame in [1,2]:
            base=f"DSC{frame:05}"
            shutil.copyfile(raw,capture/(base+".ARW"))
            Image.new("RGB",(48,32),(37*frame,52,3)).save(capture/(base+".JPG"))
            lines.append(f"{frame}  {base}.ARW  2026-11-25 10:23:{frame:02}  f/4.5")
        (capture/"ROLL_001.TXT").write_text("\n".join(lines)+"\n",encoding="ascii")
        originals=hashes(capture.iterdir())
        base_log=scene(card,"baseline")
        assert "done=1|failed=0|sheet_errors=0" in base_log,base_log[-1800:]
        jpeg_dir=next(d.parent for d in (card/"DCIM").glob("*/ROLL001.TXT"))
        roll=lab/"R001"
        first=[roll/"F01.BMP",roll/"F01.ZOM",jpeg_dir/"DSC00001.JPG"]
        second=[roll/"F02.BMP",roll/"F02.ZOM",jpeg_dir/"DSC00002.JPG"]
        bmp,zoom,jpeg=second
        sheet=roll/"SHEET.BMP"
        reference=hashes([*first,*second,sheet])
        first_times={p:p.stat().st_mtime_ns for p in first}
        for p in [first[-1],jpeg]:
            with Image.open(p) as im:
                im.load()
                dims=im.size
            z=first[1] if p==first[-1] else zoom
            with z.open("rb") as stream:
                assert struct.unpack("<4sHH",stream.read(8))==(b"FOZ1",*dims)
            assert (roll/"F01.BMP").stat().st_size==375542

        def ready(label, log, reprocessed):
            assert "done=1|failed=0|sheet_errors=0" in log,(label,log[-1800:])
            assert ("frame 2 developed in" in log)==reprocessed,(label,log[-1800:])
            assert "frame 1 developed in" not in log,label
            assert hashes([*first,*second,sheet])==reference,label
            assert hashes(capture.iterdir())==originals,label
            assert {p:p.stat().st_mtime_ns for p in first}==first_times,label
            assert not [p for directory in [roll,jpeg_dir] for p in directory.iterdir()
                        if p.suffix in (".BMT",".ZMT",".JPT")],label
            results[label]={"frame_2_rendered_on_retry":reprocessed,"matches_reference":True}
            print("PASS",label,flush=True)

        for boundary in [jpeg,zoom,bmp,sheet]:
            # Keep a previously published sheet, as when recovering damaged older output.
            with bmp.open("r+b") as stream:
                stream.truncate(1130)
            name="exit-before-"+boundary.name
            scene(card,name,expected=86,FOS_EXIT_AT_PUBLISH="/"+boundary.name)
            assert not sheet.exists(),name
            ready(name,scene(card,name+"-retry"),boundary!=sheet)

        for file,length in [(bmp,1130),(jpeg,-2),(zoom,1024),(sheet,1200)]:
            with file.open("r+b") as stream:
                stream.truncate(length if length>0 else file.stat().st_size+length)
            name="truncated-"+file.name
            ready(name,scene(card,name),file!=sheet)
        # Same byte length, plausible orientation, wrong zoom dimensions.
        with zoom.open("r+b") as stream:
            stream.seek(4)
            w,h=struct.unpack("<HH",stream.read(4))
            stream.seek(4)
            stream.write(struct.pack("<HH",h,w))
        ready("wrong-zoom-dimensions",scene(card,"wrong-zoom-dimensions"),True)
        with bmp.open("r+b") as stream:
            stream.seek(10)
            stream.write(bytes(4))
        ready("invalid-bitmap-offset",scene(card,"invalid-bitmap-offset"),True)
        zoom.unlink()
        ready("missing-zoom",scene(card,"missing-zoom"),True)

        for name,target,flag in [("write-error-zoom",zoom,"F02.ZMT"),
                                 ("write-error-jpeg",jpeg,"DSC00002.JPT"),
                                 ("write-error-sheet",sheet,"SHEET.BMT")]:
            target.unlink()
            log=scene(card,name,FOS_FAIL_WRITE=flag)
            failing="failed=0|sheet_errors=1" if target==sheet else "failed=1|sheet_errors=0"
            assert failing in log and not sheet.exists(),(name,log[-1800:])
            ready(name,scene(card,name+"-retry"),target!=sheet)

        bmp.unlink()
        early=scene(card,"leave-while-developing",start+"6300 state\n125000 end\n",
                    FOS_PAUSE_ON_OPEN="F02.ZMT")
        assert "screen=7" in early and "done=0" in early and not bmp.exists(),early[-1200:]
        assert "staging " in early and not zoom.with_suffix(".ZMT").exists() and not jpeg.with_suffix(".JPT").exists(),early[-1200:]
        ready("leave-while-developing",scene(card,"leave-while-developing-retry"),True)

        bmp.unlink()
        mixed=scene(card,"smaller-retry",FOS_SIZE="0")
        assert "done=1|failed=0|sheet_errors=0" in mixed and not zoom.exists(),mixed[-1200:]
        with Image.open(jpeg) as im:
            im.load()
            assert im.size==(720,480)
        assert hashes(first)=={p.name:reference[p.name] for p in first}
        reopened=scene(card,"reopen-mixed","2000 end\n")
        assert "|complete=2" in reopened,reopened[-1200:]
        results["smaller-retry"]={"reopened_complete_frames":2,"frame_2_size":[720,480],
                                  "frame_1_preserved":True}
        original_set=hashes([*first,bmp,jpeg,sheet])
        recipe="1500 right\n2200 right\n3000 set\n4200 right\n5200 set\n"
        reprint=scene(card,"alternate-recipe",recipe+end)
        edition=card/"MFILM/PRINTS/R001/P0001005"
        assert "done=1|failed=0|sheet_errors=0" in reprint,reprint[-1500:]
        assert len(list(edition.iterdir()))==7
        assert hashes([*first,bmp,jpeg,sheet])==original_set
        assert hashes(capture.iterdir())==originals
        results["alternate-recipe"]={"edition_files":7,"original_prints_preserved":True}
        if full_roll:
            # Distinct camera filenames on a private card, backed by one real ARW.
            lines=["film = superia400","exposures = 36","loaded = 2026-11-26 09:00"]
            for frame in range(1,37):
                name=f"DSC{100+frame:05}.ARW"
                os.link(capture/"DSC00001.ARW",capture/name)
                lines.append(f"{frame}  {name}  2026-11-26 09:00:{frame:02}  f/4.5")
            (capture/"ROLL_002.TXT").write_text("\n".join(lines)+"\n",encoding="ascii")
            keys=["right"]*5+["down"]*5+["set","tele","state","snap"]
            actions=start+"310000 state\n311000 set\n313000 state\n"
            actions+="".join(f"{314000+i*650} {key}\n" for i,key in enumerate(keys))+"325000 end\n"
            log=scene(card,"36-frames",actions)
            large=lab/"R002"
            day=next(tag.parent for tag in (card/"DCIM").glob("*/ROLL002.TXT"))
            assert "done=1|failed=0|sheet_errors=0" in log and log.count(" developed in ")==36,log[-2000:]
            assert "|mode=1|zoom=1|frame=36|" in log,log[-2200:]
            expected={f"F{i:02d}.{ext}" for i in range(1,37) for ext in ("BMP","ZOM")}|{"SHEET.BMP"}
            assert {p.name for p in large.iterdir()}==expected
            assert {p.stem for p in day.glob("*.JPG")}=={f"DSC{i:05}" for i in range(101,137)}
            with Image.open(large/"SHEET.BMP") as image:
                rgb=image.convert("RGB")
                for i in range(36):
                    assert any(rgb.getpixel((60+120*(i%6),40+80*(i//6))))
                rgb.save(output/"36-contact-sheet.png")
            with Image.open(card/"SCR01.PPM") as image:
                image.save(output/"36-last-frame-zoom.png")
            for i in range(1,37):
                with Image.open(day/f"DSC{100+i:05}.JPG") as im:
                    im.load()
                    assert im.size==dims
                assert (large/f"F{i:02d}.ZOM").stat().st_size==16+dims[0]*dims[1]
            assert hashes([*first,bmp,jpeg,sheet])==original_set
            results["36-frames"]={"frame_count":36,"published_image_files":109,
                                  "contact_sheet_cells":36,"last_frame_opened_and_zoomed":True}
        report={"source_arw":raw.name,"arw_sha256":originals["DSC00001.ARW"],
                "reference_output":reference,"medium_jpeg_dimensions":dims,
                "results":results,"validated_cases":len(results)}
        (output/"results.json").write_text(json.dumps(report,indent=2)+"\n",encoding="ascii")
        print(len(results),"restart, write failure, size and reprint checks passed")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--full-roll",action="store_true")
    args=parser.parse_args()
    main(args.raw.resolve(),args.output.resolve(),args.full_roll)
