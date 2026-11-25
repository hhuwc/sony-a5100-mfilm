#include <stdio.h>
#include <stdlib.h>
#include "fos.h"
#include "display_color.h"

int menu_color_test(void){
    const int levels[]={0,16,32,64,96,127,160,200,235,255};
    int checked=0;
    for(int r=0;r<10;r++)for(int g=0;g<10;g++)for(int b=0;b<10;b++){
        uint32_t color=(uint32_t)(levels[r]<<16 | levels[g]<<8 | levels[b]);
        if(sony_screen_rgb(color,1,0,0,0)!=color)return 1;
        for(int step=-FOS_SCR_STEPS;step<=FOS_SCR_STEPS;step++){
            uint32_t original=fos_screen_rgb(fos_screen_yuv_rgb(color,235,0,step,-step,step),235);
            if(sony_screen_rgb(color,0,step,-step,step)!=original)return 2;
            checked++;
        }
    }
    for(int standard=0;standard<=1;standard++){
        uint32_t gray=0x909090, color=0x805040;
        uint32_t cool=sony_screen_rgb(gray,standard,0,-3,0);
        uint32_t warm=sony_screen_rgb(gray,standard,0,3,0);
        if((warm>>16)<=(cool>>16) || (warm&255)>=(cool&255))return 3;
        uint32_t light=sony_screen_rgb(gray,standard,0,0,3);
        uint32_t dark=sony_screen_rgb(gray,standard,0,0,-3);
        if((light&255)<=(dark&255))return 4;
        uint32_t vivid=sony_screen_rgb(color,standard,3,0,0);
        uint32_t muted=sony_screen_rgb(color,standard,-3,0,0);
        if((int)(vivid>>16)-(int)(vivid&255)<=(int)(muted>>16)-(int)(muted&255))return 5;
    }
    printf("%d EOS M palette comparisons, 1000 neutral Rec.709 colours and all three adjustments passed\n",checked);
    return 0;
}
