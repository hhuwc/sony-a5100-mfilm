/* The footer and confirmation sheets use the same rule as the body of a
   menu: arrows move the highlight, OK activates it. Commands are copied
   because the available actions depend on the current roll. */
static struct sony_action nav_items[7];
static int nav_count,nav_at,sheet_at,photo_bar;
static int value_buttons;

void sony_focus_bar(const struct sony_action *actions,int count){
    if(count<=0 || count>7)return;
    memcpy(nav_items,actions,count*sizeof(*actions));nav_count=count;nav_at=photo_bar=0;
    ui_clobbered=1;ui_damage_all();
}
void sony_focus_photo_bar(const struct sony_action *actions,int count){
    sony_focus_bar(actions,count);photo_bar=1;
}
static int sony_bar_key(int k){
    if(!nav_count)return k;
    if(k==FK_LEFT || k==FK_RIGHT){
        nav_at=fos_clamp(nav_at+(k==FK_RIGHT?1:-1),0,nav_count-1);
        /* The opaque footer covers these rows on every draw. */
        ui_damage(HINTS_Y,FOS_H);
        return FK_NONE;
    }
    if(k==FK_DOWN)return FK_NONE;
    if(k==FK_SET)k=nav_items[nav_at].command;
    else if(k==FK_UP || k==FK_MENU)k=FK_NONE;
    nav_count=0;
    ui_clobbered=1;ui_damage_all();return k;
}
static void sony_draw_bar(void){
    if(!nav_count)return;
    if(photo_bar){
        for(int y=HINTS_Y;y<FOS_H;y++)memset(cv->px+y*cv->pitch,PX_PANEL,FOS_W);
        for(int i=0;i<nav_count;i++)
            ui_photo_text(&fos_font_sm,(2*i+1)*FOS_W/(2*nav_count),HINTS_Y+24,nav_items[i].label,i==nav_at,1);
        return;
    }
    fos_fill(cv,0,HINTS_Y,FOS_W,FOS_H-HINTS_Y,FC(RAMP_GRAY,16));
    for(int i=0;i<nav_count;i++){
        int x=(2*i+1)*FOS_W/(2*nav_count);
        fos_text_c(cv,&fos_font_sm,x,HINTS_Y+24,nav_items[i].label,
                   i==nav_at?C_ACCENT:C_TEXT2,OPAQUE,0);
    }
}
int sony_dialog_key(int k,int has_alternate){
    int last=has_alternate?2:1;
    if(k==FK_LEFT || k==FK_RIGHT){
        sheet_at=fos_clamp(sheet_at+(k==FK_RIGHT?1:-1),0,last);
        ui_clobbered=1;ui_damage_all();return FK_NONE;
    }
    if(k==FK_UP || k==FK_DOWN || k==FK_INFO)return FK_NONE;
    if(k==FK_SET)k=sheet_at==0?FK_SET:sheet_at==last?FK_MENU:FK_INFO;
    if(k==FK_MENU || k==FK_SET)sheet_at=0;
    return k;
}
void sony_focus_keep(void){sheet_at=1;}

/* Value editors start on the value. Down selects the buttons below it. */
int sony_value_key(int key){
    if(key==FK_UP || key==FK_DOWN){
        value_buttons=key==FK_DOWN;
        if(!value_buttons)sheet_at=0;
        return FK_NONE;
    }
    if(value_buttons)key=sony_dialog_key(key,0);
    if(key==FK_SET || key==FK_MENU)value_buttons=sheet_at=0;
    return key;
}
int sony_value_button(void){return value_buttons ? sheet_at : -1;}
