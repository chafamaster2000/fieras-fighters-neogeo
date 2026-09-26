;;; Driver de sonido de FIERAS FIGHTERS sobre nullsound (ngdevkit).
;;; El 68k escribe el número de comando en REG_SOUND (0x320000, ver src/sound.h);
;;; el Z80 lo recibe por NMI, lo encola y lo ejecuta desde su loop principal.
;;;
;;; Reparto de canales del YM2610:
;;;   FM1-FM4, ADPCM-A5 y A6 ... música (streams NSS generados desde assets/music/*.fur)
;;;   ADPCM-A1 ................. impactos: golpe, golpe fuerte, bloqueo, bola, K.O.
;;;   ADPCM-A2 ................. movimiento y UI: swing, cursor, fuego del título
;;;   ADPCM-A3 ................. bola de energía, caída, confirmar, golpe del logo
;;;   ADPCM-A4 ................. locutor (ROUND 1, FIGHT!, K.O....)
;;; Un efecto nuevo en el mismo canal corta al anterior (prioridad por
;;; recencia, como en los juegos de SNK). La música nunca pierde sus canales.
;;;
;;; ARCHIVO ESCRITO A MANO: si agregás un sample, sumalo también en
;;; assets/samples-map.yaml y en src/sound.h.
        .include "helpers.inc"
        .area   CODE

cmd_jmptable::
        jp      snd_command_unused
        jp      snd_command_01_prepare_for_rom_switch
        jp      music_ngdevkit_eye_catcher
        jp      snd_command_03_reset_driver
        jp      play_whoosh            ;  4 WHOOSH
        jp      play_hit               ;  5 HIT
        jp      play_heavy             ;  6 HEAVY
        jp      play_block             ;  7 BLOCK
        jp      play_fireball          ;  8 FIREBALL
        jp      play_ko                ;  9 KO
        jp      play_fbhit             ; 10 FBHIT
        jp      play_land              ; 11 LAND
        jp      play_menu_move         ; 12 MENU_MOVE
        jp      play_menu_ok           ; 13 MENU_OK
        jp      play_logo              ; 14 LOGO
        jp      play_fire              ; 15 FIRE
        jp      play_vo_round1         ; 16 VO_ROUND1
        jp      play_vo_round2         ; 17 VO_ROUND2
        jp      play_vo_final          ; 18 VO_FINAL
        jp      play_vo_fight          ; 19 VO_FIGHT
        jp      play_vo_ko             ; 20 VO_KO
        jp      play_vo_youwin         ; 21 VO_YOUWIN
        jp      snd_command_unused     ; 22 libre
        jp      snd_command_unused     ; 23 libre
        jp      music_title            ; 24 MUS_TITLE
        jp      music_select           ; 25 MUS_SELECT
        jp      music_fight            ; 26 MUS_FIGHT
        jp      music_win              ; 27 MUS_WIN
        jp      snd_stream_stop        ; 28 MUS_STOP
        jp      music_cut              ; 29 MUS_CUT
        jp      snd_command_unused     ; 30 libre
        jp      snd_command_unused     ; 31 libre
        init_unused_cmd_jmptable

;;; --- efectos: cada uno reproduce su sample en su canal ADPCM-A
play_whoosh:
        ld      ix, #sfx_whoosh
        jp      snd_adpcm_a_play

play_hit:
        ld      ix, #sfx_hit
        jp      snd_adpcm_a_play

play_heavy:
        ld      ix, #sfx_heavy
        jp      snd_adpcm_a_play

play_block:
        ld      ix, #sfx_block
        jp      snd_adpcm_a_play

play_fireball:
        ld      ix, #sfx_fireball
        jp      snd_adpcm_a_play

play_ko:
        ld      ix, #sfx_ko
        jp      snd_adpcm_a_play

play_fbhit:
        ld      ix, #sfx_fbhit
        jp      snd_adpcm_a_play

play_land:
        ld      ix, #sfx_land
        jp      snd_adpcm_a_play

play_menu_move:
        ld      ix, #sfx_menu_move
        jp      snd_adpcm_a_play

play_menu_ok:
        ld      ix, #sfx_menu_ok
        jp      snd_adpcm_a_play

play_logo:
        ld      ix, #sfx_logo
        jp      snd_adpcm_a_play

play_fire:
        ld      ix, #sfx_fire
        jp      snd_adpcm_a_play

play_vo_round1:
        ld      ix, #sfx_vo_round1
        jp      snd_adpcm_a_play

play_vo_round2:
        ld      ix, #sfx_vo_round2
        jp      snd_adpcm_a_play

play_vo_final:
        ld      ix, #sfx_vo_final
        jp      snd_adpcm_a_play

play_vo_fight:
        ld      ix, #sfx_vo_fight
        jp      snd_adpcm_a_play

play_vo_ko:
        ld      ix, #sfx_vo_ko
        jp      snd_adpcm_a_play

play_vo_youwin:
        ld      ix, #sfx_vo_youwin
        jp      snd_adpcm_a_play

;;; --- música: cambia de stream (stream_play corta el anterior)
music_title:
        ld      bc, #instr_title
        ld      de, #nss_title
        jp      snd_stream_play

music_select:
        ld      bc, #instr_select
        ld      de, #nss_select
        jp      snd_stream_play

music_fight:
        ld      bc, #instr_fight
        ld      de, #nss_fight
        jp      snd_stream_play

music_win:
        ld      bc, #instr_win
        ld      de, #nss_win
        jp      snd_stream_play

;;; --- corte de música que respeta los efectos: deja de leer los streams,
;;; suelta las teclas de FM1-FM4 (suenan su release natural) y para los
;;; ADPCM-A 5 y 6 de la batería. No toca A1-A4, así el golpe del K.O. y la
;;; voz del locutor siguen sonando. (snd_stream_stop resetea todo el YM2610;
;;; volume_fade_out de esta versión de nullsound deja muteado el ADPCM-A
;;; después del fundido, por eso no lo usamos.)
music_cut:
        xor     a
        ld      (state_stream_in_use), a
        ld      b, #0x28                ; REG_FM_KEY_ON_OFF_OPS: key off
        ld      c, #0x01
        call    ym2610_write_port_a
        ld      b, #0x28
        ld      c, #0x02
        call    ym2610_write_port_a
        ld      b, #0x28
        ld      c, #0x05
        call    ym2610_write_port_a
        ld      b, #0x28
        ld      c, #0x06
        call    ym2610_write_port_a
        ld      b, #0x00                ; REG_ADPCM_A_START_STOP (puerto B)
        ld      c, #0xb0                ; dump de A5 y A6
        jp      ym2610_write_port_b

;;; --- descriptores de samples: inicio y fin (>>8 en la V-ROM, los
;;; calcula vromtool en build/assets/samples.inc), canal, L/R+volumen, bit del canal
        .include "assets/samples.inc"

sfx_whoosh:
        .db     WHOOSH_START_LSB, WHOOSH_START_MSB
        .db     WHOOSH_STOP_LSB, WHOOSH_STOP_MSB
        .db     1, 0xda, 0x02   ; A2 movimiento/UI, vol 26

sfx_hit:
        .db     HIT_START_LSB, HIT_START_MSB
        .db     HIT_STOP_LSB, HIT_STOP_MSB
        .db     0, 0xdf, 0x01   ; A1 golpes, vol 31

sfx_heavy:
        .db     HEAVY_START_LSB, HEAVY_START_MSB
        .db     HEAVY_STOP_LSB, HEAVY_STOP_MSB
        .db     0, 0xdf, 0x01   ; A1 golpes, vol 31

sfx_block:
        .db     BLOCK_START_LSB, BLOCK_START_MSB
        .db     BLOCK_STOP_LSB, BLOCK_STOP_MSB
        .db     0, 0xdd, 0x01   ; A1 golpes, vol 29

sfx_fireball:
        .db     FIREBALL_START_LSB, FIREBALL_START_MSB
        .db     FIREBALL_STOP_LSB, FIREBALL_STOP_MSB
        .db     2, 0xdd, 0x04   ; A3 fuego/UI, vol 29

sfx_ko:
        .db     KO_START_LSB, KO_START_MSB
        .db     KO_STOP_LSB, KO_STOP_MSB
        .db     0, 0xdf, 0x01   ; A1 golpes, vol 31

sfx_fbhit:
        .db     FBHIT_START_LSB, FBHIT_START_MSB
        .db     FBHIT_STOP_LSB, FBHIT_STOP_MSB
        .db     0, 0xdf, 0x01   ; A1 golpes, vol 31

sfx_land:
        .db     LAND_START_LSB, LAND_START_MSB
        .db     LAND_STOP_LSB, LAND_STOP_MSB
        .db     2, 0xd8, 0x04   ; A3 fuego/UI, vol 24

sfx_menu_move:
        .db     MENU_MOVE_START_LSB, MENU_MOVE_START_MSB
        .db     MENU_MOVE_STOP_LSB, MENU_MOVE_STOP_MSB
        .db     1, 0xd8, 0x02   ; A2 movimiento/UI, vol 24

sfx_menu_ok:
        .db     MENU_OK_START_LSB, MENU_OK_START_MSB
        .db     MENU_OK_STOP_LSB, MENU_OK_STOP_MSB
        .db     2, 0xdc, 0x04   ; A3 fuego/UI, vol 28

sfx_logo:
        .db     LOGO_START_LSB, LOGO_START_MSB
        .db     LOGO_STOP_LSB, LOGO_STOP_MSB
        .db     2, 0xdf, 0x04   ; A3 fuego/UI, vol 31

sfx_fire:
        .db     FIRE_START_LSB, FIRE_START_MSB
        .db     FIRE_STOP_LSB, FIRE_STOP_MSB
        .db     1, 0xdb, 0x02   ; A2 movimiento/UI, vol 27

sfx_vo_round1:
        .db     VO_ROUND1_START_LSB, VO_ROUND1_START_MSB
        .db     VO_ROUND1_STOP_LSB, VO_ROUND1_STOP_MSB
        .db     3, 0xdf, 0x08   ; A4 locutor, vol 31

sfx_vo_round2:
        .db     VO_ROUND2_START_LSB, VO_ROUND2_START_MSB
        .db     VO_ROUND2_STOP_LSB, VO_ROUND2_STOP_MSB
        .db     3, 0xdf, 0x08   ; A4 locutor, vol 31

sfx_vo_final:
        .db     VO_FINAL_START_LSB, VO_FINAL_START_MSB
        .db     VO_FINAL_STOP_LSB, VO_FINAL_STOP_MSB
        .db     3, 0xdf, 0x08   ; A4 locutor, vol 31

sfx_vo_fight:
        .db     VO_FIGHT_START_LSB, VO_FIGHT_START_MSB
        .db     VO_FIGHT_STOP_LSB, VO_FIGHT_STOP_MSB
        .db     3, 0xdf, 0x08   ; A4 locutor, vol 31

sfx_vo_ko:
        .db     VO_KO_START_LSB, VO_KO_START_MSB
        .db     VO_KO_STOP_LSB, VO_KO_STOP_MSB
        .db     3, 0xdf, 0x08   ; A4 locutor, vol 31

sfx_vo_youwin:
        .db     VO_YOUWIN_START_LSB, VO_YOUWIN_START_MSB
        .db     VO_YOUWIN_STOP_LSB, VO_YOUWIN_STOP_MSB
        .db     3, 0xdf, 0x08   ; A4 locutor, vol 31
