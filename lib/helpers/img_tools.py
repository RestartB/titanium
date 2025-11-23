import io

from discord import Attachment, File
from PIL import Image
from wand.image import Image as WandImage

from lib.enums.images import ImageFormats


class ImageTools:
    """
    Handle image manipulation tasks.
    """

    def __init__(self, image: Attachment) -> None:
        self.image: Attachment = image

    @staticmethod
    def format_types() -> list[str]:
        return [format.value for format in ImageFormats]

    async def _load_image(self) -> Image.Image:
        if not self.image:
            raise ValueError("No image provided")
        data = await self.image.read()
        return Image.open(io.BytesIO(data))

    async def convert(self, output_format: ImageFormats, quality: int = 95) -> File:
        """
        Convert the image to a new format and return as discord.File.
        """
        if output_format == ImageFormats.GIF:
            output_data = io.BytesIO()

            # Convert to GIF with wand
            with WandImage(blob=await self.image.read()) as wand_image:
                # Set GIF optimization options
                wand_image.compression_quality = 80
                wand_image.quantum_operator = "dither"  # type: ignore

                # Convert to GIF format
                wand_image.format = "gif"

                blob = wand_image.make_blob("gif")

                if blob:
                    # Write to output BytesIO
                    output_data.write(blob)

            output_data.seek(0)
            return File(
                fp=output_data,
                filename=f"{self.image.filename.split('.')[0]}.gif",
            )

        img = await self._load_image()

        if output_format in [ImageFormats.JPEG] and img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            img = background
        elif output_format in [ImageFormats.JPEG]:
            img = img.convert("RGB")

        buffer = io.BytesIO()
        save_params = (
            {"quality": quality} if output_format in [ImageFormats.JPEG, ImageFormats.WEBP] else {}
        )
        img.save(buffer, format=output_format.value, **save_params)
        buffer.seek(0)

        return File(
            fp=buffer,
            filename=f"{self.image.filename.split('.')[0]}.{output_format.value.lower()}",
        )
