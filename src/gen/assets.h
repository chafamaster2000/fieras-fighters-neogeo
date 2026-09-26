/* Generado por tools/make_assets.py: no editar a mano. */
#ifndef GEN_ASSETS_H
#define GEN_ASSETS_H
#include <ngdevkit/types.h>

#define TILE_FIGHTER 256
#define TILE_FX 976
#define TILE_SKY 1008
#define TILE_CITY 1215
#define TILE_STREET 1475
#define TILE_END 1635

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
#define NUM_LAYERS 3
#define LAYER_SKY_COLS 23
#define LAYER_SKY_ROWS 9
#define LAYER_SKY_SHIFT 2
#define LAYER_SKY_Y 0
#define LAYER_CITY_COLS 26
#define LAYER_CITY_ROWS 10
#define LAYER_CITY_SHIFT 1
#define LAYER_CITY_Y 16
#define LAYER_STREET_COLS 32
#define LAYER_STREET_ROWS 5
#define LAYER_STREET_SHIFT 0
#define LAYER_STREET_Y 144

#define HUD_TILES 81
#define HUD_BAR_FULL 1
#define HUD_BAR_EMPTY 2
#define HUD_P1_PART 3
#define HUD_P2_PART 10
#define HUD_CAP_L 17
#define HUD_CAP_R 18
#define HUD_WIN_OFF 19
#define HUD_WIN_ON 20
#define HUD_DIGITS 21

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
extern const u16 pal_fighter_p1[16], pal_fighter_p2[16], pal_fx[16], pal_sky[16], pal_city[16], pal_street[16], pal_hud[16];

#endif
