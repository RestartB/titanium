from io import BytesIO

import discord
import qrcode
from qrcode.constants import ERROR_CORRECT_L


def generate_qrcode(data: str) -> discord.File:
    """Generate a qrcode from given data."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Save to memory instead of disk
    buffer = BytesIO()
    img.save(buffer, "PNG")
    buffer.seek(0)

    return discord.File(buffer, filename="titanium_qrcode.png")
