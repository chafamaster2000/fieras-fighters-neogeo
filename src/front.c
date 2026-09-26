// Pantallas previas al combate: presentación con logos, título con menú y
// selector de personajes. Todo con los recursos de la época: fundidos y
// destellos por paleta, logos que se despliegan con el zoom de hardware,
// barridos de brillo por columna y el escenario de fondo con parallax.
#include <ngdevkit/neogeo.h>
#include <ngdevkit/bios-ram.h>
#include <ngdevkit/ng-fix.h>
#include <ngdevkit/ng-video.h>
#include "front.h"
#include "game.h"
#include "hw.h"
#include "ui.h"
#include "stage.h"
#include "fighter.h"
#include "sound.h"
#include "msg.h"
#include "gen/assets.h"
#include "gen/stage_gen.h"

#define USER_MODE_GAME 2
#define TITLE_TIMEOUT  (60 * 12)     // título sin tocar nada -> demo
#define SELECT_TIME    20            // segundos del selector
#define LOGO_Y         112
// Intro de Odaclick: perro de 66 px (caja de 80) + lema + copyright, el
// bloque (unos 100 px) centrado en la pantalla. Fila de fix N = y 8*(N-2).
#define DOG_Y          94            // centro del perro (caja y 54-134, contenido 61-127)
#define TAG_ROW        20            // lema en y 144
#define COPY_ROW       22            // (C) 2026 ODACLICK en y 160
#define TITLE_Y        142           // logo abajo (y 70-214, contenido hasta y 207): el título es un VS de los bustos
#define PORTRAIT_CY    150           // grilla del selector abajo al centro (y 118-182): arriba quedan las caras de los bustos
#define LABEL_ROW      15            // 1P/2P justo arriba de la grilla (y 104)

static u8 quick;                     // START con D: directo al match
__attribute__((unused)) static u16 scroll[3];   // solo el título sin fondo propio

// Fix layer: 1 color, 2 sombra
static const u16 txt_pals[4][16] = {
    {0x8000, 0x10ed, 0x9112},        // cyan
    {0x8000, 0x4f4b, 0x9112},        // magenta
    {0x8000, 0x4fd4, 0x9112},        // dorado
    {0x8000, 0x9aab, 0x9112},        // gris
};
static const u16 txt_white[16] = {0x8000, 0x7fff, 0x9112};
static const u16 cur_pals[2][16] = {
    {0x8000, 0x3056, 0x10ed},        // P1 cyan
    {0x8000, 0x4604, 0x4f4b},        // P2 magenta
};

static u8 pad_prev[2], stat_prev;

static void wait_frame(void) {
    ng_wait_vblank();
    g.frame++;
}

// Flancos propios: un loop que tarda más de un frame no pierde botones
// (bios_p1change dura un solo frame).
static u8 pad_edge(u8 s) {
    u8 cur = s ? bios_p2current : bios_p1current;
    u8 e = cur & ~pad_prev[s];
    pad_prev[s] = cur;
    return e;
}

static u8 stat_edge(void) {
    u8 e = bios_statcurnt & ~stat_prev;
    stat_prev = bios_statcurnt;
    return e;
}

static void pads_sync(void) {
    pad_prev[0] = bios_p1current;
    pad_prev[1] = bios_p2current;
    stat_prev = bios_statcurnt;
}

// En el attract el BIOS pasa a modo juego cuando alguien aprieta START
static u8 started(void) {
    if (bios_user_mode != USER_MODE_GAME) return 0;
    quick = (bios_p1current & J_D) != 0;
    return 1;
}

static void clear_screen(void) {
    ng_cls();
    hw_clear_sprites();
    fade_clear();
    *REG_BACKDROP = 0x8000;
    for (u8 i = 0; i < 4; i++) {
        hw_load_palette(PAL_TXT_CYAN + i, txt_pals[i]);
        fade_add(PAL_TXT_CYAN + i, txt_pals[i], 16);
    }
    hw_load_palette(PAL_TEXT, txt_white);
    fade_add(PAL_TEXT, txt_white, 16);
}

// Escenario de fondo, apagado a cap/16 (hoy solo lo usa el título sin fondo
// propio; el selector carga el escenario ya en negro)
__attribute__((unused)) static void stage_bg(u8 cap) {
    static const struct { u8 pal; const u16 *src; } p[] = {
        {PAL_SKY, pal_sky}, {PAL_CITY, pal_city}, {PAL_STREET, pal_street}, {PAL_CROWD, pal_crowd}};
    for (u8 i = 0; i < 4; i++) {
        hw_load_palette(p[i].pal, p[i].src);
        fade_add(p[i].pal, p[i].src, cap);
    }
    stage_init();
}

static void clear_row(u8 row) {
    ng_text(0, row, PAL_TEXT, "                                        ");
}

// ------------------------------------------------------------ presentación

static void backdrop(u8 white_level) {
    *REG_BACKDROP = white_level ? col_mix(0x7fff, white_level, 0) : 0x8000;
}

