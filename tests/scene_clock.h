/* A real-time mode for the isolated ARM UI harness. No Android key or window events. */
#include <time.h>
#include <unistd.h>
#include <sys/syscall.h>

static int wall_mode, busy_done, busy_start=-1, pending_at=-1, pending_key;
static long long epoch_ms;

static long long monotonic_ms(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC,&t);
    return (long long)t.tv_sec*1000 + t.tv_nsec/1000000;
}

static int elapsed_ms(void) { return (int)(monotonic_ms()-epoch_ms); }

static void start_clock(void) {
    wall_mode=getenv("FOS_WALL")!=NULL;
    if (!wall_mode) return;
    unsigned long cpu3=1UL<<3;
    if (syscall(__NR_sched_setaffinity,0,sizeof(cpu3),&cpu3)<0) {perror("CPU3");exit(2);}
    epoch_ms=monotonic_ms();
}

static void busy_clock(int on) {
    if (!wall_mode) return;
    if (on) busy_start=elapsed_ms();
    else if (busy_start>=0) {
        fprintf(stderr,"job_ms=%d\n",elapsed_ms()-busy_start);
        busy_start=-1;
        busy_done=1;
        FILE *f=fopen("/proc/self/status","r");
        if (!f) return;
        char line[256];
        while(fgets(line,sizeof(line),f))
            if(!strncmp(line,"VmHWM:",6) || !strncmp(line,"Cpus_allowed_list:",18)) fputs(line,stderr);
        fclose(f);
    }
}

static void record_key(int key,int due) {
    if (!wall_mode || busy_start<0 || (key & FK_RELEASE)) return;
    if (pending_at>=0) fprintf(stderr,"coalesced_key=%d\n",pending_key);
    pending_at=due; pending_key=key;
}

static void record_canvas(void) {
    if (pending_at<0) return;
    fprintf(stderr,"key=%d due=%d canvas_ms=%d\n",pending_key,pending_at,elapsed_ms()-pending_at);
    pending_at=-1;
}
