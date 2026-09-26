;;; Comandos de sonido del prototipo de pelea (driver nullsound de ngdevkit).
;;; El 68k escribe el número de comando en 0x320000 (ver src/sound.h).
        .include "helpers.inc"
        .area   CODE

cmd_jmptable::
        jp      snd_command_unused
        jp      snd_command_01_prepare_for_rom_switch
        jp      music_ngdevkit_eye_catcher
        jp      snd_command_03_reset_driver
        jp      play_whoosh    ; 4
        jp      play_hit       ; 5
        jp      play_heavy     ; 6
        jp      play_block     ; 7
        jp      play_fireball  ; 8
        jp      play_ko        ; 9
        init_unused_cmd_jmptable

play_whoosh:
        ld      ix, #adpcm_a_whoosh
        call    snd_adpcm_a_play
        ret

play_hit:
        ld      ix, #adpcm_a_hit
        call    snd_adpcm_a_play
        ret

play_heavy:
        ld      ix, #adpcm_a_heavy
        call    snd_adpcm_a_play
        ret

play_block:
        ld      ix, #adpcm_a_block
        call    snd_adpcm_a_play
        ret

play_fireball:
        ld      ix, #adpcm_a_fireball
        call    snd_adpcm_a_play
        ret

play_ko:
        ld      ix, #adpcm_a_ko
        call    snd_adpcm_a_play
        ret

        .include "assets/samples.inc"

adpcm_a_whoosh:
        .db     WHOOSH_START_LSB
        .db     WHOOSH_START_MSB
        .db     WHOOSH_STOP_LSB
        .db     WHOOSH_STOP_MSB
        .db     0
        .db     0xdf
        .db     1

adpcm_a_hit:
        .db     HIT_START_LSB
        .db     HIT_START_MSB
        .db     HIT_STOP_LSB
        .db     HIT_STOP_MSB
        .db     1
        .db     0xdf
        .db     2

adpcm_a_heavy:
        .db     HEAVY_START_LSB
        .db     HEAVY_START_MSB
        .db     HEAVY_STOP_LSB
        .db     HEAVY_STOP_MSB
        .db     1
        .db     0xdf
        .db     2

adpcm_a_block:
        .db     BLOCK_START_LSB
        .db     BLOCK_START_MSB
        .db     BLOCK_STOP_LSB
        .db     BLOCK_STOP_MSB
        .db     2
        .db     0xdf
        .db     4

adpcm_a_fireball:
        .db     FIREBALL_START_LSB
        .db     FIREBALL_START_MSB
        .db     FIREBALL_STOP_LSB
        .db     FIREBALL_STOP_MSB
        .db     3
        .db     0xdf
        .db     8

adpcm_a_ko:
        .db     KO_START_LSB
        .db     KO_START_MSB
        .db     KO_STOP_LSB
        .db     KO_STOP_MSB
        .db     1
        .db     0xdf
        .db     2

