#ifndef MFILM_CAPTURE_RECORD_H
#define MFILM_CAPTURE_RECORD_H
#include "fos.h"
#include <stdio.h>

int capture_sync(FILE *file);
int capture_ticket(const struct fos_roll *roll);
void capture_advance(struct fos_roll *roll, int frame, const char *time, const char *aperture, int manual_wind);
int capture_recover(const char *card, struct fos_roll *roll, int manual_wind, int (*save)(void));
int capture_restore_roll(const char *card, struct fos_roll *roll, int manual_wind, int (*save)(void));
int capture_record(const char *card, struct fos_roll *roll, int ticket, const char *raw,
                   const char *film, const char *date, const char *aperture, int manual_wind, int (*save)(void));
#endif
