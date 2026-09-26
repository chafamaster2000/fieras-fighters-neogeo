/* Generado por tools/make_assets.py: no editar a mano. */
#ifndef GEN_ASSETS_H
#define GEN_ASSETS_H
#include <ngdevkit/types.h>

#include "gen/stage_gen.h"

/* orden de la C-ROM (Makefile CROM_PARTS): fx proj sky floor0..4 font city char_p1 char_p2.
   city.gif empieza con relleno para que sus grupos animados queden alineados a 4.
   TILE_END: primer tile libre; ahí empiezan los personajes (src/gen/char_p1.c) */
#define TILE_FX 256
#define TILE_PROJ 288
#define TILE_SKY 315
#define TILE_STREET 522
#define TILE_FONT 676
#define TILE_CITY 824
#define TILE_END (TILE_CITY + CITY_TILES)

/* fuente de mensajes: glifo i ocupa 2x2 tiles; fila de abajo a FONT_GLYPHS*2 */
#define FONT_GLYPHS 37
extern const u8 font_map[96];

/* efectos: tiles de 16x16 en fx.gif (2 filas de 16) */
#define FX_ROW 16
#define FX_FIREBALL 0
#define FX_SPARK 6
#define FX_SHADOW 12
#define FX_BLOCK 14

#define CAM_RANGE 192
#define NUM_LAYERS 7
/* capas: tile base, columnas, filas, ratio (dieciseisavos de la cámara), y.
   La ciudad (capa 1) usa city_map en vez de tiles consecutivos. */
#define LAYER_CITY 1
#define LAYER_TABLE \
    {315, 23, 9, 4, 0}, \
    {TILE_CITY, 26, 10, 8, 16}, \
    {522, 28, 1, 10, 144}, \
    {550, 29, 1, 12, 160}, \
    {579, 31, 1, 14, 176}, \
    {610, 32, 1, 16, 192}, \
    {642, 34, 1, 18, 208}, \

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

extern const u16 pal_fx[16], pal_proj[16], pal_hud[16], pal_msg[16];

#endif
