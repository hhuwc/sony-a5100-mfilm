"""Build the release C screens and the upstream scripted keypad as a Windows executable."""
import argparse
from pathlib import Path
import subprocess

from build_darkroom_scene import port, prepare, stage_simulator


def edit(path, old, new):
    source = path.read_text(encoding="utf8")
    if source.count(old) != 1:
        raise ValueError(f"Missing or ambiguous simulator hook in {path}: {old}")
    path.write_text(source.replace(old, new), encoding="utf8")


def build(zig):
    prepare()
    out = port / "build/menu-scene"
    out.mkdir(exist_ok=True)
    stage_simulator(out)
    # The desktop uses only the simulator's virtual clock. Firmware timing has its own ARM runner.
    (out / "scene_clock.h").write_text("""
#define wall_mode 0
#define busy_done 0
#define start_clock() ((void)0)
#define elapsed_ms() 0
#define usleep(us) ((void)0)
#define busy_clock(on) ((void)0)
#define record_canvas() ((void)0)
#define record_key(key,due) ((void)0)
void menu_snapshot(void);
""", encoding="ascii")
    sim = out / "sim.c"
    edit(sim, '    if (argc < 3)', '    extern int menu_color_test(void), zoom_reader_test(void);\n'
         '    if(argc==2 && !strcmp(argv[1],"--check-zoom"))return zoom_reader_test();\n'
         '    if(argc==2 && !strcmp(argv[1],"--check-colour"))return menu_color_test();\n    if (argc < 3)')
    edit(sim, '#include "navigation.h"', '#include "navigation.h"\n#include "display_color.h"\n#include "stock_settings.h"')
    edit(sim,'    if (argc < 3)',r'''    if(argc==2 && !strcmp(argv[1],"--stocks")){
        sim_films();
        for(int i=0;i<fos_nfilms;i++){
            int values[SONY_STOCK_FIELDS];
            sony_stock_settings(&fos_films[i],values);
            printf("%s\t%d",fos_films[i].key,fos_films[i].box_iso);
            for(int j=0;j<SONY_STOCK_FIELDS;j++)printf("\t%d",values[j]);
            putchar('\n');
        }
        return 0;
    }
    if (argc < 3)''')
    source=sim.read_text(encoding="utf8")
    start=source.index("            settings[FS_SCR_STD] == 1 ? fos_pal[i]")
    end=source.index(";",source.index("fos_screen_rgb(",start))+1
    sim.write_text(source[:start]+"            sony_screen_rgb(fos_pal[i],settings[FS_SCR_STD],"
                   "settings[FS_SCR_SAT],settings[FS_SCR_WARM],settings[FS_SCR_BRIGHT]);"+source[end:],
                   encoding="utf8")
    edit(sim, "cur_pal[i] = settings[FS_SCR_STD] == 1 ? rgb :\n"
         "            fos_screen_rgb(fos_screen_yuv_rgb(rgb, 235, 0, settings[FS_SCR_SAT], settings[FS_SCR_WARM], settings[FS_SCR_BRIGHT]), 235);",
         "cur_pal[i] = sony_screen_rgb(rgb,settings[FS_SCR_STD],settings[FS_SCR_SAT],settings[FS_SCR_WARM],settings[FS_SCR_BRIGHT]);")
    edit(sim, 'if(key==93){', 'if(key==94){menu_snapshot();return FK_NONE;}\n        if(key==93){')
    edit(sim, '{ "snap", 93 }', '{ "state", 94 }, { "snap", 93 }')
    edit(sim, 'if (s == FS_SCR_FLIP', 'if (s == FS_CANON_OFF || s == FS_EXPSIM) return -1;\n    if (s == FS_SCR_FLIP')
    edit(sim, '[FS_DEBUG] = 0', '[FS_DEBUG] = 1')
    edit(sim, 'roll.loaded = 1; roll.film = n1;', 'roll.nrecent=0; roll.loaded = 1; roll.film = n1;')
    edit(sim, 'int  fos_port_lens_manual() { return 1; }',
         'int fos_port_lens_manual() { return !getenv("FOS_ELECTRONIC_LENS"); }')
    edit(sim, 'return "Manual lens";',
         'return getenv("FOS_ELECTRONIC_LENS") ? "Electronic lens" : "Manual lens";')
    edit(sim, 'return s >= 0 && s < FS_COUNT ? settings[s] : 0;',
         'if(getenv("FOS_ELECTRONIC_LENS") && (s==FS_FSTOP || s==FS_LENS_WIDE))\n'
         '    for(int i=0;i<fos_nfstops;i++)if(fos_fstops[i]==450)return i;\n'
         'return s >= 0 && s < FS_COUNT ? settings[s] : 0;')
    edit(out / "port_files.c", '"Canon EOS M"', '"Sony ILCE-5100"')
    edit(out / "port_files.c", 'return remove(path) ? -1 : 0;',
         'return (S_ISDIR(st.st_mode) ? _rmdir(path) : remove(path)) ? -1 : 0;')
    # Each probe reads the real screen after its key handler and animation have run.
    probes = {
        "ui": r"""
void menu_shelf_snapshot(void);
void menu_pages_snapshot(void);
void menu_dark_snapshot(void);
void menu_snapshot(void) {
    fprintf(stderr,"STATE screen=%d|bar=%s|sheet=%d|leaving=%d", screen,
            nav_count ? nav_items[nav_at].label : "-", sheet_at, leaving);
    if(screen==SCR_SHELF) menu_shelf_snapshot();
    if(screen==SCR_HOME || screen==SCR_PAGE || screen==SCR_ROLL) menu_pages_snapshot();
    if(screen==SCR_DARK || screen==SCR_PRINTS || screen==SCR_DEVELOP) menu_dark_snapshot();
    fprintf(stderr,"|size=%d\n",fos_port_get(FS_SIZE));
}
""",
        "shelf": """
void menu_shelf_snapshot(void) {
    fprintf(stderr,"|film=%d|group=%d|tabs=%d|exp=%d|ask=%d|sample=%d|loading=%d",
            list[target],group,sony_tabs,exp_sel,asking,sm_state,loading);
}
""",
        "pages": """
void menu_pages_snapshot(void) {
    const struct item *item=&pages[page].items[page_sel];
    fprintf(stderr,"|home=%d|page=%d|row=%s|stored=%d|edit=%d|value=%d|rewind=%d",
            home_sel,page,item->label,item_value(item),editing,candidate,asking_rewind);
}
""",
        "dark": """
void menu_dark_snapshot(void) {
    fprintf(stderr,"|ask=%d|stock=%d|rolls=%d|marked=%d|mode=%d|zoom=%d|frame=%d|stop=%d|done=%d",
            dk_ask,chosen_stock,nrolls,count_marked(),pv_mode,pv_zlevel,pv_cur,asking_stop,finished);
    fprintf(stderr,"|failed=%d|sheet_errors=%d|complete=%d",failed_frames,sheet_errors,
            nrolls?rolls[dk_sel].complete:0);
}
"""
    }
    core = port / "build/filmos"
    sources = [out / (name + ".c") for name in ("sim", "fonts", "films", "port_files")]
    for name in ("gfx", "film", "ui", "shelf", "pages", "hud", "print", "dark", "dev", "lab", "looks", "jpeg"):
        source = core / f"fos_{name}.c"
        if name in probes:
            modified = out / source.name
            modified.write_text(source.read_text(encoding="utf8") + probes[name], encoding="utf8")
            source = modified
        sources.append(source)
    native = port / "native"
    sources.extend([native / "editions.c", native / "master_prints.c", native / "arw.c", port / "tests/menu_color.c"])
    sources.append(port / "tests/zoom_reader_test.c")
    win = out / "win_fs.h"
    win.write_text("#include <direct.h>\n#define mkdir(path,mode) _mkdir(path)\n", encoding="ascii")
    binary = out / "menu.exe"
    subprocess.run([str(zig), "cc", "-target", "x86_64-windows-gnu", "-std=gnu99", "-O2",
                    "-I", str(core), "-I", str(native), "-include", str(win),
                    *map(str, sources), "-o", str(binary)], cwd=out, check=True)
    subprocess.run([str(binary),"--check-colour"],check=True)
    subprocess.run([str(binary),"--check-zoom"],check=True)
    return binary


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zig", type=Path, default=port / "build/host-cc/ziglang/zig.exe")
    print(build(p.parse_args().zig.resolve()))
