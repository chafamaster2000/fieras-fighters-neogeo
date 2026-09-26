#include "msg.h"
#include "hw.h"
#include "gen/assets.h"

#define MAX_CHARS 16
#define MSG_Y     70            // centro vertical: debajo del HUD, sobre las cabezas

static u8 len, t, active, hmax;
static u8 narrow[MAX_CHARS];          // puntos: la mitad de ancho

static void set_zoom(u8 h, u8 v) {
    if (h > hmax) h = hmax;
    u16 w = (u16)len * 2 * (h + 1);           // ancho total en px
    u16 hgt = (32 * ((u16)v + 1)) >> 8;       // alto visible en px
    u8 hn = h >> 1;
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB2 + SPR_MSG;
    for (u8 i = 0; i < len * 2; i++) *REG_VRAMRW = ((u16)(narrow[i >> 1] ? hn : h) << 8) | v;
    for (u8 i = 0; i < len; i++) if (narrow[i]) w -= 2 * (h - hn);
    spr_move(SPR_MSG, (SCREEN_W - (s16)w) / 2, MSG_Y - (s16)hgt / 2, 2);
}

void msg_show(const char *text) {
    len = 0;
    for (const char *c = text; *c && len < MAX_CHARS; c++, len++) {
        u8 ch = (u8)*c;
        u8 gi = (ch >= 32 && ch < 128) ? font_map[ch - 32] : 0;
        narrow[len] = ch == '.';
        for (u8 half = 0; half < 2; half++) {
            u16 tiles[2] = {TILE_FONT + gi * 2 + half, TILE_FONT + FONT_GLYPHS * 2 + gi * 2 + half};
            u16 spr = SPR_MSG + len * 2 + half;
            spr_column(spr, tiles, 2, 1, PAL_MSG, 0);
            if (spr != SPR_MSG) spr_shape(spr, 0, 0, 2, 1);
        }
    }
    // cortar la cadena: el sprite siguiente deja de estar pegado y queda oculto
    spr_shape(SPR_MSG + len * 2, 0, 0, 0, 0);
    // ancho máximo 304 px: textos largos se achican con el zoom horizontal
    u16 per = 304 / ((u16)len * 2);
    hmax = per >= 16 ? 15 : (u8)(per - 1);
    t = 0;
    active = 1;
    set_zoom(1, 40);
}

void msg_hide(void) {
    active = 0;
    spr_hide(SPR_MSG);
}

static const u16 flash_pal[16] = {0x8000, 0x8000, 0x7fff, 0x7fff, 0x7fff, 0x7ffe, 0x7ffd, 0x7fdd,
                                   0, 0, 0, 0, 0, 0, 0, 0};
extern const u16 pal_msg[16];

void msg_update(void) {
    if (!active) return;
    if (t < 14) hw_load_palette(PAL_MSG, (t & 2) ? flash_pal : pal_msg);
    else if (t == 14) hw_load_palette(PAL_MSG, pal_msg);
    if (t >= 8) { if (t < 15) t++; return; }
    t++;
    // de chico a tamaño completo en 8 frames, con un leve rebote al final
    static const u8 hz[8] = {3, 6, 9, 12, 15, 15, 14, 15};
    static const u8 vz[8] = {70, 120, 170, 220, 255, 255, 235, 255};
    set_zoom(hz[t - 1], vz[t - 1]);
}
