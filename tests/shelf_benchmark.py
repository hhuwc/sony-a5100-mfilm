"""Measure identical left/right shelf movements in a traced, foreground Film OS session."""
import argparse
from pathlib import Path
import re
import statistics
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serial")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    adb = ["adb", "-s", args.serial]

    def shell(command):
        return subprocess.check_output(adb + ["shell", command], text=True, timeout=20)

    flag = "/mnt/sdcard/MFILM/VERIFY/BASELINE.ON"
    start = f"bench{time.time_ns()}"
    def check_foreground():
        activities = shell("dumpsys activity activities").splitlines()
        resumed = next((line for line in activities if "mResumedActivity" in line), "")
        if "org.mfilm.sony/.FilmOS" not in resumed:
            raise RuntimeError("The camera left Film OS")

    def check_input():
        output = subprocess.check_output(adb + ["logcat", "-d", "FilmBench:I", "FilmOS:I", "*:S"],
                                         text=True, encoding="utf-8", errors="replace", timeout=10)
        _, marker, recent = output.rpartition(start + "-watch")
        if not marker or re.search(r"input key=\d+ scan=[1-9]|rocker=", recent):
            raise RuntimeError("Stopped the trial after camera input or loss of its log marker")

    check_foreground()
    shell(f"log -t FilmBench {start}-watch")
    records = []
    try:
        for block, baseline in enumerate((True, False, False, True)):
            shell("echo 1 > " + flag if baseline else "rm " + flag)
            time.sleep(1.6)
            shell(f"log -t FilmBench {start}-{block}-start")
            for key in (22, 21, 22, 21):
                check_foreground()
                check_input()
                shell(f"input keyevent {key}")
                time.sleep(1.5)
            shell(f"log -t FilmBench {start}-{block}-end")
            output = subprocess.check_output(adb + ["logcat", "-d", "-v", "time", "FilmBench:I",
                                                     "FilmFrame:D", "FilmOS:I", "*:S"], text=True,
                                             encoding="utf-8", errors="replace")
            first = output.index(f"{start}-{block}-start")
            last = output.index(f"{start}-{block}-end", first)
            section=output[first:last]
            modes=set(re.findall(r"engine baseline=(\d+)",section))
            if modes!={str(int(baseline))}:
                raise RuntimeError(f"Camera render mode did not settle in block {block}: {modes}")
            if re.search(r"input key=\d+ scan=[1-9]",section):
                raise RuntimeError("Physical input overlapped the scripted trial")
            records.append(section)
    finally:
        shell("rm " + flag)
        args.output.write_text("\n".join(records), encoding="utf-8")
    for name, indexes in (("baseline", [0, 3]), ("optimized", [1, 2])):
        groups, latencies = [], []
        for index in indexes:
            active = None
            for line in records[index].splitlines():
                if re.search(r"input key=[12] scan=0 down=false", line):
                    active = []
                    groups.append(active)
                frame = re.search(r"FilmFrame.*: draw (\d+) (\d+)", line)
                if frame and active is not None:
                    active.append(int(frame[2]))
                latency = re.search(r"key to draw (\d+) ms", line)
                if latency and active is not None:
                    latencies.append(int(latency[1]))
        intervals = [b-a for group in groups for a,b in zip(group,group[1:]) if b-a<500]
        if not intervals or not latencies:
            raise RuntimeError(f"No complete animation samples for {name}")
        print(f"{name}: gestures={len(groups)}, completed frame intervals={len(intervals)}, "
              f"median interval={statistics.median(intervals)} ms, "
              f"median release to draw={statistics.median(latencies)} ms, latencies={latencies}")


if __name__ == "__main__":
    main()
