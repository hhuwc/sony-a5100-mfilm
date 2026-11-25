"""Stage the pinned Film OS tree and its matching release data, then adapt the RAW input."""
from pathlib import Path
import hashlib, shutil, subprocess, zipfile
ROOT=Path(__file__).resolve().parent
UP=ROOT.parent/"mfilm-canon-film-simulation"
OUT=ROOT/"build"
CORE=OUT/"filmos"
RELEASE=ROOT.parent/"toolchain/mfilm-release.zip"
def replace(src,old,new):
    assert src.count(old)==1,old
    return src.replace(old,new)
def prepare():
    revision=subprocess.check_output(["git","-C",UP,"rev-parse","HEAD"],text=True).strip()
    assert revision=="84370e411ae8e106e8a4df5f094150a162707bcb", revision
    CORE.mkdir(parents=True,exist_ok=True)
    for p in (UP/"ml-dev/filmos").glob("fos*.*"):
        shutil.copyfile(p,CORE/p.name)
    path=CORE/"fos_gfx.c"
    s=path.read_text(encoding="utf8")
    s=replace(s,"    if (!v) return 0;\n    unsigned int r", """#if defined(__ANDROID__) && defined(__arm__)
    extern int sony_baseline(void);
    if (!sony_baseline()) return (unsigned)__builtin_sqrt((double)v);
#endif
    if (!v) return 0;
    unsigned int r""")
    path.write_text(s,encoding="utf8")
    path=CORE/"fos_dev.c"
    s='#include "arw.h"\n'+path.read_text(encoding="utf8")
    s=s.replace("#include <math.h>", "#include <math.h>\nstatic float sony_log2(float x){return logf(x)*1.44269504089f;}").replace("log2f(","sony_log2(")
    s=replace(s,"struct fos_dev\n{","struct fos_dev\n{\n    Arw arw;")
    s=replace(s,"#if defined(CONFIG_6D) || defined(CONFIG_70D)", "#if 1 /* Sony ILCE-5100, LibRaw colordata */\nstatic const float XYZ_CAM[3][3] = M3(5991,-1456,-455,-4764,12135,2980,-707,1425,6701);\n#elif defined(CONFIG_6D) || defined(CONFIG_70D)")
    s=replace(s,"#define WHITE_LEVEL 13600","#define WHITE_LEVEL (d->arw.white)")
    s=replace(s,"d->rphase = row_phase(d->raw_w, d->raw_h);","d->rphase = 0; /* ILCE-5100 RGGB */")
    a=s.index("                if (parse_tiff(d) < 0")
    b=s.index("                d->stage = ST_DECODE;",a)
    s=s[:a]+'''                if (!arw_open(&d->arw,d->f)) return fail(d,"Unsupported or incomplete ILCE-5100 ARW");
                if(d->arw.capture.when[0])snprintf(d->when,sizeof(d->when),"%s",d->arw.capture.when);
                if(d->arw.capture.fstop[0])snprintf(d->fstop,sizeof(d->fstop),"%s",d->arw.capture.fstop);
                d->wide=ARW_WIDTH; d->high=d->arw.height; d->clrs=1; d->bits=14;
                d->orient=d->arw.orientation;
                d->crop_l=d->crop_t=0; d->crop_w=d->arw.visible_width; d->crop_h=d->arw.height;
                d->black_sum=d->arw.black; d->black_n=1;
                memcpy(d->wb,d->arw.wb,sizeof(d->wb));
                if (setup_maps(d)<0) return -1;
'''+s[b:]
    s=replace(s,"decode(d, 1 << 14);",'''if (!arw_read(&d->arw,d->f)) return fail(d,"Truncated ARW sensor row");
                scatter(d,d->arw.row,ARW_WIDTH);
                d->done+=ARW_WIDTH;''')
    s=s.replace('#include "arw.h"', '#include "arw.h"\n#ifdef __ANDROID__\n#include "batch.h"\n#include <stdlib.h>\n#endif')
    s=s.replace("    Arw arw;","    Arw arw;\n#ifdef __ANDROID__\n    struct Batch *batch;\n#endif")
    s=s.replace("                if (setup_maps(d)<0)",'''#ifdef __ANDROID__
                const char *variant=getenv("MFILM_THREADS");
                if(!variant || *variant=='p')d->batch=batch_new('p');
                if(variant && (*variant=='1' || *variant=='2'))d->batch=batch_new(*variant-'0');
#endif
                if (setup_maps(d)<0)''')
    s=s.replace("                if (!arw_read",'''#ifdef __ANDROID__
                if(d->batch){
                    int n=batch_next(d->batch,&d->arw,d->f,(d->total-d->done)/ARW_WIDTH);
                    if(n<1)return fail(d,"ARW batch read failed");
                    for(int i=0;i<n;i++)scatter(d,batch_row(d->batch,i),ARW_WIDTH);
                    d->done+=n*ARW_WIDTH;
                }else
#endif
                {if (!arw_read''').replace("d->done+=ARW_WIDTH;","d->done+=ARW_WIDTH;}")
    s=replace(s,"    if (d->f) fos_port_close(d->f);","#ifdef __ANDROID__\n    batch_end(d->batch);\n#endif\n    if (d->f) fos_port_close(d->f);")
    s=replace(s,"        switch (d->stage)\n", """#ifdef __ANDROID__
        extern int sony_pending_input(void);
        if (now-t0>=12 && sony_pending_input()) break;
#endif
        switch (d->stage)
""")
    path.write_text(s,encoding="utf8")
    path=CORE/"fos_lab.c"
    s=path.read_text(encoding="utf8").replace('".CR2"','".ARW"')
    a=s.index("        int n = fos_lab_frames(roll, frames, FOS_MAX_FRAMES);")
    b=s.index("        f.n = 0;",a)
    path.write_text(s[:a]+"        /* Keep camera originals when removing a roll. */\n"+s[b:],encoding="utf8")
    path=CORE/"fos_dark.c"
    s=path.read_text(encoding="utf8")
    s=replace(s, "if (vh * step * pv_zf.w > most) most = vh * step * pv_zf.w;",
              "int band = (vh < FOS_ZOOM_BAND ? vh : FOS_ZOOM_BAND) * step * pv_zf.w;\n"
              "        if (band > most) most = band;")
    s=replace(s, 'T_TIMES "%d.%d", f10 / 10, f10 % 10',
              'pv_zf.f ? T_TIMES "%d.%d" : "Preview " T_TIMES "%d.%d", f10 / 10, f10 % 10')
    s=replace(s,"static int dk_sel;","static int dk_sel, chosen_stock, reprint_roll=-1;\n#define ASK_STOCK 20")
    s=replace(s,"    if (dk_ask == ASK_DEVELOP)\n",'''    if (!dk_ask && k==SONY_RECIPE && r && !r->in_camera && r->shot>0){
        dk_ask=ASK_STOCK; chosen_stock=r->film; ui_damage_all(); return;
    }
    if(dk_ask==ASK_STOCK){
        k=sony_value_key(k);
        if(k==FK_LEFT)chosen_stock=(chosen_stock+fos_nfilms-1)%fos_nfilms;
        else if(k==FK_RIGHT)chosen_stock=(chosen_stock+1)%fos_nfilms;
        else if(k==FK_MENU)dk_ask=DEL_NONE;
        else if(k==FK_SET){
            dk_ask=DEL_NONE; dark_queue_clear(); reprint_roll=r->number;
            dark_queue_add(r->number); ui_go(SCR_DEVELOP,0,GO_FADE);
        }
        ui_damage_all();return;
    }
    if (dk_ask == ASK_DEVELOP)
''')
    s=replace(s,"    if (dk_said == ASK_DEVELOP)",'''    if(dk_said==ASK_STOCK){
        char choice[96];
        snprintf(choice,sizeof(choice),sony_value_button()<0?"<  %s  >":"%s",fos_films[chosen_stock].name);
        ui_sheet(dk_sheet.x,"Choose reprint film",choice,"Develop","Cancel");return;
    }
    if (dk_said == ASK_DEVELOP)''')
    s=replace(s,"void dark_queue_clear() { nqueue = 0; }","void dark_queue_clear() { nqueue = 0; reprint_roll=-1; }")
    s=replace(s,"    if (pv_state != PV_SHOW) return;", """    if (pv_state != PV_SHOW) return;
    if(k==31){
        if(!pv_have)return;
        k=pv_mode?FK_WHEEL_R:FK_SET;
    }else if(k==32){
        if(!pv_mode)return;
        k=pv_zlevel?FK_WHEEL_L:FK_SET;
    }
    /* W/T uses the original print zoom state. */
""")
    s=replace(s,"    if (!fos_zoom_open(path, &pv_zf)) return;", """    if (!fos_zoom_open(path, &pv_zf)){
        /* Virtual 4x coordinates reuse the original pan and viewport bounds. */
        if(pv_print.x0>=0 && pv_print.w>0 && pv_print.w<=FOS_W-pv_print.x0){
            pv_zf.w=pv_print.w*4;pv_zf.h=FOS_H*4;
            pv_zsteps[0]=2;pv_zsteps[1]=1;pv_znsteps=2;
        }
        return;
    }""")
    s=replace(s,"        zoomed = fos_zoom_read(", """        if(!pv_zf.f){
            uint8_t *out=cv->px+((FOS_H-vh)/2)*cv->pitch+(FOS_W-vw)/2;
            for(int y=0;y<vh;y++,out+=cv->pitch){
                const uint8_t *line=pv_print.px+((fy+y*step)/4)*FOS_W+pv_print.x0;
                for(int x=0;x<vw;x++)out[x]=line[(fx+x*step)/4];
            }
            zoomed=1;
        }else zoomed = fos_zoom_read(""")
    s=s.replace('"ARROWS MOVE   SET OUT"','"W/T ZOOM   ARROWS MOVE"').replace('"SET OPEN   WHEEL ROLLS"','"T OPEN   OK OPEN"').replace('"WHEEL ZOOM   SET SHEET"','"W/T ZOOM   OK SHEET"')
    s=replace(s,"            ui_go(SCR_HOME, HOME_DARK, GO_POP);", "            if(ui_from()==SCR_NONE)ui_leave();\n            else ui_go(SCR_HOME, HOME_DARK, GO_POP);")
    s=replace(s,"cur_film = ri >= 0 ? rolls[ri].film : 0;","cur_film = cur_roll==reprint_roll ? chosen_stock : ri >= 0 ? rolls[ri].film : 0;")
    s=replace(s,"if (file_exists(path) &&","if (cur_roll!=reprint_roll && file_exists(path) &&")
    s=replace(s,"if (fos_lab_dcim_dir(dcim_dir, sizeof(dcim_dir), cur_roll, cur_film, first) < 0)",'''if(cur_roll==reprint_roll){
                working_edition=edition_begin(cur_roll,cur_film,dcim_dir,sizeof(dcim_dir));
                if(!working_edition){
                    snprintf(last_error,sizeof(last_error),"Could not create reprint folder");
                    failed_frames+=nframes;done_frames+=nframes;qi++;continue;
                }
            }else if (fos_lab_dcim_dir(dcim_dir, sizeof(dcim_dir), cur_roll, cur_film, first) < 0)''')
    s=s.replace("Its %d frame%s, prints and log. They can't come back.","Remove prints and roll log for %d frame%s. Keep original files.")
    path.write_text(s,encoding="utf8")
    path=CORE/"fos_pages.c"
    s=path.read_text(encoding="utf8").replace('"Canon menu"','"Exit to camera"').replace("Leave and open the camera's own menu (format card, RAW...).","Close Film OS and return to the camera.")
    path.write_text(s,encoding="utf8")
    path=CORE/"fos_ui.c"
    s=path.read_text(encoding="utf8")
    s=replace(s,"int ui_keycap(int x, int base, const char *key)\n{",'''static const char *sony_key_label(const char *key)
{
    if(!strcmp(key,"SET"))return "OK";
    if(!strcmp(key,"INFO"))return "?";
    return key;
}
int ui_keycap(int x, int base, const char *key)
{
    key=sony_key_label(key);''')
    s=replace(s,"static int keycap_w(const char *key)\n{",'''static int keycap_w(const char *key)
{
    key=sony_key_label(key);''')
    s=replace(s,"        if (moving || in_tr)\n", "        if (!in_tr) {extern void sony_trace_screen(int);sony_trace_screen(screen);}\n        if (moving || in_tr)\n")
    path.write_text(s,encoding="utf8")
    path=CORE/"fos_shelf.c"
    s=path.read_text(encoding="utf8").replace("SET LOAD   PLAY BACK","OK LOAD   MENU BACK")
    s=replace(s,'FOS_KEY_INFO, "Exposures"','FOS_KEY_INFO, "Frames"')
    path.write_text(s,encoding="utf8")
    path=CORE/"fos_hud.c"
    s=path.read_text(encoding="utf8").replace('FOS_KEY_TRASH "  Home     PLAY  Prints"','"OK  Home     PLAY  Prints"')
    path.write_text(s,encoding="utf8")
    from navigation import adapt_controls
    adapt_controls(CORE,replace)
    from reprints import adapt_reprints
    adapt_reprints(CORE,replace)
    path=CORE/"fos_dev.h"
    s=path.read_text(encoding="utf8")
    s=replace(s,"#define FOS_ZOOM_HEAD   16","#define FOS_ZOOM_HEAD   16\n#define FOS_ZOOM_BAND   8")
    s=replace(s,"rows: room for oh * step rows of the file,\n * read in one go.",
              "rows: scratch space for min(oh, FOS_ZOOM_BAND) * step source rows.")
    path.write_text(s,encoding="utf8")
    path=CORE/"fos_print.c"
    s=path.read_text(encoding="utf8")
    s=replace(s,"    if (fos_port_read(z->f, rows, nrows * z->w) != nrows * z->w) return 0;\n","")
    s=replace(s,"        const uint8_t *s = rows + (ry < nrows ? ry : nrows - 1) * z->w + x;",
              """        int band_row = j % FOS_ZOOM_BAND;
        if (band_row == 0)
        {
            int count = nrows - ry;
            if (count > FOS_ZOOM_BAND * step) count = FOS_ZOOM_BAND * step;
            int bytes = count * z->w;
            if (fos_port_read(z->f, rows, bytes) != bytes) return 0;
        }
        const uint8_t *s = rows + band_row * step * z->w + x;""")
    path.write_text(s,encoding="utf8")
    path=CORE/"fos_jpeg.c"
    s=path.read_text(encoding="utf8")
    s=replace(s,'{ 0x010F, 2, "Canon" }, { 0x0110, 2, fos_port_model() }',
              '{ 0x010F, 2, "SONY" }, { 0x0110, 2, "ILCE-5100" }')
    s=replace(s,'memcpy(date + 16, ":00", 4);',
              'memcpy(date + 16, strlen(m->when)==19 ? m->when+16 : ":00", 4);')
    path.write_text(s,encoding="utf8")
    assert hashlib.file_digest(RELEASE.open("rb"),"sha256").hexdigest()=="e8a3cb6e67fdd339cdedfd052b01988a48cb6b3e34f5b022b031e72e96796c1c"
    with zipfile.ZipFile(RELEASE) as z:
        for n in z.namelist():
            rel=n.upper()
            if (rel.startswith(("ML/DATA/FOS","ML/DARKROOM/LOOK","ML/SAMPLES/F")) and rel.endswith((".BIN",".LUT",".BMP"))) or ("LICENSE" in rel and "/" not in rel):
                dest=OUT/"assets"/rel
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(z.read(n))
    from fonts import apply_to
    apply_to(OUT/"assets/ML/DATA/FOSFONT.BIN")
if __name__=="__main__":prepare()

