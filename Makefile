# Copyright (c) 2015-2025 Damien Ciabrini
# This file is part of ngdevkit
#
# ngdevkit is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# ngdevkit is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with ngdevkit.  If not, see <http://www.gnu.org/licenses/>.



all: cart bios

# These are various variables that you might want to customize
# based on your liking or your requirements.
# location of generated and compiled content
BUILDDIR=build
# all directories that contain source to be compiled
SRCDIRS=assets src
# default build flags, can be overriden per target
CFLAGS=-I$(BUILDDIR) -Isrc -std=c99 -fomit-frame-pointer -O2 -g -Wall -Werror=overflow
LDFLAGS=
Z80FLAGS=
Z80LDFLAGS=

# This is an autoconf-generated configuration for your environment
# (ngdevkit path, OS-specific configs...)
include config.mk

# This defines the layout of your game cartridge
# You can customize it to match your requirements
# Name of the rom file created
GAMEROM=fighter
# Game title, long description
GAMETITLE=Neo Geo Fighter prototype
include rom.mk

# All the generic build targets (68k, Z80, assets, run)
include build.mk

# Some default targets for running your project via emulators
include emu.mk



# program ROM: your main program
# Add your dependencies below to compile your sources into an ELF binary
# that is used as the content of the program ROM (referenced by symbol PROM1)
# 
# Note: build rules (%.c -> %.o -> %.elf) are defined in Makefile.build
ELF=$(BUILDDIR)/rom.elf
OBJS=$(patsubst %.c,$(BUILDDIR)/%.o,$(wildcard src/*.c src/gen/*.c))
$(ELF):	$(OBJS)
$(OBJS): $(wildcard src/*.h src/gen/*.h)
$(PROM1): $(ELF)



# fixed tiles ROM: all your 8x8 pixel tiles for the fixed layer
# Add your dependencies below to convert images to fixed tile binary data
# and pack it into the fixed tile ROM (referenced by symbol SROM1)
# 
# By default, this makefile creates a tileset ROM with small and tall
# latin characters for printing ASCII string, and tiles that are
# displayed during the attract mode.
# Note: build rules (%.gif -> %.fix) are defined in Makefile.build
# fix: fuente base (1280 tiles) y después los tiles del HUD (ver HUD_FIX_BASE en src/hud.c)
$(SROM1): $(BUILDDIR)/assets/base-srom-text-shadow.fix $(BUILDDIR)/assets/hud.fix



# sprite ROM: all your 16x16 pixel tiles for sprites
# Add your dependencies below to convert images to fixed sprite binary data
# and pack it into two separate sprite ROMs that hold odd and even bits of
# color information (referenced by symbols CROM1 and CROM2)
#
# By default, this makefile creates CROMs with tiles for displaying a ngdevkit
# logo during the attract mode.
# Note: build rules (%.gif -> %.c<1,2>) are defined in Makefile.build
# El orden define el número de tile y tiene que coincidir con tools/make_assets.py
# (TILE_* en src/gen/assets.h): logo del BIOS (0-255) -> efectos -> cielo ->
# piso (5 franjas) -> fuente -> ciudad con público animado -> personajes P1 y P2.
# Los personajes van al final: tools/neosprite.py los numera desde TILE_END.
CROM_PARTS=base-crom-logo fx proj sky floor0 floor1 floor2 floor3 floor4 font city char_p1 char_p2
$(CROM1): $(CROM_PARTS:%=$(BUILDDIR)/assets/%.c1)
$(CROM2): $(CROM_PARTS:%=$(BUILDDIR)/assets/%.c2)



# sound driver ROM: nullsound + your configured sound commands
# Add your dependencies below to compile your z80 sources into a HEX binary
# that is used as the sound driver ROM (referenced by symbol MROM1)
#
# By default, this makefile uses the empty sound driver provided by ngdevkit
# Note: build rules (%.s -> %.o -> %.ihx) are defined in Makefile.build
SOUND_DRIVER=$(BUILDDIR)/sound_driver.ihx
$(MROM1): $(SOUND_DRIVER)
$(SOUND_DRIVER): $(BUILDDIR)/assets/ngdevkit-eye-catcher.lib $(BUILDDIR)/src/sound_driver.rel
$(BUILDDIR)/src/sound_driver.rel: $(BUILDDIR)/assets/samples.inc
$(VROM1): assets/samples-map.yaml



# sound FX ROM: all your ADPCM samples
# Add your dependencies below to convert your samples into suitable
# ADPCM data and pack it into the sound ROM (referenced by symbol VROM1)
#
# Music and SFX assets can be managed with <> rather to generate
# the dependencies automatically.
# By default, no sample is used, so the VROM is empty
# Note: build rules (%.wav-> %.adpcm<a,b>) are defined in Makefile.build



# One-time asset preprocessing
# Various assets may have to be processed before they can be used to
# build your ROM, for example:
#   . the ngdevkit assets must be converted to sprite and text tiles
#   . converting your SFX assets from .mp3 into .wav so they can be
#     processed by ngdevkit tools
# To handle these pre-processing requirements, `make` automatically
# runs into all subdirectories under ./setup/, so you get a chance
# to preprocess what you need before anything is built.
#
# Other assets must be processed only once to generate source files
# that gets built into your ROM, for example:
#   . converting your musics from .fur to z80 code and data files
#   . generating make dependencies to pack gfx or sound assets into
#     the right ROM bank based on your input assets
# Those actions can be achieved by creating custom make targets
# that get invoked automatically when added to the variable below.
CUSTOM_GENERATE_TARGETS=generate-sfx
generate-sfx: $(BUILDDIR)/assets/samples.inc
$(BUILDDIR)/assets/samples.inc: assets/samples-map.yaml $(wildcard assets/sfx/*.wav)
	$(VROMTOOL) --asm -s $(VROMSIZE) $< -o $(VROM1) -m $@



# a default `clean` target removes .o .elf and .ihx from the builddir
# a default `distclean` target removes the build directory entirely
# you can customize clean up by adding dependencies to those targets



# Regenerar assets placeholder (gráficos, paletas, animaciones y sonidos).
# Los luchadores procedurales pasan por el mismo conversor que el arte real.
CHARS=ROBO NINJA
assets:
	python3 tools/make_assets.py
	for n in $(CHARS); do python3 tools/neosprite.py char art/tmp-procedural/$$n --name $$n || exit 1; done
	tools/make_sfx.sh

# Arte real: art/src/characters/<NOMBRE>/ y
# art/src/stage/. Lo que falte sale del procedural (art/tmp-procedural/).
art:
	python3 tools/make_assets.py
	for n in $(CHARS); do \
	  d=art/src/characters/$$n; [ -d $$d/idle ] || d=art/tmp-procedural/$$n; \
	  python3 tools/neosprite.py char $$d --name $$n --preview || exit 1; \
	done
	python3 tools/neosprite.py stage art/src/stage

.PHONY: assets art
