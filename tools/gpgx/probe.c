/* Exports for tools/gpgx.py: where the Mega-CD memories live inside Genesis Plus GX, and PC breakpoints for the
   main and sub 68000 (checked in the patched m68k_run / s68k_run loops, see tools/gpgx.py PATCHES). */
#include "shared.h"

unsigned int gpgx_bp[2][32];
int gpgx_bp_n[2];
void (*gpgx_bp_cb)(int cpu, unsigned int pc);

void gpgx_check_bp(int cpu, unsigned int pc)
{
  int i;
  for (i = 0; i < gpgx_bp_n[cpu]; i++)
    if (gpgx_bp[cpu][i] == pc && gpgx_bp_cb)
      gpgx_bp_cb(cpu, pc);
}

uint8 *gpgx_prg_ram(void) { return scd.prg_ram; }
uint8 *gpgx_word_ram_2m(void) { return scd.word_ram_2M; }
uint8 *gpgx_word_ram(int bank) { return scd.word_ram[bank]; }
uint8 *gpgx_work_ram(void) { return work_ram; }
uint8 *gpgx_vram(void) { return vram; }
uint8 *gpgx_cram(void) { return cram; }
uint8 *gpgx_vsram(void) { return vsram; }
uint8 *gpgx_vdp_reg(void) { return reg; }

unsigned int gpgx_reg(int cpu, int r) { return cpu ? s68k_get_reg(r) : m68k_get_reg(r); }
void gpgx_set_reg(int cpu, int r, unsigned int v) { if (cpu) s68k_set_reg(r, v); else m68k_set_reg(r, v); }
