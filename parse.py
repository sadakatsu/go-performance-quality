# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.

import json
import os
import re
import sys
import uuid
from typing import Tuple, Union, Optional, List

from katago import Player, Coordinate, Pass
from katago.query import Query, MoveDTO, Ruleset

debug = False
sys.setrecursionlimit(10_000)


def log_parsing(label, text, index, depth):
    if debug:
        if index < len(text):
            tail = text[index:min(len(text), index + 20)]
        else:
            tail = '<<EOF>>'
        print(f'{" " * depth}{label} @ {index} :: {tail}')


def build_terminal(name, pattern):
    label = f'Terminal {name}'
    regex = re.compile(pattern)

    def curried(text, index, depth=0):
        log_parsing(label, text, index, depth)
        matcher = regex.match(text, index)
        if matcher:
            if debug:
                print(' ' * depth, matcher.group())
            return matcher.group(0), matcher.end()
        else:
            raise Exception(f'Could not parse beyond {index}')

    return curried


def build_ignore(name, parse):
    label = f'Ignore {name}'
    parser = build_terminal(name, parse) if isinstance(parse, str) else parse

    def curried(text, index, depth=0):
        log_parsing(label, text, index, depth)
        _, end = parser(text, index, depth + 1)
        return None, end

    return curried


def build_transform(name, parser, transformation):
    label = f'Transform {name}'

    def curried(text, index, depth=0):
        log_parsing(label, text, index, depth)
        result, end = parser(text, index, depth + 1)
        x = transformation(result)
        if debug:
            print(' ' * depth, f'{index}:: {text[index:end]} => {x}')
        return x, end

    return curried


def build_and(name, *parsers):
    label = f'And {name}'

    def curried(text, index, depth=0):
        log_parsing(label, text, index, depth)
        results, end = [], index
        for parser in parsers:
            result, end = parser(text, end, depth + 1)
            if result is not None:
                results.append(result)
        if len(results) == 0:
            results = None
        elif len(results) == 1:
            results = results[0]
        return results, end

    return curried


def build_or(name, *parsers):
    label = f'Or {name}'

    def curried(text, index, depth=0):
        log_parsing(label, text, index, depth)
        matched, best_result, best_end = False, None, -1
        for parser in parsers:
            try:
                result, end = parser(text, index, depth + 1)
                if end > best_end:
                    best_result, best_end = result, end
                    matched = True
            except Exception as e:
                if debug:
                    print(e)
        if matched:
            return best_result, best_end
        else:
            raise Exception(f'Could not parse beyond {index}; no ORed productions matched')

    return curried


def build_one_or_more(name, parser, separator=None):
    label = f'One-Or-More {name}'

    def curried(text, index, depth=0):
        log_parsing(label, text, index, depth)
        result, end = parser(text, index, depth + 1)
        results = [result]

        while end < len(text):
            try:
                middle_end = end
                if separator is not None:
                    _, middle_end = separator(text, middle_end, depth + 1)

                result, end = parser(text, middle_end, depth + 1)
                if result is not None:
                    results.append(result)
            except Exception as e:
                if debug:
                    print(e)
                break

        if len(results) == 0:
            results = None
        elif len(results) == 1:
            results = results[0]
        return results, end

    return curried


def build_zero_or_more(name, parser, separator=None):
    label = f'Zero-Or-More {name}'

    def curried(text, index, depth=0):
        log_parsing(label, text, index, depth)
        end = index
        results = []
        continuation = False

        try:
            while end < len(text):
                middle_end = end
                if continuation and separator is not None:
                    _, middle_end = separator(text, middle_end, depth + 1)

                result, end = parser(text, middle_end, depth + 1)
                if result is not None:
                    results.append(result)
                continuation = True
        except Exception as e:
            if debug:
                print(e)

        if len(results) == 0:
            results = None
        elif len(results) == 1:
            results = results[0]
        return results, end

    return curried


class Placeholder:
    def __init__(self):
        self.parser = None

    def __call__(self, text, index, depth=0):
        if self.parser is None:
            raise Exception('Placeholder not defined!')
        return self.parser(text, index, depth)


board_size = 19


def translate_sgf_coord(coord):
    uppercase = coord.upper()
    if uppercase == 'TT':
        return ()
    first, second = uppercase
    column = first if first < 'I' else f'{chr(ord(first) + 1)}'
    row = ord("A") + board_size - ord(second)
    return f'{column}{row}'


