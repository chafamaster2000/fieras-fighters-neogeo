// Luchador: máquina de estados, física, detección de especiales y dibujo.
#include "fighter.h"
#include "hw.h"
#include "sound.h"

#define WALK_F_V    FP(2) + 0x40       // 2.25 px/frame
#define WALK_B_V    FP(1) + 0x80       // 1.5 px/frame
#define JUMP_V      FP(8)
#define JUMP_H      FP(2) + 0x80
#define GRAVITY     0x66               // 0.4 px/frame^2
#define KO_V        FP(5)

// Datos de golpes (inspirados en frames de KOF: jab rápido, patada más lenta)
static const attack_t attacks[] = {
    {ANIM_PUNCH,  6, 14,  8,  8, 2, SND_HIT},    // +6 al conectar: se encadena
    {ANIM_KICK,  10, 16, 12, 10, 4, SND_HEAVY},
    {ANIM_CPUNCH, 5, 11,  8,  8, 2, SND_HIT},
    {ANIM_JKICK,  9, 15, 11, 10, 3, SND_HEAVY},
};

const attack_t *fighter_attack(const fighter_t *f) {
    for (u8 i = 0; i < sizeof(attacks) / sizeof(attacks[0]); i++)
        if (attacks[i].anim == f->anim) return &attacks[i];
    return 0;
}

const frame_t *fighter_frame(const fighter_t *f) {
    return &fighter_frames[fighter_anims[f->anim].first + f->fidx];
}

void fighter_set_anim(fighter_t *f, u8 anim) {
    f->anim = anim;
    f->fidx = 0;
    f->ftimer = fighter_frame(f)->dur;
    f->anim_done = 0;
    f->entered = 1;
}

static void advance_anim(fighter_t *f) {
    f->entered = 0;
    if (f->anim_done) return;
    if (--f->ftimer) return;
    const anim_t *a = &fighter_anims[f->anim];
    if (f->fidx + 1 < a->count) {
        f->fidx++;
    } else if (a->loop) {
        f->fidx = 0;
    } else {
        f->anim_done = 1;
        f->ftimer = 1;
        return;
    }
    f->ftimer = fighter_frame(f)->dur;
    f->entered = 1;
}

void fighter_init(fighter_t *f, u8 id, u16 spr, u8 pal) {
    f->id = id;
    f->spr = spr;
    f->pal = pal;
    f->wins = 0;
    f->cpu = 1;
    f->hits_landed = f->hits_blocked = f->specials = f->max_combo = 0;
    for (u8 c = 0; c < FIGHTER_COLS; c++) spr_shape(spr + c, 0, 0, FIGHTER_ROWS, c != 0);
}

void fighter_reset_round(fighter_t *f, s16 x, s8 facing) {
    f->x = FP(x);
    f->y = f->vx = f->vy = f->push = 0;
    f->facing = facing;
    f->hp = MAX_HP;
    f->stun = 0;
    f->state = FS_FROZEN;
    f->hit_done = f->air_attack = 0;
    f->joy = f->joy_prev = 0;
    f->buf = f->buf_t = 0;
    f->dirpos = 0;
    for (u8 i = 0; i < 16; i++) f->dirbuf[i] = 5;
    f->ai_timer = f->ai_seq_len = f->ai_seq_pos = 0;
    f->combo = 0;
    f->drawn_tmap = -1;
    fighter_set_anim(f, ANIM_IDLE);
}

// ---------------------------------------------------------------- entrada

static u8 fwd_bit(const fighter_t *f)  { return f->facing > 0 ? J_RIGHT : J_LEFT; }
static u8 back_bit(const fighter_t *f) { return f->facing > 0 ? J_LEFT : J_RIGHT; }

u8 fighter_holding_back(const fighter_t *f) { return (f->joy & back_bit(f)) != 0; }

// Dirección en notación de teclado numérico, relativa a hacia dónde mira
static u8 numpad(const fighter_t *f) {
    u8 h = (f->joy & fwd_bit(f)) ? 6 : (f->joy & back_bit(f)) ? 4 : 5;
    if (f->joy & J_DOWN) return h == 6 ? 3 : h == 4 ? 1 : 2;
    if (f->joy & J_UP) return h == 6 ? 9 : h == 4 ? 7 : 8;
    return h;
}