// Logo de estudio con la coreografía del eye-catcher del BIOS de Neo Geo
// (wiki.neogeodev.org/index.php?title=Eyecatcher): fondo blanco, el logo
// espejado y en silueta crece con el zoom de hardware, se aplasta hasta una
// línea mientras el fondo pasa a gris, se da vuelta, vuelve a abrirse ya en
// color sobre negro con un destello, y abajo se escribe el lema letra por
// letra. Son unos 6 segundos, como el original.
static u8 eyecatch_logo(u8 img) {
    static const char tag[] = "CRAFTING THE FUTURE OF PLAY";
    clear_screen();
    ui_load_flip(img, SPR_LOGO, 1);
    ui_shine_reset();
    ui_shine(img, -100, 0, 0);                    // silueta negra
    ui_place(img, SPR_LOGO, SCREEN_W / 2, DOG_Y, 0, 0);
    s16 w = ui_imgs[img].w * 16;
    u8 tag_n = 0;
    for (u16 t = 0; t < 380; t++) {
        wait_frame();
        if (t == 4) backdrop(16);
        if (t >= 4 && t < 50) {                   // crece de chico a pleno
            u16 k = (t - 4) * 256 / 46;
            ui_place(img, SPR_LOGO, SCREEN_W / 2, DOG_Y, (u8)(k * 15 / 256), (u8)(k > 255 ? 255 : k));
        } else if (t >= 60 && t < 82) {           // se aplasta, el fondo va a gris
            u8 v = (u8)(255 - (t - 60) * 255 / 22);
            ui_place(img, SPR_LOGO, SCREEN_W / 2, DOG_Y, 15, v);
            backdrop((u8)(16 - (t - 60) * 8 / 22));
        } else if (t == 82) {                     // en la línea: se da vuelta y toma color
            ui_load_flip(img, SPR_LOGO, 0);
            ui_place(img, SPR_LOGO, SCREEN_W / 2, DOG_Y, 15, 0);   // sigue en la línea
            ui_shine_reset();
            ui_shine(img, -100, 16, 16);
            sound_cmd(SND_LOGO);
        } else if (t > 82 && t < 104) {           // se abre en color sobre negro
            u8 v = (u8)((t - 82) * 255 / 22);
            ui_place(img, SPR_LOGO, SCREEN_W / 2, DOG_Y, 15, t == 103 ? 255 : v);
            backdrop((u8)(8 - (t - 82) * 8 / 22));
            ui_shine(img, -100, (u8)(16 - (t - 82) * 16 / 22), 16);
        } else if (t == 104) {
            backdrop(0);
            ui_shine(img, -100, 0, 16);
        } else if (t >= 115 && tag_n < sizeof(tag) - 1 && (t - 115) % 5 == 0) {
            // el lema se escribe como el "MAX 330 MEGA" del BIOS
            char one[2] = {tag[tag_n], 0};
            ng_text(20 - (sizeof(tag) - 1) / 2 + tag_n, TAG_ROW, PAL_TXT_GRAY, one);
            tag_n++;
            if (tag_n == sizeof(tag) - 1) ng_center_text(COPY_ROW, PAL_TXT_GRAY, "(C) 2026 ODACLICK");
        }
        if (t >= 250 && t < 294)                  // barrido de brillo
            ui_shine(img, -SHINE_PAD + (s16)(t - 250) * (w + 2 * SHINE_PAD) / 44, 0, 16);
        if (t >= 360) {
            u8 l = (u8)((380 - t) * 16 / 20);
            ui_shine(img, -100, 0, l);
            fade_apply(l);
        }
        if (started()) return 1;
    }
    return 0;
}

// Otros logos: se despliegan desde una línea blanca, se asientan del blanco
// a su color, pasa un brillo y se funden a negro.
static u8 show_logo(u8 img) {
    clear_screen();
    ui_load(img, SPR_LOGO, 1);
    ui_shine_reset();
    fade_apply(16);
    s16 w = ui_imgs[img].w * 16;
    for (u16 t = 0; t < 190; t++) {
        wait_frame();
        if (t < 18) {
            static const u8 vz[18] = {0, 2, 6, 12, 22, 36, 54, 76, 102, 130, 160, 190, 218, 240, 255, 246, 240, 255};
            ui_place(img, SPR_LOGO, SCREEN_W / 2, LOGO_Y - 8, 15, vz[t]);
            ui_shine(img, -100, 16, 16);
            if (t == 12) sound_cmd(SND_LOGO);
        } else if (t < 40) {
            ui_shine(img, -100, (u8)((40 - t) * 16 / 22), 16);
        } else if (t < 90) {
            ui_shine(img, -SHINE_PAD + (s16)(t - 40) * (w + 2 * SHINE_PAD) / 50, 0, 16);
        } else if (t >= 170) {
            u8 l = (u8)((190 - t) * 16 / 20);
            ui_shine(img, -100, 0, l);
            fade_apply(l);
        }
        if (started()) return 1;
    }
    return 0;
}

static u8 front_logos(void) {
    g.mode = MODE_LOGOS;
    sound_cmd(SND_MUS_STOP);          // si venimos de la demo, silencio para los logos
    for (u8 i = 0; i < UI_NLOGOS; i++)
        if (i == 0 ? eyecatch_logo(UI_LOGO0) : show_logo(UI_LOGO0 + i)) return 1;
    return 0;
}

// ------------------------------------------------------------ título

static s16 pan;
static s8 pan_dir;
static u16 tt;                        // tiempo del título
static u8 fire_on;                    // encendido del fuego de FIERAS, 0..16
static u16 rng = 0x1998;

#define FIRE_ANIM_SPEED 3             // auto-animación: cuadro nuevo cada 4 frames (15 fps)

// Paleta del fuego: sube con el encendido, baja con el fundido y titila
// un poco hacia blanco, como el fuego de los títulos de SNK.
static void fire_palette(u8 level) {
#if UI_HAS_FIRE
    const uiimg_t *im = &ui_imgs[UI_TITLE_FIRE];
    const u16 *src = ui_pals[im->pal0];
    volatile u16 *dst = MMAP_PALBANK1 + (PAL_UI + im->pal0) * 16;
    u8 l = level < fire_on ? level : fire_on;
    rng = rng * 25173 + 13849;
    u8 flick = (u8)((rng >> 13) & 3);
    for (u8 k = 1; k < 16; k++) {
        u16 v = l >= 16 ? src[k] : col_mix(src[k], l, 0);
        dst[k] = (l >= 16 && flick) ? col_mix(v, flick, 1) : v;
    }
#else
    (void)level;
#endif
}

static void title_place(u8 hz, u8 vz) {
    ui_place(UI_TITLE, SPR_LOGO, SCREEN_W / 2, TITLE_Y, hz, vz);
#if UI_HAS_FIRE
    ui_place(UI_TITLE_FIRE, SPR_FIRE, SCREEN_W / 2, TITLE_Y, hz, vz);
#endif
}

#if UI_HAS_TITLE_BG
#define LOGO_T0 26                    // los bustos entran primero, después golpea el logo
#else
#define LOGO_T0 0
#endif
#define PRESS_ROW 28                  // fila del PRESS START y del menú (y 208)

