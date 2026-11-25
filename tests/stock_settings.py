"""Exercise the production Java stock settings with all profiles read by the production C catalogue."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

PORT=Path(__file__).resolve().parents[1]


def run(apk, output):
    output.mkdir(parents=True,exist_ok=True)
    java=PORT.parent/"toolchain/jdk-11.0.25+9/bin"
    with tempfile.TemporaryDirectory(dir=PORT/"build") as work:
        temp=Path(work)
        with zipfile.ZipFile(apk) as archive:
            films=temp/"FOSFILMS.BIN"
            films.write_bytes(archive.read("assets/ML/DATA/FOSFILMS.BIN"))
        table=subprocess.check_output([PORT/"build/menu-scene/menu.exe","--stocks"],
                                      env={**os.environ,"FOS_FILMS":str(films)},text=True)
        (output/"stocks.tsv").write_text(table,encoding="ascii")
        subprocess.run([java/"javac.exe","--release","8","-d",temp,
                        PORT/"src/org/mfilm/sony/StockSettings.java",PORT/"tests/StockSettingsTest.java"],check=True)
        result=subprocess.check_output([java/"java.exe","-cp",temp,"org.mfilm.sony.StockSettingsTest",
                                        output/"stocks.tsv"],text=True)
        print(result,end="")
        (output/"stock-check.txt").write_text(result,encoding="ascii")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("apk",type=Path);p.add_argument("output",type=Path)
    args=p.parse_args()
    run(args.apk.resolve(),args.output.resolve())
