// HUD en el fix layer: barras de vida, reloj con dígitos grandes, nombres,
// marcas de rounds ganados y mensajes centrales.
#include <ngdevkit/ng-fix.h>
#include <stdio.h>
#include "hud.h"
#include "hw.h"
#include "gen/assets.h"
#include "msg.h"

// La fuente base de ngdevkit ocupa 1280 tiles del S-ROM; hud.gif va después
// (ver regla SROM1 en el Makefile).
#define HUD_FIX_BASE 1280
#define T(n) (HUD_FIX_BASE + (n))

#define BAR_ROW 3               // filas 3 y 4: barra de 16 px de alto
#define BAR_TILES 14
#define BAR_PX (BAR_TILES * 8)
#define P1_BAR_COL 2
#define P2_BAR_COL 24
#define TIMER_COL 17

static u16 last_hp[2] = {0xffff, 0xffff};
static u16 drain[2], last_drain[2], drain_delay[2];
static u16 last_timer = 0xffff;
static u8 last_wins[2] = {0xff, 0xff};
static u8 combo_timer[2];

// Estado de un píxel de la barra: 0 lleno, 1 daño reciente, 2 vacío
static u8 px_state(u8 side, s16 x, s16 fill, s16 dfill) {
    if (side == 0) {                           // P1: lo lleno queda del lado del reloj
        if (x >= BAR_PX - fill) return 0;
        if (x >= BAR_PX - dfill) return 1;
        return 2;
    }
    if (x < fill) return 0;
    if (x < dfill) return 1;
    return 2;
}

static const char pair_names[6][2] = {{'E','D'}, {'D','F'}, {'E','F'}, {'F','D'}, {'D','E'}, {'F','E'}};
static const char state_names[3] = {'F', 'D', 'E'};

static void draw_bar(u8 side, u16 hp, u16 dr) {
    s16 fill = (s16)(hp * BAR_PX / 100), dfill = (s16)(dr * BAR_PX / 100);
    u8 col0 = side == 0 ? P1_BAR_COL : P2_BAR_COL;
    for (u8 i = 0; i < BAR_TILES; i++) {
        s16 a = i * 8;
        u8 s0 = px_state(side, a, fill, dfill), m = 0, s1 = s0;
        for (u8 k = 1; k < 8; k++) {
            u8 sk = px_state(side, a + k, fill, dfill);
            if (sk != s0) { m = k; s1 = sk; break; }
        }
        for (u8 row = 0; row < 2; row++) {
            u16 t;
            if (!m) {
                t = HUD_BAR_SOLID + s0 * 2 + row;
            } else {
                u8 pi = 0;
                for (u8 q = 0; q < 6; q++)
                    if (pair_names[q][0] == state_names[s0] && pair_names[q][1] == state_names[s1]) pi = q;
                t = HUD_BAR_EDGE + (pi * 7 + m - 1) * 2 + row;
            }
            fix_put(col0 + i, BAR_ROW + row, PAL_HUD, T(t));
        }
    }
}

static void draw_digit(u8 col, u8 d) {
    for (u8 r = 0; r < 4; r++)
        for (u8 c = 0; c < 3; c++)
            fix_put(col + c, 2 + r, PAL_HUD, T(HUD_DIGITS + d * 12 + r * 3 + c));
}

void hud_init(void) {
    ng_cls();
    for (u8 row = 0; row < 2; row++) {
        fix_put(P1_BAR_COL - 1, BAR_ROW + row, PAL_HUD, T(HUD_CAP_L));
        fix_put(P1_BAR_COL + BAR_TILES, BAR_ROW + row, PAL_HUD, T(HUD_CAP_R));
        fix_put(P2_BAR_COL - 1, BAR_ROW + row, PAL_HUD, T(HUD_CAP_L));
        fix_put(P2_BAR_COL + BAR_TILES, BAR_ROW + row, PAL_HUD, T(HUD_CAP_R));
    }
    ng_text(P1_BAR_COL, 5, PAL_TEXT, "BLAZE");
    ng_text(P2_BAR_COL + BAR_TILES - 5, 5, PAL_TEXT, "FROST");
    last_hp[0] = last_hp[1] = 0xffff;
    drain[0] = drain[1] = 100;
    last_drain[0] = last_drain[1] = 0xffff;
    drain_delay[0] = drain_delay[1] = 0;
    last_timer = 0xffff;
    last_wins[0] = last_wins[1] = 0xff;
    combo_timer[0] = combo_timer[1] = 0;
}

void hud_update(u16 hp1, u16 hp2, u16 timer, u8 wins1, u8 wins2) {
    u16 hp[2] = {hp1, hp2};
    for (u8 s = 0; s < 2; s++) {
        // el tramo de daño reciente espera 24 frames y después se vacía de a 1
        if (hp[s] > drain[s]) drain[s] = hp[s];
        if (hp[s] != last_hp[s]) drain_delay[s] = 24;
        if (drain[s] > hp[s]) {
            if (drain_delay[s]) drain_delay[s]--;
            else drain[s]--;
        }
        if (hp[s] != last_hp[s] || drain[s] != last_drain[s]) {
            draw_bar(s, hp[s], drain[s]);
            last_hp[s] = hp[s];
            last_drain[s] = drain[s];
        }
    }
    if (timer != last_timer) {
        draw_digit(TIMER_COL, (timer / 10) % 10);
        draw_digit(TIMER_COL + 3, timer % 10);
        last_timer = timer;
    }
    if (wins1 != last_wins[0] || wins2 != last_wins[1]) {
        // medallones de 16x16 bajo cada barra, del lado del reloj
        for (u8 i = 0; i < 2; i++) {
            u8 c1 = P1_BAR_COL + BAR_TILES - 2 - i * 3, c2 = P2_BAR_COL + i * 3;
            u16 b1 = HUD_MEDAL + (wins1 > i ? 4 : 0), b2 = HUD_MEDAL + (wins2 > i ? 4 : 0);
            for (u8 r = 0; r < 2; r++)
                for (u8 c = 0; c < 2; c++) {
                    fix_put(c1 + c, 5 + r, PAL_HUD, T(b1 + r * 2 + c));
                    fix_put(c2 + c, 5 + r, PAL_HUD, T(b2 + r * 2 + c));
                }
        }
        last_wins[0] = wins1;
        last_wins[1] = wins2;
    }
}

void hud_message(const char *msg) {
    if (msg) msg_show(msg);
    else msg_hide();
}

void hud_combo(u8 side, u16 hits) {
    char buf[12];
    snprintf(buf, sizeof(buf), "%u HITS", hits);
    ng_text_tall(side == 0 ? 2 : 29, 8, PAL_TEXT, buf);
    combo_timer[side] = 60;
}

void hud_tick(void) {
    msg_update();
    for (u8 s = 0; s < 2; s++) {
        if (combo_timer[s] && --combo_timer[s] == 0)
            ng_text_tall(s == 0 ? 2 : 29, 8, PAL_TEXT, "         ");
    }
}
