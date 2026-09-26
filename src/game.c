// Match: rounds, combate, cámara, proyectiles y HUD.
#include <ngdevkit/neogeo.h>
#include <ngdevkit/bios-ram.h>
#include <ngdevkit/ng-fix.h>
#include <ngdevkit/ng-video.h>
#include "game.h"
#include "hw.h"
#include "fighter.h"
#include "stage.h"
#include "fx.h"
#include "hud.h"
#include "ai.h"
#include "sound.h"

volatile game_t g;

#define USER_MODE_GAME 2
#define ROUND_TIME     60
#define PUSH_W         36
#define EDGE           20
#define DEMO_FRAMES    (60 * 40)

static fighter_t fs[2];
static s16 cam_x;
static u16 hitstop;
static u8 shake_side;
static u16 scroll[3];
static s16 cam_drawn;

static const attack_t fireball_atk = {ANIM_FIREBALL, 12, 18, 14, 8, 3, SND_HEAVY};

static void sync_obs(void) {
    for (u8 i = 0; i < 2; i++) {
        fighter_t *f = &fs[i];
        volatile obs_t *o = &g.p[i];
        o->x = PX(f->x); o->y = PX(f->y); o->hp = f->hp; o->state = f->state;
        o->anim = f->anim; o->fidx = f->fidx; o->facing = f->facing; o->wins = f->wins;
        o->hits_landed = f->hits_landed; o->hits_blocked = f->hits_blocked;
        o->specials = f->specials; o->combo = f->combo; o->max_combo = f->max_combo;
        o->cpu = f->cpu; o->joy = f->joy;
    }
    g.cam_x = cam_drawn;   // la cámara con la que se dibujó este frame
    g.hitstop = hitstop;
    g.scroll[0] = scroll[0]; g.scroll[1] = scroll[1]; g.scroll[2] = scroll[2];
}

static u8 overlap(s16 ax0, s16 ay0, s16 ax1, s16 ay1, s16 bx0, s16 by0, s16 bx1, s16 by1) {
    return ax0 < bx1 && bx0 < ax1 && ay0 < by1 && by0 < ay1;
}

// Resuelve un impacto de `a` (o de su proyectil) sobre `d`
static void resolve(fighter_t *a, fighter_t *d, const attack_t *atk, u8 flags, s16 cx, s16 cy) {
    u8 crouch = (d->joy & J_DOWN) != 0;
    u8 can_block = fighter_holding_back(d) && d->y == 0 &&
                   (fighter_actionable(d) || d->state == FS_BLOCK);
    if ((flags & FF_LOW) && !crouch) can_block = 0;
    if ((flags & FF_OVERHEAD) && crouch) can_block = 0;

    s32 push = FP(atk->push) * a->facing;
    if (can_block) {
        d->state = FS_BLOCK;
        d->crouch_block = crouch;
        d->stun = atk->blockstun;
        d->vx = 0;
        fighter_set_anim(d, crouch ? ANIM_CBLOCK : ANIM_BLOCK);
        a->hits_blocked++;
        fx_spark(cx, cy, 1);
        sound_cmd(SND_BLOCK);
        hitstop = atk->hitstop - 2;
        d->push = push / 2;
    } else {
        u8 was_stunned = d->state == FS_HIT || d->state == FS_KNOCKDOWN;
        d->hp = d->hp > atk->dmg ? d->hp - atk->dmg : 0;
        a->hits_landed++;
        a->combo = was_stunned ? a->combo + 1 : 1;
        if (a->combo > a->max_combo) a->max_combo = a->combo;
        if (a->combo >= 2) hud_combo(a->id, a->combo);
        if (d->hp == 0) {
            d->state = FS_KO;
            fighter_set_anim(d, ANIM_KO);
            d->vy = -FP(5);
            d->vx = a->facing * FP(2);
            sound_cmd(SND_KO);
            hitstop = 30;
        } else if (d->y < 0 || d->state == FS_AIR) {
            d->state = FS_KNOCKDOWN;
            fighter_set_anim(d, ANIM_KNOCKDOWN);
            d->vy = -FP(4);
            d->vx = a->facing * FP(2);
            hitstop = atk->hitstop;
        } else {
            d->state = FS_HIT;
            d->stun = atk->hitstun;
            d->vx = 0;
            fighter_set_anim(d, (d->joy & J_DOWN) ? ANIM_CHIT : ANIM_HIT);
            hitstop = atk->hitstop;
        }
        fx_spark(cx, cy, 0);
        sound_cmd(atk->sfx);
        d->push = push;
    }
    shake_side = d->id;
    // contra la pared, el que retrocede es el atacante (como en KOF)
    s16 dx = PX(d->x) - cam_x;
    if (dx <= EDGE + 2 || dx >= SCREEN_W - EDGE - 2) a->push = -push;
}

