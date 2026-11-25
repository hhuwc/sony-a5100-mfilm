#include "batch.h"
#include "read_ahead.h"
#include <pthread.h>
#include <stdlib.h>
#include <time.h>
#include <stdio.h>
extern void fos_port_log(const char *);
#define ROWS 16
struct Batch {
    pthread_t thread;
    pthread_mutex_t lock;
    pthread_cond_t cond;
    int parallel,waiting,quit,count,failure;
    Arw *a;
    int prefetch;
    struct ReadAhead *reader;
    const uint8_t *source;
    uint8_t packed[ROWS*ARW_WIDTH+1];
    uint16_t rows[ROWS][ARW_WIDTH];
    double read_ms,decode_ms;
};
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return 1000.*t.tv_sec+t.tv_nsec/1e6;}
static int decode_range(struct Batch *b,int from,int to){
    for(int i=from;i<to;i++)if(!arw_unpack(b->a,b->source+i*ARW_WIDTH,b->rows[i]))return 0;
    return 1;
}
static void *decode_worker(void *arg){
    struct Batch *b=arg;
    pthread_mutex_lock(&b->lock);
    for(;;){
        while(!b->waiting && !b->quit)pthread_cond_wait(&b->cond,&b->lock);
        if(b->quit)break;
        pthread_mutex_unlock(&b->lock);
        int ok=decode_range(b,b->count/2,b->count);
        pthread_mutex_lock(&b->lock);
        b->failure=!ok;b->waiting=0;pthread_cond_signal(&b->cond);
    }
    pthread_mutex_unlock(&b->lock);return NULL;
}
struct Batch *batch_new(int threads){
    struct Batch *b=calloc(1,sizeof(*b));
    if(b && threads=='p')b->prefetch=1;
    if(b && threads==2){
        pthread_mutex_init(&b->lock,NULL);pthread_cond_init(&b->cond,NULL);
        if(!pthread_create(&b->thread,NULL,decode_worker,b))b->parallel=1;
        else{pthread_cond_destroy(&b->cond);pthread_mutex_destroy(&b->lock);}
    }
    return b;
}
int batch_next(struct Batch *b,Arw *a,FILE *f,int remaining){
    int count=remaining<ROWS?remaining:ROWS;
    double start=now();
    if(b->prefetch && !b->reader){
        b->reader=read_ahead_start(f,remaining,ROWS);
        if(!b->reader)b->prefetch=0;
    }
    if(b->reader){
        int n;
        b->source=read_ahead_next(b->reader,&n);
        if(n!=count)return -1;
    }else{
        b->source=b->packed;
        if(fread(b->packed,ARW_WIDTH,count,f)!=(size_t)count)return -1;
    }
    double read_done=now();b->read_ms+=read_done-start;
    b->count=count;b->a=a;
    if(b->parallel){
        pthread_mutex_lock(&b->lock);b->waiting=1;pthread_cond_signal(&b->cond);pthread_mutex_unlock(&b->lock);
    }
    int ok=decode_range(b,0,b->parallel?count/2:count);
    if(b->parallel){
        pthread_mutex_lock(&b->lock);
        while(b->waiting)pthread_cond_wait(&b->cond,&b->lock);
        ok=ok&&!b->failure;pthread_mutex_unlock(&b->lock);
    }
    b->decode_ms+=now()-read_done;return ok?count:-1;
}
const uint16_t *batch_row(struct Batch *b,int i){return b->rows[i];}
void batch_end(struct Batch *b){
    if(!b)return;
    read_ahead_close(b->reader);
    if(b->parallel){pthread_mutex_lock(&b->lock);b->quit=1;pthread_cond_signal(&b->cond);pthread_mutex_unlock(&b->lock);
        pthread_join(b->thread,NULL);pthread_cond_destroy(&b->cond);pthread_mutex_destroy(&b->lock);}
    char msg[160];snprintf(msg,sizeof(msg),"ARW2 batch threads=%d prefetch=%d read_wait_ms=%.1f unpack_ms=%.1f",1+b->parallel+b->prefetch,b->prefetch,b->read_ms,b->decode_ms);fos_port_log(msg);free(b);
}

