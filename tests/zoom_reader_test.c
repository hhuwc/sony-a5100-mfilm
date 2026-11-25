#include "fos_dev.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8_t pixel(int x, int y)
{
    return (uint8_t)((x*77 + y*17 + (x^y)/3) % 240 + 1);
}

static int check_size(int w, int h)
{
    FILE *file = tmpfile();
    assert(file);
    for (int i=0; i<FOS_ZOOM_HEAD; i++) fputc(0, file);
    uint8_t *row=malloc(w);
    assert(row);
    for (int y=0; y<h; y++) {
        for (int x=0; x<w; x++) row[x]=pixel(x,y);
        assert(fwrite(row,1,w,file)==(size_t)w);
    }
    free(row);
    struct fos_zoom zoom={file,w,h};
    int checked=0;
    for (int step=1; step<=4; step++) {
        int ow=(w+step-1)/step;
        if (ow>720) ow=720;
        const int heights[]={1,7,8,9,480};
        for (int t=0; t<5; t++) {
            int oh=heights[t];
            if ((oh-1)*step >= h) continue;
            int pitch=ow+5, size=w*step*(oh<FOS_ZOOM_BAND?oh:FOS_ZOOM_BAND);
            uint8_t *band=malloc(size+16), *out=malloc(oh*pitch);
            assert(band && out);
            memset(band+size,0xFA,16);
            for (int corner=0; corner<2; corner++) {
                int x=corner?w-1-(ow-1)*step:0, y=corner?h-1-(oh-1)*step:0;
                memset(out,0xFA,oh*pitch);
                assert(fos_zoom_read(&zoom,x,y,step,out,pitch,ow,oh,band));
                for (int j=0; j<oh; j++) {
                    for (int i=0; i<ow; i++) assert(out[j*pitch+i]==pixel(x+i*step,y+j*step));
                    for (int i=ow; i<pitch; i++) assert(out[j*pitch+i]==0xFA);
                }
                for (int i=0; i<16; i++) assert(band[size+i]==0xFA);
                checked++;
            }
            free(out);
            free(band);
        }
    }
    fclose(file);
    return checked;
}

int zoom_reader_test(void)
{
    int tested=check_size(2008,1341)+check_size(3012,2012)+check_size(2012,3012);
    FILE *short_file=tmpfile();
    assert(short_file);
    uint8_t data[FOS_ZOOM_HEAD+16*16]={0}, out[256];
    assert(fwrite(data,1,sizeof(data)-1,short_file)==sizeof(data)-1);
    struct fos_zoom z={short_file,16,16};
    assert(!fos_zoom_read(&z,0,0,1,out,16,16,16,data));
    fclose(short_file);
    printf("PASS %d zoom windows, four sampling steps, guard bytes and late short read\n",tested);
    return 0;
}
