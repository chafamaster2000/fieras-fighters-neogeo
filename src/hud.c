// HUD en el fix layer: barras de vida, reloj con dígitos grandes, nombres,
// marcas de rounds ganados y mensajes centrales.
#include <ngdevkit/ng-fix.h>
#include <stdio.h>
#include "hud.h"
#include "hw.h"
#include "gen/assets.h"

// La fuente base de ngdevkit ocupa 1280 tiles del S-ROM; hud.gif va después
// (ver regla SROM1 en el Makefile).
#define HUD_FIX_BASE 1280
#define T(n) (HUD_FIX_BASE + (n))

#define BAR_ROW 3
#define BAR_TILES 15
#define BAR_PX (BAR_TILES * 8)
#define P1_BAR_COL 2
#define P2_BAR_COL 23
#define TIMER_COL 18
#define MSG_ROW 12

static u16 last_hp[2] = {0xffff, 0xffff};
static u16 last_timer = 0xffff;
static u8 last_wins[2] = {0xff, 0xff};
static u8 combo_timer[2];

static void draw_bar(u8 side, u16 hp) {
    u16 fill = (u16)(hp * BAR_PX / 100);
    for (u8 i = 0; i < BAR_TILES; i++) {
        u16 t;
        if (side == 0) {                       // P1: lo lleno queda del lado del reloj
            s16 start = BAR_PX - fill;         // primer px lleno
            s16 a = i * 8, b = a + 8;
            if (a >= start) t = HUD_BAR_FULL;
            else if (b <= start) t = HUD_BAR_EMPTY;
            else t = HUD_P1_PART + (b - start) - 1;
            fix_put(P1_BAR_COL + i, BAR_ROW, PAL_HUD, T(t));
        } else {                               // P2: espejo
            s16 a = i * 8, b = a + 8;
            if (b <= (s16)fill) t = HUD_BAR_FULL;
            else if (a >= (s16)fill) t = HUD_BAR_EMPTY;
            else t = HUD_P2_PART + (fill - a) - 1;
            fix_put(P2_BAR_COL + i, BAR_ROW, PAL_HUD, T(t));
        }
    }
}

static void draw_digit(u8 col, u8 d) {
    for (u8 r = 0; r < 3; r++)
        for (u8 c = 0; c < 2; c++)
            fix_put(col + c, 2 + r, PAL_HUD, T(HUD_DIGITS + d * 6 + r * 2 + c));
}

void hud_init(void) {
    ng_cls();
    fix_put(P1_BAR_COL - 1, BAR_ROW, PAL_HUD, T(HUD_CAP_L));
    fix_put(P1_BAR_COL + BAR_TILES, BAR_ROW, PAL_HUD, T(HUD_CAP_R));
    fix_put(P2_BAR_COL - 1, BAR_ROW, PAL_HUD, T(HUD_CAP_L));
    fix_put(P2_BAR_COL + BAR_TILES, BAR_ROW, PAL_HUD, T(HUD_CAP_R));
    ng_text(P1_BAR_COL, 5, PAL_TEXT, "BLAZE");
    ng_text(P2_BAR_COL + BAR_TILES - 5, 5, PAL_TEXT, "FROST");
    last_hp[0] = last_hp[1] = 0xffff;
    last_timer = 0xffff;
    last_wins[0] = last_wins[1] = 0xff;
    combo_timer[0] = combo_timer[1] = 0;
}

void hud_update(u16 hp1, u16 hp2, u16 timer, u8 wins1, u8 wins2) {
    if (hp1 != last_hp[0]) { draw_bar(0, hp1); last_hp[0] = hp1; }
    if (hp2 != last_hp[1]) { draw_bar(1, hp2); last_hp[1] = hp2; }
    if (timer != last_timer) {
        draw_digit(TIMER_COL, (timer / 10) % 10);
        draw_digit(TIMER_COL + 2, timer % 10);
        last_timer = timer;
    }
    if (wins1 != last_wins[0] || wins2 != last_wins[1]) {
        for (u8 i = 0; i < 2; i++) {
            fix_put(P1_BAR_COL + BAR_TILES - 1 - i, 5, PAL_HUD, T(wins1 > i ? HUD_WIN_ON : HUD_WIN_OFF));
            fix_put(P2_BAR_COL + i, 5, PAL_HUD, T(wins2 > i ? HUD_WIN_ON : HUD_WIN_OFF));
        }
        last_wins[0] = wins1;
        last_wins[1] = wins2;
    }
}

void hud_message(const char *msg) {
    ng_center_text_tall(MSG_ROW, PAL_TEXT, "                    ");
    if (msg) ng_center_text_tall(MSG_ROW, PAL_TEXT, msg);
}

void hud_combo(u8 side, u16 hits) {
    char buf[12];
    snprintf(buf, sizeof(buf), "%u HITS", hits);
    ng_text_tall(side == 0 ? 2 : 29, 8, PAL_TEXT, buf);
    combo_timer[side] = 60;
}

void hud_tick(void) {
    for (u8 s = 0; s < 2; s++) {
        if (combo_timer[s] && --combo_timer[s] == 0)
            ng_text_tall(s == 0 ? 2 : 29, 8, PAL_TEXT, "         ");
    }
}
