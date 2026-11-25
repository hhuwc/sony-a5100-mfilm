"""Bootstrap a sibling workspace on Windows, keeping git checkouts under its root."""
from pathlib import Path
import hashlib, subprocess, urllib.request, zipfile
ROOT=Path(__file__).resolve().parent.parent
TC=ROOT/"toolchain"
REPOS={
    "HNGSeries/mfilm-canon-film-simulation":"84370e411ae8e106e8a4df5f094150a162707bcb",
    "cameronspears/latent":"1a7a10635dc1b1a2df8e2cf327a629e1eb9813e3",
    "voxivoid/recipe-lab-sony-pmca":"c5f1501cb35ba410ec98c982c0a22b965b9193c6",
    "ukiki0718-netizen/sony-a5100-film-studio":"ea766496cb40ec6a21beeb88da762679cf1786c8",
    "LibRaw/LibRaw":"9646d776c7c61976080a8f2be67928df0750493e",
    "ma1co/Sony-PMCA-RE":"a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0",
    "ma1co/PMCADemo":"12f34e49d48a1d9496ea3c2792911867ea4c985b",
    "obs1dium/BetterManual":"b6ab3c2feaf79c7360e9fdbc2aa6336a55a05a1d",
}
GOOGLE="https://dl.google.com/android/repository/"
ARCHIVES=[
    ("android.zip",GOOGLE+"platform-28_r06.zip","9a4e52b1d55bd2e24216b150aafae2503d3efba6","android-9/android.jar"),
    ("bt.zip",GOOGLE+"91936d4ee3ccc839f0addd53c9ebf087b1e39251.build-tools_r30.0.3-windows.zip","fc165c721b8d2da55e6fede467526c81f562be7b","android-11/aapt.exe"),
    ("ndk-parts.zip",GOOGLE+"android-ndk-r16b-windows-x86_64.zip","f3f1909ed1052e98dda2c79d11c22f3da28daf25","android-ndk-r16b/ndk-build.cmd"),
    ("jdk.zip","https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.25%2B9/OpenJDK11U-jdk_x64_windows_hotspot_11.0.25_9.zip","472d59e54f81e86c79192b7d9291d94f6e29d6d56ef7ed1d8aa74fcc7df548dc","jdk-11.0.25+9/bin/java.exe"),
    ("mfilm-release.zip","https://github.com/HNGSeries/mfilm-canon-film-simulation/releases/download/v0.2.4/M-Film-0.2.4-camera-EOSM.202.zip","e8a3cb6e67fdd339cdedfd052b01988a48cb6b3e34f5b022b031e72e96796c1c",None),
]
def bootstrap():
    for repo,sha in REPOS.items():
        path=ROOT/repo.split("/")[1]
        if not path.exists():
            subprocess.run(["git","clone","--no-checkout","https://github.com/"+repo+".git",path],check=True)
            subprocess.run(["git","-C",path,"checkout","--detach",sha],check=True)
        actual=subprocess.check_output(["git","-C",path,"rev-parse","HEAD"],text=True).strip()
        if actual!=sha:raise SystemExit(f"{path} is at {actual}, expected {sha}")
    recipe=ROOT/"recipe-lab-sony-pmca"
    subprocess.run(["git","-C",recipe,"submodule","update","--init","jni/platform"],check=True)
    # The original stlport remote disappeared. The mirror contains the exact pinned commit.
    subprocess.run(["git","-C",recipe/"jni/platform","-c",
                    "submodule.stlport.url=https://github.com/vincenthsu/stlport.git",
                    "submodule","update","--init","stlport"],check=True)
    TC.mkdir(exist_ok=True)
    for name,url,digest,entry in ARCHIVES:
        z=TC/name
        if not z.exists():
            tmp=z.with_suffix(".download")
            urllib.request.urlretrieve(url,tmp)
            tmp.replace(z)
        with z.open("rb") as f:actual=hashlib.file_digest(f,"sha1" if len(digest)==40 else "sha256").hexdigest()
        if actual!=digest:raise SystemExit(f"Incomplete or different archive {z}")
        if entry and not (TC/entry).exists():
            with zipfile.ZipFile(z) as archive:archive.extractall(TC)
if __name__=="__main__":bootstrap()

