#include "arw.h"
#include <string.h>
#include <stdlib.h>

static unsigned le16(const uint8_t *p) { return p[0] | ((unsigned)p[1]<<8); }
static uint32_t le32(const uint8_t *p) { return le16(p) | (uint32_t)le16(p+2)<<16; }
static int at(FILE *f, unsigned off, void *p, unsigned n) {
    return off <= 0x7fffffff && !fseek(f, (long)off, SEEK_SET) && fread(p,1,n,f)==n;
}
static int tag(FILE *f,unsigned dir,unsigned id,unsigned type,unsigned count,unsigned *value) {
    uint8_t n[2],entry[12];
    if (!at(f,dir,n,2) || le16(n)>512) return 0;
    for (unsigned i=0;i<le16(n);i++) {
        if (fread(entry,1,12,f)!=12) return 0;
        if (le16(entry)!=id) continue;
        if (le16(entry+2)!=type || le32(entry+4)!=count) return 0;
        *value=(type==3 && count==1) ? le16(entry+8) : le32(entry+8);
        return 1;
    }
    return 0;
}
static int capture_date(const char date[20]) {
    const char *pattern="0000:00:00 00:00:00";
    for (int i=0;i<19;i++) {
        if (pattern[i]=='0') {
            if (date[i]<'0' || date[i]>'9') return 0;
        } else if (date[i]!=pattern[i]) return 0;
    }
    return date[19]==0 && atoi(date)>0 && atoi(date+5)>=1 && atoi(date+5)<=12
        && atoi(date+8)>=1 && atoi(date+8)<=31 && atoi(date+11)<24
        && atoi(date+14)<60 && atoi(date+17)<60;
}

static void read_capture(FILE *f,unsigned root,ArwCapture *capture) {
    unsigned exif,off;
    char date[20];
    uint8_t fraction[8];
    if (!tag(f,root,0x8769,4,1,&exif)) return;
    if (tag(f,exif,0x9003,2,20,&off) && at(f,off,date,sizeof(date)) && capture_date(date)) {
        date[4]=date[7]='-';
        memcpy(capture->when,date,sizeof(date));
    }
    if (tag(f,exif,0x829d,5,1,&off) && at(f,off,fraction,sizeof(fraction))) {
        uint32_t num=le32(fraction),den=le32(fraction+4);
        if (!den) return;
        uint64_t tenth=((uint64_t)num*10+den/2)/den;
        if (!tenth || tenth>9999) return;
        unsigned value=(unsigned)tenth;
        if(value%10)snprintf(capture->fstop,sizeof(capture->fstop),"%u.%u",value/10,value%10);
        else snprintf(capture->fstop,sizeof(capture->fstop),"%u",value/10);
    }
}

void arw_capture(FILE *file, ArwCapture *capture) {
    uint8_t header[8];
    memset(capture,0,sizeof(*capture));
    if (file && at(file,0,header,sizeof(header)) && !memcmp(header,"II*\0",4))
        read_capture(file,le32(header+4),capture);
}

