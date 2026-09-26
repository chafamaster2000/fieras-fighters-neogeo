/* Generado por tools/make_assets.py: no editar a mano. */
#ifndef GEN_ASSETS_H
#define GEN_ASSETS_H
#include <ngdevkit/types.h>

#define TILE_FIGHTER 256
#define TILE_FX 1104
#define TILE_PROJ 1136
#define TILE_SKY 1163
#define TILE_CITY 1370
#define TILE_STREET 1630
#define TILE_FONT 1784
#define TILE_END 1928

/* fuente de mensajes: glifo i ocupa 2x2 tiles; fila de abajo a FONT_GLYPHS*2 */
#define FONT_GLYPHS 36
extern const u8 font_map[96];

/* efectos: tiles de 16x16 en fx.gif (2 filas de 16) */
#define FX_ROW 16
#define FX_FIREBALL 0
#define FX_SPARK 6
#define FX_SHADOW 12
#define FX_BLOCK 14

#define FIGHTER_PX_W 112
#define FIGHTER_PX_H 128
#define FIGHTER_COLS 7
#define FIGHTER_ROWS 8
#define FIGHTER_AX 56
#define FIGHTER_AY 124

#define CAM_RANGE 192
#define NUM_LAYERS 7
/* capas: tile base, columnas, filas, ratio (dieciseisavos de la cámara), y */
#define LAYER_TABLE \
    {1163, 23, 9, 4, 0}, \
    {1370, 26, 10, 8, 16}, \
    {1630, 28, 1, 10, 144}, \
    {1658, 29, 1, 12, 160}, \
    {1687, 31, 1, 14, 176}, \
    {1718, 32, 1, 16, 192}, \
    {1750, 34, 1, 18, 208}, \

#define STAGE_W 512

#define HUD_TILES 223
#define HUD_BAR_SOLID 1
#define HUD_BAR_EDGE 7
/* pares de borde: ED DF EF FD DE FE */
#define HUD_CAP_L 91
#define HUD_CAP_R 92
#define HUD_WIN_OFF 93
#define HUD_WIN_ON 94
#define HUD_DIGITS 95
#define HUD_MEDAL 215

#define FF_ACTIVE 1
#define FF_LOW 2
#define FF_OVERHEAD 4
#define FF_SPAWN 8

enum {
    ANIM_IDLE,
    ANIM_WALK_F,
    ANIM_WALK_B,
    ANIM_CROUCH_T,
    ANIM_CROUCH,
    ANIM_PREJUMP,
    ANIM_AIR_UP,
    ANIM_AIR_DOWN,
    ANIM_LAND,
    ANIM_PUNCH,
    ANIM_KICK,
    ANIM_CPUNCH,
    ANIM_JKICK,
    ANIM_FIREBALL,
    ANIM_BLOCK,
    ANIM_CBLOCK,
    ANIM_HIT,
    ANIM_CHIT,
    ANIM_KNOCKDOWN,
    ANIM_KO,
    ANIM_WIN,
    ANIM_COUNT
};

typedef struct { s8 x, y, w, h; } box_t;
typedef struct {
    u16 tmap;       /* índice en fighter_tmaps */
    u8 dur;
    u8 flags;
    box_t hit;      /* w == 0: sin hitbox */
    box_t hurt_hi;
    box_t hurt_lo;
} frame_t;
typedef struct { u16 first; u8 count; u8 loop; } anim_t;

extern const u16 fighter_tmaps[][56];
extern const frame_t fighter_frames[];
extern const anim_t fighter_anims[];
extern const u16 pal_fighter_p1[16], pal_fighter_p2[16], pal_fx[16], pal_proj[16], pal_sky[16], pal_city[16], pal_street[16], pal_hud[16], pal_msg[16];

#endif
