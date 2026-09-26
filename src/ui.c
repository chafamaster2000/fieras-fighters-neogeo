// Imágenes de UI, fundidos y brillos. Los efectos son los de la época:
// todo por paleta (fundidos, destellos a blanco, barrido de brillo) y por
// el zoom de hardware del LSPC (SCB2), sin redibujar tiles.
#include "ui.h"
#include "hw.h"

#define FADE_MAX 64
#define SHINE_W  28               // media franja del barrido, en px

static u8 fn;
static u8 f_idx[FADE_MAX], f_cap[FADE_MAX];
static const u16 *f_src[FADE_MAX];

// canal de 5 bits mezclado hacia negro / blanco en 17 niveles (sin mul del 68000)
static const u8 mix_b[17][32] = {
    {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0},
    {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1},
    {0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,3,3,3,3,3,3,3,3},
    {0,0,0,0,0,0,1,1,1,1,1,2,2,2,2,2,3,3,3,3,3,3,4,4,4,4,4,5,5,5,5,5},
    {0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,6,6,6,6,7,7,7,7},
    {0,0,0,0,1,1,1,2,2,2,3,3,3,4,4,4,5,5,5,5,6,6,6,7,7,7,8,8,8,9,9,9},
    {0,0,0,1,1,1,2,2,3,3,3,4,4,4,5,5,6,6,6,7,7,7,8,8,9,9,9,10,10,10,11,11},
    {0,0,0,1,1,2,2,3,3,3,4,4,5,5,6,6,7,7,7,8,8,9,9,10,10,10,11,11,12,12,13,13},
    {0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13,14,14,15,15},
    {0,0,1,1,2,2,3,3,4,5,5,6,6,7,7,8,9,9,10,10,11,11,12,12,13,14,14,15,15,16,16,17},
    {0,0,1,1,2,3,3,4,5,5,6,6,7,8,8,9,10,10,11,11,12,13,13,14,15,15,16,16,17,18,18,19},
    {0,0,1,2,2,3,4,4,5,6,6,7,8,8,9,10,11,11,12,13,13,14,15,15,16,17,17,18,19,19,20,21},
    {0,0,1,2,3,3,4,5,6,6,7,8,9,9,10,11,12,12,13,14,15,15,16,17,18,18,19,20,21,21,22,23},
    {0,0,1,2,3,4,4,5,6,7,8,8,9,10,11,12,13,13,14,15,16,17,17,18,19,20,21,21,22,23,24,25},
    {0,0,1,2,3,4,5,6,7,7,8,9,10,11,12,13,14,14,15,16,17,18,19,20,21,21,22,23,24,25,26,27},
    {0,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29},
    {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31},
};
static const u8 mix_w[17][32] = {
    {0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31},
    {1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31},
    {3,4,5,6,7,8,9,10,10,11,12,13,14,15,16,17,17,18,19,20,21,22,23,24,24,25,26,27,28,29,30,31},
    {5,6,7,8,9,9,10,11,12,13,13,14,15,16,17,18,18,19,20,21,22,22,23,24,25,26,26,27,28,29,30,31},
    {7,8,9,10,10,11,12,13,13,14,15,16,16,17,18,19,19,20,21,22,22,23,24,25,25,26,27,28,28,29,30,31},
    {9,10,11,11,12,13,13,14,15,15,16,17,17,18,19,20,20,21,22,22,23,24,24,25,26,26,27,28,28,29,30,31},
    {11,12,12,13,14,14,15,16,16,17,17,18,19,19,20,21,21,22,22,23,24,24,25,26,26,27,27,28,29,29,30,31},
    {13,14,14,15,15,16,16,17,18,18,19,19,20,20,21,22,22,23,23,24,24,25,25,26,27,27,28,28,29,29,30,31},
    {15,16,16,17,17,18,18,19,19,20,20,21,21,22,22,23,23,24,24,25,25,26,26,27,27,28,28,29,29,30,30,31},
    {17,17,18,18,19,19,20,20,20,21,21,22,22,23,23,24,24,24,25,25,26,26,27,27,27,28,28,29,29,30,30,31},
    {19,19,20,20,20,21,21,22,22,22,23,23,23,24,24,25,25,25,26,26,26,27,27,28,28,28,29,29,29,30,30,31},
    {21,21,21,22,22,22,23,23,23,24,24,24,25,25,25,26,26,26,26,27,27,27,28,28,28,29,29,29,30,30,30,31},
    {23,23,23,24,24,24,24,25,25,25,25,26,26,26,26,27,27,27,27,28,28,28,28,29,29,29,29,30,30,30,30,31},
    {25,25,25,25,25,26,26,26,26,26,27,27,27,27,27,28,28,28,28,28,28,29,29,29,29,29,30,30,30,30,30,31},
    {27,27,27,27,27,27,27,28,28,28,28,28,28,28,28,29,29,29,29,29,29,29,29,30,30,30,30,30,30,30,30,31},
    {29,29,29,29,29,29,29,29,29,29,29,29,29,29,29,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30,31},
    {31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31,31},
};