// Cuarto de círculo adelante (abajo, abajo-adelante, adelante) en los
// últimos 15 frames, en ese orden.
static u8 qcf(const fighter_t *f) {
    u8 want = 6, seen = 0;
    for (u8 i = 0; i < 15; i++) {
        u8 d = f->dirbuf[(f->dirpos - 1 - i) & 15];
        if (want == 6 && d == 6) { want = 3; seen++; }
        else if (want == 3 && d == 3) { want = 2; seen++; }
        else if (want == 2 && (d == 2 || d == 1)) return 1;
    }
    (void)seen;
    return 0;
}

u8 fighter_is_crouching(const fighter_t *f) {
    return f->state == FS_CROUCH || f->anim == ANIM_CPUNCH || f->anim == ANIM_CHIT ||
           (f->state == FS_BLOCK && f->crouch_block);
}

u8 fighter_actionable(const fighter_t *f) {
    return f->state == FS_IDLE || f->state == FS_WALK_F || f->state == FS_WALK_B ||
           f->state == FS_CROUCH;
}

static void start_attack(fighter_t *f, u8 anim) {
    f->state = FS_ATTACK;
    f->vx = 0;
    f->hit_done = 0;
    fighter_set_anim(f, anim);
    sound_cmd(anim == ANIM_FIREBALL ? SND_FIREBALL : SND_WHOOSH);
}

// ---------------------------------------------------------------- lógica

void fighter_update(fighter_t *f, const fighter_t *opp, u8 control, u8 can_fireball) {
    if (!control) f->joy = 0;
    u8 pressed = f->joy & ~f->joy_prev;
    f->dirbuf[f->dirpos++ & 15] = numpad(f);
    f->dirpos &= 15;

    // buffer de 8 frames: un botón apretado mientras no se puede actuar
    // se ejecuta apenas el luchador vuelve a estar libre
    if (fighter_actionable(f)) {
        if (f->buf_t) pressed |= f->buf;
        f->buf_t = 0;
    } else {
        if (pressed & (J_A | J_B)) { f->buf = pressed & (J_A | J_B); f->buf_t = 8; }
        else if (f->buf_t) f->buf_t--;
    }

    switch (f->state) {
    case FS_IDLE: case FS_WALK_F: case FS_WALK_B: case FS_CROUCH: {
        s8 want = opp->x >= f->x ? 1 : -1;
        f->facing = want;
        u8 down = f->joy & J_DOWN;
        if ((pressed & J_A) && can_fireball && qcf(f)) {
            f->specials++;
            start_attack(f, ANIM_FIREBALL);
        } else if (pressed & (J_A | J_B)) {
            start_attack(f, down ? ANIM_CPUNCH : (pressed & J_A) ? ANIM_PUNCH : ANIM_KICK);
        } else if (f->joy & J_UP) {
            f->state = FS_PREJUMP;
            f->vx = 0;
            f->jump_dir = (f->joy & fwd_bit(f)) ? 1 : (f->joy & back_bit(f)) ? -1 : 0;
            fighter_set_anim(f, ANIM_PREJUMP);
        } else if (down) {
            if (f->state != FS_CROUCH) {
                f->state = FS_CROUCH;
                fighter_set_anim(f, ANIM_CROUCH_T);
            } else if (f->anim == ANIM_CROUCH_T && f->anim_done) {
                fighter_set_anim(f, ANIM_CROUCH);
            }
            f->vx = 0;
        } else if (f->joy & fwd_bit(f)) {
            if (f->state != FS_WALK_F) { f->state = FS_WALK_F; fighter_set_anim(f, ANIM_WALK_F); }
            f->vx = f->facing * (WALK_F_V);
        } else if (f->joy & back_bit(f)) {
            if (f->state != FS_WALK_B) { f->state = FS_WALK_B; fighter_set_anim(f, ANIM_WALK_B); }
            f->vx = -f->facing * (WALK_B_V);
        } else {
            if (f->state != FS_IDLE) { f->state = FS_IDLE; fighter_set_anim(f, ANIM_IDLE); }
            f->vx = 0;
        }
        break;
    }
    case FS_PREJUMP:
        if (f->anim_done) {
            f->state = FS_AIR;
            f->vy = -JUMP_V;
            f->vx = f->jump_dir * f->facing * (JUMP_H);
            f->air_attack = 0;
            fighter_set_anim(f, ANIM_AIR_UP);
        }
        break;
    case FS_AIR:
        if ((pressed & (J_A | J_B)) && !f->air_attack) {
            f->air_attack = 1;
            f->hit_done = 0;
            fighter_set_anim(f, ANIM_JKICK);
            sound_cmd(SND_WHOOSH);
        } else if (f->anim == ANIM_AIR_UP && f->vy > 0) {
            fighter_set_anim(f, ANIM_AIR_DOWN);
        }
        break;
    case FS_LAND:
        if (f->anim_done) { f->state = FS_IDLE; fighter_set_anim(f, ANIM_IDLE); }
        break;
    case FS_ATTACK:
        if (f->anim_done) {
            if (f->anim == ANIM_CPUNCH && (f->joy & J_DOWN)) {
                f->state = FS_CROUCH;
                fighter_set_anim(f, ANIM_CROUCH);
            } else {
                f->state = FS_IDLE;
                fighter_set_anim(f, ANIM_IDLE);
            }
        }
        break;
    case FS_BLOCK: case FS_HIT:
        if (f->stun) f->stun--;
        if (!f->stun) {
            if (f->joy & J_DOWN) { f->state = FS_CROUCH; fighter_set_anim(f, ANIM_CROUCH); }
            else { f->state = FS_IDLE; fighter_set_anim(f, ANIM_IDLE); }
            f->combo = 0;
        }
        break;
    case FS_KNOCKDOWN:
        if (f->anim_done && f->y == 0) { f->state = FS_IDLE; fighter_set_anim(f, ANIM_IDLE); f->combo = 0; }
        break;
    default:
        break;
    }
    f->joy_prev = f->joy;
    advance_anim(f);
}

