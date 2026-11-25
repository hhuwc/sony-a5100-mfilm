#define _BSD_SOURCE 1
#include "fos.h"
#include "fos_dev.h"
#include "display.h"
#include "display_color.h"
#include "arw.h"
#include "capture_record.h"
#include "master_prints.h"
#include "finder_hud.h"
#include "stock_settings.h"
#include <android/bitmap.h>
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <android/log.h>
#include <jni.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include <stdlib.h>
#include <errno.h>
#include <stddef.h>
#include <dirent.h>
#include <sys/stat.h>

#define PKG(m) Java_org_mfilm_sony_FilmOS_##m
#define CARD "/mnt/sdcard/"
#define DATA CARD "MFILM/"
static struct {
    unsigned magic;
    struct fos_roll active;
    int setting[FS_COUNT];
} state={.magic=0x464f5301,.setting={
    [FS_HUD]=1,[FS_LEDS]=1,[FS_FOCUS]=1,[FS_LENS_WIDE]=6,[FS_FSTOP]=10,[FS_PLAYLOCK]=1,
    [FS_BOOTANIM]=1,[FS_WIND]=1,[FS_SCR_FLIP]=-1,[FS_EXPSIM]=-1,[FS_CANON_OFF]=-1,
    [FS_HUD_BATT]=1,[FS_FADE]=1,[FS_STARTUP]=2,[FS_DEBUG]=1}};
