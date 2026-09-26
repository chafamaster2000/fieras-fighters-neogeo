#ifndef AI_H
#define AI_H
#include "fighter.h"
void ai_seed(u16 seed);
u16 ai_rng(void);
// Devuelve los bits de joystick (absolutos, como el BIOS) para este frame.
u8 ai_input(fighter_t *f, const fighter_t *opp);
#endif
