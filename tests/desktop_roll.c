/* A full reel in one process, with the same per-frame developer and contact sheet as Film OS. */
#include "fos.h"
#include "fos_dev.h"
#include <stdlib.h>
#include <windows.h>
#include <psapi.h>

int main(int argc,char **argv){
    if(argc!=4)return 2;
    int count=atoi(argv[3]);
    if(count!=12 && count!=24 && count!=36)return 2;
    char paths[36][256],jpeg[256],zoom[256],sheet[256],cache[128];
    const char *prints[36];
    fos_lab_cache_dir(cache,sizeof(cache));
    fos_dev_cache(cache);
    int start=fos_port_ms();
    for(int i=0;i<count;i++){
        int frame=i+1;
        if(snprintf(paths[i],sizeof(paths[i]),"%s/F%02d.BMP",argv[2],frame)>=(int)sizeof(paths[i])
            || snprintf(jpeg,sizeof(jpeg),"%s/F%02d.JPG",argv[2],frame)>=(int)sizeof(jpeg)
            || snprintf(zoom,sizeof(zoom),"%s/F%02d.ZOM",argv[2],frame)>=(int)sizeof(zoom))return 2;
        prints[i]=paths[i];
        struct fos_dev *dev=fos_dev_start(argv[1],paths[i],5,frame,"2001-01-02 03:04","8");
        if(!dev)return 3;
        fos_dev_jpeg(dev,jpeg);
        fos_dev_big(dev,FOS_SIZE_M,zoom);
        int progress;
        do{progress=fos_dev_step(dev,20);}while(progress>=0 && progress<1000);
        int w,h;
        int made=fos_dev_made(dev,&w,&h);
        fos_dev_free(dev);
        if(progress!=1000 || made!=FOS_SIZE_M || w!=2008 || h!=1341)return 4;
    }
    if(snprintf(sheet,sizeof(sheet),"%s/SHEET.BMP",argv[2])>=(int)sizeof(sheet)
        || !fos_dev_sheet(sheet,5,prints,count))return 5;
    fos_dev_release();
    PROCESS_MEMORY_COUNTERS mem={0};
    if(!GetProcessMemoryInfo(GetCurrentProcess(),&mem,sizeof(mem)))return 6;
    printf("frames=%d job_ms=%d peak_desktop_working_set_KiB=%llu\n",count,fos_port_ms()-start,
           (unsigned long long)(mem.PeakWorkingSetSize/1024));
    return 0;
}
