#include "arw.h"
#include <jni.h>
JNIEXPORT jstring JNICALL Java_org_mfilm_sony_Probe_machine(JNIEnv *e,jobject self){
    return (*e)->NewStringUTF(e,"Film OS / native ARM");
}
JNIEXPORT jboolean JNICALL Java_org_mfilm_sony_FilmOS_completeRaw(JNIEnv *e,jobject self,jstring filename){
    const char *p=(*e)->GetStringUTFChars(e,filename,NULL);
    if(!p)return 0;
    FILE *f=fopen(p,"rb");
    (*e)->ReleaseStringUTFChars(e,filename,p);
    if(!f)return 0;
    Arw a;
    int ok=arw_open(&a,f) && !fseek(f,0,SEEK_END) && ftell(f)>=(long)a.offset+(long)ARW_WIDTH*a.height;
    fclose(f);return ok;
}
