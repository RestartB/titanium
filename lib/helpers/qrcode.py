from io import BytesIO

import discord
import qrcode


def generate_qrcode(data: str) -> discord.File:
    """Generate a qrcode from given data."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Save to memory instead of disk
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return discord.File(buffer, filename="qrcode.png")
