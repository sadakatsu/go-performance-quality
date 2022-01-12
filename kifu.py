from typing import Tuple

from mako.template import Template

from common import get_filename_core, render_html, ImageData


def print_kifu(
    kifu_directory: str,
    analysis_filename: str,
    game,
    height
) -> ImageData:
    filename_core = get_filename_core(analysis_filename)
    kifu_filename = f'{kifu_directory}/{filename_core}.png'

    overlaps = []
    rows = [[None for x in range(19)] for y in range(19)]
    for move_number, node in enumerate(game):
        if 'AB' in node:
            for label in node['AB']:
                x, y = _convert_coordinate_to_index(label)
                rows[y][x] = 'B', None
        if 'AW' in node:
            for label in node['AW']:
                x, y = _convert_coordinate_to_index(label)
                rows[y][x] = 'W', None
        if 'B' in node:
            label = node['B']
            if not label:
                overlaps.append(('B', move_number, 'pass'))
            else:
                x, y = _convert_coordinate_to_index(label)
                if rows[y][x]:
                    overlaps.append(('B', move_number, label))
                else:
                    rows[y][x] = 'B', move_number
        if 'W' in node:
            label = node['W']
            if not label:
                overlaps.append(('W', move_number, 'pass'))
            else:
                x, y = _convert_coordinate_to_index(label)
                if rows[y][x]:
                    overlaps.append(('W', move_number, label))
                else:
                    rows[y][x] = 'W', move_number

    template = Template(_template)
    html = template.render(
        dimension=height,
        overlaps=overlaps,
        rows=rows
    )

    size = render_html(html, kifu_filename)
    return ImageData(kifu_filename, size[0], size[1])


def _convert_coordinate_to_index(coordinate) -> Tuple[int, int]:
    column_label, row_label = coordinate[0], coordinate[1:]
    column = ord(column_label) - ord('A')
    if column_label >= 'I':
        column -= 1
    row = 19 - int(row_label)
    return column, row

