// Proyectiles, chispas de impacto y sombras.
#include "fx.h"
#include "hw.h"

proj_t projs[2];

typedef struct { u8 active, t, blocked; s16 x, y; } spark_t;
static spark_t sparks[2];
static u8 spark_next;

static void fx_tiles(u16 spr, u8 col, u8 flip) {
    // bloque de 2x2 tiles (32x32) de fx.gif, empezando en la columna col
    u16 t[2];
    for (u8 c = 0; c < 2; c++) {
        u8 src = flip ? 1 - c : c;
        t[0] = TILE_FX + col + src;
        t[1] = TILE_FX + FX_ROW + col + src;
        spr_column(spr + c, t, 2, 1, PAL_FX, flip);
    }
}

void fx_init(void) {
    for (u8 i = 0; i < 2; i++) {
        projs[i].active = 0;
        sparks[i].active = 0;
        for (u8 c = 0; c < 2; c++) {
            spr_shape(SPR_SPARK + i * 2 + c, 0, 0, 0, c);
            spr_shape(SPR_SHADOW + i * 2 + c, 0, 0, 0, c);
        }
        fx_tiles(SPR_SHADOW + i * 2, FX_SHADOW, 0);
        for (u8 c = 0; c < 3; c++) spr_shape(SPR_PROJ + i * 3 + c, 0, 0, 0, c != 0);
    }
    spark_next = 0;
}

void fx_spawn_projectile(const fighter_t *f) {
    proj_t *p = &projs[f->id];
    p->active = 1;
    p->owner = f->id;
    p->dir = f->facing;
    p->x = f->x + FP(f->facing * 40);
    p->y = PX(f->y) - 72;
    p->frame = 0;
    p->timer = 0;
}

void fx_explode(proj_t *p, s16 x, s16 y) {
    p->active = 2;
    p->timer = 0;
    p->x = FP(x);
    p->y = y;
}

void fx_spark(s16 x, s16 y, u8 blocked) {
    spark_t *s = &sparks[spark_next];
    spark_next ^= 1;
    s->active = 1;
    s->t = 0;
    s->x = x;
    s->y = y;
    s->blocked = blocked;
}

void fx_update(void) {
    for (u8 i = 0; i < 2; i++) {
        proj_t *p = &projs[i];
        if (p->active == 1) {
            p->x += p->dir * FP(4);
            if (++p->timer >= 5) { p->timer = 0; p->frame = (p->frame + 1) % 3; }
            if (p->x < FP(-32) || p->x > FP(STAGE_W + 32)) p->active = 0;
        }
    }
}

void fx_tick_sparks(void) {
    for (u8 i = 0; i < 2; i++) {
        proj_t *p = &projs[i];
        if (p->active == 2) {
            if (++p->timer >= 24) p->active = 0;
            p->frame = (p->timer / 3) % 3;
        }
        spark_t *s = &sparks[i];
        if (s->active && ++s->t >= 15) s->active = 0;
    }
}

void fx_draw(s16 cam_x, const fighter_t *p1, const fighter_t *p2) {
    const fighter_t *fs[2] = {p1, p2};
    for (u8 i = 0; i < 2; i++) {
        // sombra al pie del luchador, más chica si está en el aire
        const fighter_t *f = fs[i];
        s16 sx = PX(f->x) - cam_x - 16;
        spr_move(SPR_SHADOW + i * 2, sx, FLOOR_Y - 16 + (f->y < FP(-40) ? 2 : 0), 2);

        proj_t *p = &projs[i];
        if (p->active) {
            // bola de 48x48 (3x3 tiles de proj.gif), espejada si va a la izquierda
            for (u8 c = 0; c < 3; c++) {
                u8 src = p->dir < 0 ? 2 - c : c;
                u16 t[3];
                for (u8 r = 0; r < 3; r++) t[r] = TILE_PROJ + r * 9 + p->frame * 3 + src;
                spr_column(SPR_PROJ + i * 3 + c, t, 3, 1, PAL_PROJ, p->dir < 0);
            }
            if (p->active == 2 && (p->timer & 4) && p->timer > 12) spr_hide(SPR_PROJ + i * 3);
            else spr_move(SPR_PROJ + i * 3, PX(p->x) - cam_x - 24, FLOOR_Y + p->y - 24, 3);
        } else {
            spr_hide(SPR_PROJ + i * 3);
        }
        spark_t *s = &sparks[i];
        if (s->active) {
            u8 col = s->blocked ? FX_BLOCK : FX_SPARK + (s->t / 5) * 2;
            fx_tiles(SPR_SPARK + i * 2, col, 0);
            spr_move(SPR_SPARK + i * 2, s->x - cam_x - 16, FLOOR_Y + s->y - 16, 2);
        } else {
            spr_hide(SPR_SPARK + i * 2);
        }
    }
}