void fighter_physics(fighter_t *f) {
    f->x += f->vx + f->push;
    f->push -= f->push >> 3;
    if (f->push > -0x20 && f->push < 0x20) f->push = 0;

    u8 airborne = f->state == FS_AIR || f->y < 0 ||
                  ((f->state == FS_KO || f->state == FS_KNOCKDOWN) && f->vy);
    if (airborne) {
        f->y += f->vy;
        f->vy += GRAVITY;
        if (f->y >= 0) {
            f->y = 0;
            f->vy = 0;
            if (f->state == FS_AIR) {
                f->state = FS_LAND;
                f->vx = 0;
                fighter_set_anim(f, ANIM_LAND);
            } else if (f->state == FS_KO || f->state == FS_KNOCKDOWN) {
                f->vx = 0;
            }
        }
    }
    if (f->x < FP(24)) f->x = FP(24);
    if (f->x > FP(STAGE_W - 24)) f->x = FP(STAGE_W - 24);
}

// ---------------------------------------------------------------- cajas

void fighter_world_box(const fighter_t *f, const box_t *b, s16 *x0, s16 *y0, s16 *x1, s16 *y1) {
    s16 x = PX(f->x), y = PX(f->y);
    if (f->facing > 0) { *x0 = x + b->x; *x1 = x + b->x + b->w; }
    else { *x0 = x - b->x - b->w; *x1 = x - b->x; }
    *y0 = y + b->y;
    *y1 = y + b->y + b->h;
}

// ---------------------------------------------------------------- dibujo

void fighter_draw(fighter_t *f, s16 cam_x, s8 shake) {
    const frame_t *fr = fighter_frame(f);
    if (fr->tmap != f->drawn_tmap || f->facing != f->drawn_facing) {
        const u16 *map = fighter_tmaps[fr->tmap];
        for (u8 c = 0; c < FIGHTER_COLS; c++) {
            u8 src = f->facing > 0 ? c : FIGHTER_COLS - 1 - c;
            spr_column(f->spr + c, &map[src], FIGHTER_ROWS, FIGHTER_COLS, f->pal, f->facing < 0);
        }
        f->drawn_tmap = fr->tmap;
        f->drawn_facing = f->facing;
    }
    s16 sx = PX(f->x) - cam_x - FIGHTER_AX + shake;
    s16 sy = FLOOR_Y + PX(f->y) - FIGHTER_AY;
    spr_move(f->spr, sx, sy, FIGHTER_ROWS);
}
