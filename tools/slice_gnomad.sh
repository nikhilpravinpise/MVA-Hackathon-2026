#!/usr/bin/env bash
# Slice gnomAD v4.1 joint sites to exonic regions (GENCODE v47 exons
# +/-200bp) via remote tabix reads. One job per chromosome inside the
# bcftools container; INFO trimmed to the AF fields the funnel consumes.
# Output: env/vep_ann/gnomad_slices/joint_<chr>.vcf.gz with contigs
# stripped to bare '15' style via /refdir/chrmap.txt.
set -euo pipefail
BASE="https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/joint"
IMG="quay.io/biocontainers/bcftools:1.21--h8b25389_0"
KEEP='^INFO/AF_joint,INFO/AF_exomes,INFO/AF_genomes,'
KEEP+='INFO/AF_exomes_afr,INFO/AF_exomes_ami,INFO/AF_exomes_amr,'
KEEP+='INFO/AF_exomes_asj,INFO/AF_exomes_eas,INFO/AF_exomes_fin,'
KEEP+='INFO/AF_exomes_mid,INFO/AF_exomes_nfe,INFO/AF_exomes_remaining,'
KEEP+='INFO/AF_exomes_sas,'
KEEP+='INFO/AF_genomes_afr,INFO/AF_genomes_ami,INFO/AF_genomes_amr,'
KEEP+='INFO/AF_genomes_asj,INFO/AF_genomes_eas,INFO/AF_genomes_fin,'
KEEP+='INFO/AF_genomes_mid,INFO/AF_genomes_nfe,INFO/AF_genomes_remaining,'
KEEP+='INFO/AF_genomes_sas,INFO/nhomalt_joint'

REPO="C:/Dev/MVA-Hackathon-2026"
mkdir -p "$REPO/env/vep_ann/gnomad_slices"

job() {
  local c=$1
  local out="gnomad_slices/joint_chr${c}.vcf.gz"
  [ -s "$REPO/env/vep_ann/$out" ] && [ -s "$REPO/env/vep_ann/$out.tbi" ] \
    && { echo "chr$c done"; return 0; }
  # write to .part and mv on success: a killed job must not leave a
  # partial .vcf.gz (or a complete one missing its .tbi) that the -s
  # resume guard would treat as done
  MSYS_NO_PATHCONV=1 docker run --rm \
    -v "$REPO/env/ref:/refdir:ro" -v "$REPO/env/vep_ann:/ann" "$IMG" \
    bash -c "bcftools view -R /refdir/beds/exon_chr${c}.bed -Ou \
        ${BASE}/gnomad.joint.v4.1.sites.chr${c}.vcf.bgz | \
      bcftools annotate --rename-chrs /refdir/chrmap.txt \
        -x ${KEEP} -Oz -o /ann/${out}.part && \
      tabix -f -p vcf /ann/${out}.part && \
      mv /ann/${out}.part /ann/${out} && \
      mv /ann/${out}.part.tbi /ann/${out}.tbi" \
      >"$REPO/env/vep_ann/gnomad_slices/chr${c}.log" 2>&1
  echo "chr$c -> $out"
}

CHRS="${CHROMS:-1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 X Y}"
for c in $CHRS; do
  job "$c" &
  while [ "$(jobs -r | wc -l)" -ge 8 ]; do wait -n; done
done
wait

# background-job failures are invisible to set -e - verify loudly
for c in $CHRS; do
  [ -s "$REPO/env/vep_ann/gnomad_slices/joint_chr${c}.vcf.gz" ] \
    && [ -s "$REPO/env/vep_ann/gnomad_slices/joint_chr${c}.vcf.gz.tbi" ] \
    || { echo "chr$c slice failed - see \
env/vep_ann/gnomad_slices/chr${c}.log"; exit 1; }
done
echo "ALL_SLICES_DONE"
