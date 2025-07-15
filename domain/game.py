from __future__ import annotations

from typing import Optional, Set, List, Tuple

from domain.board import Board
from domain.color import Color
from domain.coordinate import Coordinate
from domain.group import Group
from domain.korule import KoRule
from domain.orientation import Orientation
from domain.pass_enum import Pass
from domain.ruleset import Ruleset
from domain.scoring import Scoring


class Game:
    def __init__(
        self,
        ruleset=Ruleset.JAPANESE,
        komi=6.5,
        handicap_stones: Optional[Set[Coordinate]] = None,
        _previous_state: Optional[Game] = None,
        _previous_move: Optional[Coordinate | Pass] = None,
        _additional_captures=0,
        _board: Optional[Board] = None,
        _kos: Optional[Set[Coordinate]] = None,
    ):
        self._representation: Optional[str] = None

        if not _previous_state:
            self._captures_by_black = 0
            self._captures_by_white = 0
            self._ko_capture = False
            self._ko_ended = False
            self._kos = _kos or set()
            self._kos_previous = set()
            self._komi = komi
            self._moves_played = 0
            self._previous_move: Optional[Coordinate | Pass] = None
            self._previous_state: Optional[Game] = None
            self._ruleset = ruleset
            self._stones_captured_last_turn = 0
            self._turn_counter = 0

            self._board = Board()
            if handicap_stones:
                self._current_player = Color.WHITE

                # TODO: THIS GETS CALLED TWO DIFFERENT WAYS?!
                self._handicap_stones = set()
                for coordinate in self._handicap_stones:
                    if isinstance(coordinate, str):
                        coordinate = Coordinate[coordinate]

                    self._board.set(coordinate, Color.BLACK)
                    self._handicap_stones.add(coordinate)

                self._process_board()
            else:
                self._current_player = Color.BLACK
                self._handicap_stones = set()

            self._initial = self._board
            if ruleset.ko_rule != KoRule.SIMPLE:
                self._ko_lookup = {self._board.zobrist_hash: {self}}
            else:
                self._ko_lookup = dict()
        else:
            self._handicap_stones = _previous_state._handicap_stones
            self._initial = _previous_state._initial
            self._komi = _previous_state._komi
            self._ruleset = _previous_state._ruleset
            self._turn_counter = _previous_state._turn_counter + 1

            self._board = _board
            self._captures_by_black = _previous_state._captures_by_black
            self._captures_by_white = _previous_state._captures_by_white
            if _additional_captures:
                if Color.BLACK == _previous_state._current_player:
                    self._captures_by_black += _additional_captures
                else:
                    self._captures_by_white += _additional_captures

            self._current_player = _previous_state._current_player.opposite
            self._moves_played = _previous_state.moves_played + 1
            self._previous_move = _previous_move
            self._previous_state = _previous_state
            self._stones_captured_last_turn = _additional_captures

            # Handle processing kos for stat tracking.
            self._ko_capture = _additional_captures == 1 and len(_kos) > 0
            self._kos = _kos or set()
            self._kos_previous = _previous_state._kos

            if KoRule.SIMPLE == _previous_state._ruleset.ko_rule:
                self._ko_lookup = dict()
                if Pass.PASS != _previous_move:
                    self._ko_lookup[self._board.zobrist_hash] = {self}
            else:
                self._ko_lookup = dict()
                for k, v in _previous_state._ko_lookup.items():
                    self._ko_lookup[k] = {*v}
                zobrist = self._board.zobrist_hash
                if zobrist in self._ko_lookup:
                    self._ko_lookup[zobrist].add(self)
                else:
                    self._ko_lookup[zobrist] = {self}

            # There are two ways to determine whether the previous board move ended (or prevented) a ko:
            # 1. A move that was in the kos set two turns ago is not in the legal moves list this turn.
            # 2. Suppose the previous move was actually a pass.  If there is a move the current player could have made
            #    on that board that would have started a ko that is not a legal move on this actual board, then the
            #    previous move ended or prevented a ko.
            if _previous_move != Pass.PASS:
                self._ko_ended = (
                    (not not _previous_state._kos_previous) and not (_previous_state._kos_previous & self.legal_moves)
                )
                if not self._ko_ended:
                    pass_board = Board(_previous_state._board)
                    hypothetical_board, hypothetical_kos = _previous_state._prepare_board_for_next_player(pass_board)

                    # Are there board moves that are illegal for the current player now that would have been legal on
                    # the pass board?
                    for c in Coordinate:
                        if self._board.get(c) != Color.EMPTY and hypothetical_board.get(c) == Color.EMPTY:
                            after_candidate_board = Board(hypothetical_board)
                            after_candidate_board.set(c, self._current_player)
                            candidate_captures, captured_stones = Game._remove_captures(
                                after_candidate_board,
                                c,
                                self._current_player
                            )
                            if candidate_captures == 1:
                                for e in captured_stones:
                                    break
                                after_candidate_board.set(e, self._current_player.opposite)
                                Game._remove_captures(after_candidate_board, e, self._current_player.opposite)
                                if pass_board.zobrist_hash == after_candidate_board.zobrist_hash:
                                    self._ko_ended = True
                                    break
            else:
                self._ko_ended = False

            print(f'{self._turn_counter} {self._ko_capture} {self._ko_ended}')

        self._board.lock()

    def _process_board(self):
        borders_black: List[bool] = [False for _ in range(361)]
        colors: List[Optional[Color]] = [None for _ in range(361)]
        liberties: List[int] = [0 for _ in range(361)]

        for coordinate in Coordinate:
            color = self._board.get(coordinate)
            colors[coordinate.index] = color
            if color.counts_as_liberty:
                for neighbor in coordinate.neighbors():
                    liberties[neighbor.index] += 1
            elif color == Color.BLACK:
                for neighbor in coordinate.neighbors():
                    borders_black[neighbor.index] = True

        for coordinate in Coordinate:
            i = coordinate.index
            if colors[i].counts_as_liberty and not liberties[i] and borders_black[i]:
                self._board.set(coordinate, Color.TEMPORARILY_UNPLAYABLE)

    @property
    def legal_moves(self) -> Set[Coordinate | Pass]:
        legal = {c for c in Coordinate if self._board.get(c) == Color.EMPTY}
        legal.add(Pass.PASS)
        return legal

    def play(self, move: Coordinate | Pass) -> Game:
        self._validate_move(move)
        return self._pass() if Pass.PASS == move else self._perform_move(move)

    def _validate_move(self, move: Coordinate | Pass):
        if type(move) == Coordinate:
            color = self._board.get(move)
            if Color.EMPTY != color:
                raise Exception(f'Received an illegal move coordinate: {move}')

    def _pass(self) -> Game:
        next_board, kos = self._prepare_board_for_next_player(self._board)
        return Game(
            _previous_state=self,
            _previous_move=Pass.PASS,
            _additional_captures=0,
            _board=next_board,
            _kos=kos
        )

    def _prepare_board_for_next_player(
        self,
        board: Board,
        scanning=False
    ) -> Tuple[Board, Set[Coordinate]]:
        next_board = Board(board)
        next_player = self._current_player.opposite

        kos: Set[Coordinate] = set()
        for coordinate in Coordinate:
            color = next_board.get(coordinate)
            if color.counts_as_liberty:
                playable = True

                scratch_pad = Board(board)
                scratch_pad.set(coordinate, next_player)
                captures, captured = Game._remove_captures(scratch_pad, coordinate, next_player)
                if not captures:
                    group = Group(scratch_pad, coordinate)
                    if not group.liberties:
                        playable = False

                if playable and self._violates_ko_rule(self._current_player, scratch_pad, scanning):
                    playable = False
                    kos.add(coordinate)

                next_color = Color.EMPTY if playable else Color.TEMPORARILY_UNPLAYABLE
                next_board.set(coordinate, next_color)

        return next_board, kos

    @staticmethod
    def _remove_captures(board: Board, around: Coordinate, played_by: Color) -> Tuple[int, Set[Coordinate]]:
        captures = 0
        captured = set()

        opposite = played_by.opposite
        column = around.column
        row = around.row

        if row - 1 >= 0:
            additional, group = Game._handle_capture(column, row - 1, board, opposite)
            if additional > 0:
                captures += additional
                captured |= group.members
        if column + 1 <= 18:
            additional, group = Game._handle_capture(column + 1, row, board, opposite)
            if additional > 0:
                captures += additional
                captured |= group.members
        if row + 1 <= 18:
            additional, group = Game._handle_capture(column, row + 1, board, opposite)
            if additional > 0:
                captures += additional
                captured |= group.members
        if column - 1 >= 0:
            additional, group = Game._handle_capture(column - 1, row, board, opposite)
            if additional > 0:
                captures += additional
                captured |= group.members

        return captures, captured

    @staticmethod
    def _handle_capture(column: int, row: int, board: Board, opposite: Color) -> Tuple[int, Optional[Group]]:
        captures = 0

        neighbor = Coordinate.get(column, row)
        color = board.get(neighbor)
        if color == opposite:
            group = Group(board, neighbor)
            if group.liberties == 0:
                captures = len(group)
                for captured in group.members:
                    board.set(captured, Color.EMPTY)
        else:
            group = None

        return captures, group

    def _violates_ko_rule(self, next_player: Color, board: Board, scanning: bool) -> bool:
        same = False

        zobrist_hash = board.zobrist_hash
        if zobrist_hash in self._ko_lookup:
            collisions = [g for g in self._ko_lookup[zobrist_hash] if g._board.is_same_position_as(board)]
            if collisions:
                # Developer's Note: (J. Craig, 2022-04-29)
                # This comment is copied from the Java implementation I wrote:
                # The Situational Super Ko rule states that a player is not allowed to play a board move that recreates
                # a position they created before.  I use the Natural Situational Super Ko variation that exempts
                # positions that were created by passes since that is almost certainly what every rule designer
                # intends.
                if not scanning and KoRule.SITUATIONAL == self._ruleset.ko_rule:
                    same = any(
                        filter(
                            lambda g: next_player == g._current_player and g._previous_move != Pass.PASS,
                            collisions
                        )
                    )
                else:
                    same = True

        return same

    def _perform_move(self, move: Coordinate) -> Game:
        next_board = Board(self._board)
        next_board.set(move, self._current_player)
        additional_captures, _ = Game._remove_captures(next_board, move, self._current_player)
        next_board, kos = self._prepare_board_for_next_player(next_board)
        return Game(
            _previous_state=self,
            _previous_move=move,
            _additional_captures=additional_captures,
            _board=next_board,
            _kos=kos
        )

    @property
    def canonical_code(self) -> str:
        code = f'{self._ruleset.command}_{self._komi}_{"B" if Color.BLACK == self._current_player else "W"}_'

        if Scoring.TERRITORY == self._ruleset.scoring:
            code += f'{self._captures_by_black - self._captures_by_white}_'

        current_board_code = None
        if not self._moves_played:
            current_board_code = self._board.canonical_code
            code += current_board_code
        else:
            orientation = self._board.canonical_orientation
            code += self._initial.get_code_for(orientation)

        code += f'_{current_board_code or self._board.canonical_code}'

        return code

    @property
    def canonical_orientation(self) -> Orientation:
        return self._board.canonical_orientation

    def __str__(self) -> str:
        if not self._representation:
            self._representation = f'{self._ruleset.name} Game, {self._moves_played} Moves, ' \
                                   f'{self._current_player.name} to Play\n'
            self._representation += f'Komi {self._komi}, Handicap {len(self._handicap_stones)}'
            if self._handicap_stones:
                self._representation += f' {[x.name for x in self._handicap_stones]}'
            self._representation += f'\nBlack Captures {self._captures_by_black}, '
            self._representation += f'White Captures {self._captures_by_white}\n'
            if self._previous_move:
                self._representation += f'Previous Move @ {self._previous_move.name}\n'
            self._representation += f'Zobrist Hash: {hex(self._board.zobrist_hash)}\n'
            self._representation += f'Canonical Code: {self._board.canonical_code}\n'
            self._representation += f'Canonical Orientation: {self._board.canonical_orientation}\n{self._board}'

        return self._representation

    @property
    def board(self) -> Board:
        return Board(self._board)

    @property
    def initial(self) -> Board:
        return Board(self._initial)

    @property
    def komi(self) -> float:
        return float(self._komi)

    @property
    def previous_state(self) -> Game:
        return self._previous_state

    @property
    def captures_by_black(self) -> int:
        return self._captures_by_black

    @property
    def captures_by_white(self) -> int:
        return self._captures_by_white

    @property
    def moves_played(self) -> int:
        return self._moves_played

    @property
    def previous_move(self) -> Optional[Coordinate | Pass]:
        return self._previous_move

    @property
    def current_player(self) -> Color:
        return self._current_player

    @property
    def ruleset(self) -> Ruleset:
        return self._ruleset

    @property
    def handicap_stones(self) -> Set[Coordinate]:
        return {*self._handicap_stones}

    @property
    def stones_captured_last_turn(self) -> int:
        return self._stones_captured_last_turn

    @property
    def kos(self) -> Set[Coordinate]:
        return {*self._kos}

    @property
    def previous_turn_captured_ko(self) -> bool:
        return self._ko_capture

    @ property
    def previous_turn_ended_ko(self) -> bool:
        return self._ko_ended
