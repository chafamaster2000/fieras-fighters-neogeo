#!/bin/sh
# Efectos PLACEHOLDER sintetizados con sox. ADPCM-A: WAV mono, 18500 Hz, 16 bits.
set -e
cd "$(dirname "$0")/../assets/sfx"
R="-r 18500 -c 1 -b 16"
sox -n $R whoosh.wav synth 0.14 pinknoise vol 0.5 bandpass 1400 900 fade 0.02 0.14 0.08
sox -n $R hit.wav synth 0.12 brownnoise vol 0.9 synth 0.12 sine mix 120-60 fade 0 0.12 0.08
sox -n $R heavy.wav synth 0.22 brownnoise vol 1.0 synth 0.22 sine mix 90-40 fade 0 0.22 0.15
sox -n $R block.wav synth 0.07 square 1800-900 vol 0.35 fade 0 0.07 0.04
sox -n $R fireball.wav synth 0.35 sawtooth 200-700 vol 0.4 fade 0.02 0.35 0.2
sox -n $R ko.wav synth 0.7 brownnoise vol 1.0 synth 0.7 sine mix 70-30 fade 0 0.7 0.5
echo "sfx listos"