static void title_enter(void) {
    clear_screen();
#if UI_HAS_TITLE_BG
    // fondo propio del título: cielo de Córdoba de noche y los dos bustos
    ui_palettes(UI_TITLE_SKY, 16);
    ui_palettes(UI_TITLE_LEFT, 16);
    ui_palettes(UI_TITLE_RIGHT, 16);
    ui_load(UI_TITLE_SKY, SPR_TBG, 0);
    ui_load(UI_TITLE_LEFT, SPR_TBUST_L, 0);
    ui_load(UI_TITLE_RIGHT, SPR_TBUST_R, 0);
    ui_put(UI_TITLE_SKY, SPR_TBG, 0, 0);
    ui_put(UI_TITLE_LEFT, SPR_TBUST_L, -200, 0);
    ui_put(UI_TITLE_RIGHT, SPR_TBUST_R, 200, 0);
#else
    stage_bg(7);
#endif
    ui_load(UI_TITLE, SPR_LOGO, 1);
    ui_hide(SPR_LOGO);
#if UI_HAS_FIRE
    ui_load(UI_TITLE_FIRE, SPR_FIRE, 0);
    ui_hide(SPR_FIRE);
    // el fuego (8 cuadros) y la tribuna (4) comparten el contador del LSPC
    *REG_LSPCMODE = (u16)FIRE_ANIM_SPEED << 8;
#endif
    ui_shine_reset();
    pan = CAM_RANGE / 2;
    pan_dir = 1;
    tt = 0;
    fire_on = 0;
    fade_apply(0);
    fire_palette(0);
}

// Un frame del título: el fondo (bustos que entran desde los costados y
// flotan, o el escenario paseándose con parallax), el logo que golpea con
// zoom y destello, FIERAS que se enciende, brillo que respira y un barrido
// cada 3 segundos.
static void title_tick(void) {
    wait_frame();
#if UI_HAS_TITLE_BG
    if (tt <= LOGO_T0) {
        s16 k = LOGO_T0 - (s16)tt;                    // frena al llegar
        s16 off = (s16)((s32)200 * k * k / (LOGO_T0 * LOGO_T0));
        ui_put(UI_TITLE_LEFT, SPR_TBUST_L, -off, 0);
        ui_put(UI_TITLE_RIGHT, SPR_TBUST_R, off, 0);
    } else if ((tt & 31) == 0) {
        // respiración: los bustos suben y bajan 1 px, a contratiempo
        s16 b = (tt & 64) ? 1 : 0;
        ui_put(UI_TITLE_LEFT, SPR_TBUST_L, 0, b);
        ui_put(UI_TITLE_RIGHT, SPR_TBUST_R, 0, 1 - b);
    }
#else
    if ((tt & 1) == 0) {
        pan += pan_dir;
        if (pan <= 0 || pan >= CAM_RANGE) pan_dir = -pan_dir;
    }
    stage_update(pan, scroll);
#endif
    s16 w = ui_imgs[UI_TITLE].w * 16;
    if (tt <= 16) fade_apply((u8)tt);
    s16 lt = (s16)tt - LOGO_T0;                        // tiempo del logo
    if (lt >= 0 && lt < 14) {
        static const u8 hz[14] = {1, 2, 4, 6, 8, 10, 12, 14, 15, 15, 14, 15, 15, 15};
        static const u8 vz[14] = {16, 36, 64, 96, 128, 160, 192, 224, 255, 255, 236, 255, 255, 255};
        title_place(hz[lt], vz[lt]);
        ui_shine(UI_TITLE, -100, 16, 16);
        if (lt == 8) { sound_cmd(SND_MUS_TITLE); sound_cmd(SND_LOGO); }
    } else if (lt >= 14 && lt < 34) {
        ui_shine(UI_TITLE, -100, (u8)((34 - lt) * 16 / 20), 16);
    } else if (lt >= 34) {
        u16 c = (u16)(lt - 34) % 180;
        // respiración: brillo parejo de 0 a 3 en un ciclo de 64 frames
        u8 ph = (u8)(tt & 63), glow = ph < 32 ? ph >> 3 : (63 - ph) >> 3;
        s16 pos = c < 44 ? -SHINE_PAD + (s16)c * (w + 2 * SHINE_PAD) / 44 : -100;
        ui_shine(UI_TITLE, pos, glow, 16);
    }
    // FIERAS se enciende después del golpe del logo: letras negras que se
    // llenan de fuego en medio segundo
    if (lt == 22) sound_cmd(SND_FIRE);
    if (lt >= 22 && fire_on < 16 && (tt & 1)) fire_on++;
    if ((tt & 3) == 0 || fire_on < 16) fire_palette(16);
    tt++;
}

static void title_fade_out(void) {
    for (u8 l = 16; l-- > 0;) {
        wait_frame();
        fade_apply(l);
        ui_shine(UI_TITLE, -100, 0, l);
        fire_palette(l);
    }
}

static const char *const menu_items[2] = {"VS CPU", "VS PLAYER"};
static const u8 menu_col[2] = {9, 23};

static void draw_menu(u8 cur, u8 arrows, u8 blank_cur) {
    clear_row(PRESS_ROW); clear_row(PRESS_ROW + 1);
    for (u8 i = 0; i < 2; i++) {
        u8 on = i == cur;
        if (on && blank_cur) continue;
        ng_text_tall(menu_col[i], PRESS_ROW, on ? (blank_cur == 2 ? PAL_TEXT : PAL_TXT_GOLD) : PAL_TXT_GRAY, menu_items[i]);
    }
    if (arrows) {
        u8 len = cur ? 9 : 6;
        ng_text_tall(menu_col[cur] - 2, PRESS_ROW, PAL_TXT_CYAN, ">");
        ng_text_tall(menu_col[cur] + len + 1, PRESS_ROW, PAL_TXT_CYAN, "<");
    }
}