#define roll state.active
#define settings state.setting
static const char *slot[]={DATA "ROLLA.DAT",DATA "ROLLB.DAT"};
struct state_record {unsigned generation;typeof(state) value;unsigned checksum;};
static unsigned generation;
static pthread_mutex_t state_lock=PTHREAD_MUTEX_INITIALIZER;
static int needs_roll_scan=1;
static struct finder_exposure exposure={-1,-1,0,0};
static char lens_name[80]="Lens info unavailable";
static int recover_capture(void);
static unsigned checksum(const struct state_record *r){
    const uint8_t *p=(const uint8_t*)r;
    unsigned h=2166136261u;
    for(unsigned i=0;i<offsetof(struct state_record,checksum);i++)h=(h^p[i])*16777619u;
    return h;
}
static int save_state(void){
    struct state_record r={generation+1,state,0};r.checksum=checksum(&r);
    FILE *f=fopen(slot[r.generation&1],"wb");
    if(!f)return 0;
    int ok=fwrite(&r,1,sizeof(r),f)==sizeof(r) && capture_sync(f);
    if(fclose(f))ok=0;
    if(ok)generation=r.generation;
    return ok;
}
static JNIEnv *worker; static jobject owner; /* valid during one synchronous native call */
static jmethodID redraw,action;
static jmethodID mode_changed;
static int direct_mode=-1;
static int previous_menu=FOS_OPEN_HOME;
void sony_remember_menu(int page){previous_menu=page;}
JNIEXPORT jint JNICALL PKG(previousMenu)(JNIEnv *env,jobject self){return previous_menu;}
static int key_stamp[64],render_stamp;
static uint8_t pixels[FOS_H][FOS_W];
static uint32_t palette[256];
static pthread_mutex_t frame_lock=PTHREAD_MUTEX_INITIALIZER, input_lock=PTHREAD_MUTEX_INITIALIZER;
static int queue[64],head,tail,stopping,dirty;
static pthread_cond_t key_ready=PTHREAD_COND_INITIALIZER;
static int changed_top=0,changed_bottom=FOS_H;
static int baseline;
int sony_baseline(void){return __atomic_load_n(&baseline,__ATOMIC_RELAXED);}
int sony_pending_input(void){
    pthread_mutex_lock(&input_lock);
    int pending=head!=tail || stopping;
    pthread_mutex_unlock(&input_lock);
    return pending;
}
static int battery=-1,trace_on;
static int card_log_enabled=1;
/* Record the settled design canvas with its active palette for hardware acceptance. */
void sony_trace_screen(int screen){
    static int previous=-1,since,saved,seq,last_check;
    if(!trace_on)return;
    int now=fos_port_ms(),requested=0;
    if(now-last_check>=1000){
        last_check=now;
        int old=sony_baseline(),new_mode=access(DATA "VERIFY/BASELINE.ON",F_OK)==0;
        if(old!=new_mode){
            __atomic_store_n(&baseline,new_mode,__ATOMIC_RELAXED);
            dirty=1;
            __android_log_print(ANDROID_LOG_INFO,"FilmOS","baseline=%d",new_mode);
        }
        if(access(DATA "VERIFY/CAPTURE.REQ",F_OK)==0)requested=1;
    }
    if(previous!=screen){previous=screen;since=now;saved=0;}
    if(!requested && (saved || now-since<700))return;
    char path[96];
    if(requested)snprintf(path,sizeof(path),DATA "VERIFY/CURRENT.PPM");
    else{
        saved=1;
        snprintf(path,sizeof(path),DATA "VERIFY/S%02d_%03d.PPM",screen,(seq++)%1000);
    }
    FILE *f=fopen(path,"wb");if(!f)return;
    fprintf(f,"P6\n720 480\n255\n");
    uint8_t row[3*FOS_W];
    for(int y=0;y<FOS_H;y++){
        for(int x=0;x<FOS_W;x++){uint32_t rgb=palette[pixels[y][x]];row[3*x]=rgb;row[3*x+1]=rgb>>8;row[3*x+2]=rgb>>16;}
        if(fwrite(row,1,sizeof(row),f)!=sizeof(row))break;
    }
    if(!fclose(f) && requested)remove(DATA "VERIFY/CAPTURE.REQ");
}
static time_t camera_local_time,clock_synced;
JNIEXPORT void JNICALL PKG(alignClock)(JNIEnv *e,jobject self,jlong seconds){
    struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
    camera_local_time=(time_t)seconds;clock_synced=t.tv_sec;
}
static void date_string(char *b,int n,const char *fmt){
    struct tm tm;
    if(camera_local_time){
        struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
        time_t local=camera_local_time+(t.tv_sec-clock_synced);
        gmtime_r(&local,&tm);
    }else{time_t ts=time(NULL);localtime_r(&ts,&tm);}
    strftime(b,n,fmt,&tm);
}
int fos_port_ms(){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (int)((t.tv_sec*1000u+t.tv_nsec/1000000u)&0x7fffffff);}
void fos_port_sleep(int ms){
    if((sony_surface_changed() || dirty) && worker){
        int start=fos_port_ms();
        int direct=!sony_baseline() && sony_post_canvas(&pixels[0][0],palette);
        int end=fos_port_ms();
        if(direct!=direct_mode){
            direct_mode=direct;
            (*worker)->CallVoidMethod(worker,owner,mode_changed,(jboolean)direct);
            if(trace_on)__android_log_print(ANDROID_LOG_INFO,"FilmOS","direct display=%d",direct);
        }
        if(direct && trace_on){
            __android_log_print(ANDROID_LOG_DEBUG,"FilmFrame","draw %d %d",start,end);
            if(render_stamp)__android_log_print(ANDROID_LOG_INFO,"FilmOS","key to draw %d ms",end-render_stamp);
        }
        render_stamp=0;
        if(!direct)(*worker)->CallVoidMethod(worker,owner,redraw);
        dirty=0;
    }
    if(ms<=0)return;
    if(!worker || sony_baseline()){usleep(ms*1000u);return;}
    struct timespec until;
    clock_gettime(CLOCK_REALTIME,&until);
    until.tv_nsec+=ms*1000000L;
    until.tv_sec+=until.tv_nsec/1000000000L;
    until.tv_nsec%=1000000000L;
    pthread_mutex_lock(&input_lock);
    while(head==tail && !stopping && !pthread_cond_timedwait(&key_ready,&input_lock,&until)){}
    pthread_mutex_unlock(&input_lock);
}
int fos_port_abort(){pthread_mutex_lock(&input_lock);int v=stopping;pthread_mutex_unlock(&input_lock);return v;}
int fos_port_key(){
    pthread_mutex_lock(&input_lock);int k=0;
    if(head!=tail){
        k=queue[head];if(key_stamp[head])render_stamp=key_stamp[head];
        head=(head+1)%64;
    }
    pthread_mutex_unlock(&input_lock);return k;
}
JNIEXPORT void JNICALL PKG(input)(JNIEnv *e,jobject self,jint k){
    pthread_mutex_lock(&input_lock);
    if(k<0)stopping=1;
    else if((tail+1)%64!=head){queue[tail]=k;key_stamp[tail]=trace_on && k<256?fos_port_ms():0;tail=(tail+1)%64;}
    pthread_cond_signal(&key_ready);
    pthread_mutex_unlock(&input_lock);
}
void fos_port_present(const uint8_t *rows,int pitch,int y0,int y1){
    pthread_mutex_lock(&frame_lock);
    for(int y=y0;y<y1;y++,rows+=pitch)memcpy(pixels[y],rows,FOS_W);
    if(y0<changed_top)changed_top=y0;
    if(y1>changed_bottom)changed_bottom=y1;
    pthread_mutex_unlock(&frame_lock);dirty=1;
}
static uint32_t rgba(uint32_t rgb){return 0xff000000u|((rgb&255)<<16)|(rgb&0xff00)|(rgb>>16);}
static uint32_t screen_color(uint32_t rgb){
    return rgba(sony_screen_rgb(rgb,settings[FS_SCR_STD],settings[FS_SCR_SAT],settings[FS_SCR_WARM],settings[FS_SCR_BRIGHT]));
}
void fos_port_palette(){
    pthread_mutex_lock(&frame_lock);
    changed_top=0;changed_bottom=FOS_H;
    for(int i=0;i<256;i++){
        palette[i]=screen_color(fos_pal[i]);
    }
    pthread_mutex_unlock(&frame_lock);dirty=1;
}
void fos_port_photo(const uint8_t (*pal)[3],int n,int k){
    pthread_mutex_lock(&frame_lock);
    changed_top=0;changed_bottom=FOS_H;
    for(int i=1;i<255;i++){
        const uint8_t *p=i<=n?pal[i-1]:i>=FOS_FIXED_BASE?fos_fixed_rgb[i-FOS_FIXED_BASE]:(uint8_t[3]){0,0,0};
        unsigned rgb=(p[0]*k>>8)<<16|(p[1]*k>>8)<<8|(p[2]*k>>8);
        palette[i]=screen_color(rgb);
    }
    pthread_mutex_unlock(&frame_lock);dirty=1;
}
JNIEXPORT void JNICALL PKG(copyFrame)(JNIEnv *env,jobject self,jobject bitmap){
    AndroidBitmapInfo info;void *dst;
    if(AndroidBitmap_getInfo(env,bitmap,&info)||info.width!=FOS_W||info.height!=FOS_H||
       info.format!=ANDROID_BITMAP_FORMAT_RGBA_8888||AndroidBitmap_lockPixels(env,bitmap,&dst))return;
    pthread_mutex_lock(&frame_lock);
    int full=sony_baseline();
    for(int y=full?0:changed_top;y<(full?FOS_H:changed_bottom);y++){
        uint32_t *row=(uint32_t *)((uint8_t *)dst+y*info.stride);
        for(int x=0;x<FOS_W;x++) row[x]=palette[pixels[y][x]];
    }
    changed_top=FOS_H;changed_bottom=0;
    pthread_mutex_unlock(&frame_lock);AndroidBitmap_unlockPixels(env,bitmap);
}
void *fos_port_alloc(int n){return n>0?malloc(n):NULL;}
void fos_port_free(void *p){free(p);}
const char *fos_port_card(){return CARD;}
/* Keep Film OS resources and work files in their own folder on the card. */
static const char *mapped(const char *p,char *b,size_t n){
    if(!strncmp(p,CARD "ML/",strlen(CARD "ML/"))){snprintf(b,n,DATA "%s",p+strlen(CARD));return b;}
    return p;
}
static AAssetManager *assets;
int sony_replace_output(const char *from,const char *to){
    char src[256],dst[256];
    const char *pending=mapped(from,src,sizeof(src));
    FILE *f=fopen(pending,"r+b");
    if(!f)return 0;
    int ok=capture_sync(f);
    if(fclose(f))ok=0;
    return ok && !rename(pending,mapped(to,dst,sizeof(dst)));
}
static jobject asset_owner;
static int resource_read(void *p,char *buf,int n){return AAsset_read(p,buf,n);}
static fpos_t resource_seek(void *p,fpos_t off,int whence){return AAsset_seek(p,off,whence);}
static int resource_close(void *p){AAsset_close(p);return 0;}
void *fos_port_open(const char *p,int w){
    if(!w && assets && (!strncmp(p,CARD "ML/DATA/",sizeof(CARD "ML/DATA/")-1) ||
                         !strncmp(p,CARD "ML/SAMPLES/",sizeof(CARD "ML/SAMPLES/")-1) ||
                         !strncmp(p,CARD "ML/DARKROOM/LOOK",sizeof(CARD "ML/DARKROOM/LOOK")-1))){
        AAsset *a=AAssetManager_open(assets,p+sizeof(CARD)-1,AASSET_MODE_RANDOM);
        if(a){FILE *f=funopen(a,resource_read,NULL,resource_seek,resource_close);if(!f)AAsset_close(a);return f;}
        return NULL;
    }
    char b[256];return fopen(mapped(p,b,sizeof(b)),w?"wb":"rb");
}
int fos_port_read(void *f,void *p,int n){return fread(p,1,n,f);}
int fos_port_write(void *f,const void *p,int n){return fwrite(p,1,n,f);}
int fos_port_seek(void *f,int pos){return fseek(f,pos,SEEK_SET);}
void fos_port_close(void *f){fclose(f);}
int fos_port_mkdir(const char *p){char b[256];return !mkdir(mapped(p,b,sizeof(b)),0775)||errno==EEXIST?0:-1;}
int fos_port_remove(const char *p){
    char b[256]; const char *name=mapped(p,b,sizeof(b));
    if(strlen(name)>4&&!strcasecmp(name+strlen(name)-4,".ARW"))return -1;
    return !remove(name)||errno==ENOENT?0:-1;
}
int fos_port_list(const char *p,int (*fn)(void*,const char*,int),void *ctx){
    char b[256];p=mapped(p,b,sizeof(b));DIR *dir=opendir(p);if(!dir)return -1;
    struct dirent *d;
    int count=0;
    for(;;){
        errno=0;d=readdir(dir);
        if(!d){if(errno)count=-1;break;}
        if(!strcmp(d->d_name,".")||!strcmp(d->d_name,".."))continue;
        int folder=d->d_type==DT_DIR;
        if(d->d_type==DT_UNKNOWN){
            char path[512];struct stat st;snprintf(path,sizeof(path),"%s/%s",p,d->d_name);
            if(stat(path,&st)){count=-1;break;}
            folder=S_ISDIR(st.st_mode);
        }
        count++;
        if(!fn(ctx,d->d_name,folder))break;
    }
    closedir(dir);return count;
}
JNIEXPORT jboolean JNICALL PKG(cardLogEnabled)(JNIEnv *env,jobject self){
    return __atomic_load_n(&card_log_enabled,__ATOMIC_RELAXED)!=0;
}
void fos_port_log(const char *s){
    __android_log_write(ANDROID_LOG_INFO,"FilmOS",s);
    if(!__atomic_load_n(&card_log_enabled,__ATOMIC_RELAXED))return;
    FILE *f=fopen(DATA "FILMOS.LOG","a");if(f){fprintf(f,"%d %s\n",fos_port_ms(),s);fclose(f);}
}
void fos_port_clock(char *b,int n){date_string(b,n,"%H:%M");}
int fos_port_dev_cap(){return 0;}
int fos_port_lens_manual(){
    pthread_mutex_lock(&state_lock);int manual=exposure.fstop<0;pthread_mutex_unlock(&state_lock);
    return manual;
}
const char *fos_port_lens_name(){
    /* The Film OS menu thread consumes this snapshot before it draws the next row. */
    static char label[sizeof(lens_name)];
    pthread_mutex_lock(&state_lock);memcpy(label,lens_name,sizeof(label));pthread_mutex_unlock(&state_lock);
    return label;
}
const char *fos_port_version(){return "0.2.4";}
const char *fos_port_model(){return "Sony ILCE-5100";}
int fos_port_battery(int *exact){*exact=1;return __atomic_load_n(&battery,__ATOMIC_RELAXED);}
JNIEXPORT void JNICALL PKG(batteryLevel)(JNIEnv *e,jobject self,jint percent){
    __atomic_store_n(&battery,percent,__ATOMIC_RELAXED);
}
void fos_port_stat(const struct fos_stat *s){
    if(trace_on)__android_log_print(ANDROID_LOG_DEBUG,"FilmFrame",
        "engine baseline=%d frames=%d cpu_draw_ms=%d present_ms=%d cans_ms=%d worst_ms=%d rest_ms=%d",
        sony_baseline(),s->frames,s->draw_ms,s->present_ms,s->cans_ms,s->worst_ms,s->rest_ms);
}
void fos_port_roll(struct fos_roll *r){
    pthread_mutex_lock(&state_lock);*r=roll;pthread_mutex_unlock(&state_lock);
}
int fos_port_get(int s){
    pthread_mutex_lock(&state_lock);
    int value=settings[s];
    if(s==FS_FSTOP && exposure.fstop>=0)value=exposure.fstop;
    if(s==FS_LENS_WIDE && exposure.fstop>=0)value=exposure.widest;
    pthread_mutex_unlock(&state_lock);
    return value;
}
void fos_port_set(int s,int v){
    pthread_mutex_lock(&state_lock);
    int old=settings[s];settings[s]=v;
    if(!save_state())settings[s]=old;
    if(s==FS_DEBUG)__atomic_store_n(&card_log_enabled,settings[s]!=0,__ATOMIC_RELAXED);
    pthread_mutex_unlock(&state_lock);
    if(s>=FS_SCR_STD&&s<=FS_SCR_BRIGHT)fos_port_palette();
}
void fos_port_action(int a,int x,int y){
    if(a==FA_LOAD || a==FA_REWIND){
        int highest=a==FA_LOAD?fos_lab_highest_roll():0;
        pthread_mutex_lock(&state_lock);
        int ok=recover_capture();
        struct fos_roll before=roll;
        if(ok && a==FA_LOAD){
            if(roll.number>highest)highest=roll.number;
            if(highest>=999)ok=0;
            else{
                memset(&roll,0,sizeof(roll));roll.loaded=1;roll.number=highest+1;
                roll.film=x;roll.exposures=fos_exposure_choices[y];
                date_string(roll.loaded_at,sizeof(roll.loaded_at),"%Y-%m-%d %H:%M");
            }
        }else if(ok)roll.loaded=0;
        if(ok)ok=save_state();
        if(!ok)roll=before;
        pthread_mutex_unlock(&state_lock);
        if(!ok){fos_port_log("Could not change roll");return;}
    }
    if(worker)(*worker)->CallVoidMethod(worker,owner,action,a,x,y);
}
static int load_blob(const char *path,int (*load)(const uint8_t *,int)){
    FILE *f=fos_port_open(path,0);if(!f)return 0;
    fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
    uint8_t *p=n>0 && n<8*1024*1024?malloc(n):NULL;
    int ok=p && fread(p,1,n,f)==(unsigned)n && load(p,n);
    fclose(f);if(!ok)free(p);return ok;
}
static int recover_capture(void){
    if(needs_roll_scan){
        if(!capture_restore_roll(CARD,&roll,settings[FS_WIND],save_state))return 0;
        needs_roll_scan=0;
    }
    return capture_recover(CARD,&roll,settings[FS_WIND],save_state);
}
static int initialize_assets(JNIEnv *e,jobject self,jobject manager){
    if(!asset_owner)asset_owner=(*e)->NewGlobalRef(e,manager);
    assets=AAssetManager_fromJava(e,asset_owner);
    if(!assets)return 0;
    fos_port_mkdir(DATA);fos_port_mkdir(DATA "ML");fos_port_mkdir(DATA "ML/DARKROOM");
    trace_on=access(DATA "TEST.ON",F_OK)==0;
    if(trace_on)mkdir(DATA "VERIFY",0775);
    fos_ui_init();
    if(!load_blob(CARD "ML/DATA/FOSFONT.BIN",fos_fonts_load)||
       !load_blob(CARD "ML/DATA/FOSFILMS.BIN",fos_films_load))return 0;
    FILE *f=fopen(DATA "ROLL.DAT","rb");
    if(f){typeof(state) prev;
        if(fread(&prev,1,sizeof(prev),f)==sizeof(prev)&&prev.magic==state.magic&&prev.active.film>=0&&prev.active.film<fos_nfilms)state=prev;
        fclose(f);}
    for(int i=0;i<2;i++){
        struct state_record r;f=fopen(slot[i],"rb");
        if(!f)continue;
        if(fread(&r,1,sizeof(r),f)==sizeof(r)&&r.checksum==checksum(&r)&&r.value.magic==state.magic&&
           r.generation>generation && r.value.active.film>=0 && r.value.active.film<fos_nfilms){
            state=r.value;generation=r.generation;
        }
        fclose(f);
    }
    __atomic_store_n(&card_log_enabled,settings[FS_DEBUG]!=0,__ATOMIC_RELAXED);
    if(!recover_capture())fos_port_log("Pending frame could not be recovered");
    jclass c=(*e)->GetObjectClass(e,self);redraw=(*e)->GetMethodID(e,c,"refresh","()V");action=(*e)->GetMethodID(e,c,"cameraAction","(III)V");
    mode_changed=(*e)->GetMethodID(e,c,"displayMode","(Z)V");
    fos_port_palette();return 1;
}
JNIEXPORT jboolean JNICALL PKG(initialize)(JNIEnv *e,jobject self,jobject manager){
    static pthread_mutex_t init_lock=PTHREAD_MUTEX_INITIALIZER;
    static int ready;
    pthread_mutex_lock(&init_lock);
    if(!ready)ready=initialize_assets(e,self,manager);
    int result=ready;
    pthread_mutex_unlock(&init_lock);
    return result;
}
JNIEXPORT void JNICALL PKG(runScreen)(JNIEnv *e,jobject self,jint page){
    worker=e;owner=self;direct_mode=-1;render_stamp=0;fos_ui_run(page);worker=NULL;owner=NULL;
}
JNIEXPORT void JNICALL PKG(resetInput)(JNIEnv *e,jobject self){
    pthread_mutex_lock(&input_lock);head=tail=stopping=0;pthread_mutex_unlock(&input_lock);
}
JNIEXPORT jint JNICALL PKG(remaining)(JNIEnv *e,jobject self){
    struct fos_roll active;fos_port_roll(&active);return active.loaded?active.exposures-active.shot:0;
}
JNIEXPORT jboolean JNICALL PKG(cleanFinder)(JNIEnv *e,jobject self){
    pthread_mutex_lock(&state_lock);
    int clean=roll.loaded && settings[FS_HUD] && settings[FS_HUD_STYLE]==FOS_HUD_CLEAN;
    pthread_mutex_unlock(&state_lock);
    return clean;
}
JNIEXPORT jboolean JNICALL PKG(wantsMeter)(JNIEnv *e,jobject self,jboolean lit){
    pthread_mutex_lock(&state_lock);
    int show=roll.loaded && settings[FS_HUD] && settings[FS_HUD_STYLE]!=FOS_HUD_CLEAN && (lit || !settings[FS_LEDS]);
    pthread_mutex_unlock(&state_lock);
    return show;
}
JNIEXPORT jint JNICALL PKG(captureTicket)(JNIEnv *e,jobject self){
    pthread_mutex_lock(&state_lock);
    int ticket=recover_capture()?capture_ticket(&roll):-1;
    pthread_mutex_unlock(&state_lock);return ticket;
}
JNIEXPORT jint JNICALL PKG(launchPage)(JNIEnv *e,jobject self){
    struct fos_roll active;fos_port_roll(&active);
    int startup=settings[FS_STARTUP];
    int shelf=startup==2 || (startup==1 && (!active.loaded || active.shot>=active.exposures));
    if(settings[FS_BOOTANIM] && startup)return shelf?FOS_OPEN_BOOT:FOS_OPEN_BOOT_LV;
    return shelf?FOS_OPEN_SHELF:-1;
}
JNIEXPORT jboolean JNICALL PKG(wind)(JNIEnv *e,jobject self,jboolean advance){
    pthread_mutex_lock(&state_lock);
    int pending=roll.loaded && roll.need_wind;
    if(pending && advance){roll.need_wind=0;if(!save_state()){roll.need_wind=1;pending=0;}}
    pthread_mutex_unlock(&state_lock);
    return pending;
}
JNIEXPORT void JNICALL PKG(updateExposure)(JNIEnv *e,jobject self,jint aperture,jint widest,jint num,jint den,jstring lens){
    const char *name=lens?(*e)->GetStringUTFChars(e,lens,NULL):NULL;
    if(lens && !name)return;
    pthread_mutex_lock(&state_lock);
    exposure=(struct finder_exposure){finder_fstop(aperture),finder_fstop(widest),num,den};
    snprintf(lens_name,sizeof(lens_name),"%s",name?name:"Lens info unavailable");
    pthread_mutex_unlock(&state_lock);
    if(name)(*e)->ReleaseStringUTFChars(e,lens,name);
}
JNIEXPORT jint JNICALL PKG(renderHud)(JNIEnv *e,jobject self,jboolean focus,jboolean manual,jint ev,jlong now,jlong until){
    struct fos_hud h;
    struct fos_hud_palette p;
    int exact;
    pthread_mutex_lock(&state_lock);
    int delay=finder_hud(&h,&roll,settings,&exposure,focus,manual,ev,fos_port_battery(&exact),now,until);
    int visible=settings[FS_HUD] && roll.loaded;
    pthread_mutex_unlock(&state_lock);
    pthread_mutex_lock(&frame_lock);
    memset(pixels,0,sizeof(pixels));palette[0]=0;
    changed_top=0;changed_bottom=FOS_H;
    finder_palette(&p,palette);
    if(visible)fos_hud_draw(&pixels[0][0],FOS_W,&h,&p);
    pthread_mutex_unlock(&frame_lock);
    return delay;
}
JNIEXPORT jstring JNICALL PKG(statusText)(JNIEnv *e,jobject self){
    struct fos_roll active;fos_port_roll(&active);
    char b[100];if(active.loaded)snprintf(b,sizeof(b),"%s   %02d / %02d",fos_films[active.film].name,active.shot,active.exposures);
    else strcpy(b,"No roll loaded");return (*e)->NewStringUTF(e,b);
}
JNIEXPORT jintArray JNICALL PKG(filmSettings)(JNIEnv *e,jobject self){
    struct fos_roll active;fos_port_roll(&active);
    if(!active.loaded || active.film<0 || active.film>=fos_nfilms)return NULL;
    jint values[SONY_STOCK_FIELDS];
    sony_stock_settings(&fos_films[active.film],values);
    jintArray array=(*e)->NewIntArray(e,SONY_STOCK_FIELDS);
    if(array)(*e)->SetIntArrayRegion(e,array,0,SONY_STOCK_FIELDS,values);
    return array;
}
JNIEXPORT jint JNICALL PKG(attachFrame)(JNIEnv *e,jobject self,jint ticket,jstring filename){
    const char *path=(*e)->GetStringUTFChars(e,filename,NULL);
    if(!path)return 0;
    ArwCapture captured={0};
    FILE *raw=fopen(path,"rb");
    int readable=raw!=NULL;
    if(raw){arw_capture(raw,&captured);fclose(raw);}
    pthread_mutex_lock(&state_lock);
    char date[24],aperture[8];
    if(captured.when[0])snprintf(date,sizeof(date),"%s",captured.when);
    else date_string(date,sizeof(date),"%Y-%m-%d %H:%M:%S");
    if(captured.fstop[0])snprintf(aperture,sizeof(aperture),"%s",captured.fstop);
    else fos_format_fstop(aperture,sizeof(aperture),exposure.fstop>=0?exposure.fstop:settings[FS_FSTOP]);
    int ok=readable && capture_record(CARD,&roll,ticket,path,fos_films[roll.film].key,date,aperture,settings[FS_WIND],save_state);
    pthread_mutex_unlock(&state_lock);
    (*e)->ReleaseStringUTFChars(e,filename,path);
    return ok;
}
