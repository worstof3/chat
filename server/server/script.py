import asyncio
import signal
from . import server
from . import message
import functools
import sys


def sigint_handler(ending):
    ending.set_result(True)


def handler_wrapper(reader, writer, handler, msg_handlers, msg_types, client_handlers):
    server_args = dict(handlers=msg_handlers, msg_types=msg_types)
    handling = handler(reader, writer, server_args)
    client_handlers.add(handling)
    return handling


def clean_up(loop, server_obj, client_handlers):
    for client_handler in client_handlers:
        client_handler.close()
    server_obj.close()
    loop.run_until_complete(server_obj.wait_closed())
    loop.close()


def main():
    loop = asyncio.get_event_loop()
    ending = asyncio.Future()
    msg_types = message.get_msg_types(server)
    client_handlers = set()
    msg_handlers = message.get_handlers(msg_types, server)

    loop.add_signal_handler(signal.SIGINT, sigint_handler, ending)
    handling = functools.partial(handler_wrapper,
                                 handler=server.handle_client,
                                 msg_handlers=msg_handlers,
                                 msg_types=msg_types,
                                 client_handlers=client_handlers,
                                 ending=ending)
    server_creation = asyncio.start_server(handling, sys.argv[1], sys.argv[2])
    server_obj = loop.run_until_complete(server_creation)
    loop.run_until_complete(ending)

    clean_up(loop, server_obj, client_handlers)


if __name__ == '__main__':
    main()