// attract=1: espera START (0 si se acaba el tiempo). Después, menú:
// devuelve 1 VS CPU, 2 VS PLAYER, 3 inicio rápido.
static u8 front_title(u8 attract) {
    g.mode = MODE_TITLE;
    title_enter();
    if (attract) {
        for (u16 t = 0;; t++) {
            title_tick();
            if (tt > 34 + LOGO_T0 && (t & 15) == 0) {
                // parpadeo de 16 frames, las flechas cyan como en la referencia
                clear_row(PRESS_ROW); clear_row(PRESS_ROW + 1);
                if (!(t & 32)) {
                    ng_center_text_tall(PRESS_ROW, PAL_TXT_GOLD, "PRESS START");
                    ng_text_tall(12, PRESS_ROW, PAL_TXT_CYAN, ">");
                    ng_text_tall(27, PRESS_ROW, PAL_TXT_CYAN, "<");
                }
            }
            if (started()) break;
            if (t >= TITLE_TIMEOUT) { title_fade_out(); return 0; }
        }
        if (quick) return 3;
    }
    g.mode = MODE_MENU;
    u8 cur = 0, drawn = 0xff;
    pads_sync();
    for (u16 t = 0;; t++) {
        title_tick();
        u8 j = pad_edge(0), st = stat_edge();
        if (t > 8) {
            if (j & (J_UP | J_DOWN | J_LEFT | J_RIGHT)) { cur ^= 1; sound_cmd(SND_MENU_MOVE); }
            if ((j & J_A) || (st & CNT_START1)) break;
        }
        if (cur != drawn || (t & 7) == 0) {
            draw_menu(cur, (t & 16) != 0, 0);
            drawn = cur;
        }
    }
    // confirmación: la opción parpadea rápido, como en los menús de KOF
    sound_cmd(SND_MENU_OK);
    for (u8 t = 0; t < 30; t++) {
        title_tick();
        draw_menu(cur, 0, (t & 2) ? 2 : 1);
    }
    title_fade_out();
    return cur + 1;
}

// ------------------------------------------------------------ selector
//
// Coreografía (frames a 60 Hz), todo con recursos de la época:
//   entrada (SEL_INTRO = 40, A o START salta al final):
//     0-12  el degradé VS de fondo sube desde negro (fundido de paleta)
//     2-22  los bustos grandes entran desde los costados, detrás de todo
//     4-14  SELECT YOUR FIGHTER se destapa desde el centro en blanco; en 16 se asienta en dorado
//    10-31  los retratos saltan con el zoom de hardware (SCB2), escalonados de a 4
//           frames, con rebote y un destello blanco que se apaga
//    14-30  los luchadores entran deslizándose desde los bordes, frenando
//    32     nombres, 1P/2P, cursores, reloj y ayuda: recién ahí se juega
//   cambio de cursor: el busto de ese lado se recarga (solo su SCB1) y entra
//     en 10 frames desde afuera, de blanco a su color
//   confirmación: el luchador y su busto pasan a blanco pleno y vuelven a su
//     paleta en 16 frames (col_mix hacia blanco), sincronizados con el
//     destello del retrato, con SND_CHAR_OK
//   salida tipo VS (SEL_OUTRO = 60 frames desde la segunda confirmación):
//     0-17  los dos en pose de victoria mientras termina el destello
//    18-27  destello blanco de toda la pantalla, se borra la interfaz y los
//           retratos se achican hasta desaparecer
//    20-34  "VS" gigante entra con zoom y parpadeo (msg_show) y un impacto
//    34-51  los luchadores salen disparados hacia los bordes (los bustos detrás, a 3/4)
//    42-58  fundido a negro (el VS se funde con todo) y arranca el match

#define SEL_INTRO   40
#define SEL_UI_T    32                // en la entrada: aparecen reloj, nombres y cursores
#define SEL_BLINK   16                // niveles del destello de confirmación (16 = blanco)
#define SEL_OUTRO   60
#define SLIDE_OFF   136               // px fuera de pantalla al empezar a entrar
#define HEAD_COL    10                // SELECT YOUR FIGHTER: 19 letras centradas
#define HEAD_ROW    3

typedef struct {
    u8 cur, color, done, human, flash;
    const u16 *pal;                   // paleta del luchador, para el destello
    fighter_t f;
} seat_t;

static seat_t seat[2];
static u8 sel_quiet;                  // en la entrada todavía no se escriben los nombres
static const char head_txt[] = "SELECT YOUR FIGHTER";

static s16 portrait_x(u8 i) {         // borde izquierdo del retrato i
    return SCREEN_W / 2 - (ROSTER_N * 64 + (ROSTER_N - 1) * 16) / 2 + i * 80;
}

// Paletas del selector con buffer: el 68000 tarda casi un frame en mezclar
// 15 paletas, así que la mezcla se calcula durante el frame (sp_mix) y se
// copia al principio del siguiente, en el vblank (sp_commit). Sin esto el
// destello blanco y los fundidos se cortaban a mitad de pantalla.
#define SP_MAX 24
static struct { u8 hw, cap; const u16 *src; } sp[SP_MAX];
static u16 sp_buf[SP_MAX][16];
static u8 sp_n, sp_dirty;
static u8 sp_level, sp_white;         // último sp_mix: los bustos lo siguen

static void sp_add(u8 hw, const u16 *src, u8 cap) {
    if (sp_n == SP_MAX) return;
    sp[sp_n].hw = hw; sp[sp_n].src = src; sp[sp_n].cap = cap;
    sp_n++;
}

// white=0: fundido a negro (level 16 = color pleno, respetando el tope);
// white=1: hacia blanco desde el color pleno (level 16 = blanco)
static void sp_mix(u8 level, u8 white) {
    sp_level = level;
    sp_white = white;
    for (u8 i = 0; i < sp_n; i++) {
        const u16 *src = sp[i].src;
        u8 cap = sp[i].cap;
        u8 l = (u8)(((u16)level * cap) >> 4);
        for (u8 k = 1; k < 16; k++) {
            u16 c = src[k];
            if (white) sp_buf[i][k] = col_mix(cap < 16 ? col_mix(c, cap, 0) : c, level, 1);
            else sp_buf[i][k] = l >= 16 ? c : col_mix(c, l, 0);
        }
    }
    sp_dirty = 1;
}

static void sp_commit(void) {
    if (!sp_dirty) return;
    sp_dirty = 0;
    for (u8 i = 0; i < sp_n; i++) {
        volatile u16 *dst = MMAP_PALBANK1 + sp[i].hw * 16;
        const u16 *b = sp_buf[i];
        for (u8 k = 1; k < 16; k++) dst[k] = b[k];
    }
}

// Fondo: el mismo degradé VS del título (20 columnas). El escenario de
// Córdoba costaba hasta 63 sprites por línea y con los bustos no entraba.
static void sky_pals(void) {
    const uiimg_t *im = &ui_imgs[UI_TITLE_SKY];
    for (u8 p = 0; p < im->npal; p++) sp_add(PAL_UI + im->pal0 + p, ui_pals[im->pal0 + p], 16);
}