_template = '''
<!DOCTYPE html>
<html>
    <head>
        <style>
            body {
                font-family: Calibri, sans-serif;
                height: ${dimension}px;
                margin: 0px;
                max-height: ${dimension}px;
                max-width: ${dimension}px;
                padding: 0px;
                width: ${dimension}px;
            }
            
            .container {
                display: flex;
                flex-flow: column nowrap;
                height: 100%;
                width: 100%;
            }
            
            .kifu {
                max-height: ${dimension}px;
                max-width: ${dimension}px;
            }
            
            .kifu-container {
                display: flex;
                flex: 1;
                min-height: 0;
                min-width: 0;
            }
            
            .overlap {
                align-items: center;
                display: inline-flex;
                justify-content: center;
                margin: 0.5em;
            }
            
            .move {
                font-size: 1.5em;
            }
            
            .overlap-container {
                background-color: DimGray;
                border: 1px solid black;
                display: flex;
                flex: 0 0 auto;
                flex-flow: row wrap;
                padding: 0.5em;
            }
            
            .stone {
                display: inline-block;
                height: 1.5em;
                width: 1.5em;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="kifu-container">
                <!-- START DIAGRAM -->
                <svg
                    class="kifu"
                    height="100%"
                    preserveAspectRatio="xMidYMin meet"
                    viewBox="0 0 2100 2100"
                    width="100%"
                >
                    <defs>
                        <pattern
                            height="100"
                            id="grid-horizontal-lines"
                            patternContentUnits="userSpaceOnUse"
                            patternUnits="userSpaceOnUse"
                            width="100"
                            x="48.5"
                            y="48.5"
                        >
                            <line stroke-width="3" style="stroke: rgba(0,0,0,0.7);" x1="0%" x2="100%" y1="1.5" y2="1.5"/>
                        </pattern>
            
                        <pattern
                            height="100"
                            id="grid-vertical-lines"
                            patternContentUnits="userSpaceOnUse"
                            patternUnits="userSpaceOnUse"
                            width="100"
                            x="48.5"
                            y="48.5"
                        >
                            <line stroke-width="3" style="stroke: rgba(0,0,0,0.7);" x1="1.5" x2="1.5" y1="0%" y2="100%"/>
                        </pattern>
            
                        <g id="star">
                            <circle cx="0" cy="0" r="8" style="fill: rgba(0,0,0,0.7);"/>
                        </g>
                    </defs>
                    
                    <!-- Grid -->
                    <rect fill="gray" height="100%" stroke="black" stroke-width="3" width="100%" x="0" y="0" />
                    
                    <rect fill="url(#grid-horizontal-lines)" height="1803" width="1803" x="148.5" y="148.5"/>
                    <rect fill="url(#grid-vertical-lines)" height="1803" width="1803" x="148." y="148.5"/>
            
                    <!-- Hoshi -->
                    <use x="450" xlink:href="#star" y="450"/>
                    <use x="450" xlink:href="#star" y="1050"/>
                    <use x="450" xlink:href="#star" y="1650"/>
            
                    <use x="1050" xlink:href="#star" y="450"/>
                    <use x="1050" xlink:href="#star" y="1050"/>
                    <use x="1050" xlink:href="#star" y="1650"/>
            
                    <use x="1650" xlink:href="#star" y="450"/>
                    <use x="1650" xlink:href="#star" y="1050"/>
                    <use x="1650" xlink:href="#star" y="1650"/>
                    
                    <!-- Coordinates -->
                    <svg height="100" width="100" x="100" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">A</text>
                    </svg>
                    <svg height="100" width="100" x="200" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">B</text>
                    </svg>
                    <svg height="100" width="100" x="300" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">C</text>
                    </svg>
                    <svg height="100" width="100" x="400" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">D</text>
                    </svg>
                    <svg height="100" width="100" x="500" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">E</text>
                    </svg>
                    <svg height="100" width="100" x="600" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">F</text>
                    </svg>
                    <svg height="100" width="100" x="700" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">G</text>
                    </svg>
                    <svg height="100" width="100" x="800" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">H</text>
                    </svg>
                    <svg height="100" width="100" x="900" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">J</text>
                    </svg>
                    <svg height="100" width="100" x="1000" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">K</text>
                    </svg>
                    <svg height="100" width="100" x="1100" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">L</text>
                    </svg>
                    <svg height="100" width="100" x="1200" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">M</text>
                    </svg>
                    <svg height="100" width="100" x="1300" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">N</text>
                    </svg>
                    <svg height="100" width="100" x="1400" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">O</text>
                    </svg>
                    <svg height="100" width="100" x="1500" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">P</text>
                    </svg>
                    <svg height="100" width="100" x="1600" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">Q</text>
                    </svg>
                    <svg height="100" width="100" x="1700" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">R</text>
                    </svg>
                    <svg height="100" width="100" x="1800" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">S</text>
                    </svg>
                    <svg height="100" width="100" x="1900" y="0">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">T</text>
                    </svg>
            
                    <svg height="100" width="100" x="100" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">A</text>
                    </svg>
                    <svg height="100" width="100" x="200" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">B</text>
                    </svg>
                    <svg height="100" width="100" x="300" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">C</text>
                    </svg>
                    <svg height="100" width="100" x="400" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">D</text>
                    </svg>
                    <svg height="100" width="100" x="500" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">E</text>
                    </svg>
                    <svg height="100" width="100" x="600" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">F</text>
                    </svg>
                    <svg height="100" width="100" x="700" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">G</text>
                    </svg>
                    <svg height="100" width="100" x="800" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">H</text>
                    </svg>
                    <svg height="100" width="100" x="900" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">J</text>
                    </svg>
                    <svg height="100" width="100" x="1000" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">K</text>
                    </svg>
                    <svg height="100" width="100" x="1100" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">L</text>
                    </svg>
                    <svg height="100" width="100" x="1200" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">M</text>
                    </svg>
                    <svg height="100" width="100" x="1300" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">N</text>
                    </svg>
                    <svg height="100" width="100" x="1400" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">O</text>
                    </svg>
                    <svg height="100" width="100" x="1500" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">P</text>
                    </svg>
                    <svg height="100" width="100" x="1600" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">Q</text>
                    </svg>
                    <svg height="100" width="100" x="1700" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">R</text>
                    </svg>
                    <svg height="100" width="100" x="1800" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">S</text>
                    </svg>
                    <svg height="100" width="100" x="1900" y="2000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">T</text>
                    </svg>
            
                    <svg height="100" width="100" x="0" y="100">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">19</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="200">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">18</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="300">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">17</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="400">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">16</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="500">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">15</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="600">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">14</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="700">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">13</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="800">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">12</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="900">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">11</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">10</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1100">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">9</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1200">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">8</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1300">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">7</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1400">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">6</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1500">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">5</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1600">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">4</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1700">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">3</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1800">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">2</text>
                    </svg>
                    <svg height="100" width="100" x="0" y="1900">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">1</text>
                    </svg>
            
                    <svg height="100" width="100" x="2000" y="100">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">19</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="200">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">18</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="300">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">17</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="400">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">16</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="500">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">15</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="600">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">14</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="700">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">13</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="800">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">12</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="900">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">11</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1000">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">10</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1100">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">9</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1200">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">8</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1300">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">7</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1400">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">6</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1500">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">5</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1600">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">4</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1700">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">3</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1800">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">2</text>
                    </svg>
                    <svg height="100" width="100" x="2000" y="1900">
                        <text dominant-baseline="middle" font-size="3em" style="color: rgba(0,0,0,0.7);" text-anchor="middle" x="50%"
                              y="50%">1</text>
                    </svg>
                    
                    <!-- Position Representation -->
                    % for y, row in enumerate(rows):
                    % for x, cell in enumerate(row):
                    % if cell:
                    <circle
                        cx="${x * 100 + 150}"
                        cy="${y * 100 + 150}"
                        fill="${'black' if cell[0] == 'B' else 'white'}"
                        r="46"
                        stroke="black"
                        stroke-width="3px"
                    ></circle>
                    % if cell[1]:
                    <g>
                        <svg
                            height="100"
                            width="100"
                            x="${x * 100 + 100}"
                            y="${y * 100 + 104}"
                        >
                            <text
                                dominant-baseline="middle"
                                font-size="3em"
                                style="fill: ${'white' if cell[0] == 'B' else 'black'};"
                                text-anchor="middle"
                                x="50%"
                                y="50%"
                            >
                                ${cell[1]}
                            </text>
                        </svg>
                    </g>
                    % endif
                    % endif
                    % endfor
                    % endfor
                </svg>
                <!-- END DIAGRAM -->
            </div>
            
            % if overlaps:
            <div class="overlap-container">
                % for entry in overlaps[0:min(100, len(overlaps))]:
                <span class="overlap">
                    <svg class="stone" viewBox="0 0 100 100">
                        <circle
                            cx="50"
                            cy="50"
                            fill="${'black' if entry[0] == 'B' else 'white'}"
                            r="46"
                            stroke="black"
                            stroke-width="3px"
                        ></circle>
                        <text
                            dominant-baseline="middle"
                            font-size="3em"
                            style="fill: ${'white' if entry[0] == 'B' else 'black'};"
                            text-anchor="middle"
                            x="50%"
                            y="56%"
                        >
                            ${entry[1]}
                        </text>
                    </svg>
                    <span class="move">:&nbsp;${entry[2]}</span>
                </span>
                % endfor
                % if len(overlaps) > 100:
                <span>...</span>
                % endif
            </div>
            %endif
        </div>
    </body>
</html>
'''