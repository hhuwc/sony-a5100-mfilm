#include "read_ahead.h"
#include <pthread.h>
#include <stdlib.h>

struct ReadAhead {
    FILE *file;
    pthread_t thread;
    pthread_mutex_t lock;
    pthread_cond_t changed;
    int remaining,block_rows,stop,used[2],take,previous;
    uint8_t *buffers[2];
};

static void *read_blocks(void *argument){
    struct ReadAhead *r=argument;
    int slot=0;
    pthread_mutex_lock(&r->lock);
    while(r->remaining>0 && !r->stop){
        while(r->used[slot] && !r->stop)pthread_cond_wait(&r->changed,&r->lock);
        if(r->stop)break;
        int count=r->remaining<r->block_rows?r->remaining:r->block_rows;
        pthread_mutex_unlock(&r->lock);
        size_t got=fread(r->buffers[slot],ARW_WIDTH,count,r->file);
        pthread_mutex_lock(&r->lock);
        r->used[slot]=got==(size_t)count?count:-1;
        pthread_cond_broadcast(&r->changed);
        if(r->used[slot]<0)break;
        r->remaining-=count;slot^=1;
    }
    pthread_mutex_unlock(&r->lock);
    return NULL;
}

struct ReadAhead *read_ahead_start(FILE *file,int rows,int block_rows){
    struct ReadAhead *r=calloc(1,sizeof(*r));
    if(!r)return NULL;
    for(int i=0;i<2;i++)r->buffers[i]=malloc((size_t)block_rows*ARW_WIDTH+1);
    r->file=file;r->remaining=rows;r->block_rows=block_rows;r->previous=-1;
    if(r->buffers[0] && r->buffers[1] && !pthread_mutex_init(&r->lock,NULL)){
        if(!pthread_cond_init(&r->changed,NULL)){
            if(!pthread_create(&r->thread,NULL,read_blocks,r))return r;
            pthread_cond_destroy(&r->changed);
        }
        pthread_mutex_destroy(&r->lock);
    }
    free(r->buffers[0]);free(r->buffers[1]);free(r);
    return NULL;
}

const uint8_t *read_ahead_next(struct ReadAhead *r,int *rows){
    pthread_mutex_lock(&r->lock);
    if(r->previous>=0){
        r->used[r->previous]=0;
        pthread_cond_broadcast(&r->changed);
    }
    int slot=r->take;
    while(!r->used[slot])pthread_cond_wait(&r->changed,&r->lock);
    *rows=r->used[slot];r->previous=slot;r->take^=1;
    pthread_mutex_unlock(&r->lock);
    return r->buffers[slot];
}

void read_ahead_close(struct ReadAhead *r){
    if(!r)return;
    pthread_mutex_lock(&r->lock);r->stop=1;pthread_cond_broadcast(&r->changed);
    pthread_mutex_unlock(&r->lock);
    pthread_join(r->thread,NULL);
    pthread_cond_destroy(&r->changed);pthread_mutex_destroy(&r->lock);
    free(r->buffers[0]);free(r->buffers[1]);free(r);
}