u16 col_mix(u16 c, u8 level, u8 white) {
    const u8 *t = white ? mix_w[level] : mix_b[level];
    u8 r = t[((c >> 7) & 0x1e) | ((c >> 14) & 1)];
    u8 g = t[((c >> 3) & 0x1e) | ((c >> 13) & 1)];
    u8 b = t[((c << 1) & 0x1e) | ((c >> 12) & 1)];
    return (u16)(((r & 1) << 14) | ((g & 1) << 13) | ((b & 1) << 12) |
                 ((r >> 1) << 8) | ((g >> 1) << 4) | (b >> 1));
}

void fade_clear(void) { fn = 0; }

void fade_add(u8 hw_pal, const u16 *src, u8 cap) {
    for (u8 i = 0; i < fn; i++)
        if (f_idx[i] == hw_pal) { f_src[i] = src; f_cap[i] = cap; return; }
    if (fn == FADE_MAX) return;
    f_idx[fn] = hw_pal; f_src[fn] = src; f_cap[fn] = cap; fn++;
}

void fade_apply(u8 level) {
    for (u8 i = 0; i < fn; i++) {
        volatile u16 *dst = MMAP_PALBANK1 + f_idx[i] * 16;
        u8 l = (u8)(((u16)level * f_cap[i]) >> 4);
        for (u8 k = 1; k < 16; k++) dst[k] = col_mix(f_src[i][k], l, 0);
    }
}

void fade_flash(u8 level) {
    for (u8 i = 0; i < fn; i++) {
        volatile u16 *dst = MMAP_PALBANK1 + f_idx[i] * 16;
        for (u8 k = 1; k < 16; k++) {
            u16 c = f_cap[i] < 16 ? col_mix(f_src[i][k], f_cap[i], 0) : f_src[i][k];
            dst[k] = col_mix(c, level, 1);
        }
    }
}

u8 ui_hw_pal(u8 img) { return PAL_UI + ui_imgs[img].pal0; }

void ui_palettes(u8 img, u8 cap) {
    const uiimg_t *im = &ui_imgs[img];
    for (u8 p = 0; p < im->npal; p++) {
        hw_load_palette(PAL_UI + im->pal0 + p, ui_pals[im->pal0 + p]);
        fade_add(PAL_UI + im->pal0 + p, ui_pals[im->pal0 + p], cap);
    }
}

