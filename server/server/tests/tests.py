import asyncio
import unittest
import unittest.mock as um
from .. import server


class TestBuffer(unittest.TestCase):
    @staticmethod
    def make_buffer(*args):
        buffer = server.Buffer()
        for chunk in args:
            buffer.write(chunk)
        return buffer

    def test_writing(self):
        buffer = server.Buffer()
        buffer.write(b'a')
        self.assertEqual(buffer.getvalue(), b'a')
        self.assertEqual(len(buffer), 1)

        buffer.write(b'abc')
        self.assertEqual(buffer.getvalue(), b'aabc')
        self.assertEqual(len(buffer), 4)

    def test_gather_chunks(self):
        buffer_contents = (
            (b'ab', b'b'),
            (b'',),
            (b'a', b'b'),
            (b'a', b'b'),
            (b'ab', b'b'),
        )
        nums = (0, 1, 2, 1, 1)
        real_results = (
            ([], 0),
            ([], 0),
            ([b'a', b'b'], 2),
            ([b'a'], 1),
            ([b'ab'], 2)
        )
        buffer_lefts = (
            b'abb',
            b'',
            b'',
            b'b',
            b'b'
        )

        for buffer_content, num, real_result, buffer_left in zip(buffer_contents, nums, real_results, buffer_lefts):
            with self.subTest(buffer_content=buffer_content, num=num, real_result=real_result, buffer_left=buffer_left):
                buffer = self.make_buffer(*buffer_content)
                result = buffer._Buffer__gather_chunks(num)
                self.assertTupleEqual(result, real_result)
                self.assertEqual(buffer.getvalue(), buffer_left)

    def test_cut_last(self):
        chunk = b'abc'
        real_results = (
            (b'abc', b''),
            (b'ab', b'c'),
            (b'a', b'bc'),
            (b'', b'abc'),
        )
        for length, real_result in zip(range(len(chunk)), real_results):
            with self.subTest(length=length, real_result=real_result):
                result = server.Buffer._Buffer__cut(chunk, length)
                self.assertTupleEqual(result, real_result)

    def test_read_remove(self):
        buffer = self.make_buffer(b'abcdefghi')
        nums = (0, 1, 3, 10, 3)
        datas = (
            b'',
            b'a',
            b'bcd',
            b'efghi',
            b'',
        )
        buffer_contents = (
            b'abcdefghi',
            b'bcdefghi',
            b'efghi',
            b'',
            b'',
        )

        for num, data, buffer_content in zip(nums, datas, buffer_contents):
            with self.subTest(num=num, data=data, buffer_content=buffer_content):
                read_data = buffer.read(num)
                self.assertEqual(read_data, data)
                self.assertEqual(buffer.getvalue(), buffer_content)

    def test_peek(self):
        buffer = self.make_buffer(b'')
        read_data = buffer.peek(3)
        self.assertEqual(read_data, b'')
        self.assertEqual(buffer.getvalue(), b'')

        buffer = self.make_buffer(b'abcdefghi')
        nums = (0, 1, 5, 100)
        datas = (
            b'',
            b'a',
            b'abcde',
            b'abcdefghi'
        )

        for num, data in zip(nums, datas):
            with self.subTest(num=num, data=data):
                read_data = buffer.peek(num)
                self.assertEqual(read_data, data)
                self.assertEqual(buffer.getvalue(), b'abcdefghi')


class TestServer(unittest.TestCase):
    def test_read_full_message(self):
        buffer = server.Buffer()
        buffer.write(b'\x00\x01\x00\x00\x02\x00\x00\x00\x10\x00')

        message = server.read_full_message(buffer)
        self.assertEqual(message, b'\x00')
        self.assertEqual(buffer.getvalue(), b'\x00\x02\x00\x00\x00\x10\x00')

        message = server.read_full_message(buffer)
        self.assertEqual(message, b'\x00\x00')
        self.assertEqual(buffer.getvalue(), b'\x00\x10\x00')

        message = server.read_full_message(buffer)
        self.assertEqual(message, b'')
        self.assertEqual(buffer.getvalue(), b'\x00\x10\x00')

    def test_handle_client(self):
        async def mock_read(num):
            await asyncio.sleep(0.1)
            return b'\x00\x01\x00\x00\x02\x11\x01\x00\x03\x00\x00\x02\x00'
        mock_writer = um.Mock()
        mock_reader = um.Mock()
        mock_reader.read = mock_read
        mock_handler1, mock_handler2, mock_handler3 = um.Mock(), um.Mock(), um.Mock()
        handlers = {b'\x00': mock_handler1, b'\x01': mock_handler2, b'\x02': mock_handler3}
        end = asyncio.Future()

        loop = asyncio.get_event_loop()
        loop.call_later(0.5, lambda: end.set_result(True))
        loop.run_until_complete(server.handle_client(mock_reader, mock_writer, handlers, server.Buffer(), end))
        mock_handler1.assert_called_with(message=b'\x00', writer=mock_writer)
        mock_handler2.assert_called_with(message=b'\x11\x01', writer=mock_writer)
        mock_handler3.assert_called_with(message=b'\x00\x00\x02', writer=mock_writer)
        loop.close()