#!/usr/bin/env bash


set -e

# This data was generated by manually pointing and clicking through imagery. Fun!

DIR_DEST="/scratch/nfabina/gcrmn-benthic-classification/training_data"


for REEF in batt_tongue belize hawaii heron karimunjawa little moorea ribbon; do
  if [[ ! -d ${DIR_DEST}/${REEF}/clean ]]; then
    mkdir -p ${DIR_DEST}/${REEF}/clean
  fi

  rclone copy -v --include=boundaries* remote:/data/gcrmn/${REEF}/clean/ ${DIR_DEST}/${REEF}/clean/
done