static void load_cols(u8 img, u16 spr, u8 shine, u8 fixed, u8 flip) {
    const uiimg_t *im = &ui_imgs[img];
    for (u8 c = 0; c < im->w; c++) {
        const u16 *m = &ui_map[im->first + (flip ? im->w - 1 - c : c) * im->h];
        *REG_VRAMMOD = 1;
        *REG_VRAMADDR = ADDR_SCB1 + (spr + c) * 64;
        for (u8 r = 0; r < im->h; r++, m++) {
            u8 pal = fixed ? fixed : shine ? PAL_SHINE + c * im->npal + (*m >> 12) : PAL_UI + im->pal0 + (*m >> 12);
            // bit 11: grupo de 8 cuadros, el LSPC anima los 3 bits bajos del tile
            *REG_VRAMRW = TILE_UI + (*m & 0x07ff);
            *REG_VRAMRW = ((u16)pal << 8) | ((*m & 0x0800) ? 8 : 0) | flip;
        }
        // con zoom vertical el LSPC puede leer los 32 slots de la columna:
        // los que sobran apuntan al tile vacío de la UI
        for (u8 r = im->h; r < 32; r++) {
            *REG_VRAMRW = TILE_UI;
            *REG_VRAMRW = 0;
        }
        spr_shape(spr + c, 0, 0, im->h, c != 0);
    }
    // cortar la cadena después de la última columna
    spr_shape(spr + im->w, 0, 0, 0, 0);
}

void ui_load(u8 img, u16 spr, u8 shine) { load_cols(img, spr, shine, 0, 0); }
void ui_load_flip(u8 img, u16 spr, u8 flip) { load_cols(img, spr, 1, 0, flip); }
void ui_load_as(u8 img, u16 spr, u8 pal) { load_cols(img, spr, 0, pal, 0); }

void ui_place(u8 img, u16 spr, s16 cx, s16 cy, u8 hz, u8 vz) {
    const uiimg_t *im = &ui_imgs[img];
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB2 + spr;
    for (u8 c = 0; c < im->w; c++) *REG_VRAMRW = ((u16)hz << 8) | vz;
    s16 w = (s16)im->w * (hz + 1);
    s16 h = (s16)(((u32)im->h * 16 * (vz + 1)) >> 8);
    spr_move(spr, cx - w / 2, cy - h / 2, im->h);
}

void ui_hide(u16 spr) { spr_hide(spr); }

void ui_put(u8 img, u16 spr, s16 dx, s16 dy) {
    const uiimg_t *im = &ui_imgs[img];
    spr_move(spr, im->x + dx, im->y + dy, im->h);
}

// ---- barrido de brillo por columna

static u16 shine_last[20];

void ui_shine_reset(void) {
    for (u8 c = 0; c < 20; c++) shine_last[c] = 0xffff;
}

void ui_shine(u8 img, s16 pos, u8 glow, u8 level) {
    // cada nivel de brillo distinto se calcula una sola vez por llamada y
    // después se copia a las columnas que lo usan (el 68000 no da para más)
    static u16 buf[17][6][16];
    u32 have = 0;
    const uiimg_t *im = &ui_imgs[img];
    u8 np = im->npal > 6 ? 6 : im->npal;
    for (u8 c = 0; c < im->w && c < 20; c++) {
        s16 d = (s16)c * 16 + 8 - pos;
        if (d < 0) d = -d;
        u8 s = d < SHINE_W ? (u8)(((SHINE_W - d) * 11) / SHINE_W) : 0;
        if (glow > s) s = glow;
        u16 key = (u16)(s | (level << 8));
        if (key == shine_last[c]) continue;
        shine_last[c] = key;
        if (!(have & (1ul << s))) {
            have |= 1ul << s;
            for (u8 p = 0; p < np; p++) {
                const u16 *src = ui_pals[im->pal0 + p];
                for (u8 k = 1; k < 16; k++) {
                    u16 v = level >= 16 ? src[k] : col_mix(src[k], level, 0);
                    buf[s][p][k] = s ? col_mix(v, s, 1) : v;
                }
            }
        }
        for (u8 p = 0; p < np; p++) {
            volatile u16 *dst = MMAP_PALBANK1 + (PAL_SHINE + c * im->npal + p) * 16;
            const u16 *b = buf[s][p];
            for (u8 k = 1; k < 16; k++) dst[k] = b[k];
        }
    }
}
