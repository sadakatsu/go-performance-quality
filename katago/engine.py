import io
import os
import subprocess
import uuid
from threading import Thread
from typing import Optional, Dict, List, Set

from katago import LaunchConfiguration
from katago.linetype import LineType
from katago.query import Query
from katago.response import *
from katago.shared import str_to_enum


class Engine:
    def __init__(self, launch_config: LaunchConfiguration, output: bool = False):
        self._launch_config: LaunchConfiguration = launch_config
        self._output: bool = output
        self._version: Optional[str] = None

        self._responses: Dict[str, List[SuccessResponse]] = {}
        self._ready: bool = False
        self._used: Set[uuid.UUID] = set()

        if self._output:
            print('#  Launching KataGo...')

        def read_stream(
            name: str,
            stream: io.TextIOWrapper,
            type_: LineType
        ):
            if self._output:
                print(f'#  {name} thread has begun.')
            while True:
                line = stream.readline().rstrip()
                # print(f'# !!! {type_} :: {line}')

                if (
                    type_ is LineType.error and
                    self._version is None and
                    line.startswith('KataGo v')
                ):
                    self._version = line[8:]
                elif (
                    not self._ready and
                    type_ is LineType.error and
                    line.endswith('Started, ready to begin handling requests')
                ):
                    self._ready = True
                    if self._output:
                        print('#  KataGo is ready to accept inputs.')
                elif self._ready:
                    if self._output:
                        print(f'#  {name} read: {line}')
                    if line:
                        if type_ is LineType.output:
                            try:
                                response = SuccessResponse.from_json(line)

                                # THERE ARE SOME FIELDS THAT ARE NOT UNMARSHALLED CORRECTLY.  I need to figure this out
                                # later.  For now, manually fix them  }:|
                                for mi in response.move_infos:
                                    mi.move = str_to_enum(mi.move)
                                    mi.pv = [str_to_enum(x) for x in mi.pv]

                                if response.id in self._responses:
                                    self._responses[response.id].append(response)
                                else:
                                    self._responses[response.id] = [response]
                            except Exception:
                                # We already have the message if output is configured on.
                                if not self._output:
                                    print(f'#  KataGo wrote a message that is not a success response: {line}')
                    else:
                        if self._output:
                            print(f'#  {name} thread has finished.')
                        break

        launch_script = launch_config.launch_script
        print(f'# KataGo launch script: {launch_script}')
        self._process = subprocess.Popen(
            launch_script,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        stderr = io.TextIOWrapper(self._process.stderr, encoding='utf-8', errors='strict')
        self._errors: Thread = Thread(target=read_stream, args=('ERR', stderr, LineType.error))
        self._errors.daemon = True
        self._errors.start()

        stdout = io.TextIOWrapper(self._process.stdout, encoding='utf-8', errors='strict')
        self._outputs: Thread = Thread(target=read_stream, args=('OUT', stdout, LineType.output))
        self._outputs.daemon = True
        self._outputs.start()

        if self._output:
            print(f'#  KataGo has launched.')

    @property
    def version(self) -> str:
        if not self._version:
            raise Exception('KataGo has not produced its version number line yet.')
        return self._version

    @property
    def ready(self):
        return self._ready

    def write_query(self, query: Query) -> str:
        if self._output:
            print(f'#  KataGo::write_query() called...')
        if not self._ready:
            raise RuntimeError('KataGo is not ready.')

        candidate_id = uuid.uuid4()
        while candidate_id in self._used:
            candidate_id = uuid.uuid4()
        self._used.add(candidate_id)
        query.id = str(candidate_id)

        command: str = query.to_json() + os.linesep
        encoded: bytes = command.encode('utf-8')
        self._process.stdin.write(encoded)
        self._process.stdin.flush()
        if self._output:
            print(f'# Passed query to KataGo: {encoded}')
        return query.id

    def next_response(self, query_id: str) -> Optional[SuccessResponse]:
        response: Optional[SuccessResponse] = None

        if query_id in self._responses:
            found = self._responses[query_id]
            if len(found) > 0:
                response = found.pop(0)

        return response

    def kill(self):
        if self._output:
            print('#  KataGo::kill() called...')
        self._process.kill()
        if self._output:
            print('#  KataGo::kill() call complete.')
