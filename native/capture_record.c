/* One completed Sony shutter, across the public roll log and the alternating state slots. */
#include "capture_record.h"
#include "fos_dev.h"
#include <ctype.h>
#include <errno.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#define disk_sync _commit
#define file_fd _fileno
#define same_name _stricmp
#else
#include <unistd.h>
#include <strings.h>
#define disk_sync fsync
#define file_fd fileno
#define same_name strcasecmp
#endif

enum { LOG_LIMIT=16384 };
struct receipt {
    uint32_t magic, offset, prefix_hash;
    int number, frame;
    char folder[9], file[13], time[6], aperture[8], append[192];
    uint32_t checksum;
};

static uint32_t hash_bytes(const void *data,size_t length) {
    uint32_t hash=2166136261u;
    const unsigned char *bytes=data;
    for(size_t i=0;i<length;i++)hash=(hash^bytes[i])*16777619u;
    return hash;
}

int capture_sync(FILE *file) {
    return fflush(file)==0 && disk_sync(file_fd(file))==0;
}

int capture_ticket(const struct fos_roll *r) {
    if(!r->loaded || r->number<1 || r->number>999 || r->shot<0 || r->shot>=r->exposures || r->exposures>FOS_MAX_FRAMES)return 0;
    return r->number*100+r->shot+1;
}

void capture_advance(struct fos_roll *r,int frame,const char *time,const char *aperture,int manual_wind) {
    r->shot=frame;
    r->need_wind=manual_wind && frame<r->exposures;
    memmove(r->recent+1,r->recent,(FOS_RECENT-1)*sizeof(*r->recent));
    r->recent[0].no=frame;
    snprintf(r->recent[0].time,sizeof(r->recent[0].time),"%.5s",time);
    snprintf(r->recent[0].fstop,sizeof(r->recent[0].fstop),"%.5s",aperture);
    if(r->nrecent<FOS_RECENT)r->nrecent++;
}

static int dcf_name(const char *text,int n) {
    for(int i=0;i<n;i++)if(!isalnum((unsigned char)text[i]) && text[i]!='_')return 0;
    return 1;
}

static int target(struct receipt *rec,const char *card,const char *raw) {
    size_t root=strlen(card);
    if(strncmp(raw,card,root) || strncmp(raw+root,"DCIM/",5))return 0;
    const char *folder=raw+root+5;
    if(strlen(folder)!=21 || folder[8]!='/' || !dcf_name(folder,8)
       || folder[0]<'1' || folder[0]>'9' || !isdigit((unsigned char)folder[1]) || !isdigit((unsigned char)folder[2])
       || !dcf_name(folder+9,8) || same_name(folder+17,".ARW"))return 0;
    memcpy(rec->folder,folder,8);
    memcpy(rec->file,folder+9,13);
    return 1;
}

/* Read exactly the bytes whose length and hash identify the starting log. */
static int read_log(const char *path,char *buffer,size_t *size) {
    FILE *f=fopen(path,"rb");
    if(!f){*size=0;return errno==ENOENT;}
    *size=fread(buffer,1,LOG_LIMIT+1,f);
    int ok=!ferror(f) && *size<=LOG_LIMIT;
    fclose(f);
    return ok;
}

/* Canon-compatible text logs may be spread over several DCIM directories. */
static int find_row(const char *bytes,size_t size,int frame,const char *file) {
    int found=0;
    for(const char *p=bytes;p<bytes+size;){
        const char *newline=memchr(p,'\n',(size_t)(bytes+size-p));
        size_t length=(size_t)((newline?newline:bytes+size)-p);
        if(length && isdigit((unsigned char)*p)){
            char line[192],name[32];
            int number;
            if(length>=sizeof(line))return -1;
            memcpy(line,p,length);line[length]=0;
            if(sscanf(line,"%d %31s",&number,name)!=2)return -1;
            if(number==frame || !same_name(name,file)){
                if(number!=frame || same_name(name,file) || found)return -1;
                found=1;
            }
        }
        p+=length+(newline!=NULL);
    }
    return found;
}

static void log_path(char *path,size_t capacity,const char *card,const struct receipt *rec) {
    snprintf(path,capacity,"%sDCIM/%s/ROLL_%03d.TXT",card,rec->folder,rec->number);
}

