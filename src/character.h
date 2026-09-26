#ifndef CHARACTER_H
#define CHARACTER_H
// Datos gráficos y de animación de un personaje. Los genera
// tools/neosprite.py en src/gen/char_p1.c y src/gen/char_p2.c (no editar a mano).
//
// Cada frame de animación apunta a una imagen: un rectángulo de w x h tiles
// ya recortado (sin columnas ni filas vacías), con su esquina relativa al
// ancla (entre los pies). Como en KOF, el ancho varía por frame: una pose
// angosta usa menos sprites de hardware por línea.
#include <ngdevkit/types.h>

// Entrada de tile: bits 0-13 número relativo a tile_base, bit 14 flip
// horizontal, bit 15 flip vertical (los mismos bits 0 y 1 del atributo SCB1).
#define CT_TILE(e)   ((e) & 0x3fff)
#define CT_FLIPS(e)  ((e) >> 14)

// Flags de frame
#define FF_ACTIVE   1
#define FF_LOW      2
#define FF_OVERHEAD 4
#define FF_SPAWN    8

// Columnas de hardware reservadas por luchador (ancho máximo 160 px).
// tools/neosprite.py rechaza un personaje con frames más anchos.
#define FIGHTER_HW_COLS 10

// Orden fijo: tools/neosprite.py lo lee de acá.
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

typedef struct { s8 x, y, w, h; } box_t;      // relativa al ancla, mirando a la derecha

typedef struct {
    u16 first;      // primera entrada en tiles[], por columnas (h entradas cada una)
    s8 x0, y0;      // esquina superior izquierda relativa al ancla, en px
    u8 w, h;        // columnas y filas de tiles
} cimg_t;

typedef struct {
    u16 img;        // índice en imgs[]
    u8 dur;
    u8 flags;
    box_t hit;      // w == 0: sin hitbox
    box_t hurt_hi;
    box_t hurt_lo;
} frame_t;

typedef struct { u16 first; u8 count; u8 loop; } anim_t;

typedef struct {
    const char *name;
    u16 tile_base;          // primer tile del personaje en la C-ROM
    const u16 *tiles;
    const cimg_t *imgs;
    const frame_t *frames;
    const anim_t *anims;    // ANIM_COUNT entradas
    const u16 *pal;         // 16 colores, índice 0 transparente
} character_t;

extern const character_t char_p1, char_p2;
#endif
