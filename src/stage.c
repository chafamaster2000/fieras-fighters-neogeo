// Escenario con parallax: cielo (4/16 de la cámara), ciudad (8/16) y el piso
// partido en 5 franjas horizontales que van de 10/16 a 18/16. Las franjas
// del piso imitan el line-scroll de los juegos de pelea de Neo Geo: al mover
// la cámara las juntas de las baldosas "giran" como un plano en perspectiva.
// Las franjas no se superponen en vertical, así que no suman sprites por línea.
//
// Cada capa usa 21 sprites de hardware. La columna k de la imagen vive en el
// sprite k % 21 y solo se recarga cuando la cámara cruza un borde de 16 px.
//
// La ciudad lleva el público animado por hardware: sus tiles salen de
// city_map, y los de la tribuna tienen el bit de auto-animación de 4 cuadros
// (bit 2 del atributo SCB1). El LSPC cambia los 2 bits bajos del número de
// tile cada CROWD_ANIM_SPEED+1 frames, sin CPU ni sprites extra.
#include "stage.h"
#include "hw.h"
#include "gen/assets.h"
#include "gen/stage_gen.h"

#define HW_COLS 21

typedef struct { u16 tile; u8 cols, rows, num; s16 y; } layer_def_t;
static const layer_def_t defs[] = { LAYER_TABLE };
#define NLAYERS (sizeof(defs) / sizeof(defs[0]))

static s16 loaded[NLAYERS][HW_COLS];

static u16 layer_spr(u8 i) { return SPR_STAGE + i * HW_COLS; }
static u8 layer_pal(u8 i) { return i == 0 ? PAL_SKY : i == LAYER_CITY ? PAL_CITY : PAL_STREET; }

static void load_column(u8 i, u16 hw, s16 k) {
    const layer_def_t *l = &defs[i];
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB1 + (layer_spr(i) + hw) * 64;
    if (i == LAYER_CITY) {
        const u16 *m = &city_map[k];
        for (u8 r = 0; r < l->rows; r++, m += l->cols) {
            u16 e = *m;
            *REG_VRAMRW = l->tile + (e & 0x3fff);
            *REG_VRAMRW = ((u16)((e & 0x8000) ? PAL_CROWD : PAL_CITY) << 8) | ((e >> 12) & 4);
        }
    } else {
        u16 tile = l->tile + k;
        for (u8 r = 0; r < l->rows; r++, tile += l->cols) {
            *REG_VRAMRW = tile;
            *REG_VRAMRW = (u16)layer_pal(i) << 8;
        }
    }
    loaded[i][hw] = k;
}

void stage_init(void) {
    // velocidad de la auto-animación (bits 15-8); el resto en 0: animación
    // activa y sin interrupción de timer
    *REG_LSPCMODE = (u16)CROWD_ANIM_SPEED << 8;
    for (u8 i = 0; i < NLAYERS; i++)
        for (u16 h = 0; h < HW_COLS; h++) {
            loaded[i][h] = -1;
            spr_shape(layer_spr(i) + h, 400, defs[i].y, defs[i].rows, 0);
        }
}

void stage_update(s16 cam_x, u16 *scroll_out) {
    for (u8 i = 0; i < NLAYERS; i++) {
        const layer_def_t *l = &defs[i];
        s16 scroll = (s16)(((s32)cam_x * l->num) >> 4);
        if (i == 0) scroll_out[0] = scroll;
        if (i == 1) scroll_out[1] = scroll;
        if (l->num == 16) scroll_out[2] = scroll;
        s16 c0 = scroll >> 4;
        for (s16 n = 0; n < HW_COLS; n++) {
            s16 k = c0 + n;
            u16 hw = k % HW_COLS;
            s16 x = 400;
            if (k < l->cols) {
                if (loaded[i][hw] != k) load_column(i, hw, k);
                x = k * 16 - scroll;
            }
            *REG_VRAMMOD = 1;
            *REG_VRAMADDR = ADDR_SCB4 + layer_spr(i) + hw;
            *REG_VRAMRW = (u16)((x & 0x1ff) << 7);
        }
    }
}
