#!/bin/bash

if [[ -n $UPSTREAM_REPO ]]; then
    git init && git remote add origin $UPSTREAM_REPO && git fetch origin && git checkout -f master && clear
fi