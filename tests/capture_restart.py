"""Exercise the real C roll writer, restarting its process for every operation."""
from pathlib import Path
import subprocess
import sys
import tempfile

EXE = Path(sys.argv[1]).resolve()
EVIDENCE = Path(__file__).resolve().parent / "fixtures"
DCF = Path("DCIM/100MSDCF")
NEXT = Path("DCIM/101MSDCF")
LOG = DCF / "ROLL_003.TXT"
RECEIPT = Path("MFILM/FRAME.DAT")
STATE = Path("STATE.BIN")
FIRST = "./DCIM/100MSDCF/DSC00001.ARW"
SECOND = "./DCIM/100MSDCF/DSC00002.ARW"


def card(root, name):
    directory = root / name
    for sub in (DCF, NEXT, RECEIPT.parent):
        (directory / sub).mkdir(parents=True)
    return directory


def run(directory, *args, code=0):
    result = subprocess.run([EXE, *map(str, args)], cwd=directory, capture_output=True, text=True)
    assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
    return tuple(map(int, result.stdout.split()))


def cut_every_byte(root, number):
    directory = card(root, f"cuts-{number}")
    if number == 2:
        run(directory, "attach", 301, FIRST)
    old_state = (directory / STATE).read_bytes() if (directory / STATE).exists() else None
    log, receipt = directory / LOG, directory / RECEIPT
    prefix = log.read_bytes() if log.exists() else b""
    run(directory, "attach", 300 + number, (FIRST, SECOND)[number - 1], "before", code=77)
    good, journal = log.read_bytes(), receipt.read_bytes()
    expected = run(directory, "recover")
    assert expected == (number, number, 1, number, number - 1, 301 + number)
    for end in range(len(prefix), len(good) + 1):
        if old_state is None:
            (directory / STATE).unlink(missing_ok=True)
        else:
            (directory / STATE).write_bytes(old_state)
        log.write_bytes(good[:end])
        if not end:
            log.unlink()
        receipt.write_bytes(journal)
        assert run(directory, "recover") == expected
        assert log.read_bytes() == good and not receipt.exists()
    return len(good) - len(prefix) + 1


def transactions(root):
    directory = card(root, "transactions")
    log, receipt = directory / LOG, directory / RECEIPT
    # The real writer only records the filename. Sentinel bytes ensure it never opens the original for writing.
    (directory / FIRST).write_bytes(b"camera original")
    run(directory, "attach", 301, FIRST, "after", code=78)
    assert receipt.exists()
    assert run(directory, "recover") == (1, 1, 1, 1, 0, 302)
    assert not receipt.exists()
    run(directory, "wind")
    original = log.read_bytes()
    assert run(directory, "attach", 301, FIRST) == (1, 1, 0, 1, 0, 302)
    for ticket, path in ((301, SECOND), (302, FIRST), (401, SECOND), (303, SECOND),
                         (301, FIRST.replace("100MSDCF", "101MSDCF")), (302, "../DSC00002.ARW")):
        run(directory, "attach", ticket, path, code=1)
    assert log.read_bytes() == original and (directory / FIRST).read_bytes() == b"camera original"
    run(directory, "attach", 302, SECOND, "before", code=77)
    good, journal = log.read_bytes(), receipt.read_bytes()
    for damaged in (b"X" + good[1:], original + b"X", good + b"extra"):
        log.write_bytes(damaged)
        run(directory, "recover", code=1)
        assert log.read_bytes() == damaged and receipt.read_bytes() == journal
        assert run(directory, "state")[0] == 1
    log.write_bytes(good)
    for damaged in (journal[:-1], journal[:-1] + bytes([journal[-1] ^ 1])):
        receipt.write_bytes(damaged)
        run(directory, "recover", code=1)
        assert receipt.read_bytes() == damaged
    receipt.unlink()
    scratch = receipt.with_suffix(".NEW")
    scratch.write_bytes(journal)
    assert run(directory, "recover", "fail", code=1)[0] == 1
    assert receipt.exists() and not scratch.exists()
    assert run(directory, "recover")[:4] == (2, 2, 1, 2)
    scratch.write_bytes(journal[:3])
    run(directory, "recover")
    for number in range(3, 13):
        run(directory, "attach", 300 + number, f"./DCIM/101MSDCF/DSC{number:05d}.ARW")
    assert run(directory, "recover")[0::2] == (12, 0, 11)
    assert run(directory, "state")[-1] == 0
    run(directory, "attach", 313, SECOND, code=1)


def legacy(root):
    directory = card(root, "legacy")
    lines = (EVIDENCE / "ROLL_003.TXT").read_bytes().splitlines(keepends=True)
    log, other = directory / LOG, directory / NEXT / LOG.name
    log.write_bytes(b"".join(lines[:6]))
    other.write_bytes(b"".join(lines[:3] + lines[6:]))
    assert run(directory, "recover") == (5, 5, 1, 5, 4, 306)
    run(directory, "wind")
    assert run(directory, "recover")[2] == 0
    assert log.read_bytes() == b"".join(lines[:6])
    (directory / STATE).unlink()
    for conflict in (b"".join(lines[:3] + lines[7:]), b"".join(lines[5:]), b"4  DSC01125.ARW  2026-11-25 10:2"):
        other.write_bytes(conflict)
        assert run(directory, "recover", code=1)[0] == 0
    other.unlink()
    log.write_bytes((EVIDENCE / "ROLL_001.TXT").read_bytes())
    assert run(directory, "recover")[:4] == (2, 2, 1, 2)


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    counts = [cut_every_byte(root, i) for i in (1, 2)]
    transactions(root)
    legacy(root)
    print(f"PASS first log/header {counts[0]} byte boundaries, existing log {counts[1]} byte boundaries")
    print("PASS independent process restart before/after durable state, idempotent replay, failed save rollback")
    print("PASS conflicts, unpublished receipt, bad checksum/length, folder rollover, final frame, wind")
    print("PASS real legacy log copies across two folders, gaps and duplicate rows, older rows without aperture")
