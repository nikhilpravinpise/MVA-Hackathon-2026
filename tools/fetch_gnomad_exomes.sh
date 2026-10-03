#!/usr/bin/env bash
# Download gnomAD v4.1 exomes sites VCFs (per chromosome, with .tbi)
# via fetch_big parallel ranges - replaces the slow remote-tabix slice.
set -euo pipefail
BASE="https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/exomes"
OUT="env/vep_ann/gnomad_exomes"
mkdir -p "$OUT"

for c in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 X Y; do
  f="gnomad.exomes.v4.1.sites.chr${c}.vcf.bgz"
  [ -s "$OUT/$f" ] || .venv/Scripts/python.exe tools/fetch_big.py \
      "$BASE/$f" "$OUT/$f" --parts 12 >"$OUT/chr${c}.log" 2>&1 &
  [ -s "$OUT/$f.tbi" ] || .venv/Scripts/python.exe tools/fetch_big.py \
      "$BASE/$f.tbi" "$OUT/$f.tbi" --parts 2 >>"$OUT/chr${c}.log" 2>&1 &
  while [ "$(jobs -r | wc -l)" -ge 12 ]; do wait -n; done
done
wait

# background-job failures are invisible to set -e - verify loudly
for c in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 X Y; do
  f="gnomad.exomes.v4.1.sites.chr${c}.vcf.bgz"
  { [ -s "$OUT/$f" ] && [ -s "$OUT/$f.tbi" ]; } || {
    echo "chr$c fetch failed - see $OUT/chr${c}.log"; exit 1; }
done
echo ALL_EXOMES_DONE
