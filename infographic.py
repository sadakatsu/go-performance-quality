import os

import PIL.Image as Image
from mako.template import Template

from common import ImageData, get_filename_core, render_html
from typing import List


def generate_infographic(
    configuration: dict,
    analysis_filename: str,
    game: List[dict],
    kifu: ImageData,
    performance_table: ImageData,
    expected_result: ImageData,
    distribution: ImageData
) -> ImageData:
    core_filename = get_filename_core(analysis_filename)
    infographic_filename = f'{configuration["infographics_directory"]}/{core_filename}.png'

    buffer = configuration['buffer']
    width = kifu.width + performance_table.width + buffer
    header = _compose_header(game, buffer, width)

    brand_image = Image.open(configuration['brand'])
    brand_image = brand_image.resize((int(round(brand_image.width / 2)), int(round(brand_image.height / 2))))
    header_image = Image.open(header.filename)

    width = header_image.width + buffer * 2
    height = brand_image.height + header.height + kifu.height + expected_result.height + buffer * 5

    layout = Image.new(mode='RGBA', size=(width, height), color=(31, 9, 38, 255))

    layout.paste(brand_image, (buffer + (width - brand_image.width) // 2, buffer), brand_image)
    layout.paste(header_image, (buffer, buffer * 2 + brand_image.height), header_image)

    child_image = Image.open(kifu.filename)
    layout.paste(
        child_image,
        (buffer, buffer * 3 + brand_image.height + header_image.height),
        child_image
    )

    child_image = Image.open(performance_table.filename)
    layout.paste(
        child_image,
        (buffer * 2 + kifu.width, buffer * 3 + brand_image.height + header_image.height),
        child_image
    )

    child_image = Image.open(expected_result.filename)
    layout.paste(
        child_image,
        (buffer, buffer * 4 + brand_image.height + header_image.height + kifu.height),
        child_image
    )

    child_image = Image.open(distribution.filename)
    layout.paste(
        child_image,
        (
            width - buffer - child_image.width,
            buffer * 4 + brand_image.height + header_image.height + kifu.height
        ),
        child_image
    )

    layout.save(infographic_filename)
    os.remove(header.filename)
    return ImageData(infographic_filename, layout.width, layout.height)


def _compose_header(game: List[dict], buffer: int, width: int) -> ImageData:
    root = game[0]

    title, subtitle = _get_title_and_subtitle(root)

    black = _compose_player(root, 'PB', 'BR', 'BT')
    white = _compose_player(root, 'PW', 'WR', 'WT')
    date = _get_value(root, 'DT')
    moves = int(len(game) - 1)
    place = _get_value(root, 'PC')
    result = _get_value(root, 'RE', 'Void')
    setup = _compose_setup(root)
    time = _compose_time(root)

    template = Template(_template)
    html = template.render(
        _buffer=buffer,
        black=black,
        date=date,
        moves=moves,
        place=place,
        result=result,
        setup=setup,
        subtitle=subtitle,
        time=time,
        title=title,
        white=white,
        width=width
    )
    size = render_html(html, 'header.png')
    return ImageData('header.png', size[0], size[1])


def _get_title_and_subtitle(root):
    subtitle = None

    name = _get_value(root, 'GN')
    event = _get_value(root, 'EV')
    event_round = _get_value(root, 'RO')

    if event:
        subtitle = event
        if event_round:
            subtitle += f', Round {event_round}'

    if name:
        title = root['GN']
    else:
        title = subtitle
        subtitle = None

    return title, subtitle


def _get_value(root, key, default=''):
    return root[key] if key in root else default


def _compose_player(root: dict, name: str, rank: str, team: str) -> str:
    composed = _get_value(root, name, 'Not Recorded')
    if rank in root:
        composed += f' {root[rank]}'
    if team in root:
        composed += f' of {root[team]}'
    return composed


def _compose_setup(root):
    rules = _get_value(root, 'RU', 'Japanese')
    if 'aga' == rules.lower():
        setup = 'AGA'
    else:
        setup = rules.title()

    size = _get_value(root, 'SZ', '19')
    setup += f', {size}x{size}'

    handicap = _get_value(root, 'HA')
    if handicap and handicap >= 2:
        setup += f', {handicap} stones'

    komi = _get_value(root, 'KM')
    if komi:
        setup += f', komi {komi}'

    return setup


def _compose_time(root):
    main = _get_value(root, 'TM')
    try:
        as_number = float(main)
        time = []

        hours = int(as_number // 3600)
        if hours:
            time.append(f'{hours} hours')
            as_number -= hours * 3600

        minutes = int(as_number // 60)
        if minutes:
            time.append(f'{minutes} minutes')
            as_number -= minutes * 60

        if as_number:
            time.append(f'{as_number} seconds')
        time = ', '.join(time)
    except ValueError:
        time = main

    overtime = _get_value(root, 'OT')

    return ' with '.join([x for x in [time, overtime] if x])


_template = '''
<!DOCTYPE html>
<html>
    <head>
        <style>
            body {
                font-family: 'Berlin Sans FB', 'sans-serif';
                font-size: 24pt;
                width: ${width}px;
                max-width: ${width}px;
            }
            
            table {
                margin: 0px;
                padding: ${_buffer // 2}px ${_buffer}px 0px ${_buffer}px;
            }
            
            tr td:not(:last-child) {
                padding-right: ${_buffer}px;
            }
            
            tr {
                vertical-align: bottom;
            }
            
            .center {
              margin-left: auto;
              margin-right: auto;
            }
            
            .label {
                font-weight: 500;
            }
            
            .subtitle {
                font-size: 28pt;
                font-style: italic;
                margin: 0px;
                padding: ${_buffer // 2}px ${_buffer}px 0px ${_buffer}px;
            }
            
            .title {
                font-size: 32pt;
                font-weight: 500;
                margin: 0px;
                padding: 0px;
            }
            
            .wrapped {
                background-color: rgb(143, 132, 147);
                border: 1px solid black;
                padding: ${_buffer}px;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="wrapped">
            % if title:
            <p class="title">${title}</p>
            % endif
            
            % if subtitle:
            <p class="subtitle">${subtitle}</p>
            % endif
            
            <table class="center">
                <tbody>
                    <tr>
                        <td class="label" nowrap>Black:</td>
                        <td nowrap>${black}</td>
                        <td class="label" nowrap>White:</td>
                        <td nowrap>${white}</td>
                    </tr>
                    
                    <tr>
                        <td class="label" nowrap>Date:</td>
                        <td nowrap>${date}</td>
                        <td class="label" nowrap>Place:</td>
                        <td nowrap>${place}</td>
                    </tr>
                    
                    <tr>
                        <td class="label" nowrap>Setup:</td>
                        <td nowrap>${setup}</td>
                        <td class="label" nowrap>Time:</td>
                        <td nowrap>${time}</td>
                    </tr>
                    
                    <tr>
                        <td class="label" nowrap>Moves:</td>
                        <td nowrap>${moves}</td>
                        <td class="label" nowrap>Result:</td>
                        <td nowrap>${result}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </body>
</html>
'''