parse_open_bracket = build_ignore('[', r'\[', )
parse_close_bracket = build_ignore(']', r'\]')
parse_open_parenthesis = build_ignore('(', r'\(')
parse_close_parenthesis = build_ignore(')', r'\)')
parse_semicolon = build_ignore(';', r'\;')
parse_whitespace = build_ignore('WHITESPACE', r'\s*')

parse_none = build_transform(
    'None',
    build_terminal('None', r''),
    lambda _: ()
)

parse_number = build_transform(
    'Number',
    build_terminal('Number', r'[+\-]?[0-9]+(?!\.)'),
    int
)

parse_real = build_transform(
    'Real',
    build_terminal('Real', r'[+\-]?[0-9]+(\.[0-9]+)?'),
    float
)

parse_color = build_terminal('Color', r'[BW]')

parse_text = build_terminal('Text', r'(?:[^\]\\]+|\\.)*')

parse_point = build_transform(
    'Point',
    build_terminal('Point', '[a-t]{2}'),
    translate_sgf_coord
)

parse_c_value_type = build_or(
    'CValueType',
    parse_number,
    parse_real,
    parse_color,
    parse_point,
    parse_none,
    parse_text
)

parse_prop_value = build_and(
    'PropValue',
    parse_open_bracket,
    parse_whitespace,
    parse_c_value_type,
    parse_whitespace,
    parse_close_bracket
)

parse_prop_ident = build_terminal('PropIdent', r'[A-Z]+')

parse_property = build_transform(
    'Property',
    build_and(
        'Property',
        parse_prop_ident,
        parse_whitespace,
        build_one_or_more(
            'PropValue',
            parse_prop_value,
            parse_whitespace
        )
    ),
    lambda x: {'identifier': x[0], 'value': x[1]}
)


def construct_node(properties):
    global board_size

    node = {}
    if properties:
        if not isinstance(properties, list):
            properties = [properties]
        for prop in properties:
            identifier = prop['identifier']
            if identifier in (
                'AB',
                'AW',
                'B',
                'BR',
                'BT',
                'DT',
                'EV',
                'FF',
                'GM',
                'GN',
                'HA',
                'KM',
                'OT',
                'PB',
                'PC',
                'PW',
                'RE',
                'RO',
                'RU',
                'SZ',
                'TC',  # gorram Fox
                'TM',
                'TT',  # gorram Fox
                'W',
                'WR',
                'WT'
            ):
                value = prop['value']
                node[identifier] = value

                # I am now permitting other board sizes.  I need to be able to translate coordinates based upon the
                # SZ (size) node.  This results in context-based parsing, but... oh well?
                if identifier == 'SZ':
                    board_size = int(value)
    return node


parse_node = build_transform(
    'Node',
    build_and(
        'Node',
        parse_semicolon,
        parse_whitespace,
        build_zero_or_more(
            'Property',
            parse_property,
            parse_whitespace
        )
    ),
    construct_node
)


class Sequence:
    def __init__(self, values):
        self.values = values

    def __repr__(self):
        return f'{{ Sequence values: {self.values} }}'


parse_sequence = build_transform(
    'Sequence',
    build_one_or_more('Sequence', parse_node, parse_whitespace),
    lambda x: Sequence(x) if isinstance(x, list) else Sequence([x])
)


def simplify_game_tree(arguments):
    try:
        if isinstance(arguments, Sequence):
            result = arguments
        elif isinstance(arguments, dict):
            result = Sequence([arguments])
        else:
            first = arguments[0].values
            if isinstance(arguments[1], Sequence):
                second = arguments[1].values
            else:
                second = arguments[1][0].values
            result = Sequence(first + second)
        return result
    except Exception as e:
        print('!!!!!!', e, ':', arguments)
        raise e


parse_game_tree = Placeholder()
parse_game_tree.parser = build_transform(
    'GameTree',
    build_and(
        'GameTree',
        parse_open_parenthesis,
        parse_whitespace,
        parse_sequence,
        parse_whitespace,
        build_zero_or_more(
            'GameTree',
            parse_game_tree,
            parse_whitespace
        ),
        parse_whitespace,
        parse_close_parenthesis
    ),
    simplify_game_tree
)


def return_first_sequence(collection):
    sequence = collection.values if isinstance(collection, Sequence) else collection[0].values
    while 'B' in sequence[-1] and sequence[-1]['B'] == () or 'W' in sequence[-1] and sequence[-1]['W'] == ():
        sequence.pop()
    return sequence


