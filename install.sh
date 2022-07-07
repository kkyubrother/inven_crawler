#!/bin/bash
apt update
apt upgrade -y
apt install -y python3 python3-dev python3-pip
pip3 install bs4 pandas lxml requests tqdm