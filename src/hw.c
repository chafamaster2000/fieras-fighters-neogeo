#include "hw.h"

void hw_load_palette(u8 index, const u16 *pal) {
    volatile u16 *dst = MMAP_PALBANK1 + index * 16;
    for (u8 i = 0; i < 16; i++) dst[i] = pal[i];
}

void hw_clear_sprites(void) {
    *REG_VRAMMOD = 1;
    *REG_VRAMADDR = ADDR_SCB3 + 1;
    for (u16 i = 1; i < MAX_SPRITES; i++) *REG_VRAMRW = 0;
}
