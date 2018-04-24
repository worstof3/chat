import asyncio
import unittest
import unittest.mock as um
from .. import server
from .. import message
import warnings
warnings.simplefilter('always', ResourceWarning)


class TestServer(unittest.TestCase):
    def test_handle_connection(self):
        """Test if correct handlers are called."""
        msg_lines = [
            b'#type\n',
            b'text\n',
            b'#\n',

            b'#type\n',
            b'hello\n',
            b'#\n',
        ]
        i = -1

        async def mock_read():
            nonlocal i
            await asyncio.sleep(0.05)
            i += 1
            return msg_lines[i % len(msg_lines)]

        mock_reader = um.Mock()
        mock_reader.readline = mock_read
        mock_handler1, mock_handler2, mock_handler3 = um.Mock(), um.Mock(), um.Mock()
        handlers = {b'hello': mock_handler1, b'text': mock_handler2, b'active': mock_handler3}
        client = server.Client(mock_reader, um.Mock(), handlers)
        client.__class__._recv_handlers = handlers
        loop = asyncio.get_event_loop()

        handling = loop.create_task(client.handle_connection())
        loop.call_later(0.5, handling.cancel)
        loop.run_until_complete(handling)
        mock_handler1.assert_called()
        mock_handler2.assert_called()
        mock_handler3.assert_not_called()

        loop.close()


class TestMessage(unittest.TestCase):
    def test_cut_message(self):
        all_msg_lines = (
            [
                b'#type\n',
                b'text\\\n',
                b'\n',
                b'#content\n',
                b'message\n',
                b'#\n',
            ],
            [
                b'#type\n',
                b'#\n',
            ],
            [
                b'#\n',
            ]
        )
        real_results = (
            {
                b'type': b'text\n',
                b'content': b'message',
            },
            {
                b'type': b'',
            },
            {}
        )

        for msg_lines, real_result in zip(all_msg_lines, real_results):
            with self.subTest(msg_lines=msg_lines, real_result=real_result):
                self.assertDictEqual(message.cut_message(msg_lines), real_result)

    def test_create_message(self):
        args = (
            dict(type=b'text', content=b'Text message.\n'),
            dict(type=b''),
            dict(),
        )
        real_msgs = (
            b'#type\ntext\n#content\nText message.\\\n\n#\n',
            b'#type\n\n#\n',
            b'#\n',
        )

        for arg, real_msg in zip(args, real_msgs):
            with self.subTest(arg=arg, real_msg=real_msg):
                self.assertEqual(message.create_message(**arg), real_msg)

    def test_get_handlers(self):
        mock_module = um.Mock()
        mock_module.f = lambda: None
        mock_module.recv_hello = lambda: None
        mock_module.recv_text = lambda: None
        mock_module.recvhi = lambda: None

        handlers = message.get_handlers(mock_module)
        self.assertDictEqual(handlers, {b'hello': mock_module.recv_hello, b'text': mock_module.recv_text})


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
        server.Client._nicks_clients = {b'user': um.Mock(), b'nick': um.Mock()}
        mock_client = server.Client(um.Mock(), um.Mock(), um.Mock())
        mock_client.ending = um.Mock()
        mock_client.con_handling = um.Mock()
        msg = {
            b'type': b'hello',
            b'nick': b'user',
        }

        server.recv_hello(msg, mock_client)
        mock_client.writer.write.assert_called()
        mock_client.con_handling.cancel.assert_called()

        msg = {
            b'type': b'hello',
            b'nick': b'new_user'
        }

        server.recv_hello(msg, mock_client)
        self.assertIn(b'new_user', mock_client.nicks_clients)

    def test_recv_text(self):
        server.Client._nicks_clients = {b'user': server.Client(um.Mock(), um.Mock(), um.Mock()),
                                        b'nick': server.Client(um.Mock(), um.Mock(), um.Mock())}
        mock_client = server.Client(um.Mock(), um.Mock(), um.Mock())
        msg = {
            b'type': b'text',
            b'text': b'Text.\n'
        }

        server.recv_text(msg, mock_client)
        mock_client.nicks_clients[b'user'].writer.write.assert_called_with(b'#type\ntext\n#text\nText.\\\n\n#\n')
        mock_client.nicks_clients[b'nick'].writer.write.assert_called_with(b'#type\ntext\n#text\nText.\\\n\n#\n')

    def test_recv_active(self):
        mock_client = server.Client(um.Mock(), um.Mock(), um.Mock(), b'new_user')
        server.Client._nicks_clients = {b'user': server.Client(um.Mock(), um.Mock(), um.Mock()),
                                        b'nick': server.Client(um.Mock(), um.Mock(), um.Mock())}

        server.recv_active(mock_client)
        mock_client.writer.write.assert_called_with(b'#type\ntext\n#text\nnick\\\nuser\\\n\n#\n')

        mock_client._nicks_clients[b'new_user'] = mock_client
        server.recv_active(mock_client)
        mock_client.writer.write.assert_called_with(b'#type\ntext\n#text\nnew_user (you)\\\nnick\\\nuser\\\n\n#\n')
