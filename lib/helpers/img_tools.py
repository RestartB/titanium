import io

from discord import Attachment, File
from PIL import Image


class ImageConverter:
    """
    Handle image format conversions for Discord attachments.
    Supports PNG, JPEG, WEBP, GIF
    """

    def __init__(self, image: Attachment) -> None:
        self.image: Attachment = image

    @staticmethod
    def format_types() -> list[str]:
        return ["PNG", "JPEG", "WEBP", "GIF"]

    async def _load_image(self) -> Image.Image:
        if not self.image:
            raise ValueError("No image provided")
        data = await self.image.read()
        return Image.open(io.BytesIO(data))

    async def convert(self, output_format: str = "PNG", quality: int = 95) -> File:
        """
        Convert the image to a new format and return as discord.File.
        """
        img = await self._load_image()

        if output_format.upper() in ["JPEG", "JPG"] and img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif output_format.upper() in ["JPEG", "JPG"]:
            img = img.convert("RGB")

        buffer = io.BytesIO()
        save_params = {"quality": quality} if output_format.upper() in ["JPEG", "WEBP"] else {}
        img.save(buffer, format=output_format.upper(), **save_params)
        buffer.seek(0)

        return File(
            fp=buffer,
            filename=f"{self.image.filename.split('.')[0]}.{output_format.lower()}",
        )
