// Escenario de tres capas con parallax (cielo 1/4, ciudad 1/2, calle 1).
// Cada capa usa 21 sprites de hardware. La imagen de la capa es más ancha
// que la pantalla: la columna k de la imagen vive en el sprite k % 21, y
// cuando la cámara cruza un borde de 16 px solo se recarga esa columna.
#include "stage.h"
#include "hw.h"
#include "gen/assets.h"

#define HW_COLS 21

typedef struct {
    u16 spr;
    u16 tile;
    u8 cols, rows, shift, pal;
    s16 y;
    s16 loaded[HW_COLS];
} layer_t;

static layer_t layers[NUM_LAYERS] = {
    {SPR_SKY, TILE_SKY, LAYER_SKY_COLS, LAYER_SKY_ROWS, LAYER_SKY_SHIFT, PAL_SKY, LAYER_SKY_Y, {0}},
    {SPR_CITY, TILE_CITY, LAYER_CITY_COLS, LAYER_CITY_ROWS, LAYER_CITY_SHIFT, PAL_CITY, LAYER_CITY_Y, {0}},
    {SPR_STREET, TILE_STREET, LAYER_STREET_COLS, LAYER_STREET_ROWS, LAYER_STREET_SHIFT, PAL_STREET, LAYER_STREET_Y, {0}},
};

static void load_column(layer_t *l, u16 hw, s16 k) {
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB1 + (l->spr + hw) * 64;
    u16 tile = l->tile + k;
    for (u8 r = 0; r < l->rows; r++, tile += l->cols) {
        *REG_VRAMRW = tile;
        *REG_VRAMRW = (u16)l->pal << 8;
    }
    l->loaded[hw] = k;
}

void stage_init(void) {
    for (u8 i = 0; i < NUM_LAYERS; i++) {
        layer_t *l = &layers[i];
        for (u16 h = 0; h < HW_COLS; h++) {
            l->loaded[h] = -1;
            spr_shape(l->spr + h, 400, l->y, l->rows, 0);
        }
    }
}

void stage_update(s16 cam_x, u16 *scroll_out) {
    for (u8 i = 0; i < NUM_LAYERS; i++) {
        layer_t *l = &layers[i];
        s16 scroll = cam_x >> l->shift;
        scroll_out[i] = scroll;
        s16 c0 = scroll >> 4;
        for (s16 n = 0; n < HW_COLS; n++) {
            s16 k = c0 + n;
            u16 hw = k % HW_COLS;
            s16 x;
            if (k >= l->cols) {
                x = 400;                       // fuera de pantalla
            } else {
                if (l->loaded[hw] != k) load_column(l, hw, k);
                x = k * 16 - scroll;
            }
            *REG_VRAMMOD = 1;
            *REG_VRAMADDR = ADDR_SCB4 + l->spr + hw;
            *REG_VRAMRW = (u16)((x & 0x1ff) << 7);
        }
    }
}
