#!/bin/bash

PYTHON=`which python3`

TEST_NUMBER=10

if [ $# -eq 2 ]
then
	TEST_NUMBER=$1
fi

for (( i=1; i<=$TEST_NUMBER; i++))
do
	echo -e "\ntest[$i]...\n"
	$PYTHON my_scraper.py 3
done
