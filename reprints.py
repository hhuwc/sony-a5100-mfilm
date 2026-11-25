"""Route the original darkroom and print viewer to the same Sony reprint edition."""


def adapt_reprints(core, replace):
    path = core / "fos_dark.c"
    s = path.read_text(encoding="utf8")

    def edit(old, new):
        nonlocal s
        s = replace(s, old, new)

    edit('#include "fos_dev.h"', '#include "fos_dev.h"\n#include "editions.h"')
    edit("    uint8_t marked[MAX_ROLLS];", "    uint8_t marked[MAX_ROLLS];\n    int last_edition[MAX_ROLLS];")
    edit("nrolls = dm ? fos_lab_scan(rolls, MAX_ROLLS) : 0;",
         """nrolls = dm ? fos_lab_scan(rolls, MAX_ROLLS) : 0;
    for(int i=0;i<nrolls;i++)dm->last_edition[i]=edition_find(rolls[i].number,0,1);""")
    edit("return r->sheet || r->developed > 0;", "return r->sheet || r->developed > 0 || dm->last_edition[r-rolls];")
    edit("static int cur_roll, cur_film, cur_frame;", """static int cur_roll, cur_film, cur_frame;
static int working_edition, completed_edition;
static void work_file(char *buf,int capacity,int frame,int zoom){
    if(working_edition)edition_file(buf,capacity,cur_roll,working_edition,1,frame,zoom?"ZOM":"BMP");
    else if(zoom)fos_lab_zoom_path(buf,capacity,cur_roll,frame);
    else fos_lab_print_path(buf,capacity,cur_roll,frame);
}""")
    edit("    fos_lab_prepare(cur_roll);", "    if(cur_roll!=reprint_roll)fos_lab_prepare(cur_roll);")
    edit("cur_gone = ri >= 0", "cur_gone = cur_roll!=reprint_roll && ri >= 0")
    edit("    jpeg_frames = 0;", "    completed_edition=working_edition=0;\n    jpeg_frames = 0;")
    edit("    int took = ui_now - frame_t0;", """    int took = ui_now - frame_t0;
    int incomplete=0;
    if(ok && working_edition){
        dv_made=fos_dev_made(dev,&dv_w,&dv_h);
        incomplete=!edition_frame_complete(cur_roll,working_edition,cur_frame,dv_made,dv_w,dv_h);
        if(incomplete)ok=0;
    }""")
    edit("const char *why = fos_dev_error(dev)", 'const char *why = incomplete ? "Incomplete reprint files" : fos_dev_error(dev)')
    edit("total_frames += rolls[ri].shot - rolls[ri].developed;",
         "total_frames += rolls[ri].shot - (queue[i]==reprint_roll ? 0 : rolls[ri].developed);")
    for frame in ("f->no", "0", "cur_frame"):
        edit(f"fos_lab_print_path(path, sizeof(path), cur_roll, {frame});", f"work_file(path,sizeof(path),{frame},0);")
    edit("fos_lab_print_path(dm->paths[i], sizeof(dm->paths[i]), cur_roll, i + 1);",
         "work_file(dm->paths[i],sizeof(dm->paths[i]),i+1,0);")
    edit("fos_lab_zoom_path(zoom, sizeof(zoom), cur_roll, f->no);", "work_file(zoom,sizeof(zoom),f->no,1);")
    edit("            if (dcim_dir[0])", """            if(working_edition)
                edition_file(jpeg,sizeof(jpeg),cur_roll,working_edition,1,f->no,"JPG");
            else if (dcim_dir[0])""")
    edit('        if (!fos_dev_sheet(path, cur_film, pp, nframes)) fos_port_log("darkroom: can\'t write the contact sheet");',
         """        int sheet_ok=nframes>0 && fos_dev_sheet(path,cur_film,pp,nframes);
        if(!sheet_ok)fos_port_log("darkroom: can't write the contact sheet");
        if(working_edition){
            if(!failed_frames && sheet_ok && edition_publish(cur_roll,working_edition))
                completed_edition=working_edition;
            else{
                if(!failed_frames)snprintf(last_error,sizeof(last_error),"Could not save reprint set");
                failed_frames=done_frames;
                edition_discard(cur_roll,working_edition);
            }
            working_edition=0;
        }""")
    edit("void develop_leave()\n{\n    if (dev) { fos_dev_free(dev); dev = 0; }",
         """void develop_leave()
{
    if(dev){fos_dev_free(dev);dev=0;}
    if(working_edition){edition_discard(cur_roll,working_edition);working_edition=0;}""")
    edit("if (finished) ui_go(SCR_PRINTS, nqueue ? queue[0] : 0, GO_FADE);",
         """if (finished){
                if(reprint_roll>=0 && !completed_edition)ui_go(SCR_DARK,reprint_roll,GO_FADE);
                else ui_go(SCR_PRINTS,nqueue?queue[0]:0,GO_FADE);
            }""")
    edit("static int pv_alone;", """static int pv_edition;
static void choose_edition(int roll_index){
    const struct fos_lab_roll *r=&rolls[roll_index];
    pv_edition=r->sheet || r->developed ? 0 : dm->last_edition[roll_index];
}
static int pv_alone;""")
    edit("    pv_roll = i;","""    pv_roll=i;
    pv_edition=0;
    if(i>=0){
        choose_edition(i);
        if(ui_from()==SCR_DEVELOP && rolls[i].number==reprint_roll && completed_edition)
            pv_edition=completed_edition;
    }""")
    edit("                    pv_roll = to;", "                    pv_roll=to; choose_edition(to);")
    edit("    fos_lab_zoom_path(path, sizeof(path), rolls[pv_roll].number, pv_cur);",
         """    if(pv_edition)edition_file(path,sizeof(path),rolls[pv_roll].number,pv_edition,0,pv_cur,"ZOM");
    else fos_lab_zoom_path(path,sizeof(path),rolls[pv_roll].number,pv_cur);""")
    edit("    fos_lab_print_path(path, sizeof(path), r->number, pv_mode ? pv_cur : 0);",
         """    if(pv_edition)edition_file(path,sizeof(path),r->number,pv_edition,0,pv_mode?pv_cur:0,"BMP");
    else fos_lab_print_path(path,sizeof(path),r->number,pv_mode?pv_cur:0);""")
    edit("    if (pv_state != PV_SHOW) return;", """    if (pv_state != PV_SHOW) return;
    if(k==SONY_EDITION && !pv_mode){
        const struct fos_lab_roll *r=&rolls[pv_roll];
        int next=edition_find(r->number,pv_edition,0);
        if(!next && !r->sheet && !r->developed)next=edition_find(r->number,0,0);
        pv_edition=next;pv_info=1;pv_info_t=0;pv_go(NEXT_LOAD);return;
    }""")
    edit('snprintf(b, sizeof(b), "ROLL %03d", r->number);',
         '''if(pv_edition)snprintf(b,sizeof(b),"R%03d / V%d",r->number,pv_edition/1000);
        else snprintf(b,sizeof(b),"ROLL %03d",r->number);''')
    edit('fos_films[r->film].name, pv_cur, pv_frames);',
         'fos_films[pv_have && pv_print.film>=0 && pv_print.film<fos_nfilms ? pv_print.film : r->film].name, pv_cur, pv_frames);')
    edit('snprintf(c, sizeof(c), "%s%s%s", m->when, m->fstop[0] ? "  f/" : "", m->fstop);',
         '''const char *when=pv_mode && pv_have && pv_print.when[0] ? pv_print.when : m->when;
            const char *aperture=pv_mode && pv_have && pv_print.fstop[0] ? pv_print.fstop : m->fstop;
            snprintf(c,sizeof(c),"%.16s%s%s",when,aperture[0] ? "  f/" : "",aperture);''')
    path.write_text(s, encoding="utf8")

    lab = core / "fos_lab.c"
    s = lab.read_text(encoding="utf8")
    edit('#include "fos_dev.h"', '#include "fos_dev.h"\n#include "editions.h"')
    edit("    int failed = 0, dirs = 0;", "    int failed=edition_delete_roll(roll), dirs=0;")
    lab.write_text(s, encoding="utf8")
    adapt_master_prints(core,replace)


