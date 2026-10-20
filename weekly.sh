#!/bin/sh
cd /home/ubuntu/hunter
echo "=== weekly $(date -u)" >> weekly.log
for n in freelance crypto infobiz market smm hr gamble dating; do
  echo "--- $n $(date -u)" >> weekly.log
  .venv/bin/python -u auto.py "$n" >> weekly.log 2>&1
done
echo "WEEKLY DONE $(date -u)" >> weekly.log
