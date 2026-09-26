/* Generado por tools/neoui.py: no editar a mano. */
#ifndef GEN_UI_H
#define GEN_UI_H
#include <ngdevkit/types.h>
#include "gen/assets.h"
#include "gen/char_p1.h"
#include "gen/char_p2.h"

/* los tiles de la UI van después de los dos personajes */
#define TILE_UI (TILE_END + CHAR_P1_TILES + CHAR_P2_TILES)
#define UI_TILES 1088
#define UI_PALS 26
#define UI_NLOGOS 1
#define UI_ROSTER 2
#define UI_HAS_FIRE 1
#define UI_HAS_TITLE_BG 1

enum {
    UI_LOGO0,
    UI_TITLE,
    UI_TITLE_FIRE,
    UI_TITLE_SKY,
    UI_TITLE_LEFT,
    UI_TITLE_RIGHT,
    UI_PORTRAIT_ROBOCLICK,
    UI_PORTRAIT_NINJAODA,
    UI_CURSOR,
    UI_COUNT
};

/* imagen: entradas de ui_map por columnas: tile (bits 0-10), bit 11 = grupo de
   8 cuadros con auto-animación por hardware, paleta relativa en bits 12-15 */
/* x, y: esquina de la imagen en su lienzo original (capas recortadas) */
typedef struct { u16 first; u8 w, h; u8 pal0, npal; s16 x, y; } uiimg_t;
extern const uiimg_t ui_imgs[UI_COUNT];
extern const u16 ui_map[];
extern const u16 ui_pals[UI_PALS][16];
#endif
