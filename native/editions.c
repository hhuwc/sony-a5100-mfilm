#include "fos.h"
#include "fos_dev.h"
#include "editions.h"
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Each folder name fits FAT 8.3. Publish a complete set with a single same-parent rename. */
static int roll_dir(char *out, int size, int roll) {
    return snprintf(out, size, "%sMFILM/PRINTS/R%03d", fos_port_card(), roll);
}

static int set_dir(char *out, int size, int roll, int id, char prefix) {
    char parent[128];
    roll_dir(parent, sizeof(parent), roll);
    return snprintf(out, size, "%s/%c%07d", parent, prefix, id);
}

static int name_id(const char *name) {
    if (strlen(name) != 8 || (name[0] != 'T' && name[0] != 'P')) return 0;
    int id = 0;
    for (int i=1; i<8; i++) {
        if (name[i] < '0' || name[i] > '9') return 0;
        id = id * 10 + name[i] - '0';
    }
    return id >= 1000 ? id : 0;
}

int edition_film(int id) { return id % 1000; }

static int scan(int roll, int after, int latest, int include_pending) {
    char parent[128];
    roll_dir(parent, sizeof(parent), roll);
    DIR *dir = opendir(parent);
    if (!dir) return 0;
    struct dirent *entry;
    int selected = 0;
    while ((entry = readdir(dir))) {
        int id = name_id(entry->d_name);
        if (id <= after || (!include_pending && (entry->d_name[0]!='P' || edition_film(id)>=fos_nfilms))) continue;
        if (!selected || (latest ? id>selected : id<selected)) selected=id;
    }
    closedir(dir);
    return selected;
}

int edition_find(int roll, int after, int latest) { return scan(roll, after, latest, 0); }

int edition_begin(int roll, int film, char *directory, int size) {
    char parent[128];
    if (roll<0 || roll>999 || film<0 || film>=1000 || film>=fos_nfilms) return 0;
    snprintf(parent,sizeof(parent),"%sMFILM/PRINTS",fos_port_card());
    if (fos_port_mkdir(parent)<0) return 0;
    roll_dir(parent,sizeof(parent),roll);
    if (fos_port_mkdir(parent)<0) return 0;
    int n=scan(roll,0,1,1)/1000+1;
    for (; n<=9999; n++) {
        int id=n*1000+film;
        if (set_dir(directory,size,roll,id,'T')>=size) return 0;
        if (mkdir(directory,0775)==0) {
            char published[160];
            set_dir(published,sizeof(published),roll,id,'P');
            if (access(published,F_OK)!=0 && errno==ENOENT) return id;
            rmdir(directory);
        } else if (errno!=EEXIST) return 0;
    }
    return 0;
}

void edition_file(char *out, int size, int roll, int id, int staging, int frame, const char *ext) {
    char dir[160];
    set_dir(dir,sizeof(dir),roll,id,staging?'T':'P');
    if (frame) snprintf(out,size,"%s/F%02d.%s",dir,frame,ext);
    else snprintf(out,size,"%s/SHEET.BMP",dir);
}

int edition_publish(int roll, int id) {
    char from[160],to[160];
    set_dir(from,sizeof(from),roll,id,'T');
    set_dir(to,sizeof(to),roll,id,'P');
    return rename(from,to)==0;
}

int edition_frame_complete(int roll, int id, int frame, int size, int width, int height) {
    char path[160];
    struct stat st;
    edition_file(path,sizeof(path),roll,id,1,frame,"BMP");
    if (stat(path,&st) || st.st_size < FOS_BMP_THUMB + FOS_THUMB_SIZE) return 0;
    edition_file(path,sizeof(path),roll,id,1,frame,"JPG");
    FILE *jpeg=fopen(path,"rb");
    if (!jpeg) return 0;
    int complete=fgetc(jpeg)==0xff && fgetc(jpeg)==0xd8 && !fseek(jpeg,-2,SEEK_END)
        && fgetc(jpeg)==0xff && fgetc(jpeg)==0xd9;
    fclose(jpeg);
    if (!complete || size==FOS_SIZE_S) return complete;
    edition_file(path,sizeof(path),roll,id,1,frame,"ZOM");
    return !stat(path,&st) && st.st_size==FOS_ZOOM_HEAD + width*height;
}

static int generated_file(const char *s) {
    if (!strcmp(s,"SHEET.BMP")) return 1;
    return strlen(s)==7 && s[0]=='F' && s[1]>='0' && s[1]<='9' && s[2]>='0' && s[2]<='9' &&
        (!strcmp(s+3,".BMP") || !strcmp(s+3,".JPG") || !strcmp(s+3,".ZOM"));
}

static int remove_set(const char *path) {
    DIR *dir=opendir(path);
    if (!dir) return errno==ENOENT ? 0 : 1;
    struct dirent *entry;
    int errors=0;
    while ((entry=readdir(dir))) {
        if (!generated_file(entry->d_name)) continue;
        char file[192];
        snprintf(file,sizeof(file),"%s/%s",path,entry->d_name);
        if (unlink(file)<0 && errno!=ENOENT) errors++;
    }
    closedir(dir);
    return errors+(rmdir(path)<0 && errno!=ENOENT);
}

void edition_discard(int roll, int id) {
    if (id<=0) return;
    char path[160];
    set_dir(path,sizeof(path),roll,id,'T');
    remove_set(path);
}

int edition_delete_roll(int roll) {
    char parent[128],set[160];
    roll_dir(parent,sizeof(parent),roll);
    DIR *dir=opendir(parent);
    if (!dir) return errno==ENOENT ? 0 : 1;
    int errors=0;
    struct dirent *entry;
    while ((entry=readdir(dir))) {
        int id=name_id(entry->d_name);
        if (!id) continue;
        set_dir(set,sizeof(set),roll,id,entry->d_name[0]);
        errors+=remove_set(set);
    }
    closedir(dir);
    return errors+(rmdir(parent)<0 && errno!=ENOENT);
}
