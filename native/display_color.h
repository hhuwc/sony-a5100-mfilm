#ifndef MFILM_DISPLAY_COLOR_H
#define MFILM_DISPLAY_COLOR_H

#include "fos_gfx.h"

/* Sony presents RGB pixels. Decode the selected Film OS display matrix
   back to RGB after applying the three upstream screen adjustments. */
static inline uint32_t sony_screen_rgb(uint32_t rgb,int standard,int sat,int warm,int bright){
    if(standard!=1)
        return fos_screen_rgb(fos_screen_yuv_rgb(rgb,235,0,sat,warm,bright),235);
    if(!sat && !warm && !bright)return rgb;
    uint32_t yuv=fos_screen_yuv_rgb(rgb,255,1,sat,warm,bright);
    int y=yuv>>16, cb=(int8_t)(yuv>>8), cr=(int8_t)yuv;
    int r=fos_clamp(y+15748*cr/10000,0,255);
    int g=fos_clamp(y-(1873*cb+4681*cr)/10000,0,255);
    int b=fos_clamp(y+18556*cb/10000,0,255);
    return (uint32_t)(r<<16 | g<<8 | b);
}

#endif
