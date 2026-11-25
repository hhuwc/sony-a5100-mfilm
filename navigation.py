"""Adapt Sony five-way navigation in the staged upstream screens."""

def adapt_controls(core, replace):
    def read(name):
        return (core/name).read_text(encoding="utf8")
    def write(name,s):
        (core/name).write_text(s,encoding="utf8")
    s=read("fos_ui.h")
    write("fos_ui.h",s.replace("#endif", '#include "navigation.h"\n#endif',1) if s.count("#endif")==1 else '#include "navigation.h"\n'+s)
    s=read("fos_ui.c")
    s=replace(s,"h[i].label, C_TEXT3, OPAQUE, 0) + gap","h[i].label, C_TEXT2, OPAQUE, 0) + gap")
    s=replace(s,"void ui_sheet3(float s,", '#include "navigation.inc"\n\nvoid ui_sheet3(float s,')
    s=replace(s,'x += ui_keycap(x, base, "SET") + 8;\n    x += fos_text(cv, &fos_font_md, x, base, yes, C_ACCENT',
                'if(sheet_at==0)ui_keycap(x, base, "SET");\n    x += keycap_w("SET") + 8;\n    x += fos_text(cv, &fos_font_md, x, base, yes, sheet_at==0?C_ACCENT:C_TEXT2')
    s=replace(s,'x += ui_keycap(x, base, FOS_KEY_INFO) + 8;\n        x += fos_text(cv, &fos_font_md, x, base, alt, C_TEXT',
                'if(sheet_at==1)ui_keycap(x, base, "SET");\n        x += keycap_w("SET") + 8;\n        x += fos_text(cv, &fos_font_md, x, base, alt, sheet_at==1?C_ACCENT:C_TEXT2')
    s=replace(s,'x += ui_keycap(x, base, "MENU") + 8;\n    fos_text(cv, &fos_font_md, x, base, no, C_TEXT2',
                'int selected=sheet_at==(alt?2:1);\n    ui_keycap(x, base, selected?"SET":"MENU");\n    x += keycap_w("MENU") + 8;\n    fos_text(cv, &fos_font_md, x, base, no, selected?C_ACCENT:C_TEXT2')
    for signature in ("void ui_go(int to, int arg, int how)","void fos_ui_run(int open)"):
        s=replace(s,signature+"\n{",signature+"\n{\n    nav_count=sheet_at=value_buttons=0;")
    s=replace(s,"static void screen_key(int k)\n{","""static void screen_key(int k)
{
    if((k==SONY_TELE || k==SONY_WIDE) && screen!=SCR_PRINTS)return;
    if(screen==SCR_DEVELOP)develop_note_input();
    k=sony_bar_key(k);
    if(k==FK_NONE || (screen==SCR_BOOT && k>=FK_LEFT && k<=FK_DOWN))return;""")
    s=replace(s,"        case SCR_PRINTS: prints_draw(); break;\n    }",
                "        case SCR_PRINTS: prints_draw(); break;\n    }\n    if(screen==SCR_PAGE)sony_draw_setting();\n    sony_draw_bar();")
    s=replace(s,"    if (stat.frames || stat.open_ms) fos_port_stat(&stat);","""    extern void sony_remember_menu(int page);
    sony_remember_menu(screen==SCR_SHELF?FOS_OPEN_SHELF:screen==SCR_PRINTS?FOS_OPEN_PRINTS:
                       screen==SCR_DARK || screen==SCR_DEVELOP?FOS_OPEN_DARKROOM:FOS_OPEN_HOME);
    if (stat.frames || stat.open_ms) fos_port_stat(&stat);""")
    write("fos_ui.c",s)

    s=read("fos_shelf.c")
    s=replace(s,"static int exp_sel;","static int exp_sel, sony_tabs;")
    s=replace(s,"void shelf_enter(int arg)\n{","void shelf_enter(int arg)\n{\n    sony_tabs=0;")
    s=replace(s,"    if (loading) return;\n    /* the top dial:", """    if (loading) return;
    if(asking){k=sony_dialog_key(k,0);if(!k)return;}
    else if(sm_state!=SM_OFF && k==FK_DOWN){
        const struct sony_action a[]={{"Load",FK_SET},{"Info",FK_INFO},{"Back",FK_MENU}};
        sony_focus_photo_bar(a,3);return;
    }else if(sm_state==SM_OFF){
        if(sony_tabs){
            if(k==FK_LEFT || k==FK_RIGHT)k=k==FK_LEFT?FK_DIAL_L:FK_DIAL_R;
            else if(k==FK_DOWN || k==FK_SET){sony_tabs=0;ui_clobbered=1;ui_damage_all();return;}
            else if(k==FK_UP)return;
        }else if(k==FK_UP){sony_tabs=1;ui_clobbered=1;ui_damage_all();return;}
        else if(k==FK_DOWN){
            const struct sony_action a[]={{"Frames",FK_INFO},{"Sample",FK_PLAY},{"Back",FK_MENU}};
            if(has_samples)sony_focus_bar(a,3);
            else{const struct sony_action b[]={{"Frames",FK_INFO},{"Back",FK_MENU}};sony_focus_bar(b,2);}
            return;
        }
    }
    /* the top dial:""")
    s=replace(s,"else if (k == FK_MENU || k == FK_LEFT || k == FK_RIGHT || k == FK_WHEEL_L || k == FK_WHEEL_R)","else if (k == FK_MENU)")
    s=replace(s,"    sheet_drawn = sheet.x > 0;","""    sheet_drawn = sheet.x > 0;
    if(sony_tabs && !asking)fos_rrect_line(cv,100,33,520,34,5,1,C_ACCENT,OPAQUE);""")
    s=s.replace('"^v", "Shelf"', '"^v", "Focus"')
    s=replace(s,'roll_in_progress() ? (ui_realistic() ? "Rewind & load" : "Finish & load") : "Load"','"Load"')
    s=replace(s,"            ui_go(SCR_HOME, 0, GO_POP);\n            break;\n        case FK_HOME:",'            ui_toast("No sample for this film");\n            break;\n        case FK_HOME:')
    write("fos_shelf.c",s)

    s=read("fos_pages.c")
    s=replace(s,'{ "PLAY shows prints only", IT_TOGGLE, FS_PLAYLOCK, 0, 0, "Canon\'s playback would show frames the darkroom hasn\'t developed." }',
                '{ "Playback", IT_INFO, -4, 0, 0, "Press PLAY to view developed prints. On the film shelf, PLAY opens the sample." }')
    s=replace(s,'else if (it->setting == -3)\n            {','else if (it->setting == -4) snprintf(b,sizeof(b),"Film prints");\n            else if (it->setting == -3)\n            {')
    s=replace(s,"Writes ML/FILMROLL.LOG for troubleshooting.","Write FILMOS.LOG and CAMERA.LOG to the MFILM folder on the card.")
    s=replace(s,"How colours are sent to the screen. Canon's way suits the EOS M.","Choose the EOS M display colours or Rec.709 for the Sony screen.")
    s=replace(s,'{ "Canon", "Rec.709" }','{ "EOS M", "Rec.709" }')
    s=replace(s,"After changing picture style, white balance or ISO by hand.","Apply the loaded film's ISO and white balance to the camera again.")
    s=replace(s,"Film settings go in when you return to the camera","Applying film ISO and white balance")
    s=s.replace('"Manual lens", IT_PAGE','"Lens", IT_PAGE').replace('"Manual lens", "Aperture for adapted lenses"','"Lens", "Camera readout and manual aperture"')
    s=replace(s,"The aperture of an adapted lens, which the camera can't read.","Lens information and aperture. Set the aperture here for an adapted manual lens.")
    s=replace(s,"Adapted manual lenses report no aperture: set it here.","Electronic lenses report aperture to the camera. Adapted manual lenses use the entries below.")
    s=replace(s,"The f-stop on the lens ring. Shown in the HUD, logged for the lab.","Camera-reported or manually entered aperture, shown in the finder and frame log.")
    s=replace(s,"Your manual lens' widest f-stop: the ring stops there.","Maximum aperture reported by the camera, or set here for an adapted manual lens.")
    s=replace(s,'fos_port_lens_manual() ? "Manual" : fos_port_lens_name()', 'fos_port_lens_name()')
    s=replace(s,'            if (selected)\n            {\n                fos_tri(cv, rx - w',
              '            if (selected && (it->kind!=IT_FSTOP || fos_port_lens_manual()))\n            {\n                fos_tri(cv, rx - w')
    s=replace(s,'                char ap[8];\n                fos_format_fstop', '                if(v<0){fos_text_r(cv,&fos_font_md,rx,base,"Unavailable",C_TEXT3,OPAQUE,0);break;}\n                char ap[8];\n                fos_format_fstop')
    s=replace(s,'    char ap[8], b[24];\n    fos_format_fstop', '    if(idx<0){preview_caption("Limit unavailable");return;}\n    char ap[8], b[24];\n    fos_format_fstop')
    s=replace(s,'snprintf(b, sizeof(b), "SET ON THE RING");','snprintf(b, sizeof(b), "%s", fos_port_lens_manual()?"SET ON THE RING":"CAMERA APERTURE");')
    s="\n".join(line for line in s.split("\n") if "apkey_choices" not in line)
    s=replace(s,"case FK_SET: case FK_RIGHT:\n            home_open","case FK_SET:\n            home_open")
    s=replace(s,"void home_key(int k)\n{","""void home_key(int k)
{
    if(k==FK_DOWN && home_sel==home_n-1){
        const struct sony_action a[]={{"Settings",FK_INFO},{"Prints",FK_PLAY},{"Back",FK_MENU}};
        sony_focus_bar(a,3);return;
    }""")
    s=replace(s,"static int page, page_sel, page_top;","static int page, page_sel, page_top, editing, candidate;")
    s=replace(s,"void page_enter(int arg)\n{","void page_enter(int arg)\n{\n    editing=0;")
    a=s.index("    struct hint h[]",s.index("static void page_bake()"))
    b=s.index("    fos_rrect(cv,",a)
    s=s[:a]+'''    struct hint hints[]={{"^v","Select"},{"SET","Choose"},{"MENU","Back"}};
    ui_hints(hints,3);
'''+s[b:]
    a=s.index("    /* moving the selection",s.index("void page_key"))
    s=s[:a]+'''    if(editing){
        k=sony_value_key(k);
        int lo=it->kind==IT_LEVEL?-FOS_SCR_STEPS:it->kind==IT_FSTOP && it->setting==FS_FSTOP?fos_port_get(FS_LENS_WIDE):0;
        int hi=it->kind==IT_LEVEL?FOS_SCR_STEPS:it->kind==IT_FSTOP?fos_nfstops-1:it->n-1;
        if(k==FK_LEFT || k==FK_RIGHT)candidate=fos_clamp(candidate+(k==FK_RIGHT?1:-1),lo,hi);
        else if(k==FK_SET){
            pg_set(it->setting,candidate);
            if(it->setting==FS_LENS_WIDE && fos_port_get(FS_FSTOP)<candidate)fos_port_set(FS_FSTOP,candidate);
            editing=0;
        }else if(k==FK_MENU)editing=0;
        page_damage(D_ALL);return;
    }
    if(k==FK_DOWN && page_sel==n-1){
        const struct sony_action a[]={{"Back",FK_MENU}};sony_focus_bar(a,1);return;
    }
'''+s[a:]
    a=s.index("        case FK_LEFT: case FK_RIGHT:",s.index("void page_key"))
    b=s.index("            else if (it->kind == IT_PAGE) ui_go",a)
    s=s[:a]+'''        case FK_SET:
            if(it->kind==IT_TOGGLE)change(it,0);
            else if(it->kind==IT_FSTOP && !fos_port_lens_manual())ui_toast("Reported by camera");
            else if(it->kind==IT_CHOICE || it->kind==IT_LEVEL || it->kind==IT_FSTOP){
                editing=1;candidate=pg_get(it->setting);dirty=D_ALL;
                if(it->kind==IT_CHOICE)candidate=fos_clamp(candidate,0,it->n-1);
            }
'''+s[b:]
    s=replace(s,"void page_draw()","""void sony_draw_setting(void){
    if(!editing)return;
    const struct item *it=&pages[page].items[page_sel];
    char value[72];
    if(it->kind==IT_CHOICE)snprintf(value,sizeof(value),"<   %s   >",it->choices[candidate]);
    else if(it->kind==IT_FSTOP){char f[16];fos_format_fstop(f,sizeof(f),candidate);snprintf(value,sizeof(value),"<   f/%s   >",f);}
    else snprintf(value,sizeof(value),"<   %+d   >",candidate);
    fos_rrect(cv,116,138,488,166,12,FC(RAMP_GRAY,24),OPAQUE);
    fos_text_c(cv,&fos_font_md,360,182,it->label,C_TEXT,OPAQUE,0);
    int button=sony_value_button();
    fos_text_c(cv,&fos_font_lg,360,238,value,button<0?C_ACCENT:C_TEXT,OPAQUE,0);
    fos_text_c(cv,&fos_font_sm,287,282,button==1?"Apply":"OK  Apply",button==0?C_ACCENT:C_TEXT2,OPAQUE,0);
    fos_text_c(cv,&fos_font_sm,432,282,button==1?"OK  Cancel":"MENU  Cancel",button==1?C_ACCENT:C_TEXT2,OPAQUE,0);
}
void page_draw()""")
    s=replace(s,"    if (rewinding) return;\n    if (asking_rewind)","""    if (rewinding) return;
    if(asking_rewind){k=sony_dialog_key(k,1);if(!k)return;}
    else if(k==FK_DOWN){const struct sony_action a[]={{"Back",FK_MENU}};sony_focus_bar(a,1);return;}
    if (asking_rewind)""")
    s=s.replace("case FK_HOME: case FK_PLAY:\n            ui_leave();","case FK_PLAY: ui_go(SCR_PRINTS,0,GO_FADE);break;\n        case FK_HOME:\n            ui_leave();")
    write("fos_pages.c",s)
    adapt_dark(core,replace)


