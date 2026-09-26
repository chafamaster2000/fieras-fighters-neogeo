/* Generado por tools/neofx.py: no editar a mano. */
#ifndef GEN_VFX_H
#define GEN_VFX_H
#include <ngdevkit/types.h>
#include "gen/ui_gen.h"

/* los tiles de los efectos van después de la UI (última parte de la C-ROM) */
#define TILE_VFX (TILE_UI + UI_TILES)
#define VFX_TILES 672
#define VFX_PALS 7

enum {
    VFX_HIT_L,
    VFX_HIT_H,
    VFX_BLOCK,
    VFX_BALL,
    VFX_LAUNCH,
    VFX_BOOM,
    VFX_DUST,
    VFX_DUST_S,
    VFX_COUNT
};

#define VFX_HIT_L_W 4   /* columnas máximas */
#define VFX_HIT_H_W 6   /* columnas máximas */
#define VFX_BLOCK_W 4   /* columnas máximas */
#define VFX_BALL_W 5   /* columnas máximas */
#define VFX_LAUNCH_W 3   /* columnas máximas */
#define VFX_BOOM_W 6   /* columnas máximas */
#define VFX_DUST_W 4   /* columnas máximas */
#define VFX_DUST_S_W 3   /* columnas máximas */

/* vfx_map: por cuadro, columnas de arriba a abajo: tile (bits 0-10),
   espejo horizontal (bit 11), paleta relativa a vfx_pals (bits 12-15) */
/* x, y: esquina del cuadro respecto del ancla, con el efecto mirando a la derecha */
typedef struct { u16 first; u8 w, h; s16 x, y; } vfxframe_t;
typedef struct { u8 first, count, dur, loop; } vfxanim_t;
extern const vfxanim_t vfx_anims[VFX_COUNT];
extern const vfxframe_t vfx_frames[];
extern const u16 vfx_map[];
extern const u16 vfx_pals[VFX_PALS][16];
#endif
