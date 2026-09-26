#ifndef HUD_H
#define HUD_H
#include <ngdevkit/types.h>
void hud_init(const char *name1, const char *name2);
void hud_update(u16 hp1, u16 hp2, u16 timer, u8 wins1, u8 wins2);
void hud_message(const char *msg);
void hud_combo(u8 side, u16 hits);
void hud_tick(void);
#endif
