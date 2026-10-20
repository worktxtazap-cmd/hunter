#!/bin/sh
# allniches.sh - прогнать оставшиеся ниши по очереди
cd /home/ubuntu/hunter
for n in market smm hr gamble dating; do
  echo "=== $n $(date -u)"
  .venv/bin/python -u auto.py "$n" >> auto_all.log 2>&1
done
echo "ALL DONE $(date -u)"