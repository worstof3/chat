"""
Module defines classes and functions to handle client connection.

Classes:
DisconnectedError -- Exception raised when connection is closed.
Client -- Class storing information about client.

Functions:
recv_hello -- Called when chosen nickname is taken.
recv_text -- Called when client received text message.
send_hello -- Send message to check if nickname is available.
send_text -- Send text message.
send_active -- Ask server which users are active.
"""
import asyncio
import sys
from .message import cut_message, create_message


class DisconnectedError(Exception):
    """Exception raised when connection is closed."""
    pass


class Client:
    """
    Class storing information about client.

    Instance attributes:
    loop -- Event loop bound with connection.
    recv_handlers -- Handlers called when message is received.
    send_handlers -- Handlers called when message is sent.
    infile -- Input file.
    outfile -- Output file.
    address -- Server IP address.
    port -- Server port.
    nick -- User's nickname.
    reader -- StreamReader returned after connection is opened.
    writer -- StreamWriter returned after connection is opened.
    con_handling -- Task handling connection.

    Magic methods:
    __init__ -- Initialize instance.

    Methods:
    start_connection -- Open connection with server.
    handle_connection -- Coroutine handling connection.
    stop_connection -- Close connection with server.
    send -- Send message to server.
    read_input -- Read input from infile and send it.

    Static methods:
    check_type -- Check type of message read from user.
    """
    def __init__(self, loop, recv_handlers, send_handlers, address, port, nick, infile=sys.stdin, outfile=sys.stdout):
        """Initialize instance."""
        self.loop = loop
        self.recv_handlers = recv_handlers
        self.send_handlers = send_handlers
        self.infile = infile
        self.outfile = outfile
        self.address = address
        self.port = port
        self.nick = nick
        self.reader = None
        self.writer = None
        self.con_handling = None

    def start_connection(self):
        """
        Open connection with server.

        Method opens connection with server and then initializes reader, writer and con_handling of instance.
        """
        connection_creation = asyncio.open_connection(self.address, self.port)
        self.reader, self.writer = self.loop.run_until_complete(connection_creation)
        self.con_handling = self.loop.create_task(self.handle_connection())

    async def handle_connection(self):
        """
        Coroutine handling connection.

        First check if user's nickname is available. Then if connection isn't closed data is read line by line until
        line indicating end of message is read. Then message is interpreted and handled.
        """
        try:
            self.send_handlers[b'hello'](client=self)
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

    def stop_connection(self):
        """Close connection with server."""
        self.con_handling.cancel()

    def send(self, message):
        """
        Send message to server.

        First message type is checked with check_type, then correct send handler is called.
        Args:
        message -- Message in form read from user.

        Todo:
        Test if correct handlers are called.
        """
        msg_type, msg_args = self.__class__.check_type(message)
        self.send_handlers[msg_type](client=self, msg_args=msg_args)

    def read_input(self):
        """Read input from infile and send it."""
        input_msg = self.infile.readline().encode()
        self.send(input_msg)

    @staticmethod
    def check_type(message):
        """
        Check type of message read from user.

        Commands are in form of /command: arguments. If /command is omitted message is intepreted as text message.
        Colon is only necessary when command takes arguments. Arguments are separated with whitespaces.
        """
        if message.startswith(b'/'):
            pos = message.find(b':')
            if pos > 0:
                command, args = message[1:pos], message[pos + 1:]
            else:
                command, args = message[1:], b''
            return command.strip(), args
        else:
            return b'text', message


def recv_hello(client, **kwargs):
    """
    Called when chosen nickname is taken.

    If nickname is not available connection is closed.
    """
    client.con_handling.cancel()


def recv_text(message, client, **kwargs):
    """
    Handler called when client receives text message.

    Message is just displayed.
    """
    text = message[b'text']
    print(text.decode(), end='', file=client.outfile)


def send_hello(client, **kwargs):
    """Send nickname to check if it is taken."""
    message = create_message(type=b'hello', nick=client.nick.encode())
    client.writer.write(message)


def send_text(client, msg_args, **kwargs):
    """Send text message to other client(s)."""
    text = client.nick.encode() + b': ' + msg_args
    message = create_message(type=b'text', text=text)
    client.writer.write(message)


def send_active(client, **kwargs):
    """Ask server about active users."""
    message = create_message(type=b'active')
    client.writer.write(message)
