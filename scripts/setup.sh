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
    automake
    ca-certificates
    g++
    git
    libcairo2-dev
    libicu-dev
    libleptonica-dev
    libpango1.0-dev
    libtool
    make
    pkg-config
    python3-venv
    screen
    unzip
)
for pkg in "${apt_pkgs[@]}"; do
    if [[ $(dpkg -l | grep -E "^.{4}$pkg\s" | awk '{print $1}') != 'ii' ]]; then
        echo "Installing ${pkg}..."
        sudo apt-get install -y $pkg
    fi
done

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
for pkg in "${font_pkgs[@]}"; do
    if [[ $(dpkg -l | grep -E "^.{4}$pkg\s" | awk '{print $1}') != 'ii' ]]; then
        echo "Installing ${pkg}..."
        sudo apt-get -y install $pkg
    fi
done
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
#mkdir -p "${HOME}/tesstrain/data"

# Get best Latin script traineddata model.
if [[ ! -f $HOME/tessdata_best/lat.traineddata ]]; then
    # NOTE: Cloning the full repo requires downloading > 1 GB of data.
    # git clone --depth=1 "https://github.com/tesseract-ocr/tessdata_best.git"
    mkdir -p $HOME/tessdata_best
    wget -P $HOME/tessdata_best https://github.com/tesseract-ocr/tessdata_best/raw/refs/heads/main/eng.traineddata
    wget -P $HOME/tessdata_best https://github.com/tesseract-ocr/tessdata_best/raw/refs/heads/main/lat.traineddata
fi

# Get tesseract, build & install.
tesseract_ver="5.5.1"
tesseract_dir="tesseract-$tesseract_ver"
if [[ -z $(which lstmtraining) ]]; then
    wget "https://github.com/tesseract-ocr/tesseract/archive/refs/tags/${tesseract_ver}.zip"
    unzip "$tesseract_ver"
    cd "$tesseract_dir"
    ./autogen.sh
    mkdir -p bin/release
    cd bin/release
    ../../configure \
        --disable-openmp \
        --disable-debug \
        --disable-graphics \
        --disable-shared \
        'CXXFLAGS=-g -O2 -fno-math-errno -Wall -Wextra -Wpedantic'
    make
    sudo make install
    make training
    sudo make training-install
fi

# Create venv.
cd "${HOME}/ocr"
python3 -m venv env
source ./env/bin/activate
python3 -m pip install -r ../tesstrain/requirements.txt
python3 -m pip install -r requirements.txt
cd "$HOME"
