#ifndef FX_H
#define FX_H
#include <ngdevkit/types.h>
#include "fighter.h"

typedef struct {
    u8 active, owner, frame, timer;
    s8 dir;
    s32 x;
    s16 y;                 // relativo al piso, negativo = arriba
} proj_t;

extern proj_t projs[2];

void fx_init(void);
void fx_spawn_projectile(const fighter_t *f);
void fx_spark(s16 x, s16 y, u8 blocked);
void fx_update(void);                         // mueve proyectiles y chispas
void fx_draw(s16 cam_x, const fighter_t *p1, const fighter_t *p2);
#endif
