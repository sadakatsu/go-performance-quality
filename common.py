import asyncio
import re

from PIL import Image
from pyppeteer import launch


def get_filename_core(analysis_filename: str):
    return re.match(r'^(?:[^\\/]*[\\/])*(.*)\.csv$', analysis_filename).group(1)


def render_html(html: str, filename: str):
    event_loop = asyncio.get_event_loop()
    event_loop.run_until_complete(
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
