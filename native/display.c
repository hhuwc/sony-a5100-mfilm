#include "fos.h"
#include "display.h"
#include <android/native_window_jni.h>
#include <android/log.h>
#include <pthread.h>
#include <string.h>

static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static ANativeWindow *window;
static int changed;
int sony_surface_changed(void){return __atomic_exchange_n(&changed,0,__ATOMIC_RELAXED);}

JNIEXPORT void JNICALL Java_org_mfilm_sony_FilmOS_menuSurface(JNIEnv *env,jobject activity,jobject surface){
    ANativeWindow *next=surface?ANativeWindow_fromSurface(env,surface):NULL;
    if(next && ANativeWindow_setBuffersGeometry(next,0,0,WINDOW_FORMAT_RGBX_8888)){
        ANativeWindow_release(next);next=NULL;
    }
    pthread_mutex_lock(&lock);
    ANativeWindow *old=window;window=next;
    __atomic_store_n(&changed,1,__ATOMIC_RELAXED);
    pthread_mutex_unlock(&lock);
    if(old)ANativeWindow_release(old);
}

int sony_post_canvas(const uint8_t *pixels,const uint32_t *palette){
    pthread_mutex_lock(&lock);
    ANativeWindow *out=window;
    if(out)ANativeWindow_acquire(out);
    pthread_mutex_unlock(&lock);
    if(!out)return 0;
    ANativeWindow_Buffer b;
    if(ANativeWindow_lock(out,&b,NULL)){ANativeWindow_release(out);return 0;}
    int w=b.width<b.height*3/2?b.width:b.height*3/2;
    int h=w*2/3,left=(b.width-w)/2,top=(b.height-h)/2;
    /* Same nearest-neighbour fit as the Java canvas. Convert directly into the
       compositor's back buffer. Co-ordinates are cached for the whole session. */
    static int last_width;
    static uint16_t source_x[2048];
    int ok=b.format==WINDOW_FORMAT_RGBX_8888 && w>0 && h>0 && w<=2048;
    if(ok){
        if(last_width!=w){
            for(int x=0;x<w;x++)source_x[x]=(2*x+1)*FOS_W/(2*w);
            last_width=w;
        }
        uint32_t *row=b.bits;
        for(int y=0;y<b.height;y++,row+=b.stride){
            if(y<top || y>=top+h){memset(row,0,b.width*sizeof(*row));continue;}
            const uint8_t *src=pixels+((2*(y-top)+1)*FOS_H/(2*h))*FOS_W;
            if(left)memset(row,0,left*sizeof(*row));
            for(int x=0;x<w;x++)row[left+x]=palette[src[source_x[x]]];
            if(left+w<b.width)memset(row+left+w,0,(b.width-left-w)*sizeof(*row));
        }
    }
    int posted=ANativeWindow_unlockAndPost(out)==0;
    ANativeWindow_release(out);
    return posted && ok;
}
