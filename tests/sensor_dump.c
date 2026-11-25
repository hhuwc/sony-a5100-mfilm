#include "../native/arw.h"
int main(int argc,char **argv){
    if(argc!=3)return 2;
    FILE *f=fopen(argv[1],"rb");
    Arw a;
    if(!f||!arw_open(&a,f))return 3;
    printf("width=%d height=%d black=%d white=%d wb=%d,%d,%d\n",ARW_WIDTH,a.height,a.black,a.white,a.wb[0],a.wb[1],a.wb[2]);
    FILE *out=fopen(argv[2],"wb");
    if(!out)return 4;
    for(int y=0;y<a.height;y++)if(!arw_read(&a,f)||fwrite(a.row,2,ARW_WIDTH,out)!=ARW_WIDTH)return 5;
    fclose(f);return fclose(out)!=0;
}
