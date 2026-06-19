#!/usr/bin/env bash

apt-get update

apt-get install -y poppler-utils

apt-get install -y tesseract-ocr

pip install -r requirements.txt