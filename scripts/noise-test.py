#!/usr/bin/env python3
import fitz
from PIL import Image
from PIL import ImageFilter


CHARACTER_HEIGHT = 48
NOISE_SIGMA = 50


def find_extent(pil_img, axis="x", etype="max"):
    extent = None
    # Set dimensions.
    if axis == "x":
        d1, d2 = pil_img.size
    elif axis == "y":
        d2, d1 = pil_img.size
    # Set ranges.
    if etype == "min":
        r1 = range(d1)
        r2 = range(d2)
    elif etype == "max":
        r1 = range(d1 - 1, -1, -1)
        r2 = range(d2 - 1, -1, -1)
    # Find extent.
    for x in r1:
        if extent:
            break
        for y in r2:
            if axis == "x":
                pixel = pil_img.getpixel((x, y))
            elif axis == "y":
                pixel = pil_img.getpixel((y, x))
            if pixel[0] < 255:
                extent = x
                break
    return extent


def get_box_extents_pil(pil_img):
    x_min = find_extent(pil_img, axis="x", etype="min")
    y_min = find_extent(pil_img, axis="y", etype="min")
    x_max = find_extent(pil_img, axis="x", etype="max")
    y_max = find_extent(pil_img, axis="y", etype="max")
    return x_min, y_min, x_max, y_max


def generate_text_line_png(chars, fontfile):
    with fitz.open() as doc:
        # TODO: Set page width based on font's needs?
        # NOTE: Page sizes seem to be in mm, so 350mm x 21mm provides enough
        # width and height for most reasonable font sizes and line lengths.
        page = doc.new_page(width=350, height=21)
        page.insert_font(fontname="test", fontfile=fontfile)
        # Only built-in PDF fonts are supported by get_text_length();
        #   have to crop the box outside of fitz/muPDF.
        #   Ref: https://pymupdf.readthedocs.io/en/latest/functions.html#get_text_length
        # text_length = fitz.get_text_length(chars, fontname='test')
        pt = fitz.Point(5, 16)
        page.insert_text(pt, chars, fontname="test")
        # Use dpi to give optimum character height (default seems to be 100):
        #   Ref: https://groups.google.com/g/tesseract-ocr/c/Wdh_JJwnw94/m/24JHDYQbBQAJ
        # CHARACTER_HEIGHT is a proxy; actual char ht is a few px less b/c spacing
        dpi = int(
            (88 / 13) * CHARACTER_HEIGHT - 636 / 13
        )  # linear relationship calculated using (22, 100), (35, 188)
        pix = page.get_pixmap(dpi=dpi)

    # Crop the pixmap to remove extra whitespace; convert to PIL Image.
    #   Ref: https://github.com/pymupdf/PyMuPDF/issues/322#issuecomment-512561756
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    # Get boundary extents.
    box_extents = list(get_box_extents_pil(img))
    # Add padding around text.
    pad = 3
    for i in range(len(box_extents)):
        if i < 2:  # left & top
            box_extents[i] -= pad
        else:  # right & bottom
            box_extents[i] += pad
    # Crop and return the image.
    return img.crop(box_extents)


def add_noise(image):
    alpha = 0.4
    noise = Image.effect_noise(size=image.size, sigma=NOISE_SIGMA)
    noisy_image = Image.blend(image, noise.convert(image.mode), alpha)
    del image
    return noisy_image


def add_blur(image):
    px_radius = CHARACTER_HEIGHT / 30
    blurry_image = image.filter(ImageFilter.GaussianBlur(px_radius))
    del image
    return blurry_image


def main():
    png_img = generate_text_line_png(
        chars="\u0061\u0300\u0061\u0300\u0061\u0300\u0061\u0300\u0061\u0300\u0061\u0300\u0061\u0300",
        fontfile="/usr/share/fonts/truetype/andika/Andika-Regular.ttf",
    )
    noisy_png_img = add_noise(png_img)
    blurry_png_img = add_blur(png_img)
    png_img.show()
    noisy_png_img.show()
    blurry_png_img.show()


if __name__ == "__main__":
    main()
