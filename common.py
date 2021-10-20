import asyncio
import re

from collections import namedtuple
from PIL import Image
from pyppeteer import launch
from typing import Tuple

ImageData = namedtuple('ImageData', 'filename width height')


def get_filename_core(analysis_filename: str) -> str:
    return re.match(r'^(?:[^\\/]*[\\/])*(.*)\.csv$', analysis_filename).group(1)


def render_html(html: str, filename: str) -> Tuple[int, int]:
    event_loop = asyncio.get_event_loop()
    return event_loop.run_until_complete(
        _perform_render_html(
            html,
            filename
        )
    )


async def _perform_render_html(html: str, filename: str):
    browser = await launch(defaultViewport=None)
    page = await browser.newPage()
    await page.setContent(html)
    await page.screenshot(
        {
            'path': filename,
            'fullPage': 'true',
            'omitBackground': 'true'
        }
    )
    await browser.close()

    with Image.open(filename) as image:
        bounding_box = image.getbbox()
        if bounding_box:
            cropped = image.crop(bounding_box)
            cropped.save(filename)
            size = cropped.size
        else:
            size = image.size
    return size
