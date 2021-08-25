import json
import os
import re
import sys
import uuid

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
                print(' ' * depth, matcher)
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


def translate_sgf_coord(coord):
    uppercase = coord.upper()
    if uppercase == 'TT':
        return ()
    first, second = uppercase
    column = first if first < 'I' else f'{chr(ord(first) + 1)}'
    row = ord("A") + 19 - ord(second)
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
    node = {}
    if properties:
        if not isinstance(properties, list):
            properties = [properties]
        for prop in properties:
            identifier = prop['identifier']
            if identifier in ('AB', 'B', 'BR', 'DT', 'FF', 'GM', 'HA', 'KM', 'PB', 'PW', 'RE', 'RU', 'SZ', 'W', 'WR'):
                node[identifier] = prop['value']
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


def transform_node(node):
    if 'B' in node:
        color = 'B'
        move = node['B']
    elif 'W' in node:
        color = 'W'
        move = node['W']
    else:
        return None
    if move == ():
        move = 'pass'
    return [color, move]


def transform_sgf_to_command(main_variation, convert=True):
    setup_node = main_variation[0]
    print(setup_node)
    if 'GM' not in setup_node or setup_node['GM'] != 1:
        raise Exception('Wrong game')
    elif 'FF' not in setup_node or setup_node['FF'] != 4:
        raise Exception('Wrong format')
    elif 'SZ' not in setup_node or setup_node['SZ'] != 19:
        raise Exception('Wrong size')
    elif 'HA' in setup_node and (setup_node['HA'] < 0 or setup_node['HA'] > 9):
        raise Exception('Wrong handicap')
    elif 'RU' in setup_node and setup_node['RU'].lower() not in (
            'aga',
            'aga-button',
            'bga',
            'chinese',
            'chinese-kgs',
            'chinese-ogs',
            'japanese',
            'korean',
            'new-zealand',
            'stone-scoring',
            'tromp-taylor'
    ):
        raise Exception('Wrong rule set')

    # PandaNet games can generate empty nodes
    moves = [y for y in [transform_node(x) for x in main_variation[1:]] if y]

    output = {
        "id": str(uuid.uuid4()),
        "moves": moves,
        "initialStones": [],
        "initialPlayer": 'B' if 'B' in main_variation[1] else 'W',
        "rules": 'japanese' if 'RU' not in setup_node else setup_node['RU'].lower(),
        "komi": 6.5 if 'KM' not in setup_node else setup_node['KM'],
        "boardXSize": 19,
        "boardYSize": 19,
        "analyzeTurns": [x for x in range(len(moves) + 1)]
    }

    if 'AB' in setup_node:
        placements = setup_node['AB']
        if not isinstance(placements, list):
            placements = [placements]
        output['initialStones'] = [['B', x] for x in placements]

    if 'HA' in setup_node:
        handicap = setup_node['HA']
        if 'AB' not in setup_node:
            stones = output["initialStones"]
            if handicap >= 2:
                stones.extend([['B', 'Q16'], ['B', 'D4']])
            if handicap >= 3:
                stones.append(['B', 'Q4'])
            if handicap >= 4:
                stones.append(['B', 'D16'])
            if handicap in (5, 7, 9):
                stones.append(['B', 'K10'])
            if handicap in (6, 8, 9):
                stones.extend([['B', 'D10'], ['B', 'Q10']])
            if handicap >= 8:
                stones.extend([['B', 'K16'], ['B', 'K4']])

    if convert:
        returned_command = json.dumps(output, separators=(',', ':')) + os.linesep
    else:
        returned_command = output

    return (
        returned_command,
        output['initialPlayer'],
        len(output['analyzeTurns'])
    )
