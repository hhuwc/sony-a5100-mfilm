"""Compare incremental footer navigation with forced full redraws in the on-camera C harness."""
import argparse
from pathlib import Path

from PIL import Image

from scene_camera import SceneCamera


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serial")
    parser.add_argument("fixture")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    camera = SceneCamera(args.serial, args.fixture)
    card = camera.card
    runner = camera.install_runner()
    port = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True,exist_ok=True)
    scenes = {
        "shelf": (["down","right","snap","menu","snap"],["footer","back"]),
        "darkroom": (["right","right","snap","set","right","snap","menu","snap"],["footer","recipe","back"]),
        "prints": (["down","right","right","right","snap","set","set","tele","snap"],["footer","zoom"]),
    }
    checked = []
    for page,(keys,labels) in scenes.items():
        scene=args.output/(page+".txt")
        lines=[f"{1500+850*i} {key}" for i,key in enumerate(keys+["end"])]
        scene.write_text(f"noroll\nopen {page}\n"+"\n".join(lines)+"\n",encoding="ascii")
        camera.push(scene,card+"/FOOTER.TXT")
        for full in [True,False]:
            mode="FOS_FULL=1" if full else ""
            log=camera.shell(f"cd {card} && FOS_CARD=./ FOS_FONT=ML/DATA/FOSFONT.BIN FOS_FILMS=ML/DATA/FOSFILMS.BIN "
                      f"{mode} {runner} FOOTER.TXT - 2>&1")
            assert log.count("snapshot SCR")==len(labels), log[-1200:]
            if page=="prints":
                assert "read ./MFILM/PRINTS/R001/P0001005/F01.ZOM" in log
            (args.output/(page+("-full" if full else "-incremental")+".log")).write_text(log+"\n",encoding="utf8")
            for i,label in enumerate(labels,1):
                local=port/"build/darkroom-scene"/(args.fixture+"-scr.ppm")
                camera.pull(f"SCR{i:02d}.PPM", local)
                with Image.open(local) as frame:
                    output=args.output/f"{page}-{label}.png"
                    if full:
                        frame.save(output)
                    else:
                        with Image.open(output) as expected:
                            if frame.tobytes()!=expected.tobytes():
                                frame.save(args.output/f"{page}-{label}-incremental.png")
                                raise AssertionError(f"Full and partial canvases differ at {page} {label}")
                        checked.append(f"{page} {label}: equal 720x480 RGB")
                local.unlink()
    (args.output/"results.txt").write_text("\n".join(checked)+"\n",encoding="ascii")
    print("\n".join(checked))


if __name__=="__main__":
    main()
