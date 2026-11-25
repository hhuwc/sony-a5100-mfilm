#ifndef MFILM_EDITIONS_H
#define MFILM_EDITIONS_H

/* A positive ID stores the roll-local sequence and the original Film OS stock index. */
int edition_begin(int roll, int film, char *directory, int size);
int edition_publish(int roll, int id);
int edition_frame_complete(int roll, int id, int frame, int size, int width, int height);
void edition_discard(int roll, int id);
int edition_delete_roll(int roll);
int edition_find(int roll, int after, int latest);
int edition_film(int id);
void edition_file(char *out, int size, int roll, int id, int staging, int frame, const char *ext);

#endif
