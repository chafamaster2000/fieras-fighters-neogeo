// Efectos del combate: proyectiles, chispas de impacto, guardia, explosión,
// polvo y sombras. El arte sale de art/src/fx/ (tools/neofx.py -> gen/vfx_gen).
//
// Cada efecto vive en un "slot": una cadena de sprites contiguos (el primero
// lleva x, y y alto; los demás son sticky). Solo se reescribe SCB1 cuando
// cambia el cuadro o el espejo; por frame se mueve el primer sprite.
#include "fx.h"
#include "hw.h"
#include "gen/vfx_gen.h"

proj_t projs[2];

// slots: 0-1 bola/explosión de cada jugador, 2-3 chispas, 4-5 destello de
// lanzamiento o polvo de cada jugador
#define NSLOTS      6
#define SLOT_PROJ   0
#define SLOT_SPARK  2
#define SLOT_AUX    4
static const u8 slot_spr[NSLOTS]  = {0, 6, 12, 18, 24, 28};   // + SPR_VFX
static const u8 slot_cols[NSLOTS] = {6, 6, 6, 6, 4, 4};
static const u8 vfx_hwpal[8] = {PAL_VFX0, 25, 26, 27, 28, 29, 30, 31};

typedef struct {
    u8 active, anim, frame, tick, flip, shown;
    s16 x, y;              // mundo: x absoluta del escenario, y relativa al piso
    u16 drawn;             // cuadro global cargado en SCB1 (0xffff = ninguno)
    u8 drawn_flip, drawn_w;
} vfx_t;

static vfx_t slots[NSLOTS];
static u8 spark_next;
static s16 prev_y[2];
static u8 vfx_attr[8];

static void slot_play(u8 s, u8 anim, s16 x, s16 y, u8 flip) {
    vfx_t *v = &slots[s];
    v->active = 1;
    v->anim = anim;
    v->frame = 0;
    v->tick = 0;
    v->flip = flip;
    v->x = x;
    v->y = y;
}

// Carga el cuadro en SCB1 y arma la cadena (sticky) con las columnas que usa
static void slot_load(u8 s, u16 fi) {
    vfx_t *v = &slots[s];
    const vfxframe_t *fr = &vfx_frames[fi];
    u16 base = SPR_VFX + slot_spr[s];
    u8 w = fr->w, h = fr->h, flip = v->flip;
    for (u8 c = 0; c < w; c++) {
        const u16 *e = &vfx_map[fr->first + (u16)(flip ? w - 1 - c : c) * h];
        *REG_VRAMMOD = 1;
        *REG_VRAMADDR = ADDR_SCB1 + (base + c) * 64;
        for (u8 r = 0; r < h; r++) {
            u16 m = e[r];
            *REG_VRAMRW = TILE_VFX + (m & 0x7ff);
            *REG_VRAMRW = ((u16)vfx_attr[m >> 12] << 8) | (((m >> 11) & 1) ^ flip);
        }
    }
    // SCB3: columnas 1..w-1 sticky, las sobrantes ocultas (no cuentan por línea)
    if (w != v->drawn_w || v->drawn == 0xffff) {
        *REG_VRAMMOD = 1;
        *REG_VRAMADDR = ADDR_SCB3 + base + 1;
        for (u8 c = 1; c < slot_cols[s]; c++) *REG_VRAMRW = c < w ? (1 << 6) : 0;
        v->drawn_w = w;
    }
    v->drawn = fi;
    v->drawn_flip = flip;
}

static void slot_draw(u8 s, s16 cam_x) {
    vfx_t *v = &slots[s];
    u16 base = SPR_VFX + slot_spr[s];
    if (!v->active) {
        if (v->shown) { spr_hide(base); v->shown = 0; }
        return;
    }
    u16 fi = vfx_anims[v->anim].first + v->frame;
    if (fi != v->drawn || v->flip != v->drawn_flip) slot_load(s, fi);
    const vfxframe_t *fr = &vfx_frames[fi];
    s16 ox = v->flip ? -(fr->x + (s16)fr->w * 16) : fr->x;
    spr_move(base, v->x - cam_x + ox, FLOOR_Y + v->y + fr->y, fr->h);
    v->shown = 1;
}

