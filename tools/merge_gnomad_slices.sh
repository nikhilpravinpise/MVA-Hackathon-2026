#!/usr/bin/env bash
# Merge per-chromosome gnomAD slices into the two --custom annotation
# files VEP expects: gnomade_genic.vcf.gz (gnomADe_* fields) and
# gnomadg_genic.vcf.gz (gnomADg_*), via tools/gnomad_split.py rename.
set -euo pipefail
REPO="C:/Dev/MVA-Hackathon-2026"
SL="env/vep_ann/gnomad_slices"
IMG="ensemblorg/ensembl-vep:release_116.1"

for side in e g; do
  out="env/vep_ann/gnomad${side}_genic.vcf"
  echo "building $out"
  first=1
  for c in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 X Y; do
    f="$REPO/$SL/joint_chr${c}.vcf.gz"
    [ -s "$f" ] || { echo "missing chr$c slice"; exit 1; }
    if [ $first = 1 ]; then
      .venv/Scripts/python.exe tools/gnomad_split.py "$f" "$side" > "$out"
      first=0
    else
      .venv/Scripts/python.exe tools/gnomad_split.py "$f" "$side" \
        | grep -v '^#' >> "$out"
    fi
  done
done

# per-chrom slices concatenated in chrom order are already sorted;
# just bgzip + index
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$REPO/env/vep_ann:/ann" --entrypoint bash "$IMG" -c "
  for s in gnomade_genic gnomadg_genic; do
    bgzip -f /ann/\$s.vcf
    tabix -f -p vcf /ann/\$s.vcf.gz
  done
  ls -l /ann/gnomad?_genic.vcf.gz*"
echo "MERGED"
