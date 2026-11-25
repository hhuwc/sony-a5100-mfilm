#ifndef MFILM_ARW_H
#define MFILM_ARW_H
#include <stdint.h>
#include <stdio.h>
/* Sony ILCE-5100 compressed ARW2, one strip of 6048 RGGB samples per row.
   See LibRaw 0.21.4, decoders_dcraw.cpp, sony.cpp and colordata.cpp. */
#define ARW_WIDTH 6048
typedef struct {
    char when[20], fstop[8];
} ArwCapture;
typedef struct {
    ArwCapture capture;
    int height, visible_width, orientation, black, white, wb[3];
    unsigned offset;
    uint16_t linear[4096];
    uint8_t packed[ARW_WIDTH+1];
    uint16_t row[ARW_WIDTH];
} Arw;
void arw_capture(FILE *file, ArwCapture *capture);
int arw_open(Arw *a, FILE *f);
int arw_read(Arw *a, FILE *f);
int arw_unpack(const Arw *a,const uint8_t *packed,uint16_t *row);
#endif

