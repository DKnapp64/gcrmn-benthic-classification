#!/usr/bin/env bash


# This data was initially acquired manually from allencoralatlas.org, by navigating to the MVP sites, clicking on the
# pie chart icon, and clicking 'Download Layers and Stats'. It was subsequently uploaded to nsfabina's GDrive.


for REEF in belize hawaii heron karimunjawa moorea; do
  if [[ ! -d ../data/${REEF}/raw ]]; then
    mkdir ../data/${REEF}/raw
  fi
  
  rclone copy remote:imagery/gcrmn/${REEF}/raw/responses.geojson ../data/${REEF}/raw/
done