// ---- bustos por lado
//
// Cada lado muestra, detrás de todo, el busto grande del personaje que tiene
// el cursor, mirando al centro. Los dos bustos son los del título: left.png
// (ROBOCLICK, mira a la derecha) y right.png (NINJAODA, mira a la izquierda).
// Si el busto no es el nativo de ese lado se espeja por hardware: columnas al
// revés + bit de espejo por tile, en x = 320 - x - ancho. Cada lado tiene sus
// 4 paletas propias (PAL_SBUST), así el destello o el color alternativo de un
// lado no toca al otro, y en el espejo los dos pueden mostrar el mismo busto.
//
//   cambio de cursor: el lado se oculta, en el vblank siguiente se recarga
//     solo su SCB1 y entra desde afuera en BUST_SWAP frames, de blanco a su color
//   confirmación: el mismo destello blanco que el luchador (p->flash)
//   color alternativo: canales rotados como char_palette() (el dorado de P2)
#define BUST_CAP     10               // un poco apagados: los luchadores van adelante
#define BUST_DX      12               // un poco hacia afuera: más lugar entre los dos hocicos
#define BUST_DY      0
#define BUST_SWAP    10
#define BUST_SWAP_DX 36

typedef struct {
    u8 img, flip, color, swap, pending, key_ok;
    u8 k_level, k_white, k_flash;     // lo último mezclado en bust_buf
} bust_t;
static bust_t bust[2];
static u16 bust_src[2][PAL_SBUST_N][16];
static u16 bust_buf[2][PAL_SBUST_N][16];
static u8 bust_dirty;
static s16 bust_slide;                // entrada y salida: px hacia afuera (<0 oculto)

static u8 bust_img(u8 ch) {           // el busto nativo del lado s es el imagen s
    return ch ? UI_TITLE_RIGHT : UI_TITLE_LEFT;
}

static u8 bust_npal(u8 s) {
    u8 n = ui_imgs[bust[s].img].npal;
    return n > PAL_SBUST_N ? PAL_SBUST_N : n;
}

static u16 rot_rgb(u16 c) {           // igual que char_palette(): R<-G<-B<-R
    u16 r = (c >> 8) & 15, gg = (c >> 4) & 15, b = c & 15;
    u16 lr = (c >> 14) & 1, lg = (c >> 13) & 1, lb = (c >> 12) & 1;
    return (c & 0x8000) | (lg << 14) | (lb << 13) | (lr << 12) | (gg << 8) | (b << 4) | r;
}

static void bust_colors(u8 s) {
    const uiimg_t *im = &ui_imgs[bust[s].img];
    for (u8 p = 0; p < bust_npal(s); p++)
        for (u8 k = 0; k < 16; k++) {
            u16 c = ui_pals[im->pal0 + p][k];
            bust_src[s][p][k] = bust[s].color ? rot_rgb(c) : c;
        }
    bust[s].key_ok = 0;
}

static void bust_load(u8 s) {
    ui_load_pal(bust[s].img, SPR_SBUST + s * SPR_SBUST_N, PAL_SBUST + s * PAL_SBUST_N, bust[s].flip);
    ui_hide(SPR_SBUST + s * SPR_SBUST_N);
}

// Busto del personaje ch con color `color` en el lado s. now=1 carga ya (al
// armar la pantalla, con todo en negro); si no, se oculta y se recarga en
// el vblank siguiente (bust_commit) para no mostrar tiles a medio escribir.
static void bust_set(u8 s, u8 ch, u8 color, u8 now) {
    bust_t *b = &bust[s];
    u8 img = bust_img(ch);
    u8 flip = (img == UI_TITLE_RIGHT) != s;
    u8 recolor = color != b->color;
    if (now || img != b->img || flip != b->flip) {
        b->img = img;
        b->flip = flip;
        recolor = 1;
        if (now) bust_load(s);
        else {
            ui_hide(SPR_SBUST + s * SPR_SBUST_N);
            b->pending = 1;
            b->swap = BUST_SWAP;
        }
    }
    b->color = color;
    if (recolor) bust_colors(s);
}

// Paletas del lado s: fundido/destello global de sp_mix y encima el blanco
// propio del lado. Se mezcla solo si algo cambió; bust_commit las copia.
static void bust_mix(u8 s, u8 flash) {
    bust_t *b = &bust[s];
    if (b->key_ok && b->k_level == sp_level && b->k_white == sp_white && b->k_flash == flash) return;
    b->key_ok = 1; b->k_level = sp_level; b->k_white = sp_white; b->k_flash = flash;
    u8 l = (u8)(((u16)sp_level * BUST_CAP) >> 4);
    for (u8 p = 0; p < bust_npal(s); p++)
        for (u8 k = 1; k < 16; k++) {
            u16 c = col_mix(bust_src[s][p][k], BUST_CAP, 0);
            if (sp_white) c = col_mix(c, sp_level, 1);
            else if (l < BUST_CAP) c = col_mix(bust_src[s][p][k], l, 0);
            if (flash) c = col_mix(c, flash, 1);
            bust_buf[s][p][k] = c;
        }
    bust_dirty = 1;
}

// Al principio del frame, en el vblank, justo después de sp_commit
static void bust_commit(void) {
    if (bust_dirty) {
        bust_dirty = 0;
        for (u8 s = 0; s < 2; s++)
            for (u8 p = 0; p < bust_npal(s); p++) {
                volatile u16 *dst = MMAP_PALBANK1 + (PAL_SBUST + s * PAL_SBUST_N + p) * 16;
                for (u8 k = 1; k < 16; k++) dst[k] = bust_buf[s][p][k];
            }
    }
    for (u8 s = 0; s < 2; s++)
        if (bust[s].pending) { bust[s].pending = 0; bust_load(s); }
}

