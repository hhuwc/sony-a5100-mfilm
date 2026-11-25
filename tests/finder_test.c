/* Exercise the same HUD state, palette, fonts and C painter used by the APK. */
#include "finder_hud.h"
#include <assert.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

void *fos_port_alloc(int n){return malloc(n);}
void fos_port_free(void *p){free(p);}
static uint8_t indices[FOS_W*FOS_H];
static uint32_t colors[256];
static struct fos_hud_palette palette;
static int settings[FS_COUNT];
static struct fos_roll active={.loaded=1,.exposures=36,.shot=11};
static struct finder_exposure reading;
static struct fos_hud hud;

static int draw(int half,int manual,int ev,int64_t now,int64_t until){
    int delay=finder_hud(&hud,&active,settings,&reading,half,manual,ev,82,now,until);
    memset(indices,0,sizeof(indices));
    fos_hud_draw(indices,FOS_W,&hud,&palette);
    return delay;
}
static void output(int style){
    char path[40];snprintf(path,sizeof(path),"style%d.rgba",style);
    FILE *f=fopen(path,"wb");assert(f);
    for(size_t i=0;i<sizeof(indices);i++)assert(fwrite(colors+indices[i],4,1,f)==1);
    assert(!fclose(f));
}
int main(int argc,char **argv){
    if(argc!=2)return 2;
    FILE *font=fopen(argv[1],"rb");assert(font);
    fseek(font,0,SEEK_END);int length=ftell(font);rewind(font);
    uint8_t *data=malloc(length);assert(data && fread(data,1,length,font)==(size_t)length);fclose(font);
    fos_gfx_init();assert(fos_fonts_load(data,length));
    finder_palette(&palette,colors);
    settings[FS_HUD]=settings[FS_LEDS]=settings[FS_HUD_BATT]=settings[FS_FOCUS]=1;
    settings[FS_FSTOP]=9;settings[FS_LENS_WIDE]=6;
    reading=(struct finder_exposure){finder_fstop(400),finder_fstop(180),1,125};
    assert(reading.fstop==13 && reading.widest==6 && finder_fstop(450)==14);
    assert(finder_fstop(0)==-1 && finder_fstop(449)==14);
    for(int style=0;style<FOS_HUD_STYLES;style++){
        settings[FS_HUD_STYLE]=style;
        active.need_wind=style==FOS_HUD_CLASSIC;
        draw(1,1,2,400,2900);
        assert(hud.lit && hud.flash && hud.blink && hud.meter && hud.want==15 && hud.frame==12);
        assert(hud.batt==82 && hud.batt_exact && !strcmp(hud.shutter,"125"));
        output(style);
    }
    active.need_wind=0;
    assert(draw(0,0,INT_MIN,2899,2900)==1);
    assert(draw(0,0,INT_MIN,2900,2900)==0 && !hud.flash && !hud.lit && !hud.meter);
    for(size_t i=0;i<sizeof(indices);i++)assert(indices[i]==palette.clear);
    active.need_wind=1;
    assert(draw(0,0,0,3200,2900)==400 && !hud.blink);
    assert(draw(0,0,0,3600,2900)==400 && hud.blink);
    active.need_wind=0;active.shot=36;
    assert(draw(0,0,0,4399,0)==1 && hud.finished);
    active.shot=11;settings[FS_HUD_STYLE]=FOS_HUD_RANGE;
    assert(draw(1,0,-7,4399,0)==1 && hud.meter);
    assert(draw(1,0,-6,4399,0)==0 && !hud.focus_screen);
    assert(draw(0,0,INT_MIN,4399,0)==0 && !hud.meter);
    settings[FS_HUD_STYLE]=FOS_HUD_CLASSIC;
    assert(draw(1,0,-8,4399,0)==1 && hud.want<hud.widest);
    settings[FS_LEDS]=0;settings[FS_HUD_BATT]=0;
    reading=(struct finder_exposure){-1,-1,0,0};
    assert(draw(0,1,INT_MIN,200,0)==0 && hud.lit && !hud.meter && hud.fstop==9 && hud.widest==6);
    assert(hud.batt==-1 && !strcmp(hud.shutter,"--") && hud.focus_screen);
    reading.numerator=1;reading.denominator=2;draw(0,0,0,200,0);
    assert(!strcmp(hud.shutter,"2") && hud.widest==0);
    settings[FS_HUD]=0;assert(draw(0,1,0,250,300)==0);
    puts("PASS four HUD styles, transparent idle Clean, 2500 ms count, 400 ms blink, over-range, missing readings, aperture and battery");
    free(data);return 0;
}
