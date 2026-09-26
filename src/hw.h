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
#define SPR_STAGE    1    // 7 capas x 21 columnas: 1..147
#define SPR_SHADOW   150  // 2 luchadores x 2 columnas
#define SPR_FIGHTER  156  // 2 luchadores x FIGHTER_HW_COLS (10) columnas: P2 156.., P1 166..
#define SPR_PROJ     178  // 2 proyectiles x 3 columnas
#define SPR_SPARK    184  // 2 chispas x 2 columnas
#define SPR_MSG      190  // mensajes grandes: hasta 16 letras x 2 columnas
// --- VFX del combate (src/fx.c, tools/neofx.py) ---
// 32 sprites desde 224: en el combate ese rango está libre (lo usan solo las
// pantallas previas, que reinician todo). Paletas: PAL_VFX0 (23) y 25..31.
#define SPR_VFX      224
#define SPR_VFX_N    32
#define PAL_VFX0     23
// --- fin VFX ---
// Pantallas previas (logos, título, selector): no conviven con el combate
// Fondo del título (usa el rango del escenario, que no está en pantalla)
#define SPR_TBG      1    // cielo: 20 columnas + corte
#define SPR_TBUST_L  24   // busto izquierdo: hasta 10 columnas + corte
#define SPR_TBUST_R  36   // busto derecho
#define SPR_LOGO     224  // logo o título: hasta 20 columnas + corte
#define SPR_FIRE     245  // fuego de FIERAS sobre el título: hasta 20 columnas + corte
#define SPR_PORTRAIT 248  // retratos del selector: 4 columnas cada uno
#define SPR_CURSOR   296  // 2 cursores x 4 columnas (+ corte)
// --- selector: fondo VS y bustos por lado (front.c) ---
// Mismo rango que el fondo del título (no conviven). Orden de atrás hacia
// adelante: fondo 1-21, bustos 24-46, luchadores 156-175, retratos 248+,
// cursores 296+, texto en el fix.
#define SPR_SBG      1    // degradé VS: 20 columnas + corte
#define SPR_SBUST    24   // busto del lado s en SPR_SBUST + s * SPR_SBUST_N
#define SPR_SBUST_N  12   // hasta 10 columnas + corte (+1 de margen)
#define PAL_SBUST    240  // paletas del busto del lado s: PAL_SBUST + s * PAL_SBUST_N
#define PAL_SBUST_N  4
// --- fin selector ---

// Paletas
#define PAL_TEXT     0
#define PAL_HUD      1
#define PAL_SKY      16
#define PAL_CITY     17
#define PAL_STREET   18
#define PAL_P1       19
#define PAL_P2       20
#define PAL_FX       21
#define PAL_MSG      22
#define PAL_PROJ     23
#define PAL_CROWD    24
#define PAL_CUR1     25   // cursor del selector, P1 (cyan)
#define PAL_CUR2     26   // cursor del selector, P2 (magenta)
#define PAL_UI       32   // paletas de tools/neoui.py (UI_PALS)
#define PAL_SHINE    96   // copias por columna para el barrido de brillo
// Fix layer: texto de colores (índice 1 color, 2 sombra)
#define PAL_TXT_CYAN 2
#define PAL_TXT_MAG  3
#define PAL_TXT_GOLD 4
#define PAL_TXT_GRAY 5

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

// Columna de un personaje: entradas con flips propios (ver character.h),
// desplazadas a tile_base. flip invierte el flip horizontal de cada tile.
static inline void spr_column_ct(u16 spr, const u16 *e, u8 count, u16 tile_base, u8 pal, u8 flip) {
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB1 + spr * 64;
    u16 attr = (u16)pal << 8;
    for (u8 i = 0; i < count; i++) {
        u16 v = e[i];
        *REG_VRAMRW = tile_base + (v & 0x3fff);
        *REG_VRAMRW = attr | ((v >> 14) ^ flip);
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
