#ifndef MFILM_DISPLAY_H
#define MFILM_DISPLAY_H
#include <stdint.h>
int sony_post_canvas(const uint8_t *pixels,const uint32_t *palette);
int sony_surface_changed(void);
#endif