static int apply(const char *card,struct fos_roll *r,const struct receipt *rec,int manual,int (*save)(void)) {
    if(!r->loaded || rec->number!=r->number || rec->frame<1 || rec->frame>r->exposures || rec->frame>r->shot+1)return 0;
    char path[512],*bytes=malloc(LOG_LIMIT+1);
    if(!bytes)return 0;
    log_path(path,sizeof(path),card,rec);
    size_t size;
    size_t len=strlen(rec->append);
    int ok=read_log(path,bytes,&size) && size>=rec->offset && hash_bytes(bytes,rec->offset)==rec->prefix_hash;
    if(ok){
        size_t tail=size-rec->offset;
        size_t have=tail;
        ok=have<=len && !memcmp(bytes+rec->offset,rec->append,have);
        if(ok){
            FILE *f=fopen(path,"ab");
            if(f){
                ok=(have==len || fwrite(rec->append+have,1,len-have,f)==len-have) && capture_sync(f);
                if(fclose(f))ok=0;
            }else ok=0;
        }
    }
    free(bytes);
    if(!ok)return 0;
    if(rec->frame==r->shot+1){
        struct fos_roll before=*r;
        capture_advance(r,rec->frame,rec->time,rec->aperture,manual);
        if(!save()){*r=before;return 0;}
    }
    snprintf(path,sizeof(path),"%sMFILM/FRAME.DAT",card);
    return remove(path)==0 || errno==ENOENT;
}

static int read_receipt(const char *card,struct receipt *rec) {
    char path[512],temp[512];
    snprintf(path,sizeof(path),"%sMFILM/FRAME.DAT",card);
    FILE *f=fopen(path,"rb");
    int unpublished=0;
    if(!f){
        if(errno!=ENOENT)return -1;
        snprintf(temp,sizeof(temp),"%sMFILM/FRAME.NEW",card);
        f=fopen(temp,"rb");
        if(!f)return errno==ENOENT?0:-1;
        unpublished=1;
    }
    int ok=fread(rec,1,sizeof(*rec),f)==sizeof(*rec) && fgetc(f)==EOF;
    int error=ferror(f);
    fclose(f);
    if(error)return -1;
    if(!ok || rec->magic!=0x4d464331 || rec->checksum!=hash_bytes(rec,offsetof(struct receipt,checksum))
       || rec->offset>LOG_LIMIT || !memchr(rec->append,0,sizeof(rec->append)) || rec->folder[8] || rec->file[12]
       || rec->number<1 || rec->number>999 || rec->frame<1 || rec->frame>FOS_MAX_FRAMES
       || rec->time[5] || rec->aperture[7] || !dcf_name(rec->folder,8) || !dcf_name(rec->file,8)
       || same_name(rec->file+8,".ARW"))return unpublished?0:-1;
    if(unpublished && rename(temp,path))return -1;
    return 1;
}

int capture_recover(const char *card,struct fos_roll *r,int manual,int (*save)(void)) {
    struct receipt rec;
    int found=read_receipt(card,&rec);
    return found==0 || (found==1 && apply(card,r,&rec,manual,save));
}

struct logged_frame { char time[6], aperture[8]; };
struct roll_scan {
    const char *card;
    const struct fos_roll *roll;
    const struct receipt *pending;
    struct logged_frame frames[FOS_MAX_FRAMES];
    char *bytes;
    int ok;
};

/* Historical Sony logs may omit the aperture. Only their own complete rows can advance a roll. */
static int scan_folder(void *ctx,const char *folder,int is_dir) {
    struct roll_scan *s=ctx;
    if(!is_dir || strlen(folder)!=8 || !dcf_name(folder,8) || folder[0]<'1' || folder[0]>'9'
       || !isdigit((unsigned char)folder[1]) || !isdigit((unsigned char)folder[2]))return 1;
    char path[512];
    snprintf(path,sizeof(path),"%sDCIM/%s/ROLL_%03d.TXT",s->card,folder,s->roll->number);
    size_t size;
    s->ok=read_log(path,s->bytes,&size);
    if(!s->ok)return 0;
    if(s->pending && !same_name(folder,s->pending->folder)){
        if(size<s->pending->offset || hash_bytes(s->bytes,s->pending->offset)!=s->pending->prefix_hash){
            s->ok=0;return 0;
        }
        size=s->pending->offset;
    }
    char *p=s->bytes;
    while(p<s->bytes+size){
        char *end=memchr(p,'\n',(size_t)(s->bytes+size-p));
        if(!end)end=s->bytes+size;
        *end=0;
        if(isdigit((unsigned char)*p)){
            int no;
            char file[32],day[12],clock[12],aperture[8]="",extra[2];
            int fields=sscanf(p,"%5d %31s %11s %11s f/%7s %1s",&no,file,day,clock,aperture,extra);
            if(fields<4 || fields>5 || no<1 || no>s->roll->exposures || s->frames[no-1].time[0]
               || strlen(file)!=12 || !dcf_name(file,8) || same_name(file+8,".ARW")
               || strlen(day)!=10 || strlen(clock)!=8
               || (s->pending && no==s->pending->frame &&
                   (same_name(folder,s->pending->folder) || same_name(file,s->pending->file)))){
                s->ok=0;return 0;
            }
            memcpy(s->frames[no-1].time,clock,5);
            memcpy(s->frames[no-1].aperture,aperture,sizeof(aperture));
        }
        if(end==s->bytes+size)break;
        p=end+1;
    }
    return 1;
}

