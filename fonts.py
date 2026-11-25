"""Update just the two small menu faces of the original FOSF release asset."""
import runpy
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FACES=ROOT/"assets/sony-menu-fonts.bin"

def aligned(n):
    return (n+3)&~3

def face_record(face):
    bits=face["data"]
    glyphs=face["glyphs"]
    kern=face["kerns"]
    record=bytearray(struct.pack("<5I",len(bits),len(glyphs),len(kern),face["ascent"],face["descent"]))
    record.extend(bits)
    record.extend(bytes(aligned(len(bits))-len(bits)))
    lookup=bytearray([255]*256)
    for i,g in enumerate(glyphs):
        record.extend(struct.pack("<HBBbbH",*(g[k] for k in ("off","w","h","ox","oy","adv"))))
        lookup[g["code"]]=i
    record.extend(lookup)
    for pair in kern:
        record.extend(struct.pack("<BBb",*pair))
    record.extend(bytes(aligned(len(record))-len(record)))
    return record

def regenerate():
    upstream=ROOT.parent/"mfilm-canon-film-simulation/ml-dev/filmos/tools/mkfont.py"
    builder=runpy.run_path(str(upstream))
    faces=[builder["build"](name,filename,size,builder["ASCII"]) for name,filename,size in
           (("xs","Barlow-Bold.ttf",15),("sm","Barlow-SemiBold.ttf",18))]
    FACES.parent.mkdir(exist_ok=True)
    FACES.write_bytes(b"".join(face_record(f) for f in faces))

def apply_to(path):
    original=path.read_bytes()
    if struct.unpack_from("<4sII",original)!=(b"FOSF",1,10):
        raise ValueError("Unexpected Film OS font pack")
    offset=12
    for _ in range(2):
        bits,glyphs,kern=struct.unpack_from("<3I",original,offset)
        offset+=20+aligned(bits)+8*glyphs+256+aligned(3*kern)
    path.write_bytes(original[:12]+FACES.read_bytes()+original[offset:])

if __name__=="__main__":
    regenerate()
