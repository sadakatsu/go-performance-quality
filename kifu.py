from typing import Tuple

from mako.template import Template

from common import get_filename_core, render_html, ImageData


def print_kifu(
    kifu_directory: str,
    analysis_filename: str,
    size: int,
    game,
    height
) -> ImageData:
    filename_core = get_filename_core(analysis_filename)
    kifu_filename = f'{kifu_directory}/{filename_core}.png'

    overlaps = []
    rows = [[None for x in range(size)] for y in range(size)]
    for move_number, node in enumerate(game):
        if 'AB' in node:
            # OGS -_-
            if not isinstance(node['AB'], list):
                node['AB'] = [node['AB']]
            for label in node['AB']:
                x, y = _convert_coordinate_to_index(label, size)
                rows[y][x] = 'B', None
        if 'AW' in node:
            # OGS -_-
            if not isinstance(node['AW'], list):
                node['AW'] = [node['AW']]
            for label in node['AW']:
                x, y = _convert_coordinate_to_index(label, size)
                rows[y][x] = 'W', None
        if 'B' in node:
            label = node['B']
            if not label:
                overlaps.append(('B', move_number, 'pass'))
            else:
                x, y = _convert_coordinate_to_index(label, size)
                if rows[y][x]:
                    overlaps.append(('B', move_number, label))
                else:
                    rows[y][x] = 'B', move_number
        if 'W' in node:
            label = node['W']
            if not label:
                overlaps.append(('W', move_number, 'pass'))
            else:
                x, y = _convert_coordinate_to_index(label, size)
                if rows[y][x]:
                    overlaps.append(('W', move_number, label))
                else:
                    rows[y][x] = 'W', move_number

    template = Template(_template)
    html = template.render(
        dimension=height,
        overlaps=overlaps,
        rows=rows,
        size=size,
    )

    size = render_html(html, kifu_filename)
    return ImageData(kifu_filename, size[0], size[1])


def _convert_coordinate_to_index(coordinate: str, size: int) -> Tuple[int, int]:
    column_label, row_label = coordinate[0], coordinate[1:]
    column = ord(column_label) - ord('A')
    if column_label >= 'I':
        column -= 1
    row = size - int(row_label)
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
                background-color: rgb(97, 78, 25);
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
                    viewBox="0 0 ${(size + 2) * 100} ${(size + 2) * 100}"
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
                    <rect fill="rgb(148, 118, 38)" height="100%" stroke="black" stroke-width="3" width="100%" x="0" y="0" />
                    
                    <rect
                        fill="url(#grid-horizontal-lines)"
                        height="${(size + 2) * 100 - 297}"
                        width="${(size + 2) * 100 - 297}"
                        x="148.5"
                        y="148.5"
                    />
                    <rect
                        fill="url(#grid-vertical-lines)"
                        height="${(size + 2) * 100 - 297}"
                        width="${(size + 2) * 100 - 297}"
                        x="148.5"
                        y="148.5"
                    />
            
                    <!-- Hoshi -->
                    % if size % 2 == 1:
                    <use x="${(size // 2 + 1) * 100 + 50}" xlink:href="#star" y="${(size // 2 + 1) * 100 + 50}"/>
                    
                    % if size >= 13:
                    <use x="${(size // 2 + 1) * 100 + 50}" xlink:href="#star" y="450"/>
                    <use x="450" xlink:href="#star" y="${(size // 2 + 1) * 100 + 50}"/>
                    <use x="${(size - 3) * 100 + 50}" xlink:href="#star" y="${(size // 2 + 1) * 100 + 50}"/>
                    <use x="${(size // 2 + 1) * 100 + 50}" xlink:href="#star" y="${(size - 3) * 100 + 50}"/>
                    % endif
                    
                    % endif
                    
                    % if size >= 13:
                    <use x="450" xlink:href="#star" y="450"/>
                    <use x="450" xlink:href="#star" y="${(size - 3) * 100 + 50}"/>
            
                    <use x="${(size - 3) * 100 + 50}" xlink:href="#star" y="450"/>
                    <use x="${(size - 3) * 100 + 50}" xlink:href="#star" y="${(size - 3) * 100 + 50}"/>
                    % endif
                    
                    <!-- Coordinates -->
                    % for x in range(0, size):
                    <svg height="100" width="100" x="${(x + 1) * 100}" y="0">
                        <text
                            dominant-baseline="middle"
                            font-size="3em"
                            style="color: rgba(0,0,0,0.7);"
                            text-anchor="middle"
                            x="50%"
                            y="50%"
                        >
                            ${chr(65 + x + (1 if x >= 8 else 0))}
                        </text>
                    </svg>
                        
                    <svg height="100" width="100" x="${(x + 1) * 100}" y="${(size + 1) * 100}">
                        <text
                            dominant-baseline="middle"
                            font-size="3em"
                            style="color: rgba(0,0,0,0.7);"
                            text-anchor="middle"
                            x="50%"
                            y="50%"
                        >
                            ${chr(65 + x + (1 if x >= 8 else 0))}
                        </text>
                    </svg>
                    
                    <svg height="100" width="100" x="0" y="${(x + 1) * 100}">
                        <text
                            dominant-baseline="middle"
                            font-size="3em"
                            style="color: rgba(0,0,0,0.7);"
                            text-anchor="middle"
                            x="50%"
                            y="50%"
                        >
                            ${size - x}
                        </text>
                    </svg>
                    
                    <svg height="100" width="100" x="${(size + 1) * 100}" y="${(x + 1) * 100}">
                        <text
                            dominant-baseline="middle"
                            font-size="3em"
                            style="color: rgba(0,0,0,0.7);"
                            text-anchor="middle"
                            x="50%"
                            y="50%"
                        >
                            ${size - x}
                        </text>
                    </svg>
                    % endfor
                    
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