// Un frame del busto del lado s: posición (entrada/salida + cambio) y paletas
static void bust_draw(u8 s, u8 flash, s16 slide) {
    bust_t *b = &bust[s];
    u16 spr = SPR_SBUST + s * SPR_SBUST_N;
    const uiimg_t *im = &ui_imgs[b->img];
    u8 white = flash;
    s16 out = slide;
    if (b->swap && !b->pending) {
        u8 k = b->swap--;
        u8 w = (u8)(k * 16 / BUST_SWAP);
        if (w > white) white = w;
        out += (s16)(BUST_SWAP_DX * k * k / (BUST_SWAP * BUST_SWAP));
    } else if (b->pending) {
        white = 16;                   // aparece en blanco en el frame de la recarga
    }
    bust_mix(s, white);
    if (b->pending || slide < 0) { ui_hide(spr); return; }
    s16 x = b->flip ? ui_mirror_x(b->img) : im->x;
    x += s ? BUST_DX + out : -BUST_DX - out;
    s16 w = (s16)im->w * 16;
    // fuera de pantalla se oculta: con x negativa grande las columnas darían
    // la vuelta (x es de 9 bits) y asomarían por el otro borde
    if (x <= -w || x >= SCREEN_W) { ui_hide(spr); return; }
    spr_move(spr, x, im->y + BUST_DY, im->h);
}

static void seat_name(u8 s) {
    const character_t *ch = roster[seat[s].cur];
    ng_text(s ? 28 : 2, 27, PAL_TEXT, "          ");
    u8 n = 0;
    while (ch->name[n]) n++;
    ng_text(s ? 38 - n : 2, 27, s ? PAL_TXT_MAG : PAL_TXT_CYAN, ch->name);
}

static void seat_preview(u8 s) {
    seat_t *p = &seat[s];
    const character_t *ch = roster[p->cur];
    u8 pal = s ? PAL_P2 : PAL_P1;
    fighter_init(&p->f, s, s ? SPR_FIGHTER : SPR_FIGHTER + FIGHTER_HW_COLS, pal, ch);
    fighter_reset_round(&p->f, s ? 268 : 52, s ? -1 : 1);   // al costado de la grilla
    fighter_set_anim(&p->f, p->done ? ANIM_WIN : ANIM_IDLE);
    p->f.drawn_img = -1;
    p->pal = char_palette(s, ch, p->color);
    hw_load_palette(pal, p->pal);
    fade_add(pal, p->pal, 16);
    bust_set(s, p->cur, p->color, 0);
    if (!sel_quiet) seat_name(s);
}

static void draw_labels(void) {
    clear_row(LABEL_ROW);
    for (u8 s = 0; s < 2; s++) {
        if (!seat[s].human && !seat[0].done && s == 1) continue;
        s16 x = portrait_x(seat[s].cur);
        const char *lab = s == 0 ? "1P" : seat[1].human ? "2P" : "CPU";
        u8 col = s == 0 ? (u8)(x / 8) : (u8)((x + 64) / 8 - (seat[1].human ? 2 : 3));
        ng_text(col, LABEL_ROW, s ? PAL_TXT_MAG : PAL_TXT_CYAN, lab);
    }
}

static void draw_timer(u8 sec) {
    char b[3] = {'0' + sec / 10, '0' + sec % 10, 0};
    ng_text_tall(35, 3, sec <= 5 ? PAL_TXT_MAG : PAL_TEXT, b);
}

static void confirm(u8 s, u8 color) {
    seat_t *p = &seat[s];
    seat_t *o = &seat[1 - s];
    p->color = color;
    // espejo: el segundo en elegir toma el otro color (regla de KOF)
    if (o->done && o->cur == p->cur && o->color == color) p->color ^= 1;
    p->done = 1;
    p->flash = SEL_BLINK + 1;         // sel_draw lo baja: niveles 16..0
    seat_preview(s);
    g.sel_ch[s] = p->cur;
    g.sel_color[s] = p->color;
    sound_cmd(SND_CHAR_OK);
}

static void portrait_flash(u8 i, u8 level) {
    const uiimg_t *im = &ui_imgs[UI_PORTRAIT_ROBOCLICK + i];
    for (u8 k = 0; k < im->npal; k++) {
        volatile u16 *dst = MMAP_PALBANK1 + (PAL_UI + im->pal0 + k) * 16;
        for (u8 c = 1; c < 16; c++) dst[c] = col_mix(ui_pals[im->pal0 + k][c], level, 1);
    }
}

// Luchador del selector mezclado hacia blanco: 16 blanco pleno, 0 su paleta
static void fighter_blink(u8 s, u8 level) {
    volatile u16 *dst = MMAP_PALBANK1 + (s ? PAL_P2 : PAL_P1) * 16;
    const u16 *src = seat[s].pal;
    for (u8 c = 1; c < 16; c++) dst[c] = col_mix(src[c], level, 1);
}

static void seat_input(u8 s, u8 j) {
    seat_t *p = &seat[s];
    if (p->done) return;
    if (j & (J_LEFT | J_RIGHT)) {
        p->cur = (u8)((p->cur + ((j & J_RIGHT) ? 1 : ROSTER_N - 1)) % ROSTER_N);
        sound_cmd(SND_MENU_MOVE);
        seat_preview(s);
        draw_labels();
    }
    if (j & (J_A | J_C)) confirm(s, 0);
    else if (j & (J_B | J_D)) confirm(s, 1);
}

static void portrait_pos(u8 i, u8 hz, u8 vz) {
    ui_place(UI_PORTRAIT_ROBOCLICK + i, SPR_PORTRAIT + i * 5, portrait_x(i) + 32, PORTRAIT_CY, hz, vz);
}

// Un frame de lo que se mueve siempre: cursores, destellos y luchadores.
// off: cuánto les falta a los luchadores para llegar (P1 desde la izquierda,
// P2 desde la derecha); off < 0 los deja ocultos.
static void sel_draw(u16 t, u8 cursors, s16 off) {
    // cursores: si están en el mismo retrato se alternan
    u8 same = seat[0].cur == seat[1].cur;
    for (u8 s = 0; s < 2; s++) {
        seat_t *p = &seat[s];
        u16 spr = SPR_CURSOR + s * 5;
        u8 show = cursors && (s == 0 || seat[1].human || seat[0].done) && (!same || ((t >> 2) & 1) == s);
        if (p->done) show = show && (p->flash || !same || ((t >> 2) & 1) == s);
        if (show) ui_place(UI_CURSOR, spr, portrait_x(p->cur) + 32, PORTRAIT_CY, 15, 255);
        else ui_hide(spr);
        // el cursor late mientras se elige
        if (!p->done) {
            u16 v = cur_pals[s][2];
            MMAP_PALBANK1[(PAL_CUR1 + s) * 16 + 2] = (t & 8) ? col_mix(v, 6, 1) : v;
        }
        // confirmación: luchador, busto y retrato de blanco a su color, juntos
        if (p->flash) {
            p->flash--;
            portrait_flash(p->cur, p->flash);
            fighter_blink(s, p->flash);
        }
        bust_draw(s, p->flash, bust_slide);
        fighter_tick_anim(&p->f);
        if (off < 0) spr_hide(p->f.spr);
        else fighter_draw(&p->f, s ? -off : off, 0);
    }
}