int capture_restore_roll(const char *card,struct fos_roll *r,int manual,int (*save)(void)) {
    struct receipt pending;
    int found=read_receipt(card,&pending);
    if(found<0 || (found && (!r->loaded || pending.number!=r->number)))return 0;
    if(!r->loaded)return 1;
    if(r->shot<0 || r->exposures<1 || r->exposures>FOS_MAX_FRAMES || r->shot>r->exposures)return 0;
    struct roll_scan scan={card,r,found?&pending:NULL};
    scan.ok=1;
    scan.bytes=malloc(LOG_LIMIT+1);
    if(!scan.bytes)return 0;
    char dcim[512];
    snprintf(dcim,sizeof(dcim),"%sDCIM",card);
    int listed=fos_port_list(dcim,scan_folder,&scan);
    free(scan.bytes);
    if(listed<0 || !scan.ok)return 0;
    int next=r->shot;
    while(next<r->exposures && scan.frames[next].time[0])next++;
    for(int i=next;i<r->exposures;i++)if(scan.frames[i].time[0])return 0;
    if(found && r->shot<pending.frame && next>=pending.frame)next=pending.frame-1;
    if(next==r->shot)return 1;
    struct fos_roll before=*r;
    for(int i=r->shot;i<next;i++)capture_advance(r,i+1,scan.frames[i].time,scan.frames[i].aperture,manual);
    if(save())return 1;
    *r=before;return 0;
}

int capture_record(const char *card,struct fos_roll *r,int ticket,const char *raw,
                   const char *film,const char *date,const char *aperture,int manual,int (*save)(void)) {
    struct receipt rec={0};
    if(!capture_recover(card,r,manual,save) || !r->loaded || ticket/100!=r->number || !target(&rec,card,raw))return 0;
    rec.number=r->number;rec.frame=ticket%100;rec.magic=0x4d464331;
    if(rec.frame<1 || rec.frame>r->exposures || rec.frame>r->shot+1 || strlen(date)!=19)return 0;
    memcpy(rec.time,date+11,5);
    snprintf(rec.aperture,sizeof(rec.aperture),"%s",aperture);
    char path[512],temp[512],*bytes=malloc(LOG_LIMIT+1);
    if(!bytes)return 0;
    log_path(path,sizeof(path),card,&rec);
    size_t size;
    if(!read_log(path,bytes,&size)){free(bytes);return 0;}
    int match=find_row(bytes,size,rec.frame,rec.file);
    rec.offset=(uint32_t)size;
    rec.prefix_hash=hash_bytes(bytes,size);
    int newline=size && bytes[size-1]!='\n';
    free(bytes);
    if(match<0 || rec.frame<=r->shot)return match==1;
    if(!match){
        int n=0;
        if(!size)n=snprintf(rec.append,sizeof(rec.append),"film = %s\nexposures = %d\nloaded = %s\n",film,r->exposures,r->loaded_at);
        if(n<0 || (size_t)n>=sizeof(rec.append))return 0;
        int added=snprintf(rec.append+n,sizeof(rec.append)-n,"%s%d  %s  %s  f/%s\n",
                           newline?"\n":"",rec.frame,rec.file,date,aperture);
        if(added<0 || (size_t)(n+added)>=sizeof(rec.append) || size+n+added>LOG_LIMIT)return 0;
    }
    rec.checksum=hash_bytes(&rec,offsetof(struct receipt,checksum));
    snprintf(temp,sizeof(temp),"%sMFILM/FRAME.NEW",card);
    snprintf(path,sizeof(path),"%sMFILM/FRAME.DAT",card);
    FILE *f=fopen(temp,"wb");
    if(!f)return 0;
    int ok=fwrite(&rec,1,sizeof(rec),f)==sizeof(rec) && capture_sync(f);
    if(fclose(f))ok=0;
    if(!ok || rename(temp,path))return 0;
    return apply(card,r,&rec,manual,save);
}
