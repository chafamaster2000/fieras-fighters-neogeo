// Flujo del BIOS: attract (logos, título y demo CPU contra CPU) hasta que
// el jugador aprieta START; después menú, selector y match (src/front.c).
#include <ngdevkit/neogeo.h>
#include <ngdevkit/bios-ram.h>
#include "game.h"
#include "front.h"
#include "sound.h"

#define USER_MODE_GAME 2

void player_start(void) {
    bios_user_mode = USER_MODE_GAME;
    bios_player_mod1 = 1;
}

void coin_sound(void) {}

int main(void) {
    sound_cmd(SND_RESET);
    g.magic = GAME_MAGIC;
    g.mode = MODE_BOOT;
    front_run();
    bios_player_mod1 = 0;
    return 0;
}

int main_mvs_title(void) {
    sound_cmd(SND_RESET);
    g.magic = GAME_MAGIC;
    front_run();
    bios_player_mod1 = 0;
    return 0;
}
