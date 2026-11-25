#ifndef SONY_FINDER_HUD_H
#define SONY_FINDER_HUD_H
#include "fos.h"

/* Apertures are indices into Film OS's third-stop scale. A negative index means unavailable. */
struct finder_exposure { int fstop, widest, numerator, denominator; };
int finder_fstop(int hundredths);
int finder_hud(struct fos_hud *hud,const struct fos_roll *active,const int *settings,
               const struct finder_exposure *exposure,int half,int manual,int ev_thirds,
               int battery,int64_t now,int64_t flash_until);
void finder_palette(struct fos_hud_palette *p,uint32_t *rgba);
#endif
