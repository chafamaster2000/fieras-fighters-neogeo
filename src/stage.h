#ifndef STAGE_H
#define STAGE_H
#include <ngdevkit/types.h>
void stage_init(void);
// cam_x: 0..CAM_RANGE. Devuelve el scroll aplicado a cada capa en scroll_out[3].
void stage_update(s16 cam_x, u16 *scroll_out);
#endif
