#ifndef MFILM_READ_AHEAD_H
#define MFILM_READ_AHEAD_H
#include "arw.h"
struct ReadAhead;
struct ReadAhead *read_ahead_start(FILE *file,int rows,int block_rows);
/* Returned rows remain owned by the caller until its next call or close. */
const uint8_t *read_ahead_next(struct ReadAhead *reader,int *rows);
void read_ahead_close(struct ReadAhead *reader);
#endif
