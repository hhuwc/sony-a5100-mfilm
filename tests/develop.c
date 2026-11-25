/* On-body test of the exact library in the APK. Diagnostic output goes to a
   caller-selected test directory. Arguments are input ARW, output prefix, film index. */
#include "fos.h"
#include "fos_dev.h"
#include <stdlib.h>
#ifdef __ANDROID__
#include <unistd.h>
#include <sys/syscall.h>
#endif
int main(int argc,char **argv){
    if(argc!=4 && argc!=5)return 2;
    int size=FOS_SIZE_S;
    if(argc==5){
        if(argv[4][0]=='\0' || argv[4][1]!='\0')return 2;
        const char *sizes="SML",*choice=strchr(sizes,argv[4][0]);
        if(!choice)return 2;
        size=(int)(choice-sizes);
    }
#ifdef __ANDROID__
    /* Match the foreground app's measured CPU allowance for comparisons. */
    if(getenv("MFILM_CPU3")){
        unsigned long mask=1UL<<3;
        if(syscall(__NR_sched_setaffinity,0,sizeof(mask),&mask)<0){perror("affinity");return 2;}
    }
#endif
    int film=atoi(argv[3]);
    if(film<0||film>=fos_nfilms)return 2;
    char bmp[128],jpg[128],zoom[128],dir[128];
    if(snprintf(bmp,sizeof(bmp),"%s.bmp",argv[2])>=(int)sizeof(bmp)||
       snprintf(jpg,sizeof(jpg),"%s.jpg",argv[2])>=(int)sizeof(jpg)||
       snprintf(zoom,sizeof(zoom),"%s.foz",argv[2])>=(int)sizeof(zoom))return 2;
    fos_lab_cache_dir(dir,sizeof(dir));fos_dev_cache(dir);
    const char *when=getenv("MFILM_TEST_DATE"),*fstop=getenv("MFILM_TEST_FSTOP");
    struct fos_dev *d=fos_dev_start(argv[1],bmp,film,1,when?when:"2026-11-25 00:00",fstop?fstop:"");
    if(!d)return 3;
    fos_dev_jpeg(d,jpg);
    if(size!=FOS_SIZE_S)fos_dev_big(d,size,zoom);
    int start=fos_port_ms(),progress;
    do{progress=fos_dev_step(d,20);}while(progress>=0 && progress<1000);
    printf("%s %s progress %d elapsed %d ms %s\n",fos_films[film].key,argv[1],progress,fos_port_ms()-start,progress<0?fos_dev_error(d):"");
    if(progress==1000){
        int width,height;
        int made=fos_dev_made(d,&width,&height);
        printf("requested=%c produced=%c JPEG=%dx%d\n","SML"[size],"SML"[made],width,height);
    }
    FILE *status=fopen("/proc/self/status","r");
    if(status){char line[180];while(fgets(line,sizeof(line),status))if(!strncmp(line,"VmHWM:",6)||!strncmp(line,"Cpus_allowed_list:",18))fputs(line,stdout);fclose(status);}
    fos_dev_free(d);return progress!=1000;
}
