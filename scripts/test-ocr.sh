#!/bin/bash

### Sequence of scriptable steps for creating and testing OCR via tesseract.

# Set global variables.
page="$2"
infile="$(readlink -f "$1")"

# 1. Ensure image of specified page from original PDF.
filename="$(basename "$infile")"
filetitle="${filename%.*}"
filetype="${filename##*.}"
filetype="${filetype,,}"
if [[ "$filetype" == 'pdf' ]]; then
    num_pages=$(pdfinfo "$filename" | grep 'Pages:' | awk '{print $2}')
    pg_num="$page"
    if [[ "$num_pages" -gt 9 && "${#pg_num}" == 1 ]]; then # TODO: and if # PDF pages > 9!
        # Pad single-digit page numbers with a zero.
        pg_num="0${pg_num}"
    fi
    page_image_file=$(readlink -f "${filetitle}-${pg_num}.png")
    if [[ ! -e "$page_image_file" ]]; then
        echo "Creating image from given PDF page number.."
        pdftoppm -png -f "$page" -l "$page" "$infile" "${infile%.*}"
    fi
elif [[ "$filetype" == 'tiff' || "$filetype" == 'tif' ]]; then
    if [[ ! -e "${filetitle}-aaa.tif" ]]; then
        echo "Splitting TIFF document into individual TIFF images."
        tiffsplit "$infile" "${filetitle}-"
    fi
    read -p "Please type filename of desired image: " ans
    if [[ -e "$ans" ]]; then
        page_image_file=$(readlink -f "$ans")
    else
        echo "Error: \"$ans\" not found."
        exit 1
    fi
else
    echo "Error: Unsupported filetype \"$filetype\"."
    exit 1
fi

# 2. Open image in shutter to crop the block of text.
if [[ ! -e "block.png" ]]; then
    echo "Please create \"block.png\" using the new shutter window..."
    shutter "file://${page_image_file}" >/dev/null 2>&1
fi

# 3. OCR the exported file "block.png".
if [[ ! -e "ocr-text.txt" ]]; then
    echo "Creating \"ocr-text.txt\" from \"block.png\"..."
    tesseract -c page_separator="" -l Latin "block.png" ocr-text
fi

# 4. Make sure there's an "orig-text.txt" file for comparison.
if [[ ! -e "orig-text.txt" ]]; then
    read -p "Need to create \"orig-text.txt\", then [Enter] to continue..."
    if [[ ! -e "orig-text.txt" ]]; then
        echo "Error: \"orig-text.txt\" still not available."
        exit 1
    fi
fi

# 5. Count the characters in both "orig-text.txt" and "ocr-text.txt".
echo
echo "Comparing character counts:"
wc -c "orig-text.txt" "ocr-text.txt"
echo

# 6. Open the files in meld for visual comparison.
meld "orig-text.txt" "ocr-text.txt"
