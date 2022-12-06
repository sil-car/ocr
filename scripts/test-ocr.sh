#!/bin/bash

### Sequence of scriptable steps for creating and testing OCR via tesseract.

# Set global variables.
lang="Latin"
base_dir=
infile=
page_image_file=
help_text="usage:
  $0 [-l lang/script] [source_file pg#] [base_dir]

  If \"source_file\" is given, \"base_dir\" is assumed to be its parent dir
  unless \"base_dir\" is also given. If only \"base_dir\" is given, it's assumed
  that an image \"block.png\" already exists in \"base_dir\".
"

while getopts ":hl:" opt; do
    case $opt in
        h) # help text
            echo "$help_text"
            exit 0
            ;;
        l) # lang/script
            lang="$OPTARG"
            ;;
        *) # invalid option
            echo "$help_text"
            exit 1
            ;;
    esac
done
shift $(($OPTIND - 1))

# Handle base_dir arg.
if [[ -n "$3" && -d "$3" ]]; then
    base_dir="$3"
fi

# Set base_dir.
if [[ -z "$1" ]]; then
    # Assume PWD is base_dir and OCR image already exists in PWD.
    base_dir="$PWD"
elif [[ -d "$1" ]]; then
    # Assume OCR image already exists in given base_dir.
    base_dir=$(readlink -f "$1")
elif [[ -n "$2" && -d "$2" ]]; then
    echo "Error: \"base_dir\" given out of sequence. Missing input file or page #?"
    exit 1
elif [[ -n "$3" && -d "$3" ]]; then
    base_dir=$(readlink -f "$3")
fi

# Handle input file.
if [[ -f "$1" ]]; then
    # Get input file filetype.
    filetype=$(file "$1" | awk -F':' '{print $2}' | awk '{print $1}')

    # Set remaining variables.
    if [[ "$filetype" == 'PDF' || "$filetype" == 'TIFF' ]]; then
        infile="$(readlink -f "$1")" # full path
        if [[ -z "$base_dir" ]]; then
            base_dir=$(dirname "$infile")
        fi
        page="$2"
    else
        echo "Input file has invalid filetype (must be PDF or TIFF): $1"
        exit 1
    fi

    # 1. Ensure image of specified page from original PDF.
    filename="$(basename "$infile")"
    filetitle="${filename%.*}"

    # Get image page from file.
    if [[ "$filetype" == 'PDF' ]]; then
        # Set page #.
        num_pages=$(pdfinfo "$infile" | grep 'Pages:' | awk '{print $2}')
        if [[ -n "$page" ]]; then
            pg_num="$page"
        else
            echo "Error: no page number given."
            exit 1
        fi

        # Pad page # if necessary.
        if [[ "$num_pages" -gt 9 && "${#pg_num}" == 1 ]]; then # TODO: and if # PDF pages > 9!
            # Pad single-digit page numbers with a zero.
            pg_num="0${pg_num}"
        fi

        # Create page image (replaces existing file).
        echo "Creating image from page \"$page\" of \"$infile\"..."
        page_image_file=$(readlink -f "${filetitle}-${pg_num}.png")
        pdftoppm -png -f "$page" -l "$page" "$infile" "${infile%.*}"
    elif [[ "$filetype" == 'TIFF' ]]; then
        # Split multipage TIFF into multiple TIFFs (replaces existing files).
        echo "Splitting multipage \"$inifile\" into individual TIFF images..."
        tiffsplit "$infile" "${filetitle}-"
        read -p "Please type filename of selected image for OCR testing: " ans
        page_image_file=$(readlink -f "$ans")
        if [[ ! -f "$page_image_file" ]]; then
            echo "Error: \"$ans\" not found."
            exit 1
        fi
    fi
elif [[ -f "/usr/share/tesseract-ocr/4.00/tessdata/${1}.traineddata" ]]; then
    # Input is a lang/script file.
    lang="$1"
fi

# Set OCR outfile name.
ocr_outfile_name="ocr-text_${lang}"

# Ensure block.png file.
if [[ ! -f "${base_dir}/block.png" ]]; then
    if [[ -n "$page_image_file" ]]; then
        # Create block.png.
        echo "Please create \"block.png\" in \"$base_dir\" by cropping and exporting"
        echo "the image using the new shutter window..."
        shutter "file://${page_image_file}" >/dev/null 2>&1
    else
        echo "Error: No \"block.png\" in \"$base_dir\" and no input file given."
        exit 1
    fi
fi

# OCR the exported file "block.png".
ocr_outfile="${base_dir}/${ocr_outfile_name}.txt"
if [[ ! -e "$ocr_outfile" ]]; then
    echo "Creating \"$ocr_outfile\" from \"${base_dir}/block.png\"..."
    tesseract -c page_separator="" -l "$lang" "${base_dir}/block.png" "${base_dir}/${ocr_outfile_name}"
else
    echo "Info: Output file already exists: $ocr_outfile"
    echo "Info: Skipping OCR of \"${base_dir}/block.png\""
fi

# Make sure there's an "orig-text.txt" file for comparison.
if [[ ! -e "${base_dir}/orig-text.txt" ]]; then
    read -p "Need to create \"orig-text.txt\", then [Enter] to continue..."
    if [[ ! -e "${base_dir}/orig-text.txt" ]]; then
        echo "Error: \"orig-text.txt\" still not available."
        exit 1
    fi
fi

# Count the characters in both "orig-text.txt" and "ocr-text.txt".
echo
echo "Comparing character counts:"
wc -c "${base_dir}/orig-text.txt" "$ocr_outfile"
echo

# Open the files in meld for visual comparison.
meld "${base_dir}/orig-text.txt" "$ocr_outfile"