def adapt_master_prints(core,replace):
    header=core/"fos_dev.h"
    s=header.read_text(encoding="utf8")
    s=replace(s,"    int jpegs;", """    char photo_names[FOS_MAX_FRAMES][9];
    unsigned char valid_bitmap[FOS_MAX_FRAMES];
    int complete;
    int jpegs;""")
    s=replace(s,"int  fos_lab_scan(", "int fos_lab_highest_roll(void);\nint  fos_lab_scan(")
    header.write_text(s,encoding="utf8")

    path=core/"fos_lab.c"
    s=path.read_text(encoding="utf8")
    s=replace(s,'#include "editions.h"', '#include "editions.h"\n#include "master_prints.h"')
    s=replace(s,"static void scan_header(", """static void remember_highest(void *ctx,const char *card,const char *folder,const char *name,int number)
{
    int *highest=ctx;
    if(number>*highest)*highest=number;
}
int fos_lab_highest_roll(void)
{
    int highest=0;
    each_log(remember_highest,&highest);
    return highest;
}
static void scan_header(""")
    s=replace(s,"    if (no > r->shot) r->shot = no;", """    if(no<1 || no>FOS_MAX_FRAMES)return;
    fos_copy(r->photo_names[no-1],sizeof(r->photo_names[0]),file,8);
    if (no > r->shot) r->shot = no;""")
    begin=s.index("static int print_entry(")
    end=s.index("/* paths found",begin)
    s=s[:begin]+'''struct print_scan { struct fos_lab_roll *roll; const char *dir; };
static int print_entry(void *ctx,const char *name,int is_dir)
{
    if(is_dir)return 1;
    struct print_scan *s=ctx;
    struct fos_lab_roll *r=s->roll;
    char path[128];
    if(snprintf(path,sizeof(path),"%s/%s",s->dir,name)>=(int)sizeof(path))return 1;
    if(!strcmp(name,"SHEET.BMP")){r->sheet=master_bitmap_valid(path,0);return 1;}
    if(strlen(name)!=7 || name[0]!='F' || name[1]<'0' || name[1]>'9' || name[2]<'0' || name[2]>'9')return 1;
    int frame=10*(name[1]-'0')+name[2]-'0';
    if(frame<1 || frame>r->shot)return 1;
    if(!strcmp(name+3,".BMP") && master_bitmap_valid(path,frame)){
        r->valid_bitmap[frame-1]=1;
        r->developed++;
    }
    return 1;
}
''' + s[end:]
    s=s.replace("fos_port_list(dir, print_entry, r);","fos_port_list(dir,print_entry,&(struct print_scan){r,dir});")
    s=replace(s,"static int jpeg_folder(void *ctx",'''static void count_complete_frames(struct fos_lab_roll *roll,const char *dir)
{
    for(int i=0;i<roll->shot;i++){
        char path[160];int w,h;
        if(!roll->valid_bitmap[i] || !roll->photo_names[i][0])continue;
        if(snprintf(path,sizeof(path),"%s/%s.JPG",dir,roll->photo_names[i])>=(int)sizeof(path) ||
           !master_jpeg_dimensions(path,&w,&h))continue;
        if(w>FOS_PRINT_W || h>FOS_PRINT_H){
            fos_lab_zoom_path(path,sizeof(path),roll->number,i+1);
            if(!master_zoom_valid(path,w,h))continue;
        }
        roll->complete++;
        roll->photo_names[i][0]=0;
    }
}
static int jpeg_folder(void *ctx''')
    s=replace(s,"if (s->rolls[i].number == s->roll) s->rolls[i].jpegs += s->count;",
              """if (s->rolls[i].number == s->roll && s->count){
            s->rolls[i].jpegs+=s->count;
            count_complete_frames(&s->rolls[i],dir);
        }""")
    s=replace(s,'#define SWEEP_MAX (2 * FOS_MAX_FRAMES + 2)', '#define SWEEP_MAX (2 * FOS_MAX_FRAMES + 6)')
    s=replace(s,'!strcmp(name + len - 4, ".ZOM")))', '''!strcmp(name + len - 4, ".ZOM") ||
            (len==12 && !strncmp(name,"DSC",3) && !strcmp(name+8,".JPT")) ||
            (len==7 && name[0]=='F' && name[1]>='0' && name[1]<='9' && name[2]>='0' && name[2]<='9' &&
             (!strcmp(name+3,".BMT") || !strcmp(name+3,".ZMT"))) || !strcmp(name,"SHEET.BMT")))''')
    path.write_text(s,encoding="utf8")

    path=core/"fos_dark.c"
    s=path.read_text(encoding="utf8")
    def edit(old,new):
        nonlocal s
        s=replace(s,old,new)
    edit('#include "editions.h"','#include "editions.h"\n#include "master_prints.h"')
    edit("static int working_edition, completed_edition;", """static int working_edition, completed_edition;
static struct master_work master;
static int roll_failures_at_start,sheet_errors,sheet_invalidated;
""")
    edit("static int is_developed(const struct fos_lab_roll *r) { return r->sheet && r->developed >= r->shot && r->jpegs >= r->developed; }",
         "static int is_developed(const struct fos_lab_roll *r){return r->sheet && r->complete>=r->shot;}")
    s=s.replace("(rolls[i].jpegs < rolls[i].developed ? rolls[i].jpegs : rolls[i].developed)","rolls[i].complete")
    edit("0 : rolls[ri].developed", "0 : rolls[ri].complete")
    start=s.index("static int file_exists(")
    s=s[:start]+s[s.index("/* the print's picture",start):]
    edit("total_frames = done_frames = failed_frames = rolls_done = 0;","sheet_errors=0;\n    total_frames = done_frames = failed_frames = rolls_done = 0;")
    edit("            cur_roll = queue[qi];","            roll_failures_at_start=failed_frames;sheet_invalidated=0;\n            cur_roll = queue[qi];")
    edit("            if (cur_roll!=reprint_roll && file_exists(path) && (!jpeg[0] || f->missing || file_exists(jpeg))) continue;",'''            char zoom[128];
            work_file(zoom,sizeof(zoom),f->no,1);
            if(!working_edition){
                if(!master_prepare(&master,path,jpeg,zoom)){
                    snprintf(last_error,sizeof(last_error),"No output folder for frame %d",f->no);
                    failed_frames++;done_frames++;continue;
                }
                if(master_frame_valid(&master.final,f->no)){memset(&master,0,sizeof(master));continue;}
            }''')
    edit("            dev = fos_dev_start(f->cr2, path, cur_film, f->no, f->when, f->fstop);",
         """            if(!working_edition && !sheet_invalidated){
                char sheet[128];
                work_file(sheet,sizeof(sheet),0,0);
                if(fos_port_remove(sheet)<0){
                    snprintf(last_error,sizeof(last_error),"Could not replace the old contact sheet");
                    failed_frames++;done_frames++;continue;
                }
                sheet_invalidated=1;
            }
            if(!working_edition && !master_clear_temp(&master)){
                snprintf(last_error,sizeof(last_error),"Could not clear pending output for frame %d",f->no);
                failed_frames++;done_frames++;continue;
            }
            dev=fos_dev_start(f->cr2,working_edition?path:master.temp.bmp,cur_film,f->no,f->when,f->fstop);""")
    edit("fos_dev_jpeg(dev, jpeg);","fos_dev_jpeg(dev,working_edition?jpeg:master.temp.jpeg);")
    edit("                char zoom[64];\n                work_file(zoom,sizeof(zoom),f->no,1);\n                fos_dev_big(dev, dv_size, zoom);",
         "                fos_dev_big(dev,dv_size,working_edition?zoom:master.temp.zoom);")
    edit("    if(ok && working_edition){","    if(ok){")
    edit("incomplete=!edition_frame_complete(cur_roll,working_edition,cur_frame,dv_made,dv_w,dv_h);",
         """incomplete=working_edition ? !edition_frame_complete(cur_roll,working_edition,cur_frame,dv_made,dv_w,dv_h)
                                  : !master_publish(&master,cur_frame,dv_w,dv_h);""")
    edit('incomplete ? "Incomplete reprint files"', 'incomplete ? (working_edition?"Incomplete reprint files":"Incomplete print files")')
    edit("    fos_dev_free(dev);\n    dev = 0;", "    fos_dev_free(dev);\n    dev = 0;\n    master_discard(&master);")
    edit("    if(working_edition){edition_discard(cur_roll,working_edition);working_edition=0;}",
         "    master_discard(&master);\n    if(working_edition){edition_discard(cur_roll,working_edition);working_edition=0;}")
    edit("        int sheet_ok=nframes>0 && fos_dev_sheet(path,cur_film,pp,nframes);",
         """        int sheet_ok=nframes>0 && failed_frames==roll_failures_at_start &&
            (working_edition ? fos_dev_sheet(path,cur_film,pp,nframes) : master_sheet(path,cur_film,pp,nframes));
        if(!sheet_ok && failed_frames==roll_failures_at_start){
            sheet_errors++;snprintf(last_error,sizeof(last_error),"Could not save the contact sheet");
        }""")
    edit('104, "DONE", SL_ACCENT','104, failed_frames || sheet_errors ? "INCOMPLETE" : "DONE", SL_ACCENT')
    edit("        if (failed_frames)\n", "        if (failed_frames || sheet_errors)\n")
    edit('snprintf(b, sizeof(b), "%d print%s", done_frames', 'if(!done_frames && !sheet_errors)snprintf(b,sizeof(b),"Contact sheet saved");\n        else snprintf(b, sizeof(b), "%d print%s", done_frames')
    edit('snprintf(b, sizeof(b), "%d frame%s could not be developed",', 'if(!failed_frames)snprintf(b,sizeof(b),"Contact sheet pending");\n            else snprintf(b, sizeof(b), "%d frame%s could not be developed",')
    path.write_text(s,encoding="utf8")

    path=core/"fos_dev.c"
    s=path.read_text(encoding="utf8")
    edit('    struct fos_dev *d = fos_dev_start("", sheet, film, 0, "", "");',
         '    if(frames<1 || frames>6*(FOS_PRINT_H/FOS_THUMB_H))return 0;\n    struct fos_dev *d = fos_dev_start("", sheet, film, 0, "", "");')
    edit("                    fos_port_log(msg);\n                }\n                d->stage = ST_QUANT;",
         "                    fos_port_log(msg);\n                    return fail(d,\"can't write JPEG\");\n                }\n                d->stage = ST_QUANT;")
    edit("                    big_end(d);\n                    d->stage = ST_WRITE;",
         "                    big_end(d);\n                    if(d->bfail)return fail(d,\"can't write JPEG\");\n                    d->stage = ST_WRITE;")
    edit("if (!prints[i] || !fos_print_thumb(prints[i], thumb)) continue;", """if(!prints[i] || !fos_print_thumb(prints[i],thumb)){
            fos_port_free(thumb);fos_dev_free(d);return 0;
        }""")
    path.write_text(s,encoding="utf8")
