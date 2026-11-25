"""Build the upstream scripted UI on ARM with the release darkroom and ARW sources."""
import argparse
from pathlib import Path
import subprocess
import sys

port = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(port))
from prepare import prepare


def stage_simulator(out):
    upstream = port.parent / "mfilm-canon-film-simulation/ml-dev/filmos/sim"
    for name in ["sim", "films", "fonts", "port_files"]:
        source = (upstream / (name + ".c")).read_text(encoding="utf8").replace('"../fos', '"fos')
        if name == "sim":
            source = source.replace('#include "fos.h"', '#include "fos.h"\n#include "navigation.h"')
            source = source.replace('#define FRAME_MS', '#include "scene_clock.h"\n#define FRAME_MS')
            source = source.replace('    outdir = argv[2];','    start_clock();\n    outdir = argv[2];')
            source = source.replace('return now_ms;','return wall_mode ? elapsed_ms() : now_ms;')
            source = source.replace('    /* FOS_FULL=1:', '    if(wall_mode){if(ms>0)usleep(ms*1000);now_ms=elapsed_ms();return;}\n    /* FOS_FULL=1:')
            source = source.replace('int  fos_port_dev_cap() { return 12; }', 'int fos_port_dev_cap(){return wall_mode?0:12;}')
            source = source.replace('    if (a == FA_LOAD)', '    if(a==FA_BUSY)busy_clock(x);\n    if (a == FA_LOAD)')
            source = source.replace('return now_ms > end_t;', 'extern int scene_pause_requested; return scene_pause_requested || busy_done || now_ms > end_t;')
            source = source.replace('        overdrawn_row[y] = 0;\n    }', '        overdrawn_row[y] = 0;\n    }\n    record_canvas();')
            source = source.replace('evs[next_ev].t <= now_ms','evs[next_ev].t <= fos_port_ms()')
            source = source.replace('{ "left", FK_LEFT }', '{ "snap", 93 }, { "tele", SONY_TELE }, { "wide", SONY_WIDE }, { "left", FK_LEFT }')
            source = source.replace('    if (!strcmp(outdir, "-")) return;\n', '')
            source = source.replace('    memcpy(cur_pal, pal, sizeof(cur_pal));', '    memcpy(cur_pal, pal, sizeof(cur_pal));\n    if(!strcmp(outdir,"-")) return;')
            source = source.replace('        return evs[next_ev++].key;', '''
    {
        int key=evs[next_ev++].key;
        record_key(key,evs[next_ev-1].t);
        if(key==93){
            static int sequence;
            char path[32];
            snprintf(path,sizeof(path),"SCR%02d.PPM",++sequence);
            FILE *f=fopen(path,"wb");
            if(!f)abort();
            fprintf(f,"P6\\n%d %d\\n255\\n",FOS_W,FOS_H);
            for(int i=0;i<FOS_W*FOS_H;i++){
                uint32_t color=cur_pal[screen[i]];
                fputc(color>>16,f);fputc(color>>8,f);fputc(color,f);
            }
            if(fclose(f))abort();
            fprintf(stderr,"snapshot %s at %d\\n",path,now_ms);
            return FK_NONE;
        }
        fprintf(stderr,"input %d at %d\\n",key,now_ms);
        return key;
    }''')
            source += '''
int sony_pending_input(void){return next_ev<nev && evs[next_ev].t<=fos_port_ms();}
int sony_baseline(void){return 0;}
void sony_remember_menu(int page){}
void sony_trace_screen(int page){
    static int previous=-1;
    if(page!=previous)fprintf(stderr,"screen %d at %d\\n",page,now_ms);
    previous=page;
}
'''
        if name == "port_files":
            source="int scene_pause_requested;\n"+source
            source += '''
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif
int sony_replace_output(const char *from,const char *to){
    const char *fault=getenv("FOS_EXIT_AT_PUBLISH");
#ifdef _WIN32
    if(fault && strstr(to,fault))_Exit(86);
    int ok=MoveFileExA(from,to,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=0;
#else
    if(fault && strstr(to,fault))_exit(86);
    FILE *f=fopen(from,"r+b");
    if(!f)return 0;
    int ok=!fflush(f) && !fsync(fileno(f));
    if(fclose(f))ok=0;
    ok=ok && !rename(from,to);
#endif
    if(ok)fprintf(stderr,"write %s\\n",to);
    return ok;
}
'''
            source = source.replace('    return fopen(path, write ? "wb" : "rb");', '''
    if(strstr(path,".BMP") || strstr(path,".JPG") || strstr(path,".ZOM"))
        fprintf(stderr,"%s %s\\n",write?"write":"read",path);
    if(write && (strstr(path,".BMT") || strstr(path,".JPT") || strstr(path,".ZMT")))
        fprintf(stderr,"staging %s\\n",path);
    if(write && getenv("FOS_PAUSE_ON_OPEN") && strstr(path,getenv("FOS_PAUSE_ON_OPEN")))scene_pause_requested=1;
    if(write && getenv("FOS_FAIL_WRITE") && strstr(path,getenv("FOS_FAIL_WRITE")))return 0;
    if(write && (strstr(path,".ZOM") || strstr(path,".ZMT")) && getenv("FOS_FAIL_ZOOM"))return 0;
    return fopen(path, write ? "wb" : "rb");''')
        (out / (name + ".c")).write_text(source, encoding="utf8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port12-controls",action="store_true",
                        help="Reproduce the previous full-footer redraw and develop-before-feedback scheduling")
    args = parser.parse_args()
    prepare()
    out = port / "build" / ("darkroom-scene-port12" if args.port12_controls else "darkroom-scene")
    out.mkdir(exist_ok=True)
    stage_simulator(out)
    core = ["gfx", "film", "ui", "shelf", "pages", "hud", "print", "dark", "dev", "lab", "looks", "jpeg"]
    sources = ["sim.c", "films.c", "fonts.c", "port_files.c"]
    sources += ["../filmos/fos_" + name + ".c" for name in core]
    if args.port12_controls:
        old_ui = (port/"build/filmos/fos_ui.c").read_text(encoding="utf8")
        old_ui = old_ui.replace("    if(screen==SCR_DEVELOP)develop_note_input();\n","")
        old_ui = old_ui.replace('#include "navigation.inc"', '#include "prior_navigation.inc"')
        (out/"prior_ui.c").write_text(old_ui,encoding="utf8")
        footer = (port/"native/navigation.inc").read_text(encoding="utf8")
        footer = footer.replace("ui_damage(HINTS_Y,FOS_H);","ui_clobbered=1;ui_damage_all();")
        footer = footer.replace("if(k==FK_DOWN)return FK_NONE;","if(k==FK_DOWN){ui_clobbered=1;ui_damage_all();return FK_NONE;}")
        (out/"prior_navigation.inc").write_text(footer,encoding="utf8")
        sources[sources.index("../filmos/fos_ui.c")]="prior_ui.c"
    sources += ["../../native/" + name + ".c" for name in ["editions", "master_prints", "arw", "batch", "read_ahead"]]
    (out / "Android.mk").write_text("\n".join([
        "LOCAL_PATH := $(call my-dir)", "include $(CLEAR_VARS)", "LOCAL_MODULE := darkroom_scene",
        "LOCAL_SRC_FILES := " + " ".join(sources),
        "LOCAL_C_INCLUDES := $(LOCAL_PATH)/../filmos $(LOCAL_PATH)/../../native $(LOCAL_PATH)/../../tests",
        "LOCAL_ARM_MODE := arm",
        "LOCAL_CFLAGS := -std=gnu99 -O2 -mtune=cortex-a5 -fno-math-errno -fno-strict-aliasing -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0",
        "LOCAL_LDFLAGS := -Wl,--hash-style=sysv", "LOCAL_LDLIBS := -lm -llog", "include $(BUILD_EXECUTABLE)", ""
    ]), encoding="ascii")
    subprocess.run([str(port.parent / "toolchain/android-ndk-r16b/ndk-build.cmd"),
                    "NDK_PROJECT_PATH=" + out.as_posix(), "APP_BUILD_SCRIPT=Android.mk",
                    "NDK_APPLICATION_MK=" + (port / "native/Application.mk").as_posix(), "-j6"],
                   cwd=out, check=True)


if __name__ == "__main__":
    main()
