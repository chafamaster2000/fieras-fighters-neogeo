#ifndef SOUND_H
#define SOUND_H
// Comandos del driver Z80 (ver src/sound_driver.s)
#include <ngdevkit/neogeo.h>
#define REG_SOUND ((volatile u8*)0x320000)
#define SND_RESET    3
#define SND_WHOOSH   4
#define SND_HIT      5
#define SND_HEAVY    6
#define SND_BLOCK    7
#define SND_FIREBALL 8
#define SND_KO       9
static inline void sound_cmd(u8 cmd) { *REG_SOUND = cmd; }
#endif