static void check_melee(fighter_t *a, fighter_t *d) {
    const frame_t *fr = fighter_frame(a);
    if (!(fr->flags & FF_ACTIVE) || a->hit_done || !fr->hit.w) return;
    if (d->state == FS_KO || d->state == FS_KNOCKDOWN) return;
    const attack_t *atk = fighter_attack(a);
    if (!atk) return;
    s16 hx0, hy0, hx1, hy1;
    fighter_world_box(a, &fr->hit, &hx0, &hy0, &hx1, &hy1);
    const frame_t *dfr = fighter_frame(d);
    const box_t *hurt[2] = {&dfr->hurt_hi, &dfr->hurt_lo};
    for (u8 i = 0; i < 2; i++) {
        s16 bx0, by0, bx1, by1;
        fighter_world_box(d, hurt[i], &bx0, &by0, &bx1, &by1);
        if (overlap(hx0, hy0, hx1, hy1, bx0, by0, bx1, by1)) {
            a->hit_done = 1;
            s16 cx = ((hx0 > bx0 ? hx0 : bx0) + (hx1 < bx1 ? hx1 : bx1)) / 2;
            s16 cy = ((hy0 > by0 ? hy0 : by0) + (hy1 < by1 ? hy1 : by1)) / 2;
            resolve(a, d, atk, fr->flags, cx, cy);
            return;
        }
    }
}

static void check_projectiles(void) {
    if (projs[0].active && projs[1].active) {
        s16 dx = PX(projs[0].x - projs[1].x);
        if (dx > -24 && dx < 24) {
            fx_spark(PX(projs[0].x) - dx / 2, projs[0].y, 1);
            projs[0].active = projs[1].active = 0;
            return;
        }
    }
    for (u8 o = 0; o < 2; o++) {
        proj_t *p = &projs[o];
        if (!p->active) continue;
        fighter_t *d = &fs[1 - o];
        if (d->state == FS_KO || d->state == FS_KNOCKDOWN) continue;
        s16 px = PX(p->x);
        const frame_t *dfr = fighter_frame(d);
        const box_t *hurt[2] = {&dfr->hurt_hi, &dfr->hurt_lo};
        for (u8 i = 0; i < 2; i++) {
            s16 bx0, by0, bx1, by1;
            fighter_world_box(d, hurt[i], &bx0, &by0, &bx1, &by1);
            if (overlap(px - 12, p->y - 12, px + 12, p->y + 12, bx0, by0, bx1, by1)) {
                p->active = 0;
                resolve(&fs[o], d, &fireball_atk, 0, px, p->y);
                break;
            }
        }
    }
}

static void separate_and_camera(void) {
    fighter_t *a = &fs[0], *b = &fs[1];
    if (a->y > FP(-50) && b->y > FP(-50)) {
        s16 dx = PX(b->x - a->x);
        s16 adx = dx < 0 ? -dx : dx;
        if (adx < PUSH_W) {
            s8 s = dx > 0 ? 1 : dx < 0 ? -1 : a->facing;
            s32 half = FP(PUSH_W - adx) / 2;
            a->x -= s * half;
            b->x += s * half;
        }
    }
    s16 mid = PX((a->x + b->x) >> 1);
    cam_x = mid - SCREEN_W / 2;
    if (cam_x < 0) cam_x = 0;
    if (cam_x > CAM_RANGE) cam_x = CAM_RANGE;
    for (u8 i = 0; i < 2; i++) {
        fighter_t *f = &fs[i];
        if (f->x < FP(cam_x + EDGE)) f->x = FP(cam_x + EDGE);
        if (f->x > FP(cam_x + SCREEN_W - EDGE)) f->x = FP(cam_x + SCREEN_W - EDGE);
    }
}

static void render(void) {
    cam_drawn = cam_x;
    stage_update(cam_x, scroll);
    s8 shake = (hitstop && (hitstop & 2)) ? 2 : 0;
    fighter_draw(&fs[1], cam_x, shake_side == 1 ? shake : 0);
    fighter_draw(&fs[0], cam_x, shake_side == 0 ? shake : 0);
    fx_draw(cam_x, &fs[0], &fs[1]);
    hud_update(fs[0].hp, fs[1].hp, g.timer, fs[0].wins, fs[1].wins);
    hud_tick();
}

static void read_inputs(u8 control, u8 demo) {
    if (!demo && fs[1].cpu && (bios_statchange & CNT_START2)) {
        fs[1].cpu = 0;                        // llegó un retador
    }
    for (u8 i = 0; i < 2; i++) {
        fighter_t *f = &fs[i];
        if (!control) { f->joy = 0; continue; }
        f->joy = f->cpu ? ai_input(f, &fs[1 - i]) : (i == 0 ? bios_p1current : bios_p2current);
    }
}

static void step(u8 control, u8 demo) {
    read_inputs(control, demo);
    if (hitstop) {
        hitstop--;
        return;
    }
    for (u8 i = 0; i < 2; i++) {
        fighter_t *f = &fs[i];
        fighter_update(f, &fs[1 - i], control, !projs[i].active);
        const frame_t *fr = fighter_frame(f);
        if (f->entered && (fr->flags & FF_SPAWN) && !projs[i].active) fx_spawn_projectile(f);
    }
    fighter_physics(&fs[0]);
    fighter_physics(&fs[1]);
    separate_and_camera();
    fx_update();
    check_melee(&fs[0], &fs[1]);
    check_melee(&fs[1], &fs[0]);
    check_projectiles();
}

