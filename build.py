"""Windows release build. The IDE can open this directory independently."""
import argparse,os,subprocess,zipfile,hashlib,secrets,tempfile
from xml.etree import ElementTree
from pathlib import Path
from prepare import ROOT,OUT,prepare
TC=ROOT.parent/"toolchain"
NDK=TC/"android-ndk-r16b"
BT=TC/"android-11"
AJ=TC/"android-9/android.jar"
JDK=TC/"jdk-11.0.25+9"
def run(*args,cwd=ROOT):
    subprocess.run([str(a) for a in args],cwd=cwd,check=True)
def package_entries(apk, resources, dex):
    def add(archive, name, payload, compression):
        entry=zipfile.ZipInfo(name,(1980,1,1,0,0,0))
        entry.create_system=3
        entry.external_attr=0o100644 << 16
        archive.writestr(entry,payload,compress_type=compression)

    with zipfile.ZipFile(resources) as src, zipfile.ZipFile(apk,"w") as dest:
        for entry in sorted(src.infolist(),key=lambda item:item.filename):
            add(dest,entry.filename,src.read(entry),entry.compress_type)
        add(dest,"classes.dex",dex.read_bytes(),zipfile.ZIP_DEFLATED)
        library="lib/armeabi-v7a/libfilmos.so"
        add(dest,library,(OUT/"libs/armeabi-v7a/libfilmos.so").read_bytes(),zipfile.ZIP_DEFLATED)

def main(dist=None,signing_dir=None):
    prepare()
    os.environ["JAVA_HOME"]=str(JDK)
    os.environ["PATH"]=str(JDK/"bin")+os.pathsep+os.environ["PATH"]
    run(NDK/"ndk-build.cmd","-B","NDK_PROJECT_PATH="+ROOT.as_posix(),"APP_BUILD_SCRIPT=native/Android.mk","NDK_APPLICATION_MK=native/Application.mk","NDK_OUT=build/obj","NDK_LIBS_OUT=build/libs","-j6")
    apk=OUT/"unsigned.apk"
    with tempfile.TemporaryDirectory(dir=OUT) as staging:
        classes=Path(staging)/"classes"
        classes.mkdir()
        run(JDK/"bin/javac.exe","--release","8","-encoding","UTF-8","-classpath",AJ,"-d",classes,*sorted(ROOT.glob("src/**/*.java")))
        run("python",ROOT.parent/"latent/tools/check_api.py",AJ.parent/"data/api-versions.xml",classes,"10")
        run(JDK/"bin/java.exe","-cp",BT/"lib/d8.jar","com.android.tools.r8.D8","--min-api","10","--lib",AJ,"--output",staging,*sorted(classes.rglob("*.class")))
        resources=Path(staging)/"resources.apk"
        run(BT/"aapt.exe","package","-f","-M","AndroidManifest.xml","-I",AJ,"-S",ROOT/"res","-A",OUT/"assets","-F",resources)
        package_entries(apk,resources,Path(staging)/"classes.dex")
    run(BT/"zipalign.exe","-f","4",apk,OUT/"aligned.apk")
    keys=ROOT/".signing" if signing_dir is None else Path(signing_dir).resolve()
    keys.mkdir(exist_ok=True)
    ks=keys/"release.p12";pw=keys/"password"
    if not ks.exists():
        pw.write_text(secrets.token_hex(24),encoding="ascii")
        run(JDK/"bin/keytool.exe","-genkeypair","-storetype","PKCS12","-keystore",ks,"-storepass:file",pw,"-alias","mfilm","-keyalg","RSA","-keysize","2048","-validity","10000","-dname","CN=M-Film Sony local build")
    dist=ROOT/"dist" if dist is None else Path(dist).resolve()
    dist.mkdir(parents=True,exist_ok=True)
    manifest=ElementTree.parse(ROOT/"AndroidManifest.xml").getroot()
    version=manifest.attrib["{http://schemas.android.com/apk/res/android}versionName"]
    film,port=version.split("-port")
    signed=dist/f"M-Film-{film}-ILCE5100-port{port}.apk"
    signer=[JDK/"bin/java.exe","-jar",BT/"lib/apksigner.jar"]
    run(*signer,"sign","--ks",ks,"--ks-pass","file:"+str(pw),"--min-sdk-version","10","--v1-signing-enabled","true","--v2-signing-enabled","false","--v3-signing-enabled","false","--out",signed,OUT/"aligned.apk")
    run(*signer,"verify","--verbose","--min-sdk-version","10",signed)
    run(BT/"aapt.exe","dump","badging",signed)
    with signed.open("rb") as f:
        digest=hashlib.file_digest(f,"sha256").hexdigest()
    signed.with_suffix(".apk.sha256").write_text(digest+"  "+signed.name+"\n",encoding="ascii")
if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path)
    parser.add_argument("--signing-dir",type=Path,help="directory for the signing keystore and password")
    args=parser.parse_args()
    main(args.output_dir,args.signing_dir)