parse_collection = build_transform(
    'Collection',
    build_and(
        'Collection',
        parse_whitespace,
        build_one_or_more('GameTree', parse_game_tree, parse_whitespace),
        parse_whitespace
    ),
    return_first_sequence
)


def parse_sgf_contents(text):
    c, end = parse_collection(text, 0)
    if end < len(text):
        raise Exception(f'Could only parse as far as {end}: {text[end:min(len(text), end + 20)]}')
    return c


def transform_node(node) -> Optional[MoveDTO]:
    player: Player
    value: str
    if 'B' in node:
        player = Player.B
        value = node['B']
    elif 'W' in node:
        player = Player.W
        value = node['W']
    else:
        return None

    move: Union[Coordinate, Pass] = (
        Pass.PASS
        if not value or value.lower() == 'pass'
        else Coordinate(value.upper())
    )
    return MoveDTO(player=player, move=move)


def transform_sgf_to_query(main_variation, convert=True) -> Tuple[Query, str, int]:
    setup_node = main_variation[0]
    print(setup_node)
    # Developer's Note: (J. Craig, 2022-02-24)
    # I have a lot of crappy SGFs to process.  Rather than fixing them all, I am making my code more tolerant for now.
    if 'GM' in setup_node and setup_node['GM'] != 1:
        raise Exception('Wrong game')
    elif 'FF' in setup_node and setup_node['FF'] != 4:
        # Hack because of freaking GoGoD.
        print(f'WARNING: FF[{setup_node["FF"]}] is not 4')
        # raise Exception('Wrong format')

    # Reject games that have AW (Add White) nodes because we cannot handle those yet.
    if 'AW' in setup_node:
        raise Exception('We do not support games with initial White stones yet.')

    # Ensure we have a legal handicap value and initial stone placement.
    initial_stones: Optional[List[MoveDTO]] = None
    if 'HA' in setup_node:
        handicap = setup_node['HA']
        if handicap < 0 or handicap > 9:
            raise Exception('Wrong handicap')
        elif handicap > 1:
            if 'AB' in setup_node:
                ab = setup_node['AB']
                if len(ab) != handicap:
                    raise Exception(f'HA[{handicap}], len(AB[]) is {len(ab)}')
                initial_stones = [MoveDTO(player=Player.B, move=Coordinate(x.upper())) for x in ab]
            else:
                # Technically, we should not do this.  This is yet another attempt to handle crappy SGF files.
                placement_coordinates: List[str] = ['Q16', 'D4']
                if handicap >= 3:
                    placement_coordinates.append('Q4')
                if handicap >= 4:
                    placement_coordinates.append('D16')
                if handicap in (5, 7, 9):
                    placement_coordinates.append('K10')
                if handicap in (6, 8, 9):
                    placement_coordinates.extend(['D10', 'Q10'])
                if handicap >= 8:
                    placement_coordinates.extend(['K16', 'K4'])

                initial_stones = [MoveDTO(player=Player.B, move=Coordinate(x)) for x in placement_coordinates]

    # Determine the ruleset.  Default to Japanese.
    rules: Ruleset = Ruleset.JAPANESE
    if 'RU' in setup_node:
        ruleset_name = setup_node['RU'].lower()
        if ruleset_name not in Ruleset:
            raise Exception('Wrong rule set')
        rules = Ruleset(ruleset_name)

    # Ensure we know komi.  If the setup node did not provide it, get it from the ruleset.
    komi: float = setup_node['KM'] if 'KM' in setup_node else rules.specification.komi

    # We need to generate the list of moves.  Two servers have annoying quirks we have to correct.
    # - PandaNet can generate empty nodes in the SGF file.
    # - OGS treats the first move of a one-level difference between two players as being a freely placed stone instead
    #   of a move.
    moves = [y for y in [transform_node(x) for x in main_variation[1:]] if y]
    if 'AB' in setup_node and len(setup_node['AB']) == 1:
        moves.insert(0, transform_node(setup_node['AB'][0]))
    initial_player = moves[0].player
    analyze_turns = [x for x in range(len(moves) + 1)]

    size = setup_node['SZ']

    query = Query(
        analyze_turns=analyze_turns,
        board_x_size=size,
        board_y_size=size,
        include_policy=True,
        initial_player=initial_player,
        initial_stones=initial_stones,
        komi=komi,
        moves=moves,
        rules=rules,
    )

    return (
        query,
        str(initial_player.value),
        len(analyze_turns)
    )
