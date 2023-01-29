#!/bin/bash

script_dir="$(dirname "$0")"
repo_dir="$(dirname "$script_dir")"

# Install packaged fonts.
pkgs=( fonts-lato fonts-noto-core fonts-noto-mono fonts-symbola ttf-mscorefonts-installer )
for pkg in ${pkgs[@]}; do
    if [[ $(dpkg -l | grep $pkg | awk '{print $1}') != 'ii' ]]; then
        echo "Installing ${pkg}..."
        sudo apt-get install $pkg
    fi
done
# Install non-packaged fonts.
echo "Copying user fonts..."
cp -fr "${repo_dir}/data/extra-fonts/"* "${HOME}/.local/share/fonts/"
