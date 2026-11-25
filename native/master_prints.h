#ifndef SONY_MASTER_PRINTS_H
#define SONY_MASTER_PRINTS_H

struct master_files {char bmp[128],jpeg[160],zoom[128];};
struct master_work {struct master_files final,temp;};
/* Replace within the same directory in the camera's mapped filesystem. */
int sony_replace_output(const char *from,const char *to);
int master_bitmap_valid(const char *path,int frame);
int master_jpeg_dimensions(const char *path,int *w,int *h);
int master_zoom_valid(const char *path,int w,int h);
int master_frame_valid(const struct master_files *files,int frame);
int master_prepare(struct master_work *work,const char *bmp,const char *jpeg,const char *zoom);
int master_clear_temp(const struct master_work *work);
int master_publish(struct master_work *work,int frame,int width,int height);
void master_discard(struct master_work *work);
int master_sheet(const char *path,int film,const char *const *prints,int frames);
#endif
