#!/bin/bash

script_dir="$(realpath "$(dirname "$0")")"
repo_dir="$(realpath "$(dirname "$script_dir")")"

# Ensure running from $HOME.
cd "$HOME"
if [[ $? -ne 0 ]]; then
    echo "ERROR: Couldn't cd to $HOME."
    exit 1
fi

# Install apt packages.
apt_pkgs=(
    git
    make
    python3-venv
    screen
    unzip
)
sudo apt-get install -y "${apt_pkgs[@]}"

# Install packaged fonts.
font_pkgs=(
    fonts-dejavu-core
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
sudo apt-get install -y "${font_pkgs[@]}"

# Install non-packaged fonts.
echo "Copying user fonts..."
if [[ $USER == root ]]; then
    dest_dir=/usr/share/fonts/
else
    dest_dir="${HOME}/.local/share/fonts/"
fi
cp -fr "${repo_dir}/data/extra-fonts/"* "$dest_dir"

# Get tesstrain repo.
if [[ ! -d $HOME/tesstrain ]]; then
    git clone --depth=1 "https://github.com/tesseract-ocr/tesstrain.git"
fi

# Get & install tesseract build.
tesseract_ver="5.5.1"
if [[ -z $(which lstmtraining) ]]; then
    rm -rf "${tesseract_ver}"*
    wget "https://github.com/sil-car/tesseract-builds/releases/download/${tesseract_ver}/${tesseract_ver}.zip"
    unzip "${tesseract_ver}.zip"
    cd "$tesseract_ver"
    sudo make install
    sudo make training-install
fi

# eng.traineddata needed to init tesseract
tessdata_best_repo="https://github.com/tesseract-ocr/tessdata_best"
if [[ ! -r /usr/local/share/tessdata/eng.traineddata ]]; then
    wget -P /usr/local/share/tessdata "${tessdata_best_repo}/raw/refs/heads/main/eng.traineddata"
fi

# Get best Latin script traineddata model.
if [[ ! -r $HOME/tessdata_best/lat.traineddata ]]; then
    # NOTE: Cloning the full repo requires downloading > 1 GB of data.
    # git clone --depth=1 "https://github.com/tesseract-ocr/tessdata_best.git"
    mkdir -p $HOME/tessdata_best
    wget -P $HOME/tessdata_best "${tessdata_best_repo}/raw/refs/heads/main/lat.traineddata"
fi

# Create & activate venv.
env_path=$HOME/ocr/env
python3 -m venv "$env_path"
source ${env_path}/bin/activate
if [[ $VIRTUAL_ENV != $env_path ]]; then
    echo "Error: Failed to activate virtual env."
    exit 1
fi
python3 -m pip install -r $HOME/tesstrain/requirements.txt
python3 -m pip install -r $HOME/ocr/requirements.txt
