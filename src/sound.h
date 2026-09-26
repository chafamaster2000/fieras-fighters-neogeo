#ifndef SOUND_H
#define SOUND_H
// Comandos del driver Z80 (src/sound_driver.s).
#include <ngdevkit/neogeo.h>

#define REG_SOUND ((volatile u8*)0x320000)

#define SND_RESET      3   // reservado de la BIOS: reinicia el driver

// Efectos y locutor (ADPCM-A 1-4)
#define SND_WHOOSH       4   // A2 movimiento/UI
#define SND_HIT          5   // A1 golpes
#define SND_HEAVY        6   // A1 golpes
#define SND_BLOCK        7   // A1 golpes
#define SND_FIREBALL     8   // A3 fuego/UI
#define SND_KO           9   // A1 golpes
#define SND_FBHIT       10   // A1 golpes
#define SND_LAND        11   // A3 fuego/UI
#define SND_MENU_MOVE   12   // A2 movimiento/UI
#define SND_MENU_OK     13   // A3 fuego/UI
#define SND_LOGO        14   // A3 fuego/UI
#define SND_FIRE        15   // A2 movimiento/UI
#define SND_VO_ROUND1   16   // A4 locutor
#define SND_VO_ROUND2   17   // A4 locutor
#define SND_VO_FINAL    18   // A4 locutor
#define SND_VO_FIGHT    19   // A4 locutor
#define SND_VO_KO       20   // A4 locutor
#define SND_VO_YOUWIN   21   // A4 locutor
#define SND_CHAR_OK     22   // A3 fuego/UI: personaje elegido en el selector

// Música (FM + batería en ADPCM-A 5-6). Loopea sola salvo MUS_WIN.
#define SND_MUS_TITLE   24
#define SND_MUS_SELECT  25
#define SND_MUS_FIGHT   26
#define SND_MUS_WIN     27
#define SND_MUS_STOP    28   // silencio total: resetea el YM2610 (música y efectos)
#define SND_MUS_CUT     29   // corta solo la música; los efectos y el locutor siguen

// Manda un comando al Z80. El Z80 contesta con el mismo número y el bit 7
// prendido cuando lo encoló; esperamos ese eco (con un tope de ~0.5 ms) para
// que dos comandos seguidos en el mismo frame no se pisen en el latch.
static inline void sound_cmd(u8 cmd) {
    *REG_SOUND = cmd;
    for (volatile u8 d = 0; d < 12; d++) {}
    for (u16 i = 0; i < 300; i++) {
        if (*REG_SOUND == (u8)(cmd | 0x80)) break;
    }
}
#endif
