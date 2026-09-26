#ifndef HW_H
#define HW_H
// Helpers mínimos sobre VRAM, paletas y fix layer de la Neo Geo.
// Ref: https://wiki.neogeodev.org/index.php?title=Sprites
#include <ngdevkit/neogeo.h>

#define SCREEN_W 320
#define SCREEN_H 224
#define MAX_SPRITES 381
#define REG_BACKDROP ((volatile u16*)0x401ffe)
#define ADDR_FIXMAP 0x7000

// Índices de sprite (SCB). Mayor índice = se dibuja encima.
#define SPR_SKY      1    // 21 columnas
#define SPR_CITY     22   // 21 columnas
#define SPR_STREET   43   // 21 columnas
#define SPR_SHADOW   66   // 2 luchadores x 2 columnas
#define SPR_FIGHTER  72   // 2 luchadores x 7 columnas (P2 72.., P1 79..)
#define SPR_PROJ     90   // 2 proyectiles x 2 columnas
#define SPR_SPARK    96   // 2 chispas x 2 columnas

// Paletas
#define PAL_TEXT     0
#define PAL_HUD      1
#define PAL_SKY      16
#define PAL_CITY     17
#define PAL_STREET   18
#define PAL_P1       19
#define PAL_P2       20
#define PAL_FX       21

static inline u16 scb3(s16 y, u8 height) {
    return (u16)((((496 - y) & 0x1ff) << 7) | (height & 0x3f));
}

static inline void spr_shape(u16 spr, s16 x, s16 y, u8 height, u8 sticky) {
    *REG_VRAMMOD = 0x200;
    *REG_VRAMADDR = ADDR_SCB2 + spr;
    *REG_VRAMRW = 0x0fff;
    *REG_VRAMRW = sticky ? (1 << 6) : scb3(y, height);
    if (!sticky) *REG_VRAMRW = (u16)((x & 0x1ff) << 7);
}

static inline void spr_move(u16 spr, s16 x, s16 y, u8 height) {
    *REG_VRAMMOD = 0x200;
    *REG_VRAMADDR = ADDR_SCB3 + spr;
    *REG_VRAMRW = scb3(y, height);
    *REG_VRAMRW = (u16)((x & 0x1ff) << 7);
}

static inline void spr_hide(u16 spr) {
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB3 + spr;
    *REG_VRAMRW = 0;
}

// Columna vertical de tiles (SCB1) para un sprite
static inline void spr_column(u16 spr, const u16 *tiles, u8 count, u16 stride, u8 pal, u8 flip) {
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB1 + spr * 64;
    u16 attr = ((u16)pal << 8) | flip;
    for (u8 i = 0; i < count; i++) {
        *REG_VRAMRW = tiles[i * stride];
        *REG_VRAMRW = attr;
    }
}

static inline void fix_put(u8 col, u8 row, u8 pal, u16 tile) {
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_FIXMAP + col * 32 + row;
    *REG_VRAMRW = ((u16)pal << 12) | tile;
}

void hw_load_palette(u8 index, const u16 *pal);
void hw_clear_sprites(void);
#endif