// SELECT YOUR FIGHTER destapado desde el centro: k letras a cada lado
static void head_reveal(u8 k, u8 pal) {
    char b[sizeof(head_txt)];
    for (u8 i = 0; i < sizeof(head_txt) - 1; i++) {
        s8 d = (s8)i - (s8)(sizeof(head_txt) - 1) / 2;
        if (d < 0) d = -d;
        b[i] = (u8)d <= k ? head_txt[i] : ' ';
    }
    b[sizeof(head_txt) - 1] = 0;
    ng_text_tall(HEAD_COL, HEAD_ROW, pal, b);
}

static void select_ui(u8 sec) {       // lo último de la entrada
    sel_quiet = 0;
    seat_name(0);
    seat_name(1);
    draw_labels();
    draw_timer(sec);
    ng_center_text(28, PAL_TXT_GRAY, "A:COLOR 1   B:COLOR 2");
}

// Frame t de la entrada; devuelve cuánto les falta a los luchadores
static s16 intro_frame(u8 t, u8 sec) {
    static const u8 pop_hz[9] = {1, 4, 8, 12, 15, 15, 13, 14, 15};
    static const u8 pop_vz[9] = {24, 84, 150, 220, 255, 255, 214, 238, 255};
    if (t < 12) sp_mix((u8)((t + 1) * 4 / 3), 0);   // lo copia sp_commit en el frame t+1
    // los bustos entran desde los costados (frames 2-22), antes que los luchadores
    if (t < 2) bust_slide = -1;
    else if (t < 22) { s16 r = 22 - (s16)t; bust_slide = (s16)(170 * r * r / 400); }
    else bust_slide = 0;
    if (t >= 4 && t <= 14) head_reveal(t - 4, PAL_TEXT);
    if (t == 16) head_reveal(10, PAL_TXT_GOLD);
    for (u8 i = 0; i < ROSTER_N; i++) {
        s8 k = (s8)t - (s8)(10 + i * 4);
        if (k < 0 || k >= 9) continue;
        portrait_pos(i, pop_hz[k], pop_vz[k]);
        portrait_flash(i, (u8)(16 - k * 2));
        if (k == 0) sound_cmd(SND_MENU_MOVE);
    }
    if (t == SEL_UI_T) select_ui(sec);
    if (t < 14) return -1;
    if (t >= 30) return 0;
    s16 r = 30 - (s16)t;              // frena al llegar (ease-out cuadrático)
    return (s16)(SLIDE_OFF * r * r / 256);
}

static void intro_skip(u8 sec) {
    sp_mix(16, 0);
    sp_commit();
    bust_slide = 0;
    head_reveal(10, PAL_TXT_GOLD);
    for (u8 i = 0; i < ROSTER_N; i++) {
        portrait_pos(i, 15, 255);
        portrait_flash(i, 0);
    }
    select_ui(sec);
}

static void clear_rows(u8 r0, u8 r1) {
    for (u8 r = r0; r <= r1; r++) clear_row(r);
}

// Salida tipo VS después de la segunda confirmación
static void outro_pals(u8 e) {        // paletas que tiene que mostrar el frame e
    if (e >= 18 && e <= 27) sp_mix((u8)(16 - (e - 18) * 16 / 10), 1);
    else if (e == 28) sp_mix(16, 0);
    else if (e >= 42) sp_mix(e < 58 ? (u8)(58 - e) : 0, 0);
}

static void select_outro(u16 t) {
    // todo lo que queda en pantalla entra al destello y al fundido
    sp_n = 0;
    sky_pals();
    for (u8 i = 0; i < ROSTER_N; i++) {
        const uiimg_t *im = &ui_imgs[UI_PORTRAIT_ROBOCLICK + i];
        for (u8 k = 0; k < im->npal; k++) sp_add(PAL_UI + im->pal0 + k, ui_pals[im->pal0 + k], 16);
    }
    sp_add(PAL_P1, seat[0].pal, 16);
    sp_add(PAL_P2, seat[1].pal, 16);
    s16 off = 0;
    for (u8 e = 0; e < SEL_OUTRO; e++, t++) {
        wait_frame();
        sp_commit();
        bust_commit();
        if (e < 18) {                 // pose de victoria mientras termina el destello
            sel_draw(t, 1, 0);
            outro_pals(e + 1);
            for (u8 s = 0; s < 2; s++) bust_mix(s, seat[s].flash);   // mismo frame que el destello global
            continue;
        }
        if (e == 18) {
            clear_rows(3, 4);
            clear_row(LABEL_ROW);
            clear_rows(27, 28);
            ui_hide(SPR_CURSOR);
            ui_hide(SPR_CURSOR + 5);
        }
        if (e < 26) {                 // los retratos se achican hasta desaparecer
            u8 k = e - 18;
            for (u8 i = 0; i < ROSTER_N; i++) portrait_pos(i, (u8)(15 - 2 * k), (u8)(255 - 34 * k));
        } else if (e == 26) {
            for (u8 i = 0; i < ROSTER_N; i++) ui_hide(SPR_PORTRAIT + i * 5);
        }
        if (e == 20) { msg_show("VS"); sound_cmd(SND_FBHIT); }
        if (e >= 20) msg_update();
        if (e == 36) sp_add(PAL_MSG, pal_msg, 16);    // desde acá el VS también se funde
        if (e >= 34) {                // salen disparados (ease-in)
            s16 k = (s16)(e - 34);
            off = k * k * 5 / 8;
            if (off > 170) off = 170;
        }
        for (u8 s = 0; s < 2; s++) {
            fighter_tick_anim(&seat[s].f);
            fighter_draw(&seat[s].f, s ? -off : off, 0);
        }
        outro_pals(e + 1);
        // los bustos se van con los luchadores, un poco más lentos, y se funden
        for (u8 s = 0; s < 2; s++) bust_draw(s, 0, off * 3 / 4);
    }
    wait_frame();
    sp_commit();
    bust_commit();
    msg_hide();
    fade_apply(0);                    // el resto de las paletas registradas, también a negro
}

