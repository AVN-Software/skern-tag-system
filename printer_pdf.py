from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from PIL import Image
import tempfile
import os

from utils.cmyk import to_cmyk_safe
from utils.registration import draw_registration_marks


def make_press_ready_pdf(
    pdf_path: str,
    underlay_img: Image.Image,
    qr_img: Image.Image,
    mark_size_mm: int = 40,
):
    """
    Fully automated, press-ready PDF.

    SINGLE PAGE:
    - Underlay (printed first)
    - QR overlay (printed second, perfectly registered)

    Printer loads PDF → burns screens → prints in order.
    """

    page_w, page_h = A4
    size = mark_size_mm * mm
    x = (page_w - size) / 2
    y = (page_h - size) / 2

    c = canvas.Canvas(pdf_path, pagesize=A4)

    # Draw registration marks ONCE for the page
    draw_registration_marks(c, page_w, page_h)

    def draw_layer(img: Image.Image):
        img_cmyk = to_cmyk_safe(img)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".tif") as tmp:
            img_cmyk.save(tmp.name, format="TIFF")
            tmp_path = tmp.name

        c.drawImage(
            tmp_path,
            x,
            y,
            width=size,
            height=size,
            mask=None,
            preserveAspectRatio=True,
        )

        os.unlink(tmp_path)

    # 1️⃣ UNDERLAY (base screen)
    draw_layer(underlay_img)

    # 2️⃣ QR (top screen)
    draw_layer(qr_img)

    # Finalize single page
    c.showPage()
    c.save()
