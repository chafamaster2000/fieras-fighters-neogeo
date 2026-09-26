// Flujo del BIOS: demo CPU contra CPU (attract) hasta que el jugador
// aprieta START; después un match contra la CPU. P2 puede entrar en
// cualquier momento apretando su START.
#include <ngdevkit/neogeo.h>
#include <ngdevkit/bios-ram.h>
#include "game.h"
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
    if (game_match(1, 0, 0) || bios_user_mode == USER_MODE_GAME) {
        game_match(0, 1, 0);
        bios_player_mod1 = 0;
    }
    return 0;
}

int main_mvs_title(void) {
    sound_cmd(SND_RESET);
    g.magic = GAME_MAGIC;
    game_match(1, 0, 0);
    game_match(0, 1, 0);
    bios_player_mod1 = 0;
    return 0;
}