static void front_select(u8 vs_human) {
    g.mode = MODE_SELECT;
    sound_cmd(SND_MUS_SELECT);
    clear_screen();
    // el fondo y los bustos se cargan ya en negro (las paletas de hardware
    // todavía tienen las del título a pleno) y los levanta la entrada
    sp_n = 0;
    sky_pals();
    {
        const uiimg_t *im = &ui_imgs[UI_TITLE_SKY];
        for (u8 p = 0; p < im->npal; p++) fade_add(PAL_UI + im->pal0 + p, ui_pals[im->pal0 + p], 16);
    }
    sp_add(PAL_TEXT, txt_white, 16);
    for (u8 i = 0; i < 4; i++) sp_add(PAL_TXT_CYAN + i, txt_pals[i], 16);
    sp_mix(0, 0);
    sp_commit();
    bust[0] = (bust_t){0};
    bust[1] = (bust_t){0};
    bust_slide = -1;
    ui_load(UI_TITLE_SKY, SPR_SBG, 0);
    ui_put(UI_TITLE_SKY, SPR_SBG, 0, 0);
    for (u8 i = 0; i < ROSTER_N; i++) {
        u8 img = UI_PORTRAIT_ROBOCLICK + i;
        ui_palettes(img, 16);
        ui_load(img, SPR_PORTRAIT + i * 5, 0);
        ui_hide(SPR_PORTRAIT + i * 5);
    }
    hw_load_palette(PAL_CUR1, cur_pals[0]);
    hw_load_palette(PAL_CUR2, cur_pals[1]);
    fade_add(PAL_CUR1, cur_pals[0], 16);
    fade_add(PAL_CUR2, cur_pals[1], 16);
    ui_load_as(UI_CURSOR, SPR_CURSOR, PAL_CUR1);
    ui_load_as(UI_CURSOR, SPR_CURSOR + 5, PAL_CUR2);
    ui_hide(SPR_CURSOR);
    ui_hide(SPR_CURSOR + 5);

    seat[0] = (seat_t){0};
    seat[1] = (seat_t){0};
    seat[1].cur = ROSTER_N > 1 ? 1 : 0;
    seat[0].human = 1;
    seat[1].human = vs_human;
    sel_quiet = 1;
    // bustos iniciales: carga directa (todo está en negro todavía)
    bust_set(0, seat[0].cur, 0, 1);
    bust_set(1, seat[1].cur, 0, 1);
    for (u8 s = 0; s < 2; s++) bust_mix(s, 0);
    bust_commit();
    seat_preview(0);
    seat_preview(1);
    for (u8 s = 0; s < 2; s++) {
        g.sel_ch[s] = seat[s].cur;
        g.sel_color[s] = seat[s].color;
    }

    u8 sec = SELECT_TIME, roulette = 0, intro = 0;
    u16 frames = 0, t;
    pads_sync();
    for (t = 0;; t++) {
        wait_frame();
        sp_commit();
        bust_commit();
        u8 j1 = pad_edge(0), j2 = pad_edge(1), st = stat_edge();
        if (intro < SEL_INTRO) {
            // A (de cualquiera) o START de P1 saltan la entrada
            if (((j1 | j2) & J_A) || (st & CNT_START1)) {
                intro_skip(sec);
                intro = SEL_INTRO;
                sel_draw(t, 1, 0);
            } else {
                s16 off = intro_frame(intro, sec);
                sel_draw(t, intro >= SEL_UI_T, off);
                intro++;
            }
            continue;
        }
        // un retador puede entrar con START de P2 mientras elige la CPU
        if (!seat[1].human && !seat[1].done && (st & CNT_START2)) {
            seat[1].human = 1;
            roulette = 0;
            draw_labels();
        }
        seat_input(0, j1);
        if (seat[1].human) seat_input(1, j2);
        // la CPU elige con una ruleta cuando P1 ya confirmó
        if (!seat[1].human && seat[0].done && !seat[1].done) {
            if (++roulette % 5 == 0) {
                seat[1].cur = (u8)((seat[1].cur + 1) % ROSTER_N);
                seat_preview(1);
                draw_labels();
                sound_cmd(SND_MENU_MOVE);
            }
            if (roulette >= 40 + (g.frame & 7) * 5) confirm(1, 0);
        }
        if (++frames == 60 && sec) {
            frames = 0;
            draw_timer(--sec);
            if (!sec) {
                if (!seat[0].done) confirm(0, 0);
                if (!seat[1].done && seat[1].human) confirm(1, 0);
                roulette = 60;
            }
        }
        sel_draw(t, 1, 0);
        if (seat[0].done && seat[1].done) break;
    }
    select_outro(t + 1);
    for (u8 s = 0; s < 2; s++) {
        g.sel_ch[s] = seat[s].cur;
        g.sel_color[s] = seat[s].color;
    }
}

// ------------------------------------------------------------ flujo

static void defaults(void) {
    g.sel_ch[0] = 0; g.sel_ch[1] = ROSTER_N > 1 ? 1 : 0;
    g.sel_color[0] = 0; g.sel_color[1] = g.sel_ch[0] == g.sel_ch[1];
}

void front_run(void) {
    u8 mode = 0;
    quick = 0;
    while (bios_user_mode != USER_MODE_GAME) {
        if (front_logos()) break;
        mode = front_title(1);
        if (mode) break;
        // demo con personajes al azar
        g.sel_ch[0] = (u8)(g.frame % ROSTER_N);
        g.sel_ch[1] = (u8)((g.frame >> 3) % ROSTER_N);
        g.sel_color[0] = 0;
        g.sel_color[1] = g.sel_ch[0] == g.sel_ch[1];
        g.vs_human = 0;
        if (game_match(1, 0, 0)) { started(); break; }
    }
    if (quick || mode == 3) {
        defaults();
        g.vs_human = 0;
        game_match(0, 1, 0);
        return;
    }
    if (!mode) mode = front_title(0);
    front_select(mode == 2);
    g.vs_human = mode == 2;
    game_match(0, 1, mode == 2);
}
