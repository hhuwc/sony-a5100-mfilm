/* Separate-process driver for production roll recovery. The working directory is a temporary card. */
#include "capture_record.h"
#include <stdlib.h>
#include <string.h>
#undef OPAQUE
#include <windows.h>

static struct fos_roll active;
static const char *fault="";

int fos_port_list(const char *dir,int (*visit)(void *,const char *,int),void *ctx) {
    WIN32_FIND_DATAA data;
    char pattern[MAX_PATH];
    snprintf(pattern,sizeof(pattern),"%s/*",dir);
    HANDLE entries=FindFirstFileA(pattern,&data);
    if(entries==INVALID_HANDLE_VALUE)return -1;
    int count=0;
    do {
        if(strcmp(data.cFileName,".") && strcmp(data.cFileName,"..")){
            count++;
            if(!visit(ctx,data.cFileName,!!(data.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)))break;
        }
    } while(FindNextFileA(entries,&data));
    FindClose(entries);return count;
}

static int save(void) {
    if(!strcmp(fault,"before"))ExitProcess(77);
    if(!strcmp(fault,"fail"))return 0;
    FILE *f=fopen("STATE.BIN","wb");
    if(!f)return 0;
    int ok=fwrite(&active,sizeof(active),1,f)==1 && capture_sync(f);
    if(fclose(f))ok=0;
    if(ok && !strcmp(fault,"after"))ExitProcess(78);
    return ok;
}

int main(int argc,char **argv) {
    if(argc<2)return 2;
    FILE *f=fopen("STATE.BIN","rb");
    if(f){
        if(fread(&active,sizeof(active),1,f)!=1)return 2;
        fclose(f);
    }else{
        active.loaded=1;active.number=3;active.exposures=12;
        strcpy(active.loaded_at,"2026-11-25 02:00");
    }
    int ok=1;
    if(!strcmp(argv[1],"recover")){
        if(argc==3)fault=argv[2];
        ok=capture_restore_roll("./",&active,1,save) && capture_recover("./",&active,1,save);
    }else if(!strcmp(argv[1],"attach") && argc>=4){
        if(argc==5)fault=argv[4];
        ok=capture_record("./",&active,atoi(argv[2]),argv[3],"superia400","2026-11-25 02:23:29","4.5",1,save);
    }else if(!strcmp(argv[1],"wind")){
        active.need_wind=0;ok=save();
    }else if(strcmp(argv[1],"state"))return 2;
    printf("%d %d %d %d %d %d\n",active.shot,active.nrecent,active.need_wind,active.recent[0].no,
           active.recent[1].no,capture_ticket(&active));
    return ok?0:1;
}
