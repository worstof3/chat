import asyncio
from collections import deque


read_size = 1024 * 1024


class Buffer:
    """
    Class for buffering data.

    Instance attributes:
    buffer -- Deque of byte chunks.
    length -- Number of bytes in buffer.

    Methods:
    write() -- Write data to buffer, increase length.
    read() -- Read data, remove from buffer and decrease length.
    peek() -- Check first bytes of buffer without removing anything.
    __gather_chunks() -- Return chunks with total length greater or equal than num or all chunks if
                         there is not enough and also length of these chunks.
    __cut_last() -- Cut tail of a chunk.

    Magic methods:
    __init__() -- Initialize instance attributes.
    __len__() -- Return number of bytes in buffer.
    __repr__() -- Return 'Buffer(buffer_content)'.
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
        """Return content of buffer without changing anything else."""
        return b''.join(self.buffer)

    def __repr__(self):
        """Return 'Buffer(buffer_content)'."""
        return 'Buffer(' + repr(self.getvalue()) + ')'

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

def check_full_message(buffer):
    """
    Check if there is full message in the buffer.

    Function just peeks at first two bytes in buffer and treats them as message length. Then it checks if there is
    enough bytes in the buffer.

    Args:
    buffer -- Buffer to check.

    Returns:
    True if there is full message, False otherwise.
    """
    len_bytes = buffer.read(2, False)
    if len(len_bytes) < 2:
        return False
    msg_len = int.from_bytes(len_bytes, 'big')
    if msg_len <= len(buffer) - 2:
        return True
    else:
        return False


async def handle_client(reader, writer, handlers, buffer):
    while True:
        data = await reader.read(read_size)
        buffer.write(data)
        while check_full_message(buffer):
            len_bytes = buffer.read(2)
            msg_len = int.from_bytes(len_bytes)
            message = buffer.read(msg_len)
            args = make_args(message)
            handlers[message[-1]](args)