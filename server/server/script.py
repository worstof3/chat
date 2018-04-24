"""
Main script for chat server.

Functions:
sigint_handler -- Handle keyboard interrupt.
coro_wrapper -- Wrapper around coroutine handling connection.
clean_up -- Release resources.
main -- Main script.
"""
import asyncio
import signal
from . import server
from . import message
from argparse import ArgumentParser, SUPPRESS


def sigint_handler(serverobj):
    """
    Handle keyboard interrupt.

    Function just sets ending to end the connection.
    """
    serverobj.stop_server()


def main():
    parser = ArgumentParser(description='Chat server.')
    parser.add_argument('address', default=SUPPRESS, help='Server address.')
    parser.add_argument('port', default=SUPPRESS, help="Server port.")
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    handlers = message.get_handlers(server)
    serverobj = server.Server(loop, handlers, args.address, args.port)
    loop.add_signal_handler(signal.SIGINT, sigint_handler, serverobj)

    serverobj.start_server()
    loop.run_until_complete(serverobj.server.wait_closed())
    loop.close()


if __name__ == '__main__':
    main()
