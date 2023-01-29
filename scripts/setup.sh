#!/bin/bash

script_dir="$(dirname "$0")"
repo_dir="$(dirname "$script_dir")"

if [[ $(id -u) -ne 0 ]]; then
    echo "wasta-logos64-setup started as root user."
    echo "No processing done.  Exiting...."
    exit 0
fi

# Install packaged fonts.
pkgs=( fonts-lato fonts-noto-core fonts-symbola ttf-mscorefonts-installer )
for pkg in ${pkgs[@]}; do
    if [[ $(dpkg -l | grep $pkg | awk '{print $1}') != 'ii' ]]; then
        sudo apt-get install $pkg
    fi
done
# Install non-packaged fonts.
cp -fr "${repo_dir}/data/extra-fonts/"* "${HOME}/.local/share/fonts/"
