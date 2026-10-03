#!/usr/bin/env bash
# Slim+rename downloaded gnomAD exomes sites files into the single
# gnomADe custom-annotation VCF (bare contigs, AF-only fields).
# Run from repo root. gnomad_split.py is pure-stdlib Python (host venv);
# final bgzip+tabix runs in the bcftools container.
set -euo pipefail
SRC="env/vep_ann/gnomad_exomes"
OUT="env/vep_ann/gnomade_custom.vcf"
CHROMS="1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 X Y"
IMG="quay.io/biocontainers/bcftools:1.21--h8b25389_0"
REPO="$(pwd)"

mkdir -p "$SRC/slim"
for c in $CHROMS; do
  f="$SRC/gnomad.exomes.v4.1.sites.chr${c}.vcf.bgz"
  s="$SRC/slim/chr${c}.vcf"
  [ -s "$s" ] && continue
  [ -s "$f" ] || { echo "missing $f"; exit 1; }
  # .tmp + mv: a killed/crashed split must not leave a partial file that
  # the -s resume guard would treat as complete
  ( .venv/Scripts/python.exe tools/gnomad_split.py "$f" e \
      > "$s.tmp" 2>"$s.err" && mv "$s.tmp" "$s" ) &
  while [ "$(jobs -r | wc -l)" -ge 8 ]; do wait -n; done
done
wait

# background-job failures are invisible to set -e - verify loudly
for c in $CHROMS; do
  [ -s "$SRC/slim/chr${c}.vcf" ] || {
    echo "chr${c} split failed - see $SRC/slim/chr${c}.vcf.err"; exit 1; }
done

# header from chr1's slim output, then all data rows in chrom order
grep '^#' "$SRC/slim/chr1.vcf" > "$OUT"
for c in $CHROMS; do
  grep -v '^#' "$SRC/slim/chr${c}.vcf"
done >> "$OUT"

docker run --rm -v "$REPO/env/vep_ann:/ann" "$IMG" bash -c \
  "bgzip -f /ann/gnomade_custom.vcf && tabix -f -p vcf /ann/gnomade_custom.vcf.gz"
echo GNOMADE_CUSTOM_DONE
