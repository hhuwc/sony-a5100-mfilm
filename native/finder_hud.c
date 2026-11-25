#include "finder_hud.h"
#include <limits.h>
#include <stdlib.h>
#include <string.h>

int finder_fstop(int hundredths){
    if(hundredths<=0)return -1;
    int best=0;
    for(int i=1;i<fos_nfstops;i++)
        if(abs(fos_fstops[i]-hundredths)<abs(fos_fstops[best]-hundredths))best=i;
    return best;
}

int finder_hud(struct fos_hud *h,const struct fos_roll *active,const int *settings,
               const struct finder_exposure *exposure,int half,int manual,int ev_thirds,
               int battery,int64_t now,int64_t flash_until){
    memset(h,0,sizeof(*h));
    h->fstop=exposure->fstop>=0?exposure->fstop:settings[FS_FSTOP];
    h->widest=exposure->widest>=0?exposure->widest:(manual?settings[FS_LENS_WIDE]:0);
    h->flash=now<flash_until;
    h->lit=half || h->flash || !settings[FS_LEDS];
    h->blink=(int)((now/400)%2);
    h->meter=h->lit && ev_thirds!=INT_MIN;
    if(h->meter)h->want=h->fstop+fos_clamp(ev_thirds,-99,99);
    int n=exposure->numerator,d=exposure->denominator;
    if(n<=0 || d<=0)strcpy(h->shutter,"--");
    else if(n==1 && d>1)snprintf(h->shutter,sizeof(h->shutter),"%d",d);
    else snprintf(h->shutter,sizeof(h->shutter),"%.2g\"",(double)n/d);
    h->frame=active->shot+1;h->exposures=active->exposures;
    h->finished=active->loaded && active->shot>=active->exposures;
    h->need_wind=active->need_wind;h->focus_screen=manual && settings[FS_FOCUS];
    h->film=fos_films[active->film].name;h->iso=fos_films[active->film].box_iso;
    h->style=settings[FS_HUD_STYLE];h->batt=settings[FS_HUD_BATT]?battery:-1;h->batt_exact=1;

    if(!active->loaded || !settings[FS_HUD])return 0;
    int delay=h->flash?(int)(flash_until-now):0;
    int over=h->style==FOS_HUD_CLASSIC?(h->want<h->widest || h->want>=fos_nfstops):abs(h->want-h->fstop)>6;
    int blink=h->finished || (h->need_wind && (h->style!=FOS_HUD_CLEAN || !h->flash))
             || (h->style!=FOS_HUD_CLEAN && h->meter && over);
    if(blink){
        int phase=400-(int)(now%400);
        if(!delay || phase<delay)delay=phase;
    }
    return delay;
}

void finder_palette(struct fos_hud_palette *p,uint32_t *rgba){
    *p=(struct fos_hud_palette){0,1,101,102,103,{0}};
    rgba[0]=0;
    for(int i=0;i<=100;i++){
        p->gray[i]=(uint8_t)(i+1);
        rgba[i+1]=0xff000000u|(i*255u/100u)*0x010101u;
    }
    rgba[p->red]=0xff2434ff;rgba[p->dark_red]=0xff1a2272;
}
