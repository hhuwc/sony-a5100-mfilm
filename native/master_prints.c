#include "fos.h"
#include "fos_dev.h"
#include "master_prints.h"
#include <stdio.h>
#include <string.h>

static unsigned le16(const unsigned char *p){return p[0]|((unsigned)p[1]<<8);}
static unsigned le32(const unsigned char *p){return le16(p)|(le16(p+2)<<16);}
static unsigned be16(const unsigned char *p){return ((unsigned)p[0]<<8)|p[1];}

static long file_length(FILE *f){
    if(fseek(f,0,SEEK_END))return -1;
    long bytes=ftell(f);
    return fseek(f,0,SEEK_SET)?-1:bytes;
}

int master_bitmap_valid(const char *path,int frame){
    FILE *f=fos_port_open(path,0);
    if(!f)return 0;
    unsigned char header[30],meta[8];
    int ok=file_length(f)==FOS_BMP_SIZE && fread(header,1,sizeof(header),f)==sizeof(header) &&
           !memcmp(header,"BM",2) && le32(header+10)==FOS_BMP_PIXELS &&
           le32(header+18)==FOS_PRINT_W && le32(header+22)==(unsigned)-FOS_PRINT_H &&
           le16(header+26)==1 && le16(header+28)==8 &&
           !fseek(f,FOS_BMP_META,SEEK_SET) && fread(meta,1,sizeof(meta),f)==sizeof(meta) &&
           !memcmp(meta,"FOP2",4) && le16(meta+6)==(unsigned)frame;
    fos_port_close(f);return ok;
}

/* Read the JPEG envelope and its dimensions without decoding the image.
   The Film OS encoder writes baseline SOF0. Accept the other common SOFs for old prints. */
int master_jpeg_dimensions(const char *path,int *w,int *h){
    FILE *f=fos_port_open(path,0);
    if(!f)return 0;
    int ok=0;
    if(fseek(f,-2,SEEK_END) || fgetc(f)!=255 || fgetc(f)!=0xd9 ||
       fseek(f,0,SEEK_SET) || fgetc(f)!=255 || fgetc(f)!=0xd8)goto done;
    while(fgetc(f)==255){
        int marker;
        do{marker=fgetc(f);}while(marker==255);
        if(marker<0 || marker==0xda || marker==0xd9)break;
        unsigned char length[2],shape[5];
        if(fread(length,1,2,f)!=2)break;
        int n=be16(length);
        if(n<2)break;
        if(marker>=0xc0 && marker<=0xc2){
            if(n>=8 && fread(shape,1,sizeof(shape),f)==sizeof(shape)){
                *h=be16(shape+1);*w=be16(shape+3);ok=*h>0 && *w>0;
            }
            break;
        }
        if(fseek(f,n-2,SEEK_CUR))break;
    }
done:
    fos_port_close(f);return ok;
}

int master_zoom_valid(const char *path,int w,int h){
    FILE *f=fos_port_open(path,0);
    if(!f)return 0;
    long length=file_length(f);
    unsigned char head[FOS_ZOOM_HEAD];
    int ok=fread(head,1,sizeof(head),f)==sizeof(head) && !memcmp(head,"FOZ1",4);
    if(ok){
        int zw=le16(head+4),zh=le16(head+6);
        ok=zw>=16 && zh>=16 && length==FOS_ZOOM_HEAD+(long long)zw*zh &&
           zw==w && zh==h;
    }
    fos_port_close(f);return ok;
}

static int check_frame(const struct master_files *files,int frame,int w,int h){
    int jw,jh;
    if(!master_bitmap_valid(files->bmp,frame) || !master_jpeg_dimensions(files->jpeg,&jw,&jh))return 0;
    if(w && (jw!=w || jh!=h))return 0;
    return (jw<=FOS_PRINT_W && jh<=FOS_PRINT_H) || master_zoom_valid(files->zoom,jw,jh);
}

int master_frame_valid(const struct master_files *files,int frame){return check_frame(files,frame,0,0);}

static int temp_path(char *out,size_t n,const char *path,const char *extension){
    size_t len=strlen(path);
    if(len<4 || len>=n || path[len-4]!='.')return 0;
    memcpy(out,path,len-3);
    memcpy(out+len-3,extension,4);
    return 1;
}

int master_prepare(struct master_work *work,const char *bmp,const char *jpeg,const char *zoom){
    memset(work,0,sizeof(*work));
    if(!temp_path(work->temp.bmp,sizeof(work->temp.bmp),bmp,"BMT") ||
       !temp_path(work->temp.jpeg,sizeof(work->temp.jpeg),jpeg,"JPT") ||
       !temp_path(work->temp.zoom,sizeof(work->temp.zoom),zoom,"ZMT"))return 0;
    strcpy(work->final.bmp,bmp);strcpy(work->final.jpeg,jpeg);strcpy(work->final.zoom,zoom);
    return 1;
}

int master_clear_temp(const struct master_work *work){
    int a=fos_port_remove(work->temp.bmp),b=fos_port_remove(work->temp.jpeg),c=fos_port_remove(work->temp.zoom);
    return a>=0 && b>=0 && c>=0;
}

void master_discard(struct master_work *work){
    if(!work->final.bmp[0])return;
    master_clear_temp(work);
    memset(work,0,sizeof(*work));
}

int master_publish(struct master_work *work,int frame,int width,int height){
    if(!check_frame(&work->temp,frame,width,height))return 0;
    /* The bitmap is the frame's completion marker. Publish it last. */
    if(fos_port_remove(work->final.bmp)<0)return 0;
    if(!sony_replace_output(work->temp.jpeg,work->final.jpeg))return 0;
    if(width>FOS_PRINT_W || height>FOS_PRINT_H){
        if(!sony_replace_output(work->temp.zoom,work->final.zoom))return 0;
    }else if(fos_port_remove(work->final.zoom)<0)return 0;
    return sony_replace_output(work->temp.bmp,work->final.bmp);
}

int master_sheet(const char *path,int film,const char *const *prints,int frames){
    char temp[128];
    if(!temp_path(temp,sizeof(temp),path,"BMT"))return 0;
    int ok=fos_dev_sheet(temp,film,prints,frames) && master_bitmap_valid(temp,0) &&
           sony_replace_output(temp,path);
    if(!ok)fos_port_remove(temp);
    return ok;
}
