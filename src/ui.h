#ifndef UI_H
#define UI_H
// Imágenes de UI (tools/neoui.py), fundidos de paleta y efectos de brillo
// de las pantallas previas al combate.
#include <ngdevkit/types.h>
#include "gen/ui_gen.h"

// Fundido: cada paleta registrada tiene un tope (16 = color pleno) y
// fade_apply(nivel) la escribe a nivel*tope/16. Nivel 0 = negro.
void fade_clear(void);
void fade_add(u8 hw_pal, const u16 *src, u8 cap);
void fade_apply(u8 level);
void fade_flash(u8 level);              // hacia blanco: 0 normal, 16 blanco
u16 col_mix(u16 c, u8 level, u8 white);

// Carga una imagen en sprites consecutivos desde `spr` (una columna por
// sprite, encadenadas). shine=1: cada columna con sus propias paletas,
// para el barrido de brillo por columna (ui_shine).
void ui_load(u8 img, u16 spr, u8 shine);
// Ubica la imagen centrada en (cx, cy) con zoom por hardware:
// hz 0..15 (ancho de columna hz+1 px), vz 0..255 (alto (vz+1)/256).
// ui_load con brillo y espejado horizontal (el logo del eye-catcher entra espejado).
void ui_load_flip(u8 img, u16 spr, u8 flip);
// Igual que ui_load pero con todos los tiles en la paleta de hardware `pal`.
void ui_load_as(u8 img, u16 spr, u8 pal);
// Paletas normales (sin brillo por columna) reubicadas desde la paleta de
// hardware `pal_base` (0 = las de la imagen), con espejo opcional: flip=1
// invierte el orden de las columnas y prende el bit de espejo de cada tile.
void ui_load_pal(u8 img, u16 spr, u8 pal_base, u8 flip);
// x de la esquina izquierda de la imagen espejada en su lienzo de 320:
// 320 - x - ancho (para ubicarla con spr_move)
s16 ui_mirror_x(u8 img);
void ui_place(u8 img, u16 spr, s16 cx, s16 cy, u8 hz, u8 vz);
void ui_hide(u16 spr);
// Sin zoom, en su posición del lienzo original más (dx, dy)
void ui_put(u8 img, u16 spr, s16 dx, s16 dy);
void ui_palettes(u8 img, u8 cap);      // registra y carga las paletas normales
u8 ui_hw_pal(u8 img);                  // primera paleta de hardware de la imagen
// Barrido: una franja clara centrada en la x `pos` (px de la imagen) más un
// brillo parejo `glow` (0..16) en toda la imagen. Solo para ui_load(..., 1).
#define SHINE_PAD 40
void ui_shine(u8 img, s16 pos, u8 glow, u8 level);
void ui_shine_reset(void);
#endif
