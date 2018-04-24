"""
Module defines classes and functions to handle client connections.

Classes:
DisconnectedError -- Exception raised when connection is closed.
Client -- Class storing information about client.
Server -- Class storing information about server.

Functions:
recv_hello -- Handler called when client checks if nickname is available.
recv_text -- Handler called when client sends text message.
recv_active -- Handler called when client wants to know active users.
"""
import asyncio
import functools
from .message import cut_message, create_message


class DisconnectedError(Exception):
    """Exception raised when connection is closed."""
    pass


class Client:
    """
    Class storing information about client.

    Properties:
    nicks_clients -- Mapping nicks of all active users to client instances.

    Instance attributes:
    reader -- Reader from client.
    writer -- Writer to client.
    recv_handlers -- Handlers called when message is received.
    nick -- Nickname of client.
    receivers -- Receivers of messages, if it is empty messages go to everyone.
    con_handling -- Task handling connection.

    Magic methods:
    __init__ -- Initialize instance.

    Methods:
    handle_connection -- Read message from client and handle it.
    """
    _nicks_clients = {}

    def __init__(self, reader, writer, recv_handlers, nick=None):
        """Initialize instance."""
        self.reader = reader
        self.writer = writer
        self.recv_handlers = recv_handlers
        self.nick = nick
        self.receivers = set()
        self.con_handling = None

    @property
    def nicks_clients(self):
        return self.__class__._nicks_clients

    async def handle_connection(self):
        """
        Read message from client and handle it.

        Data is read line by line until line indicating end of message is read. Then message is interpreted and handled.
        """
        try:
            while True:
                msg_lines = []
                while True:
                    msg_line = await self.reader.readline()
                    if not msg_line:
                        raise DisconnectedError
                    msg_lines.append(msg_line)
                    if msg_line == b'#\n':
                        break
                message = cut_message(msg_lines)
                self.recv_handlers[message[b'type']](message=message, client=self)
        except (asyncio.CancelledError, DisconnectedError):
            pass

        self.writer.close()


class Server:
    """
    Class storing information about server.

    Instance attributes:
    loop -- Event loop bound to server.
    recv_handlers -- Handlers called when message is received.
    address -- Address on which server is listening.
    port -- Port on which server is listening.
    server -- Server object returned after server is created.
    clients -- All clients connected.
    listening -- Future marking if server is listening.

    Methods:
    remove_client -- Remove client from clients when connection is closed.
    con_handler -- Wrapper around client_handler.
    start_server -- Start listening.
    stop_server -- Stop listening.
    """
    def __init__(self, loop, recv_handlers, address, port):
        self.loop = loop
        self.recv_handlers = recv_handlers
        self.address = address
        self.port = port
        self.server = None
        self.clients = set()
        self.listening = asyncio.Future()

    def remove_client(self, future, client):
        """
        Remove client from clients when connection is closed.

        Args:
        future -- It's here just so method can be used as callback.
        client -- Client to be removed.
        """
        self.clients.remove(client)
        del client.nicks_clients[client.nick]

    async def con_handler(self, reader, writer):
        """
        Connection handler.

        It just adds created client to clients and sets remove_client to be called after connection is closed.

        Args:
        reader -- Reader from client.
        writer -- Writer to client.
        """
        client = Client(reader, writer, self.recv_handlers)
        self.clients.add(client)
        coro = client.handle_connection()
        handler = self.loop.create_task(coro)
        client.con_handling = handler
        handler.add_done_callback(functools.partial(self.remove_client, client=client))
        return handler

    def start_server(self):
        """Start listening."""
        server_creation = asyncio.start_server(self.con_handler, self.address, self.port)
        self.server = self.loop.run_until_complete(server_creation)
        self.loop.run_until_complete(self.listening)

    def stop_server(self):
        """Stop listening."""
        self.listening.set_result(True)
        for client in self.clients:
            client.con_handling.cancel()
        self.server.close()
        self.loop.run_until_complete(self.server.wait_closed())


def recv_hello(message, client, **kwargs):
    """
    Handler called when client checks if nickname is available.

    If nickname is not available connection is closed otherwise nickname is remembered.
    """
    nick = message[b'nick']
    if nick in client.nicks_clients:
        answer = create_message(type=b'hello', nick=nick)
        client.writer.write(answer)
        client.con_handling.cancel()
    else:
        client.nicks_clients[nick] = client
        client.nick = nick


def recv_text(message, client, **kwargs):
    """
    Handler called when client sends text message.

    Message is just propagated to all receivers of the client.
    """
    if not client.receivers:
        receivers = set(client.nicks_clients.values()) - {client}
    else:
        receivers = client.receivers
    for receiver in receivers:
        answer = create_message(type=message[b'type'], text=message[b'text'])
        receiver.writer.write(answer)


def recv_active(client, **kwargs):
    """
    Handler called when client wants to know active users.

    Function sends to the client newline separated list of active users (nicknames).
    """
    nicks = set(client.nicks_clients.keys())
    if client.nick in nicks:
        nicks.add(client.nick + b' (you)')
        nicks.remove(client.nick)
    active = b'\n'.join(sorted(nicks)) + b'\n'
    answer = create_message(type=b'text', text=active)
    client.writer.write(answer)
