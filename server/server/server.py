"""
Module defines coroutine to handle client connection and also functions and classes to help with it.

Classes:
Buffer -- Class for buffering data.
Client -- Class storing information about client.

Functions:
read_full_message -- Check if there is full message in buffer and read it if there is.
handle_client -- Coroutine to handle connection.
recv_hello -- Handler called when client checks if nickname is available.
recv_text -- Handler called when client sends text message.
recv_active -- Handler called when client wants to know active users.
"""
from .message import read_message, create_message, read_type
from collections import deque


read_size = 1024 * 1024


class Buffer:
    """
    Class for buffering data.

    Instance attributes:
    buffer -- Deque of byte chunks.
    length -- Number of bytes in buffer.

    Methods:
    write -- Write data to buffer, increase length.
    getvalue -- Return content of buffer without changing anything.
    read -- Read data, remove from buffer and decrease length.
    peek -- Check first bytes of buffer without removing anything.
    __gather_chunks -- Return chunks with total length greater or equal than num or all chunks if
                         there is not enough and also length of these chunks.
    __cut_last -- Cut tail of a chunk.

    Magic methods:
    __init__ -- Initialize instance attributes.
    __len__ -- Return number of bytes in buffer.
    __repr__ -- Return '<Buffer buffer_content>'
    """
    def __init__(self, init_data=b''):
        """Initialize instance attributes."""
        self.buffer = deque((init_data, ))
        self.length = len(init_data)

    def __len__(self):
        """Return number of bytes in buffer."""
        return self.length

    def write(self, data):
        """
        Write data to buffer, increase length.

        Args:
        data -- Data to be written.
        """
        if data:
            self.buffer.append(data)
            self.length += len(data)

    def getvalue(self):
        """Return content of buffer without changing anything."""
        return b''.join(self.buffer)

    def __repr__(self):
        """Return '<Buffer buffer_content>'."""
        return '<Buffer ' + repr(self.getvalue()) + '>'

    def read(self, num):
        """
        Read data, remove from buffer and decrease length.

        If there is not enough data in buffer return all that is left.

        Args:
        num -- Number of bytes to read.

        Returns:
        First num bytes of buffer.
        """
        # Take enough chunks from queue.
        chunks, chunks_len = self.__gather_chunks(num)

        # Cut last chunk and return result.
        if chunks_len > num:
            last = chunks[-1]
            last_cut, rest = self.__class__.__cut(last, chunks_len - num)
            chunks[-1] = last_cut
            self.buffer.appendleft(rest)
        read_data = b''.join(chunks)
        self.length -= len(read_data)
        return read_data

    def peek(self, num):
        """
        Check first bytes of buffer without removing anything.

        Args:
        num -- Number of bytes to see.

        Returns:
        First num bytes of buffer.
        """
        chunks, chunks_len = self.__gather_chunks(num)
        read_data = b''.join(chunks)
        self.buffer.appendleft(read_data)
        return read_data[:num]

    def __gather_chunks(self, num):
        """
        Return chunks with total length greater or equal than num or all chunks if there is not enough and also
        length of these chunks.

        Chunks are popped from buffer.

        Args:
        num -- Length of chunks to be gathered.

        Returns:
        chunks -- Joined chunks.
        chunks_len -- Length of returned chunks.
        """
        chunks = []
        chunks_len = 0
        while chunks_len < num and self.buffer:
            chunk = self.buffer.popleft()
            if chunk:
                chunks.append(chunk)
                chunks_len += len(chunk)
        return chunks, chunks_len

    @staticmethod
    def __cut(chunk, length):
        """
        Cut tail of a chunk.

        Args:
        chunk -- Chunk to be cut.
        length -- Length of piece to be cut.

        Returns:
        Tuple (first part of chunk, last part of chunk).
        """
        if not length:
            return chunk, b''
        else:
            return chunk[:-length], chunk[-length:]


def read_full_message(buffer):
    """
    Check if there is full message in the buffer and if there is, read it.

    Function just peeks at first three bytes in buffer and treats them as message length. Then it checks if there is
    enough bytes in the buffer. Buffer may be modified in this function.

    Args:
    buffer -- Buffer to check.

    Returns:
    Message if it is found, empty bytes object otherwise.
    """
    len_bytes = buffer.peek(3)
    if len(len_bytes) < 3:
        return b''
    msg_len = int.from_bytes(len_bytes, 'big')
    if msg_len <= len(buffer) - 3:
        buffer.read(3)  # Reading length out of buffer.
        return buffer.read(msg_len)
    else:
        return b''


class Client:
    """
    Class storing information about client.

    Properties:
    nicks_clients -- Mapping nicks of all active users to client instances.

    Instance attributes:
    writer -- StreamWriter object.
    nick -- Nickname of user.
    ending -- asyncio.Future indicating if connection should close.
    receivers -- Receivers of client messages.
    """
    _nicks_clients = {}

    def __init__(self, writer, ending, nick=None):
        self.writer = writer
        self.nick = nick
        self.ending = ending
        self.receivers = self.nicks_clients.values()

    @property
    def nicks_clients(self):
        return self.__class__._nicks_clients


async def handle_client(reader, writer, handlers, msg_types, ending):
    """
    Read message from client and handle it.

    Incoming data has to be buffered because some message may be split over two data chunks. Type of message is coded
    in its last byte.

    Args:
    reader -- Reader connected to client.
    writer -- Writer connected to client.
    handlers -- Mapping byte types to handlers.
    msg_types -- Mapping message type names to byte types.
    ending -- Future indicating if coroutine should end.
    """
    client = Client(writer, ending)
    buffer = Buffer()

    while not client.ending.done():
        data = await reader.read(read_size)
        buffer.write(data)
        while True:
            message = read_full_message(buffer)
            if not message:
                break
            msg_type, msg_bytes = read_type(message)
            handlers[msg_type](message=msg_bytes, msg_types=msg_types, client=client)

    writer.close()


def recv_hello(msg_types, message, client, **kwargs):
    """
    Handler called when client checks if nickname is available.

    If nickname is not available connection is closed.
    """
    nick = read_message(message)
    if nick in client.nicks_clients:
        msg = create_message(content=nick.encode(), msg_type=msg_types['hello'])
        client.writer.write(msg)
        client.ending.set_result(True)
    else:
        client.nicks_clients[nick] = client
        client.nickname = nick


def recv_text(msg_types, message, client, **kwargs):
    """
    Handler called when client sends text message.

    Message is just propagated to all receivers of the client.
    """
    for receiver in client.receivers:
        receiver.writer.write(create_message(message, msg_types['text']))


def recv_active(msg_types, client, **kwargs):
    """Handler called when client wants to know active users."""
    nicks = set(client.nicks_clients.keys())
    if client.nick in nicks:
        nicks.add(client.nick + ' (you)')
        nicks.remove(client.nick)
    active = '\n'.join(sorted(nicks)) + '\n'
    client.writer.write(create_message(active.encode(), msg_types['text']))
