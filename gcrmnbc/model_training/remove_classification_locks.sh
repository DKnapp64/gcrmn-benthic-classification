#!/usr/bin/env bash


DIR_MODELS="../models"

for MODEL in `ls models`; do
  for RESPONSE_MAPPING in `ls ../models/${MODEL}`; do
    LOCK="${DIR_MODELS}/${MODEL}/${RESPONSE_MAPPING}/classify.lock"
    JOB_NAME="classify_${MODEL}_${RESPONSE_MAPPING}"
    FOUND=$(squeue -u nfabina -o %j | grep ${JOB_NAME})
    if [[ ${FOUND} != ${JOB_NAME} ]] && [[ -f ${LOCK} ]]; then
      rm -f ${LOCK}
    fi
  done
done