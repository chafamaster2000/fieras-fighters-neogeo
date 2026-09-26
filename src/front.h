#ifndef FRONT_H
#define FRONT_H
#include <ngdevkit/types.h>
// Flujo previo al combate, como las intros de Neo Geo:
// presentación con logos -> título (PRESS START) -> demo CPU contra CPU,
// en loop hasta que alguien aprieta START; después menú, selector y match.
// START con D apretado salta menú y selector (atajo de prueba).
void front_run(void);
#endif
