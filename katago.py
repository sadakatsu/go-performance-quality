# © 2021 Joseph Craig <the.sadakatsu@gmail.com>
# This code is not released under a standard OSS license.  Please read README.md.

import io
import json
import os
import subprocess

from enum import auto, Enum
from threading import Thread


class LineType(Enum):
    error = auto()
    output = auto()


class KataGo:
    def __init__(
        self,
        executable,
        configuration,
        model,
        analysis_threads=10,
        search_threads=1,
        max_playouts=16385,
        max_visits=1048576,
        output=False
    ):
        self.output = output
        if output:
            print('  Launching KataGo...')

        def read_stream(name, stream, type_, buffer):
            if output:
                print(f'  {name} thread has begun.')
            while True:
                line = stream.readline().rstrip()
                if (
                    not self._ready and
                    type_ is LineType.error and
                    line.endswith('Started, ready to begin handling requests')
                ):
                    self._ready = True
                    if output:
                        print('  KataGo is ready to accept inputs.')
                if output:
                    print(f'  {name} read: {line}')
                if line:
                    buffer.append((type_, line))
                else:
                    if output:
                        print(f'  {name} thread has finished.')
                    break

        command = f'{executable} analysis -config {configuration} -model {model} ' \
                  f'-override-config numSearchThreads={search_threads} ' \
                  f'-override-config numAnalysisThreads={analysis_threads} ' \
                  f'-override-config maxPlayouts={max_playouts} ' \
                  f'-override-config maxVisits={max_visits} '
        print(f'  KATAGO COMMAND: {command}')
        self._process = subprocess.Popen(
            command,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

        self._buffer = []
        self._ready = False

        stderr = io.TextIOWrapper(self._process.stderr, encoding='utf-8', errors='strict')
        self._errors = Thread(target=read_stream, args=('ERR', stderr, LineType.error, self._buffer))
        self._errors.daemon = True
        self._errors.start()

        stdout = io.TextIOWrapper(self._process.stdout, encoding='utf-8', errors='strict')
        self._outputs = Thread(target=read_stream, args=('OUT', stdout, LineType.output, self._buffer))
        self._outputs.daemon = True
        self._outputs.start()

        if output:
            print('  KataGo has launched.')

    @property
    def ready(self):
        return self._ready

    def write_message(self, message):
        if self.output:
            print(f'  KataGo::write_message() called...')
        if not self._ready:
            raise Exception('KataGo is not ready!  Learn some damn patience.')
        command = json.dumps(message, separators=(',', ':')) + os.linesep
        encoded = command.encode('utf-8')
        self._process.stdin.write(encoded)
        self._process.stdin.flush()
        if self.output:
            print(f'  Passed message to KataGo: {encoded}')

    def next_line(self):
        return self._buffer.pop(0) if self._buffer else None

    def kill(self):
        if self.output:
            print('  KataGo::kill() called...')
        self._process.kill()
        if self.output:
            print('  KataGo::kill() call complete.')