static void setup_video(void) {
    ng_cls();
    hw_clear_sprites();
    hw_load_palette(PAL_HUD, pal_hud);
    hw_load_palette(PAL_SKY, pal_sky);
    hw_load_palette(PAL_CITY, pal_city);
    hw_load_palette(PAL_STREET, pal_street);
    hw_load_palette(PAL_P1, pal_fighter_p1);
    hw_load_palette(PAL_P2, pal_fighter_p2);
    hw_load_palette(PAL_FX, pal_fx);
    MMAP_PALBANK1[0] = 0x8000;
    MMAP_PALBANK1[1] = 0x7fff;
    MMAP_PALBANK1[2] = 0x0333;
    *REG_BACKDROP = 0x8000;
    stage_init();
    fx_init();
    // P2 usa sprites de índice menor: P1 se dibuja encima
    fighter_init(&fs[1], 1, SPR_FIGHTER, PAL_P2);
    fighter_init(&fs[0], 0, SPR_FIGHTER + FIGHTER_COLS, PAL_P1);
}

static void round_setup(void) {
    fighter_reset_round(&fs[0], STAGE_W / 2 - 70, 1);
    fighter_reset_round(&fs[1], STAGE_W / 2 + 70, -1);
    projs[0].active = projs[1].active = 0;
    cam_x = STAGE_W / 2 - SCREEN_W / 2;
    hitstop = 0;
    g.timer = ROUND_TIME;
    g.winner = 0;
    hud_init();
}

// Espera `frames` renderizando; en la demo corta si se apretó START.
static u8 hold_frames(u16 frames, u8 control, u8 demo) {
    for (u16 t = 0; t < frames; t++) {
        ng_wait_vblank();
        render();
        step(control, demo);
        g.frame++;
        sync_obs();
        if (demo && bios_user_mode == USER_MODE_GAME) return 1;
    }
    return 0;
}

u8 game_match(u8 demo, u8 p1_human, u8 p2_human) {
    g.magic = GAME_MAGIC;
    g.mode = demo ? MODE_DEMO : MODE_MATCH;
    setup_video();
    fs[0].cpu = !p1_human;
    fs[1].cpu = !p2_human;
    ai_seed(demo ? 0x1998 : 0x2000);
    g.round = 1;
    u16 demo_left = DEMO_FRAMES;

    while (fs[0].wins < 2 && fs[1].wins < 2 && g.round <= 5) {
        round_setup();
        if (demo) ng_center_text(24, PAL_TEXT, "PRESS START");

        g.rstate = RS_INTRO;
        char msg[10] = "ROUND 1";
        msg[6] = '0' + g.round;
        hud_message(msg);
        if (hold_frames(50, 0, demo)) return 1;
        hud_message("FIGHT!");
        if (hold_frames(40, 0, demo)) return 1;
        hud_message(0);
        fs[0].state = fs[1].state = FS_IDLE;

        g.rstate = RS_FIGHT;
        u16 sec = 0;
        while (fs[0].hp && fs[1].hp && g.timer) {
            ng_wait_vblank();
            render();
            step(1, demo);
            g.frame++;
            if (++sec == 60) { sec = 0; g.timer--; }
            sync_obs();
            if (demo) {
                if (bios_user_mode == USER_MODE_GAME) return 1;
                if ((g.frame & 31) == 0) ng_center_text(24, PAL_TEXT, (g.frame & 32) ? "           " : "PRESS START");
                if (!--demo_left) return 0;
            }
        }

        // fin de round
        fighter_t *win = 0;
        if (!fs[1].hp && fs[0].hp) win = &fs[0];
        else if (!fs[0].hp && fs[1].hp) win = &fs[1];
        else if (!g.timer && fs[0].hp != fs[1].hp) win = fs[0].hp > fs[1].hp ? &fs[0] : &fs[1];
        g.rstate = g.timer ? RS_KO : RS_TIMEUP;
        hud_message(g.timer ? "K.O." : "TIME OVER");
        if (hold_frames(120, 0, demo)) return 1;
        if (win) {
            win->wins++;
            win->state = FS_WIN;
            fighter_set_anim(win, ANIM_WIN);
            g.winner = win->id + 1;
        }
        hud_message(win ? (win->id == 0 ? "BLAZE WINS" : "FROST WINS") : "DRAW");
        g.rstate = RS_END;
        if (hold_frames(90, 0, demo)) return 1;
        g.round++;
    }
    g.mode = MODE_MATCH_END;
    hud_message(fs[0].wins > fs[1].wins ? "BLAZE WINS MATCH" : "FROST WINS MATCH");
    hold_frames(150, 0, 0);
    return 0;
}
