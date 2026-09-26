#ifndef FIGHTER_H
#define FIGHTER_H
#include <ngdevkit/types.h>
#include "gen/assets.h"
#include "character.h"

// Posiciones en punto fijo 24.8. y = 0 es el piso, negativo = arriba.
#define FP(px)        ((s32)(px) << 8)
#define PX(fp)        ((s16)((fp) >> 8))
#define FLOOR_Y       200               // fila de pantalla del piso
#define MAX_HP        100

// Bits del joystick tal como los da el BIOS
#define J_UP    0x01
#define J_DOWN  0x02
#define J_LEFT  0x04
#define J_RIGHT 0x08
#define J_A     0x10
#define J_B     0x20
#define J_C     0x40
#define J_D     0x80

enum {
    FS_IDLE, FS_WALK_F, FS_WALK_B, FS_CROUCH, FS_PREJUMP, FS_AIR, FS_LAND,
    FS_ATTACK, FS_BLOCK, FS_HIT, FS_KNOCKDOWN, FS_KO, FS_WIN, FS_FROZEN
};

typedef struct {
    s32 x, y, vx, vy;
    s32 push;              // velocidad de empuje por golpe, decae
    u8 id;                 // 0 = P1, 1 = P2
    s8 facing;             // +1 derecha, -1 izquierda
    u8 state;
    u8 anim, fidx, ftimer, anim_done, entered;
    s8 jump_dir;
    u8 crouch_block;
    u16 hp;
    u16 stun;
    u8 hit_done;
    u8 air_attack;
    u8 cpu;
    u8 wins;
    u8 joy, joy_prev;
    u8 buf, buf_t;          // botón apretado durante una recuperación
    u8 dirbuf[16];
    u8 dirpos;
    u8 ai_timer, ai_hold, ai_seq_len, ai_seq_pos;
    u8 ai_seq[12];
    u16 hits_landed, hits_blocked, specials, combo, max_combo;
    s16 drawn_img;
    s8 drawn_facing;
    u8 drawn_w;
    u16 spr;
    u8 pal;
    const character_t *ch;
} fighter_t;

typedef struct {
    u8 anim;
    u8 dmg, hitstun, blockstun, hitstop;
    u8 push;               // px/frame iniciales
    u8 sfx;
} attack_t;

void fighter_init(fighter_t *f, u8 id, u16 spr, u8 pal, const character_t *ch);
void fighter_reset_round(fighter_t *f, s16 x, s8 facing);
void fighter_set_anim(fighter_t *f, u8 anim);
const frame_t *fighter_frame(const fighter_t *f);
const attack_t *fighter_attack(const fighter_t *f);
void fighter_update(fighter_t *f, const fighter_t *opp, u8 control, u8 can_fireball);
void fighter_physics(fighter_t *f);
void fighter_draw(fighter_t *f, s16 cam_x, s8 shake);
void fighter_world_box(const fighter_t *f, const box_t *b, s16 *x0, s16 *y0, s16 *x1, s16 *y1);
u8 fighter_holding_back(const fighter_t *f);
u8 fighter_is_crouching(const fighter_t *f);
u8 fighter_actionable(const fighter_t *f);
#endif
