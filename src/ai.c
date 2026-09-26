// CPU simple y determinística: se acerca, golpea, bloquea y tira proyectiles.
// Usa secuencias de joystick de varios frames (por ejemplo el cuarto de
// círculo + A) para ejercitar el mismo camino de entrada que un humano.
#include "ai.h"
#include "fx.h"

static u16 rng_state = 0x5eed;

void ai_seed(u16 seed) { rng_state = seed ? seed : 0x5eed; }

u16 ai_rng(void) {
    rng_state ^= rng_state << 7;
    rng_state ^= rng_state >> 9;
    rng_state ^= rng_state << 8;
    return rng_state;
}

static void queue(fighter_t *f, const u8 *seq, u8 n) {
    for (u8 i = 0; i < n && i < sizeof(f->ai_seq); i++) f->ai_seq[i] = seq[i];
    f->ai_seq_len = n;
    f->ai_seq_pos = 0;
}

static void hold(fighter_t *f, u8 joy, u8 frames) {
    f->ai_hold = joy;
    f->ai_timer = frames;
}

u8 ai_input(fighter_t *f, const fighter_t *opp) {
    if (f->ai_seq_pos < f->ai_seq_len) return f->ai_seq[f->ai_seq_pos++];
    if (f->ai_timer) { f->ai_timer--; return f->ai_hold; }

    u8 fwd = opp->x >= f->x ? J_RIGHT : J_LEFT;
    u8 back = fwd == J_RIGHT ? J_LEFT : J_RIGHT;
    s16 dist = PX(opp->x - f->x);
    if (dist < 0) dist = -dist;
    u8 r = ai_rng() % 100;

    const proj_t *enemy = &projs[opp->id];
    s16 pdist = 999;
    if (enemy->active) {
        pdist = PX(enemy->x - f->x);
        if (pdist < 0) pdist = -pdist;
    }
    u8 threatened = (opp->state == FS_ATTACK && dist < 110) || pdist < 110;

    if (threatened && r < 55) {
        u8 low = opp->anim == ANIM_CPUNCH;
        hold(f, back | (low ? J_DOWN : 0), 14);
    } else if (pdist < 150 && r < 75) {
        const u8 seq[] = {J_UP | fwd, J_UP | fwd, J_UP | fwd, 0, 0, 0, 0, 0, 0, 0, J_B};
        queue(f, seq, sizeof(seq));
    } else if (dist > 170) {
        if (r < 22 && !projs[f->id].active) {
            const u8 seq[] = {J_DOWN, J_DOWN, J_DOWN | fwd, J_DOWN | fwd, fwd, fwd | J_A, fwd};
            queue(f, seq, sizeof(seq));
        } else {
            hold(f, fwd, 16);
        }
    } else if (dist > 72) {
        if (r < 15) {
            const u8 seq[] = {J_UP | fwd, J_UP | fwd, 0, 0, 0, 0, 0, 0, 0, 0, J_B};
            queue(f, seq, sizeof(seq));
        } else if (r < 30 && !projs[f->id].active) {
            const u8 seq[] = {J_DOWN, J_DOWN, J_DOWN | fwd, J_DOWN | fwd, fwd, fwd | J_A, fwd};
            queue(f, seq, sizeof(seq));
        } else if (r < 75) {
            hold(f, fwd, 10);
        } else {
            hold(f, 0, 8);
        }
    } else {
        if (r < 30) { const u8 seq[] = {0, J_A}; queue(f, seq, 2); hold(f, 0, 10); }
        else if (r < 55) { const u8 seq[] = {0, J_B}; queue(f, seq, 2); hold(f, 0, 14); }
        else if (r < 70) { const u8 seq[] = {J_DOWN, J_DOWN | J_A}; queue(f, seq, 2); hold(f, J_DOWN, 10); }
        else if (r < 82) hold(f, back, 12);
        else hold(f, back | J_DOWN, 12);
    }
    return f->ai_timer ? f->ai_hold : 0;
}
