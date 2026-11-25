#include "fos.h"
#include <windows.h>
#include <stdlib.h>
void *fos_port_alloc(int n){return malloc(n);}
void fos_port_free(void *p){free(p);}
int fos_port_ms(){return (int)(GetTickCount64() & 0x7fffffffu);}
int fos_port_dev_cap(){return 0;}
void fos_port_log(const char *s){puts(s);}
void *fos_port_open(const char *p,int w){return fopen(p,w?"wb":"rb");}
int fos_port_read(void *f,void *p,int n){return (int)fread(p,1,n,f);}
int fos_port_write(void *f,const void *p,int n){return (int)fwrite(p,1,n,f);}
void fos_port_close(void *f){fclose(f);}
int fos_port_seek(void *f,int pos){return fseek(f,pos,SEEK_SET);}
const char *fos_port_model(){return "Sony ILCE-5100";}
void fos_lab_cache_dir(char *b,int n){snprintf(b,n,"assets/ML/DARKROOM");}

