"""Check Sony capture tags and the roll fallback on copies of a valid 5100 ARW."""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from PIL import Image


def entries(data, directory):
    count = struct.unpack_from("<H",data,directory)[0]
    offsets = range(directory+2,directory+2+12*count,12)
    return {struct.unpack_from("<H",data,o)[0]:o for o in offsets}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw",type=Path)
    args=parser.parse_args()
    build=Path(__file__).resolve().parents[1]/"build"
    source=args.raw.read_bytes()
    offset=lambda o:struct.unpack_from("<I",source,o)[0]
    root=entries(source,offset(4))
    exif=entries(source,offset(root[0x8769]+8))
    date_entry,aperture_entry=exif[0x9003],exif[0x829d]
    when=source[offset(date_entry+8):offset(date_entry+8)+19].decode("ascii")
    numerator,denominator=struct.unpack_from("<II",source,offset(aperture_entry+8))
    aperture=round(10*numerator/denominator)/10
    env=dict(os.environ,MFILM_TEST_DATE="2001-01-02 03:04",MFILM_TEST_FSTOP="8")
    with tempfile.TemporaryDirectory(dir=build) as temp:
        copy=Path(temp)/"TEST.ARW"
        prefix=Path(temp)/"out"
        for drop_date,drop_aperture in [(False,False),(True,False),(False,True),(True,True)]:
            data=bytearray(source)
            if drop_date:
                struct.pack_into("<H",data,date_entry,0)
            if drop_aperture:
                struct.pack_into("<I",data,offset(aperture_entry+8)+4,0)
            copy.write_bytes(data)
            subprocess.run([str(build/"develop.exe"),str(copy),str(prefix),"5","S"],
                           cwd=build,env=env,check=True,capture_output=True)
            with Image.open(prefix.with_suffix(".jpg")) as result:
                tags=result.getexif()
                photo=tags.get_ifd(34665)
                assert (tags[271],tags[272])==("SONY","ILCE-5100")
                assert photo[36867]==("2001:01:02 03:04:00" if drop_date else when)
                assert photo[33437]==(8 if drop_aperture else aperture)
                print(f"missing_date={drop_date} invalid_aperture={drop_aperture}: {photo[36867]}, f/{photo[33437]}")


if __name__=="__main__":
    main()