def adapt_dark(core,replace):
    path=core/"fos_dark.c"
    s=path.read_text(encoding="utf8")
    s=replace(s,"void develop_enter(int arg)\n{","""/* Show the key's visual feedback before the next long RAW work slice.
 * With repeating input, always allow work on the following tick. */
enum { DEV_NORMAL, DEV_SHOW_INPUT, DEV_RESUME_WORK };
static int work_turn;
void develop_note_input(void){
    if(work_turn==DEV_NORMAL)work_turn=DEV_SHOW_INPUT;
}
void develop_enter(int arg)
{
    work_turn=DEV_NORMAL;""")
    s=replace(s,"        if (!dev) next_job();","""        if(work_turn==DEV_SHOW_INPUT){
            work_turn=DEV_RESUME_WORK;
            return 1;
        }
        work_turn=DEV_NORMAL;
        if (!dev) next_job();""")
    s=replace(s,"    if (dk_doing) return;","""    if (dk_doing) return;
    if(dk_ask && dk_ask!=ASK_STOCK){
        k=sony_dialog_key(k,dk_ask==ASK_DEVELOP || dk_ask==DEL_WHICH);
        if(!k)return;
    }else if(!dk_ask && (k==FK_RIGHT || (k==FK_DOWN && dk_sel+1>=nrolls))){
        struct sony_action a[6]; int n=0;
        if(r && is_waiting(r))a[n++]=(struct sony_action){marked[dk_sel]?"Unmark":"Mark",FK_SET};
        if(r && has_prints(r))a[n++]=(struct sony_action){"Prints",FK_PLAY};
        if(r && !r->in_camera && r->shot>0)a[n++]=(struct sony_action){"Recipe",SONY_RECIPE};
        if(count_waiting(0))a[n++]=(struct sony_action){"Develop",FK_INFO};
        if(r && !r->in_camera)a[n++]=(struct sony_action){"Delete",SONY_DELETE};
        a[n++]=(struct sony_action){"Back",FK_MENU};
        sony_focus_bar(a,n);return;
    }""")
    s=s.replace('k == FK_INFO || k == FK_RIGHT || k == FK_WHEEL_R','k == FK_INFO')
    s=replace(s,'        else if (k == FK_LEFT || k == FK_WHEEL_L) fos_port_set(FS_SIZE, (cur_size() + FOS_SIZES - 1) % FOS_SIZES);','')
    s=replace(s,"case FK_SET: case FK_RIGHT: case FK_LEFT:","case FK_SET: case SONY_DELETE:")
    s=replace(s,"(k == FK_LEFT || !finished_in_camera(r))","(k == SONY_DELETE || !finished_in_camera(r))")
    s=replace(s,"else if (k == FK_LEFT) dk_ask","else if (k == SONY_DELETE) dk_ask")
    s=replace(s,"dk_ask = k == FK_SET ? DEL_PRINTS : DEL_WHOLE;",
              "{ dk_ask = k == FK_SET ? DEL_PRINTS : DEL_WHOLE; sony_focus_keep(); }")
    s=replace(s,"dk_ask = has_prints(r) || r->jpegs ? DEL_WHICH : DEL_WHOLE;",
              "{ dk_ask = has_prints(r) || r->jpegs ? DEL_WHICH : DEL_WHOLE; if(dk_ask==DEL_WHOLE)sony_focus_keep(); }")
    s=replace(s,'if (r && !r->in_camera) h[n++] = (struct hint) { "<", "Delete" };','h[n++] = (struct hint) { ">", "Actions" };')
    s=s.replace("/* LEFT: Delete roll, never the one in the camera */","/* Delete is an explicit footer command on a finished roll. */")
    s=replace(s,"    /* with the screen dimmed, the first button only brings it back */","""    if(asking_stop){k=sony_dialog_key(k,0);if(!k)return;}
    else if(k>=FK_LEFT && k<=FK_DOWN){
        if(k==FK_DOWN){
            if(dv_dimmed){const struct sony_action a[]={{"Wake",FK_INFO}};sony_focus_bar(a,1);}
            else if(finished){const struct sony_action a[]={{"Prints",FK_PLAY},{"Back",FK_MENU}};sony_focus_bar(a,2);}
            else{const struct sony_action a[]={{"Dim",FK_INFO},{"Stop",FK_MENU}};sony_focus_bar(a,2);}
        }
        return;
    }
    /* A confirmed action or shortcut wakes the dimmed screen. */""")
    s=s.replace('Any button: screen back','OK: screen back')
    s=replace(s,"    int n = pv_frames;","""    if(!pv_zlevel && k==FK_DOWN && (pv_mode || pv_cur+6>pv_frames)){
        if(pv_mode){const struct sony_action a[]={{"Sheet",FK_SET},{"Info",FK_INFO},{"Back",FK_MENU}};sony_focus_photo_bar(a,3);}
        else{
            struct sony_action a[5]={{"Open",FK_SET},{"Prev roll",FK_WHEEL_L},{"Next roll",FK_WHEEL_R}};
            int n=3;
            if(dm->last_edition[pv_roll])a[n++]=(struct sony_action){"Version",SONY_EDITION};
            a[n++]=(struct sony_action){"Back",FK_MENU};
            sony_focus_photo_bar(a,n);
        }
        return;
    }
    int n = pv_frames;""")
    s=replace(s,"    if(k==31){","""    if(pv_mode && (k==FK_WHEEL_R || k==FK_WHEEL_L))return;
    if(k==SONY_TELE){""")
    s=replace(s,"}else if(k==32){","}else if(k==SONY_WIDE){")
    s=replace(s,"    if (pv_alone) ui_leave();\n    else if (ui_from()", """    if (pv_alone) ui_leave();
    else if(ui_from()==SCR_PAGE)ui_go(SCR_PAGE,0,GO_POP);
    else if(ui_from()==SCR_ROLL)ui_go(SCR_ROLL,0,GO_POP);
    else if (ui_from()""")
    s=replace(s,"else if (k == FK_MENU || k == FK_PLAY) { if (pv_alone) ui_leave(); else ui_go(SCR_HOME, HOME_DARK, GO_FADE); }","else if (k == FK_MENU || k == FK_PLAY) pv_back();")
    s=replace(s,"            case FK_SET: case FK_MENU: case FK_PLAY: case FK_HOME: pv_zlevel = 0; break;","""            case FK_MENU: pv_mode=0;pv_go(NEXT_LOAD);return;
            case FK_SET: case FK_PLAY: return;
            case FK_HOME: pv_go(NEXT_BACK);return;""")
    s=replace(s,'    if (pv_state == PV_NONE)\n    {\n        if (k == FK_SET)', '''    if (pv_state == PV_NONE)
    {
        if(k==FK_DOWN){const struct sony_action a[]={{"Darkroom",FK_SET},{"Back",FK_MENU}};sony_focus_bar(a,2);return;}
        if (k == FK_SET)''')
    path.write_text(s,encoding="utf8")
