#ifndef MFILM_BATCH_H
#define MFILM_BATCH_H
#include "arw.h"
/* One slab is decoded in two disjoint halves, then accumulated in sensor order. */
struct Batch;
struct Batch *batch_new(int threads);
int batch_next(struct Batch *b,Arw *a,FILE *f,int remaining);
const uint16_t *batch_row(struct Batch *b,int i);
void batch_end(struct Batch *b);
#endif