void fx_init(void) {
    for (u8 i = 0; i < 8; i++) vfx_attr[i] = i < VFX_PALS ? vfx_hwpal[i] : vfx_hwpal[0];
    for (u8 i = 0; i < VFX_PALS; i++) hw_load_palette(vfx_hwpal[i], vfx_pals[i]);
    // las pantallas previas usan este rango con zoom: sin zoom y ocultos
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB2 + SPR_VFX;
    for (u8 i = 0; i < SPR_VFX_N; i++) *REG_VRAMRW = 0x0fff;
    *REG_VRAMADDR = ADDR_SCB3 + SPR_VFX;
    for (u8 i = 0; i < SPR_VFX_N; i++) *REG_VRAMRW = 0;
    for (u8 s = 0; s < NSLOTS; s++) {
        slots[s].active = slots[s].shown = 0;
        slots[s].drawn = 0xffff;
        slots[s].drawn_w = 0;
    }
    for (u8 i = 0; i < 2; i++) {
        projs[i].active = 0;
        prev_y[i] = 0;
        // los sprites viejos de bola y chispa quedan ocultos
        for (u8 c = 0; c < 2; c++) {
            spr_shape(SPR_SPARK + i * 2 + c, 0, 0, 0, 0);
            spr_shape(SPR_SHADOW + i * 2 + c, 0, 0, 0, c);
        }
        for (u8 c = 0; c < 3; c++) spr_shape(SPR_PROJ + i * 3 + c, 0, 0, 0, 0);
        // sombra: 2x2 tiles de fx.gif
        for (u8 c = 0; c < 2; c++) {
            u16 t[2] = {TILE_FX + FX_SHADOW + c, TILE_FX + FX_ROW + FX_SHADOW + c};
            spr_column(SPR_SHADOW + i * 2 + c, t, 2, 1, PAL_FX, 0);
        }
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
    u8 flip = f->facing < 0;
    slot_play(SLOT_PROJ + f->id, VFX_BALL, PX(p->x), p->y, flip);
    slot_play(SLOT_AUX + f->id, VFX_LAUNCH, PX(p->x) - f->facing * 8, p->y, flip);
}

void fx_explode(proj_t *p, s16 x, s16 y) {
    p->active = 2;
    p->timer = 0;
    p->x = FP(x);
    p->y = y;
    slot_play(SLOT_PROJ + p->owner, VFX_BOOM, x, y, p->dir < 0);
    // la chispa que resolve() acaba de poner en el mismo punto taparía la explosión
    vfx_t *v = &slots[SLOT_SPARK + (spark_next ^ 1)];
    if (v->active && v->frame == 0 && v->tick == 0 && v->x == x && v->y == y && v->anim != VFX_BOOM)
        v->active = 0;
}

void fx_spark(s16 x, s16 y, u8 kind, s8 dir) {
    static const u8 kind_anim[4] = {VFX_HIT_L, VFX_HIT_H, VFX_BLOCK, VFX_HIT_H};
    u8 s = SLOT_SPARK + spark_next;
    spark_next ^= 1;
    slot_play(s, kind_anim[kind & 3], x, y, dir < 0);
    if (kind == FXS_KO) {
        // K.O.: la explosión grande en el otro slot de chispa
        s = SLOT_SPARK + spark_next;
        spark_next ^= 1;
        slot_play(s, VFX_BOOM, x, y, dir < 0);
    }
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
    }
    // los efectos siguen animando durante el hitstop
    for (u8 s = 0; s < NSLOTS; s++) {
        vfx_t *v = &slots[s];
        if (!v->active) continue;
        const vfxanim_t *a = &vfx_anims[v->anim];
        if (++v->tick < a->dur) continue;
        v->tick = 0;
        if (++v->frame >= a->count) {
            if (a->loop) v->frame = 0;
            else v->active = 0;
        }
    }
}

void fx_draw(s16 cam_x, const fighter_t *p1, const fighter_t *p2) {
    const fighter_t *fs[2] = {p1, p2};
    for (u8 i = 0; i < 2; i++) {
        // sombra al pie del luchador, más chica si está en el aire
        const fighter_t *f = fs[i];
        s16 fx = PX(f->x);
        spr_move(SPR_SHADOW + i * 2, fx - cam_x - 16, FLOOR_Y - 16 + (f->y < FP(-40) ? 2 : 0), 2);

        // polvo al tocar el piso (caída, K.O. o fin de un salto)
        s16 fy = PX(f->y);
        if (prev_y[i] < -6 && fy == 0) {
            u8 hard = f->state == FS_KNOCKDOWN || f->state == FS_KO;
            if (hard || !slots[SLOT_AUX + i].active)
                slot_play(SLOT_AUX + i, hard ? VFX_DUST : VFX_DUST_S, fx, 0, f->facing < 0);
        }
        prev_y[i] = fy;

        // la bola sigue al proyectil; si desapareció (choque, fuera de pantalla) se apaga
        proj_t *p = &projs[i];
        vfx_t *v = &slots[SLOT_PROJ + i];
        if (v->active && v->anim == VFX_BALL) {
            if (p->active == 1) v->x = PX(p->x);
            else if (p->active == 0) v->active = 0;
        }
    }
    for (u8 s = 0; s < NSLOTS; s++) slot_draw(s, cam_x);
}
