"""
Main script for chat server.

Functions:
sigint_handler -- Handle keyboard interrupt.
got_stdin -- Handler called when there is new user input.
"""
import asyncio
import signal
import sys
from argparse import ArgumentParser, SUPPRESS
from . import client
from . import message


def sigint_handler(cl):
    """Handle keyboard interrupt."""
    cl.stop_connection()


def got_stdin(cl):
    """Handler called when there is new user input."""
    cl.read_input()


def main():
    parser = ArgumentParser(description='Chat client.')
    parser.add_argument('address', default=SUPPRESS, help='Server address.')
    parser.add_argument('port', default=SUPPRESS, help="Server port.")
    parser.add_argument('nick', default=SUPPRESS, help="User nickname.")
    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    recv_handlers = message.get_handlers(client, 'recv_')
    send_handlers = message.get_handlers(client, 'send_')
    cl = client.Client(loop, recv_handlers, send_handlers, args.address, args.port, args.nick)
    loop.add_signal_handler(signal.SIGINT, sigint_handler, cl)
    loop.add_reader(sys.stdin, got_stdin, cl)

    cl.start_connection()
    loop.run_until_complete(cl.con_handling)

    loop.close()


if __name__ == '__main__':
    main()
