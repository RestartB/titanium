import asyncio
import os
import textwrap
from io import BytesIO
from typing import Literal

from discord import Attachment, File
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFont, ImageOps
from wand.image import Image as WandImage

from lib.enums.images import ImageFormats


class ImageTooSmallError(Exception):
    """Raised when the image is too small for the operation."""


class OperationTooLargeError(Exception):
    """Raised when the operation would result in an image that is too large."""


class ImageTools:
    """
    Handle image manipulation tasks.
    """

    def __init__(self, image: Attachment) -> None:
        self.image: Attachment = image

    @staticmethod
    def format_types() -> list[str]:
        return [format.value for format in ImageFormats]

    def _get_output_filename(self, output_format: ImageFormats) -> str:
        """Generate output filename safely handling files with or without extensions."""
        base_name = (
            self.image.filename.rsplit(".", 1)[0]
            if "." in self.image.filename
            else self.image.filename
        )
        return f"titanium_{base_name}.{output_format.value.lower()}"

    def _load_sync(self, data: bytes) -> Image.Image:
        return Image.open(BytesIO(data))

    async def _load_image(self) -> Image.Image:
        if not self.image:
            raise ValueError("No image provided to load")
        data = await self.image.read()

        return await asyncio.to_thread(self._load_sync, data)

    def _save_sync(self, img: Image.Image, output_format: ImageFormats, quality: int) -> BytesIO:
        if output_format == ImageFormats.GIF:
            is_animated = getattr(img, "n_frames", 1) > 1

            if is_animated:
                # animation, use pillow
                buffer = BytesIO()
                frames = []
                durations = []

                for frame_idx in range(getattr(img, "n_frames", 1)):
                    img.seek(frame_idx)
                    frame = img.convert("RGB").copy()
                    frames.append(frame)
                    duration = getattr(img, "info", {}).get("duration", 100)
                    durations.append(duration)

                frames[0].save(
                    buffer,
                    format="GIF",
                    save_all=True,
                    append_images=frames[1:],
                    duration=durations,
                    loop=0,
                    optimize=False,
                )
                buffer.seek(0)
                return buffer
            else:
                # single frame, use wand
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                buffer.seek(0)

                with WandImage(blob=buffer.getvalue()) as wand_image:
                    wand_image.compression_quality = 80
                    wand_image.quantum_operator = "dither"  # type: ignore

                    wand_image.format = "gif"
                    blob = wand_image.make_blob("gif")

                    if blob:
                        output_buffer = BytesIO(blob)
                        output_buffer.seek(0)
                        return output_buffer

                buffer.seek(0)
                return buffer

        if output_format in [ImageFormats.JPEG, ImageFormats.BMP] and img.mode in (
            "RGBA",
            "LA",
            "P",
        ):
            # these formats do not support alpha, add a white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif output_format in [ImageFormats.JPEG, ImageFormats.BMP]:
            img = img.convert("RGB")

        buffer = BytesIO()
        save_params = (
            {"quality": quality}
            if output_format in [ImageFormats.JPEG, ImageFormats.WEBP, ImageFormats.AVIF]
            else {}
        )
        img.save(buffer, format=output_format.value, **save_params)
        buffer.seek(0)

        return buffer

    async def convert(self, output_format: ImageFormats, quality: int) -> File:
        """
        Convert the image to a new format and return file.
        """
        img = await self._load_image()
        buffer = await asyncio.to_thread(self._save_sync, img, output_format, quality)

        return File(
            fp=buffer,
            filename=self._get_output_filename(output_format),
        )

    def _resize_sync(self, img: Image.Image, width: int, height: int) -> Image.Image:
        return img.resize((width, height))

    async def resize(self, output_format: ImageFormats, width: int, height: int) -> File:
        """
        Resize the image to the specified width and height and return file.
        """
        if width <= 0 or height <= 0:
            raise ValueError("Width and height must be positive integers")
        if width > 10000 or height > 10000:
            raise OperationTooLargeError("Dimensions exceed maximum allowed size (10000x10000)")

        img = await self._load_image()
        resized_img = await asyncio.to_thread(self._resize_sync, img, width, height)
        buffer = await asyncio.to_thread(self._save_sync, resized_img, output_format, 95)

        return File(
            fp=buffer,
            filename=self._get_output_filename(output_format),
        )

    def _deepfry(self, img: Image.Image, intensity_scale: float, red_filter: bool) -> BytesIO:
        # Crediit: https://github.com/Ovyerus/deeppyer
        # MIT Licence - https://github.com/Ovyerus/deeppyer/blob/master/LICENSE

        # Deepfry image
        img = img.convert("RGB")
        width, height = img.width, img.height
        img = img.resize((int(width**0.75), int(height**0.75)), resample=Image.Resampling.LANCZOS)
        img = img.resize((int(width**0.88), int(height**0.88)), resample=Image.Resampling.BILINEAR)
        img = img.resize((int(width**0.9), int(height**0.9)), resample=Image.Resampling.BICUBIC)
        img = img.resize((width, height), resample=Image.Resampling.BICUBIC)
        img = ImageOps.posterize(img, 4)

        # Generate colour overlay
        r = img.split()[0]
        r = ImageEnhance.Contrast(r).enhance(1.0 + intensity_scale)  # Scale from 1.0 to 2.0
        r = ImageEnhance.Brightness(r).enhance(
            1.0 + (0.5 * intensity_scale)
        )  # Scale from 1.0 to 1.5

        if red_filter:
            colours = ((254, 0, 2), (255, 255, 15))
            r = ImageOps.colorize(r, colours[0], colours[1])
        else:
            r = img.copy()

        # Blend scaled from 0 to 0.75
        img = Image.blend(img, r, 0.75 * intensity_scale)

        # Sharpness scaled from 1.0 to 100.0
        img = ImageEnhance.Sharpness(img).enhance(1.0 + (99.0 * intensity_scale))

        buffer = BytesIO()

        # Save image
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer

    async def deepfry(
        self, output_format: ImageFormats, intensity_scale: float, red_filter: bool
    ) -> File:
        """
        Deepfry the image and return file.
        """
        if not 0.0 <= intensity_scale <= 1.0:
            raise ValueError("intensity_scale must be between 0.0 and 1.0")

        img = await self._load_image()
        deepfried_buffer = await asyncio.to_thread(self._deepfry, img, intensity_scale, red_filter)
        deepfried_img = await asyncio.to_thread(self._load_sync, deepfried_buffer.getvalue())
        final_buffer = await asyncio.to_thread(self._save_sync, deepfried_img, output_format, 95)

        return File(
            fp=final_buffer,
            filename=self._get_output_filename(output_format),
        )

    def _speech_bubble_sync(
        self,
        img: Image.Image,
        direction: Literal["left", "right"],
        colour: Literal["black", "white", "transparent"],
    ) -> BytesIO:
        img = img.convert("RGBA").copy()

        # Open speech bubble image
        with Image.open(os.path.join("lib", "images", "speech.png")) as bubble_source:
            bubble = bubble_source.convert("RGBA").copy()
            bubble = bubble.resize(img.size, Image.Resampling.LANCZOS)

            if direction == "left":  # Flip bubble image if left selected
                bubble = bubble.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

            if colour == "black":  # Invert if black selected
                bubble_a = bubble.getchannel("A")
                bubble = bubble.convert("RGB")  # Convert to RGB for invert

                bubble = ImageOps.invert(bubble)
                bubble.putalpha(bubble_a)

        if colour == "transparent":
            # Subtract bubble shape from image
            output_img = ImageChops.subtract_modulo(img, bubble)

            with Image.open(
                os.path.join("lib", "images", "speech_border.png")
            ) as bubble_border_source:
                bubble_border = bubble_border_source.convert("RGBA").copy()
                bubble_border = bubble_border.resize(img.size, Image.Resampling.LANCZOS)

                # Make border white
                bubble_border_a = bubble_border.getchannel("A")
                bubble_border = bubble_border.convert("RGB")  # Convert to RGB for invert

                bubble_border = ImageOps.invert(bubble_border)
                bubble_border.putalpha(bubble_border_a)

                if direction == "left":
                    bubble_border = bubble_border.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

            output_img.paste(bubble_border, (0, 0), bubble_border)

            buffer = BytesIO()
            output_img.save(buffer, format="PNG")
            buffer.seek(0)

            return buffer
        else:
            # Create new output image for white/black speech bubble
            output_img = Image.new("RGBA", img.size)
            output_img.paste(img, (0, 0))
            output_img.paste(bubble, (0, 0), bubble.getchannel("A"))

            buffer = BytesIO()
            output_img.save(buffer, format="PNG")
            buffer.seek(0)

            return buffer

    async def speech_bubble(
        self,
        output_format: ImageFormats,
        direction: Literal["left", "right"],
        colour: Literal["black", "white", "transparent"],
    ) -> File:
        """
        Add a speech bubble to the image and return file.
        """
        img = await self._load_image()
        bubble_buffer = await asyncio.to_thread(self._speech_bubble_sync, img, direction, colour)
        bubble_img = await asyncio.to_thread(self._load_sync, bubble_buffer.getvalue())
        final_buffer = await asyncio.to_thread(self._save_sync, bubble_img, output_format, 95)

        return File(
            fp=final_buffer,
            filename=self._get_output_filename(output_format),
        )

    def _create_caption_frame(
        self,
        img: Image.Image,
        font_data: ImageFont.FreeTypeFont,
        text_width: int,
        white_height: int,
        wrapped_text: str,
        pos: Literal["top", "bottom"],
    ) -> Image.Image:
        img = img.convert("RGBA").copy()

        # Create a new image with white background for this frame
        frame_output = Image.new(
            "RGBA",
            (img.width, img.height + white_height),
            (255, 255, 255, 255),
        )
        frame_output.paste(img, (0, (white_height if pos == "top" else 0)), img)

        # Calculate X position for text
        x = (frame_output.width - text_width) // 2

        # Calculate Y position for text
        if pos == "top":
            y = 10
        else:
            y = img.height + 10

        draw = ImageDraw.Draw(frame_output)
        draw.text(
            (x, y),
            wrapped_text,
            font=font_data,
            fill=(0, 0, 0, 255),
            align="center",
        )

        if frame_output.height > 4000:
            raise OperationTooLargeError

        return frame_output

    def _caption_sync(
        self, img: Image.Image, caption: str, font_path: str, pos: Literal["top", "bottom"]
    ) -> BytesIO:
        output_data = BytesIO()

        if img.width < 100:
            raise ImageTooSmallError

        wrapped_text = textwrap.fill(caption, width=(img.width // 13))

        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font file not found: {font_path}")
        font_data = ImageFont.truetype(font_path, img.width // 11)

        # decide font size
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        while True:
            bbox = draw.textbbox((0, 0), wrapped_text, font=font_data)
            size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
            if size[0] <= img.width - 20:
                break
            elif font_data.size <= 6:
                break
            else:
                font_data = ImageFont.truetype(font_path, font_data.size - 1)

        TEXT_WIDTH = size[0]
        TEXT_HEIGHT = size[1]

        # decide padding
        if img.width < 500:
            # less padding on smaller images
            padding = max(10, int(img.width * 0.08))  # 8% of width, minimum 10px
        else:
            # normal padding
            padding = 40

        WHITE_HEIGHT = 10 + TEXT_HEIGHT + padding

        is_animated = getattr(img, "n_frames", 1) > 1

        if is_animated:
            frames: list[Image.Image] = []

            # process frames
            for frame in range(getattr(img, "n_frames", 1)):
                img.seek(frame)

                frames.append(
                    self._create_caption_frame(
                        img,
                        font_data,
                        int(TEXT_WIDTH),
                        int(WHITE_HEIGHT),
                        wrapped_text,
                        pos,
                    )
                )

            # save as png to convert later
            frames[0].save(
                output_data,
                format="PNG",
                save_all=True,
                append_images=frames[1:],
                duration=getattr(img, "info", {}).get("duration", 100)
                if hasattr(img, "info")
                else 100,
                loop=0,
            )
        else:
            output_img = self._create_caption_frame(
                img,
                font_data,
                int(TEXT_WIDTH),
                int(WHITE_HEIGHT),
                wrapped_text,
                pos,
            )

            output_img.save(output_data, format="PNG")

        output_data.seek(0)
        return output_data

    async def caption(
        self,
        output_format: ImageFormats,
        caption: str,
        font: str,
        pos: Literal["top", "bottom"],
    ) -> File:
        """
        Add a caption to the image and return file.
        """
        img = await self._load_image()
        captioned_buffer = await asyncio.to_thread(self._caption_sync, img, caption, font, pos)

        # check if image is animated
        captioned_img = await asyncio.to_thread(self._load_sync, captioned_buffer.getvalue())
        is_animated = getattr(captioned_img, "n_frames", 1) > 1

        if is_animated and output_format not in [
            ImageFormats.GIF,
            ImageFormats.WEBP,
            ImageFormats.PNG,
        ]:
            # static - get first frame
            captioned_img.seek(0)
            first_frame = captioned_img.convert("RGBA").copy()
            final_buffer = await asyncio.to_thread(self._save_sync, first_frame, output_format, 95)
        else:
            # animated - convert normally
            final_buffer = await asyncio.to_thread(
                self._save_sync, captioned_img, output_format, 95
            )

        return File(
            fp=final_buffer,
            filename=self._get_output_filename(output_format),
        )

    def _rotate_sync(self, img: Image.Image, angle: int) -> Image.Image:
        return img.rotate(angle, expand=True)

    async def rotate(self, output_format: ImageFormats, angle: int) -> File:
        """
        Rotate the image by the specified angle and return file.
        """
        img = await self._load_image()
        rotated_img = await asyncio.to_thread(self._rotate_sync, img, angle)
        buffer = await asyncio.to_thread(self._save_sync, rotated_img, output_format, 95)

        return File(
            fp=buffer,
            filename=self._get_output_filename(output_format),
        )

    def _invert_sync(self, img: Image.Image) -> Image.Image:
        if img.mode == "RGBA":
            r, g, b, a = img.split()
            rgb_image = Image.merge("RGB", (r, g, b))
            inverted_image = ImageOps.invert(rgb_image)
            r2, g2, b2 = inverted_image.split()
            final_image = Image.merge("RGBA", (r2, g2, b2, a))
            return final_image
        else:
            return ImageOps.invert(img)

    async def invert(self, output_format: ImageFormats) -> File:
        """
        Invert the colors of the image and return file.
        """
        img = await self._load_image()
        inverted_img = await asyncio.to_thread(self._invert_sync, img)
        buffer = await asyncio.to_thread(self._save_sync, inverted_img, output_format, 95)

        return File(
            fp=buffer,
            filename=self._get_output_filename(output_format),
        )

    def _grayscale_sync(self, img: Image.Image) -> Image.Image:
        return ImageOps.grayscale(img).convert("RGBA")

    async def grayscale(self, output_format: ImageFormats) -> File:
        """
        Convert the image to grayscale and return file.
        """
        img = await self._load_image()
        grayscale_img = await asyncio.to_thread(self._grayscale_sync, img)
        buffer = await asyncio.to_thread(self._save_sync, grayscale_img, output_format, 95)

        return File(
            fp=buffer,
            filename=self._get_output_filename(output_format),
        )
