#ifndef SONY_STOCK_SETTINGS_H
#define SONY_STOCK_SETTINGS_H
#include "fos.h"

/* Shared by JNI and the desktop catalogue check. Keep the field order with StockSettings.apply. */
enum { SONY_STOCK_FIELDS=8 };
static inline void sony_stock_settings(const struct fos_film *film,int values[SONY_STOCK_FIELDS]){
    /* The EOS M port's iso_to_raw advances by whole stops from ISO 100. */
    int iso=100;
    while(iso<film->iso && iso<25600)iso*=2;
    values[0]=iso;
    values[1]=film->kelvin;
    values[2]=film->picstyle;
    values[3]=film->contrast;
    values[4]=film->saturation;
    values[5]=film->sharpness;
    values[6]=film->wbs_ba;
    values[7]=film->wbs_gm;
}
#endif
