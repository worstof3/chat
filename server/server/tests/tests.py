import asyncio
import unittest
import unittest.mock as um
from .. import server
from .. import message
import functools


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
        buffer.write(b'\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x00\x10\x00')

        msg = server.read_full_message(buffer)
        self.assertEqual(msg, b'\x00')
        self.assertEqual(buffer.getvalue(), b'\x00\x00\x02\x00\x00\x00\x00\x10\x00')

        msg = server.read_full_message(buffer)
        self.assertEqual(msg, b'\x00\x00')
        self.assertEqual(buffer.getvalue(), b'\x00\x00\x10\x00')

        msg = server.read_full_message(buffer)
        self.assertEqual(msg, b'')
        self.assertEqual(buffer.getvalue(), b'\x00\x00\x10\x00')

    def test_handle_client(self):
        async def mock_read(num):
            await asyncio.sleep(0.1)
            return b'\x00\x00\x01\x00\x00\x00\x02\x11\x01\x00\x00\x03\x00\x00\x02\x00'
        mock_writer = um.Mock()
        mock_reader = um.Mock()
        mock_reader.read = mock_read
        mock_handler1, mock_handler2, mock_handler3 = um.Mock(), um.Mock(), um.Mock()
        handlers = {b'\x00': mock_handler1, b'\x01': mock_handler2, b'\x02': mock_handler3}
        ending = asyncio.Future()

        loop = asyncio.get_event_loop()
        handling = server.handle_client(mock_reader, mock_writer, handlers, um.Mock(), ending)
        loop.call_later(0.5, functools.partial(ending.set_result, True))
        loop.run_until_complete(handling)
        mock_handler1.assert_called()
        mock_handler2.assert_called()
        mock_handler3.assert_called()
        loop.close()


class TestMessage(unittest.TestCase):
    def test_create_message(self):
        contents = (
            b'',
            b'\x00',
        )
        msg_types = (
            b'\x00',
            b'\x01',
        )
        real_results = (
            b'\x00\x00\x01\x00',
            b'\x00\x00\x02\x00\x01'
        )

        for content, msg_type, real_result in zip(contents, msg_types, real_results):
            with self.subTest(content=content, msg_type=msg_type, real_result=real_result):
                self.assertEqual(message.create_message(content, msg_type), real_result)


class TestHandlers(unittest.TestCase):
    def setUp(self):
        patcher = um.patch('server.server.Client',
                           type('MockClient', server.Client.__bases__, dict(server.Client.__dict__)))
        # Mocking Client with copy, so we don't have to worry about nicks_clients staying between tests.
        self.msg_types = {
            'hello': b'\x00',
            'text': b'\x01',
            'active': b'\x02'
        }
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_recv_hello(self):
        server.Client._nicks_clients = {'user': um.Mock(), 'nick': um.Mock()}
        mock_ending = um.Mock()
        mock_client = server.Client(um.Mock(), mock_ending)
        msg = b'user'
        server.recv_hello(self.msg_types, msg, mock_client)
        mock_client.writer.write.assert_called()
        mock_ending.set_result.assert_called_with(True)

        msg = b'new_user'
        server.recv_hello(self.msg_types, msg, mock_client)
        self.assertIn('new_user', mock_client.nicks_clients)

    def test_recv_text(self):
        server.Client._nicks_clients = {'user': server.Client(um.Mock(), um.Mock()),
                                        'nick': server.Client(um.Mock(), um.Mock())}
        mock_client = server.Client(um.Mock(), um.Mock())

        server.recv_text(self.msg_types, b'text', mock_client)
        mock_client.nicks_clients['user'].writer.write.assert_called_with(b'\x00\x00\x05text\x01')
        mock_client.nicks_clients['nick'].writer.write.assert_called_with(b'\x00\x00\x05text\x01')

    def test_recv_active(self):
        mock_client = server.Client(um.Mock(), um.Mock(), 'new_user')
        server.Client._nicks_clients = {'user': server.Client(um.Mock(), um.Mock()),
                                        'nick': server.Client(um.Mock(), um.Mock())}

        server.recv_active(self.msg_types, mock_client)
        mock_client.writer.write.assert_called_with(b'\x00\x00\x0bnick\nuser\n\x01')

        mock_client._nicks_clients['new_user'] = mock_client
        server.recv_active(self.msg_types, mock_client)
        mock_client.writer.write.assert_called_with(b'\x00\x00\x1anew_user (you)\nnick\nuser\n\x01')


class TestScript(unittest.TestCase):
    def test_get_msg_types(self):
        mock_module = um.Mock()
        mock_module.f = lambda: None
        mock_module.recv_hello = lambda: None
        mock_module.recv_text = lambda: None
        mock_module.recvhi = lambda: None

        msg_types = message.get_msg_types(mock_module)
        self.assertDictEqual(msg_types, {'hello': b'\x00', 'text': b'\x01'})

    def test_get_handlers(self):
        mock_module = um.Mock()
        mock_module.f = lambda: None
        mock_module.recv_hello = lambda: None
        mock_module.recv_text = lambda: None
        mock_module.recvhi = lambda: None
        msg_types = {'hello': b'\x00', 'text': b'\x01'}

        handlers = message.get_handlers(msg_types, mock_module)
        self.assertDictEqual(handlers, {b'\x00': mock_module.recv_hello, b'\x01': mock_module.recv_text})