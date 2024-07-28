#!/bin/bash
TASK=$1
if [ "$TASK" = "encrypt"  ]; then
  echo "encrypting config.env with cipher aes-256-cbc"
  openssl aes-256-cbc -a -salt -pbkdf2 -in config.env -out config_env.enc
fi
if [ "$TASK" = "decrypt"  ]; then
  echo "backing up config.env"
  cp config.env config_env.bak
  echo "decrypting config.env with cipher aes-256-cbc"
  openssl aes-256-cbc -d -a -pbkdf2 -in config_env.enc -out config.env
fi
