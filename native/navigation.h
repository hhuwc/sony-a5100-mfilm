#ifndef SONY_NAVIGATION_H
#define SONY_NAVIGATION_H
enum { SONY_RECIPE=40, SONY_DELETE, SONY_EDITION };
enum { SONY_TELE=31, SONY_WIDE=32 };
struct sony_action {const char *label; int command;};
void sony_focus_bar(const struct sony_action *actions,int count);
void sony_focus_photo_bar(const struct sony_action *actions,int count);
int sony_dialog_key(int key,int has_alternate);
void sony_focus_keep(void);
int sony_value_key(int key);
int sony_value_button(void);
void sony_draw_setting(void);
void develop_note_input(void);
#endif