/* Decode the maker's SR2 metadata block, using Sony's word order. */
static int calibration(Arw *a,FILE *f,unsigned dir) {
    unsigned off,len,key; uint32_t pad[128]; unsigned p=0;
    if (!tag(f,dir,0x7200,4,1,&off) || !tag(f,dir,0x7201,4,1,&len) ||
        !tag(f,dir,0x7221,7,4,&key) || len<2 || len>262144) return 0;
    uint8_t *b=malloc(len);
    if (!b || !at(f,off,b,len)) { free(b);return 0; }
    for (;p<4;p++) pad[p]=key=key*48828125u+1;
    pad[3]=(pad[3]<<1)|((pad[0]^pad[2])>>31);
    for (;p<127;p++) pad[p]=((pad[p-4]^pad[p-2])<<1)|((pad[p-3]^pad[p-1])>>31);
    for (unsigned j=0;j+4<=len;j+=4,p++) {
        uint32_t word=pad[p&127]=pad[(p+1)&127]^pad[(p+65)&127];
        for (int k=0;k<4;k++) b[j+k]^=(uint8_t)(word>>(24-8*k));
    }
    unsigned count=le16(b);
    for (unsigned i=0;i<count && 2+12*(i+1)<=len;i++) {
        const uint8_t *e=b+2+i*12;
        unsigned id=le16(e), loc=le32(e+8)-off;
        if ((le16(e+2)!=3 && le16(e+2)!=8) || le32(e+4)!=4 || loc>len-8) continue;
        const uint8_t *v=b+loc;
        if (id==0x7313 || id==0x7303) {
            int r=id==0x7313?0:1, blue=id==0x7313?3:2;
            a->wb[0]=le16(v+2*r); a->wb[1]=le16(v+2*(1-r)); a->wb[2]=le16(v+2*blue);
        }
        if (id==0x7310 || id==0x7300) a->black=le16(v);
    }
    free(b);
    return a->wb[0]>0 && a->wb[1]>0 && a->wb[2]>0;
}
int arw_open(Arw *a, FILE *f) {
    uint8_t h[10],knees[8]; unsigned root,raw,priv,w,height,model,bits,comp,cfa,curve,bytes,orient;
    memset(a,0,sizeof(*a));
    if (!at(f,0,h,8) || memcmp(h,"II*\0",4)) return 0;
    root=le32(h+4);
    if (!tag(f,root,0x110,2,10,&model) || !at(f,model,h,10) || memcmp(h,"ILCE-5100",10) ||
        !tag(f,root,0x14a,4,1,&raw) || !tag(f,root,0xc634,1,4,&priv) ||
        !tag(f,raw,0x100,3,1,&w) || w!=ARW_WIDTH || !tag(f,raw,0x101,3,1,&height) || height!=4024 ||
        !tag(f,raw,0x102,3,1,&bits) || bits!=12 || !tag(f,raw,0x103,3,1,&comp) || comp!=32767 ||
        !tag(f,raw,0x828e,1,4,&cfa) || cfa!=0x02010100 || !tag(f,raw,0x111,4,1,&a->offset) ||
        !tag(f,raw,0x117,4,1,&bytes) || bytes!=w*height || !tag(f,raw,0x7010,3,4,&curve) ||
        !at(f,curve,knees,8)) return 0;
    unsigned prev=0;
    for (int k=0;k<5;k++) {
        unsigned end=k==4?4095:(le16(knees+2*k)>>2)&4095;
        if (end<prev) return 0;
        for (unsigned i=prev+1;i<=end;i++) a->linear[i]=a->linear[i-1]+(1u<<k);
        prev=end;
    }
    a->height=height; a->visible_width=w-24;
    read_capture(f,root,&a->capture);
    a->orientation=tag(f,root,0x112,3,1,&orient)?orient:1;
    a->white=16383; a->black=512; /* LibRaw ILCE-5100 calibrated saturation */
    return calibration(a,f,priv) && a->black<a->white && !fseek(f,(long)a->offset,SEEK_SET);
}
int arw_read(Arw *a, FILE *f) {
    if (fread(a->packed,1,ARW_WIDTH,f)!=ARW_WIDTH) return 0;
    return arw_unpack(a,a->packed,a->row);
}
int arw_unpack(const Arw *a,const uint8_t *packed,uint16_t *row) {
    for (int base=0;base<ARW_WIDTH;base+=32) for (int parity=0;parity<2;parity++) {
        const uint8_t *p=packed+base+parity*16;
        uint32_t header=le32(p);
        unsigned hi=header&2047,lo=(header>>11)&2047,imax=(header>>22)&15,imin=(header>>26)&15;
        unsigned shift=0,bit=30;
        if (hi<lo || (imax==imin && hi!=lo)) return 0;
        while (shift<4 && (128u<<shift)<=hi-lo) shift++;
        for (unsigned i=0;i<16;i++) {
            unsigned val;
            if (hi==lo) val=lo;
            else if (i==imax) val=hi;
            else if (i==imin) val=lo;
            else { val=lo+(((le16(p+bit/8)>>(bit%8))&127)<<shift); bit+=7; }
            row[base+parity+i*2]=a->linear[(val>2047?2047:val)*2];
        }
    }
    return 1;
}

