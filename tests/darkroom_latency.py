"""Measure button schedule to C canvas completion while the same test ARW is developing."""
import argparse
import hashlib
import math
import re
import statistics
from pathlib import Path


from scene_camera import SceneCamera


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serial")
    parser.add_argument("fixture", help="The eight-character R directory created by reprint_scene.py")
    parser.add_argument("output", type=Path)
    parser.add_argument("--port12-controls",action="store_true")
    parser.add_argument("--resume",action="store_true",help="Continue an interrupted run with the same fixture and binary")
    args = parser.parse_args()
    camera = SceneCamera(args.serial, args.fixture)
    card = camera.card
    previous = Path(__file__).resolve().parents[1]/"build/darkroom-scene-port12/libs/armeabi-v7a/darkroom_scene"
    runner = camera.install_runner(previous if args.port12_controls else None)
    args.output.mkdir(exist_ok=True, parents=True)
    actions = [(1500,"right"),(2200,"right"),(3000,"set"),(4200,"right"),(5200,"set"),(7000,"down")]
    actions.extend((t, "right" if i%2==0 else "left") for i,t in enumerate(range(7500,18501,500)))
    actions.append((90000,"end"))
    scene = args.output / "schedule.txt"
    scene.write_text("noroll\nopen darkroom\n" + "".join(f"{ms} {key}\n" for ms,key in actions), encoding="ascii")
    camera.push(scene, card + "/LATENCY.TXT")
    expected = None
    rows = []
    for i,mode in enumerate(["1","p","p","1"], 1):
        record=args.output / f"run{i}-{mode}.log"
        if args.resume and record.exists():
            result=record.read_text(encoding="utf8")
        else:
            result=camera.shell(f"cd {card} && FOS_CARD=./ FOS_SIZE=1 FOS_WALL=1 FOS_FONT=ML/DATA/FOSFONT.BIN "
                                f"FOS_FILMS=ML/DATA/FOSFILMS.BIN MFILM_THREADS={mode} {runner} LATENCY.TXT - 2>&1")
            record.write_text(result+"\n", encoding="utf8")
        assert "frame 1 developed" in result and "Cpus_allowed_list:\t3" in result, result[-2200:]
        folder = re.search(r"write \./MFILM/PRINTS/R001/T(\d+)/SHEET.BMP", result)
        assert folder
        path = args.output / "check.jpg"
        camera.pull("MFILM/PRINTS/R001/P"+folder[1]+"/F01.JPG", path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.unlink()
        if expected is None:
            expected = digest
        assert expected == digest
        presented={int(due):int(due)+int(delay) for due,delay in re.findall(r"due=(\d+) canvas_ms=(\d+)",result)}
        scheduled=[t for t,key in actions if t>=7000 and key!="end"]
        shared=result.count("coalesced_key=")
        assert len(presented)+shared==len(scheduled) and set(presented)<=set(scheduled)
        # Several queued presses can reach the same canvas. Keep the earlier
        # press's full waiting time and count its missing intermediate highlight.
        delays=sorted(presented[min(s for s in presented if s>=due)]-due for due in scheduled)
        row = [i,mode,int(re.search(r"job_ms=(\d+)",result)[1]),int(re.search(r"VmHWM:\s+(\d+)",result)[1]),
               len(delays),shared,statistics.median(delays),delays[math.ceil(.95*len(delays))-1],max(delays)]
        rows.append(row)
        print(row, flush=True)
    report = ["run mode job_ms peak_kib events shared median_ms p95_ms max_ms"] + [" ".join(map(str,row)) for row in rows]
    report.append("JPEG SHA256 " + expected)
    (args.output / "results.txt").write_text("\n".join(report)+"\n", encoding="ascii")


if __name__ == "__main__":
    main()
