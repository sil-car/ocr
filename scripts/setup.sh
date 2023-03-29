#!/bin/bash

script_dir="$(dirname "$0")"
repo_dir="$(dirname "$script_dir")"

# Ensure running from $HOME.
cd "$HOME"
if [[ $? -ne 0 ]]; then
    echo "ERROR: Couldn't cd to $HOME."
    exit 1
fi

# Install apt packages.
apt_pkgs=(
    screen
    wireguard
)
for pkg in "${apt_pkgs[@]}"; do
    if [[ $(dpkg -l | grep -E "^.{4}$pkg" | awk '{print $1}') != 'ii' ]]; then
        echo "Installing ${pkg}..."
        sudo apt-get install $pkg
    fi
done

# Get wireguard-vpn-setup repo.
if [[ ! -d $HOME/wireguard-vpn-setup ]]; then
    git clone --depth=1 "https://github.com/sil-car/wireguard-vpn-setup.git"
fi
# TODO: Run wireguard setup script.

# TODO: Add SSH key.
# TODO: Allow SSH only on wireguard port.

# Install packaged fonts.
font_pkgs=(
    fonts-lato
    fonts-noto-core
    fonts-noto-mono
    fonts-sil-andika
    fonts-sil-andika-compact
    fonts-sil-charis
    fonts-sil-charis-compact
    fonts-sil-doulos
    fonts-sil-doulos-compact
    fonts-sil-gentium
    fonts-sil-gentium-basic
    fonts-sil-gentiumplus
    fonts-sil-gentiumplus-compact
    fonts-symbola
    ttf-mscorefonts-installer
)
for pkg in "${font_pkgs[@]}"; do
    if [[ $(dpkg -l | grep -E "^.{4}$pkg" | awk '{print $1}') != 'ii' ]]; then
        echo "Installing ${pkg}..."
        sudo apt-get install $pkg
    fi
done
# Install non-packaged fonts.
echo "Copying user fonts..."
cp -fr "${repo_dir}/data/extra-fonts/"* "${HOME}/.local/share/fonts/"

# Get tesstrain repo.
if [[ ! -d $HOME/tesstrain ]]; then
    git clone --depth=1 "https://github.com/tesseract-ocr/tesstrain.git"
fi
# Get tesseract repo.
if [[ ! -d $HOME/tesseract ]]; then
    git clone --depth=1 "https://github.com/tesseract-ocr/tesseract.git"
fi