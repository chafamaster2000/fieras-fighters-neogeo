#ifndef MSG_H
#define MSG_H
#include <ngdevkit/types.h>
// Mensajes grandes centrados (ROUND 1, FIGHT!, K.O.) hechos con sprites.
// Entran con el zoom por hardware de la Neo Geo (SCB2), como en KOF.
void msg_show(const char *text);
void msg_hide(void);
void msg_update(void);        // una vez por frame
#endif
