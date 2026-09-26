#ifndef GAME_H
#define GAME_H
#include <ngdevkit/types.h>

enum { MODE_BOOT = 0, MODE_DEMO = 1, MODE_MATCH = 2, MODE_MATCH_END = 3,
       MODE_LOGOS = 4, MODE_TITLE = 5, MODE_MENU = 6, MODE_SELECT = 7 };
enum { RS_INTRO = 0, RS_FIGHT = 1, RS_KO = 2, RS_TIMEUP = 3, RS_END = 4 };

// Estado observable por luchador (32 bytes).
typedef struct {
    s16 x, y;              // +0 +2  ancla en px de mundo (y: 0 = piso)
    u16 hp;                // +4
    u16 state;             // +6  FS_*
    u16 anim;              // +8  ANIM_*
    u16 fidx;              // +10
    s16 facing;            // +12
    u16 wins;              // +14
    u16 hits_landed;       // +16
    u16 hits_blocked;      // +18 golpes de este luchador que el rival bloqueó
    u16 specials;          // +20
    u16 combo;             // +22
    u16 max_combo;         // +24
    u16 cpu;               // +26
    u16 joy;               // +28
    u16 pad;               // +30
} obs_t;

// Contrato con los tests: se lee por el símbolo `g` en build/rom.elf.
typedef struct {
    u32 magic;             // +0  GAME_MAGIC
    u16 mode;              // +4
    u16 rstate;            // +6
    u16 round;             // +8
    u16 timer;             // +10
    u32 frame;             // +12
    s16 cam_x;             // +16
    u16 hitstop;           // +18
    u16 scroll[3];         // +20 +22 +24  cielo, ciudad, calle
    u16 winner;            // +26 0 nadie, 1 P1, 2 P2
    obs_t p[2];            // +28 P1, +60 P2
    u16 sel_ch[2];         // +92 +94  personaje elegido (índice en roster)
    u16 sel_color[2];      // +96 +98  0 color normal, 1 alternativo
    u16 vs_human;          // +100 1 si el match es contra otro jugador
} game_t;

#define GAME_MAGIC 0x4e474654   // "NGFT"
extern volatile game_t g;

// Personajes elegibles, en el orden de la grilla del selector (UI_PORTRAIT_*)
#include "character.h"
#define ROSTER_N 2
extern const character_t *const roster[ROSTER_N];
// Paleta de un personaje: color 0 normal, 1 alternativo (canales rotados,
// como los colores de botón de KOF). Buffer propio por lado.
const u16 *char_palette(u8 side, const character_t *ch, u8 color);

// Corre un match con los personajes de g.sel_ch / g.sel_color.
// demo=1: CPU contra CPU hasta que alguien aprieta START.
// Devuelve 1 si terminó porque se apretó START durante la demo.
u8 game_match(u8 demo, u8 p1_human, u8 p2_human);
#endif
