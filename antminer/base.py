import socket
import json
import sys

from antminer.exceptions import (
    WarningResponse, ErrorResponse, FatalResponse, UnknownError
)
from antminer.constants import (
    STATUS_INFO, STATUS_SUCCESS, DEFAULT_PORT, MINER_CGMINER,
    MINER_BMMINER
)
from antminer.utils import parse_version_number


class Core(object):
    def __init__(self, host, port=DEFAULT_PORT):
        self.host = host
        self.port = int(port)

    def connect(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.conn.connect((self.host, self.port))

    def send_command(self, command):
        cmd = command.split('|')
        if len(cmd) > 2 or len(cmd) == 0:
            raise ValueError("Commands must be one or two parts")

        payload = {
            'command': cmd[0]
        }

        if len(cmd) == 2:
            payload['parameter'] = cmd[1]

        self.conn.send(json.dumps(payload))
        result = self.read_response()
        try:
            return json.loads(result)
        except ValueError:
            raise UnknownError(result)

    def read_response(self):
	done = False
	buf = self.conn.recv(4096)
	while done is False:
            more = self.conn.recv(4096)
            if not more:
                done = True
            else:
                buf += more

        return buf.replace('\x00','')


class Base(Core):
    STATUS_CODE_TO_EXCEPTION = {
        'W': WarningResponse,
        'E': ErrorResponse,
        'F': FatalResponse
    }

    def version(self):
        """
        Get basic hardware and software version information for a miner.

        This returns a number of important version numbers for the miner. Each of the
        version numbers is an instance of Version from the SemVer Python package.
        """
        fields = [
            ('Type', 'type', str),
            ('API', 'api', parse_version_number),
            ('Miner', 'version', parse_version_number),
        ]

        resp = self.command('version')

        version = {}
        for from_name, to_name, formatter in fields:
            try:
                version[to_name] = formatter(str(resp['VERSION'][0][from_name]))
            except KeyError:
                pass

        version['miner'] = {}
        if MINER_CGMINER in resp['VERSION'][0]:
            version['miner']['vendor'] = MINER_CGMINER
            version['miner']['version'] = parse_version_number(resp['VERSION'][0][MINER_CGMINER])
        elif MINER_BMMINER in resp['VERSION'][0]:
            version['miner']['vendor'] = MINER_BMMINER
            version['miner']['version'] = parse_version_number(resp['VERSION'][0][MINER_BMMINER])
        else:
            version['miner']['vendor'] = MINER_UNKNWON
            version['miner']['version'] = None

        return version

    def command(self, *args):
        """
        Send a raw command to the API.

        This is a lower level method that assumes the command is the first
        argument and that the rest of the arguments are parameters that should
        be comma separated. 

        The basic format of API commands is 'command|param1,param2,etc'. The meaning
        of parameters depends greatly on the command provided. This method will return
        odd results if poorly constructed commands are passed.
        """
        return self._send('{command}|{parameters}'.format(command=args[0],
            parameters=','.join(args[1:])))

    def _raise(self, response, message=None):
        try:
            raise self.STATUS_CODE_TO_EXCEPTION[response['STATUS'][0]['STATUS']](response, message)
        except KeyError, IndexError:
            raise UnknownError(response)

    def _send(self, command):
        response = self.send_command(command)
        try:
            success = (response['STATUS'][0]['STATUS'] in [STATUS_INFO, STATUS_SUCCESS])
        except KeyError, IndexError:
            raise UnknownError(response)

        if not success:
            self._raise(response)

        return response

BaseClient = Base