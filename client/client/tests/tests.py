import asyncio
import io
import unittest
import unittest.mock as um
from .. import client
from .. import message


class TestClient(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.addCleanup(self.loop.close)

    def test_handle_connection_hello(self):
        """Test if hello message is sent."""
        mock_handler1, mock_handler2, mock_handler3 = um.Mock(), um.Mock(), um.Mock()
        send_handlers = {b'hello': mock_handler1, b'text': mock_handler2, b'active': mock_handler3}
        cl = client.Client(self.loop, um.Mock(), send_handlers, um.Mock(), um.Mock(), 'nick')

        async def mock_readline():
            await asyncio.sleep(1)
        cl.reader = um.Mock()
        cl.reader.readline = mock_readline
        cl.writer = um.Mock()

        handling = self.loop.create_task(cl.handle_connection())
        self.loop.call_later(0.5, handling.cancel)
        self.loop.run_until_complete(handling)
        mock_handler1.assert_called()

    def test_handle_connection_handlers(self):
        """Test if correct recv_handlers are called"""
        msg_lines = [
            b'#type\n',
            b'text\n',
            b'#\n',

            b'#type\n',
            b'hello\n',
            b'#\n',
        ]
        i = -1

        async def mock_readline():
            nonlocal i
            await asyncio.sleep(0.05)
            i += 1
            return msg_lines[i % len(msg_lines)]

        mock_handler1, mock_handler2, mock_handler3 = um.Mock(), um.Mock(), um.Mock()
        send_handlers = {b'hello': um.Mock()}
        recv_handlers = {b'hello': mock_handler1, b'text': mock_handler2, b'active': mock_handler3}
        cl = client.Client(self.loop, recv_handlers, send_handlers, um.Mock(), um.Mock(), um.Mock())
        cl.reader = um.Mock()
        cl.reader.readline = mock_readline
        cl.writer = um.Mock()

        handling = self.loop.create_task(cl.handle_connection())
        self.loop.call_later(0.5, handling.cancel)
        self.loop.run_until_complete(handling)
        mock_handler1.assert_called()
        mock_handler2.assert_called()
        mock_handler3.assert_not_called()

    def test_send(self):
        """Test if correct send_handlers are called."""
        mock_handler1, mock_handler2, mock_handler3 = um.Mock(), um.Mock(), um.Mock()
        send_handlers = {b'hello': mock_handler1, b'text': mock_handler2, b'active': mock_handler3}
        cl = client.Client(self.loop, um.Mock(), send_handlers, um.Mock(), um.Mock(), um.Mock())

        msg = b'/active'
        cl.send(msg)
        mock_handler3.assert_called()

        msg = b'Text message.'
        cl.send(msg)
        mock_handler2.assert_called()


class TestRecvHandlers(unittest.TestCase):
    def test_recv_text(self):
        """Test if correct message is displayed."""
        cl = client.Client(um.Mock(), um.Mock(), um.Mock(), um.Mock(), um.Mock(), um.Mock())
        msgs = (
               {b'type': b'text', b'text': b'Text message.\n'},
               {b'type': b'text', b'text': b'Message.'},
        )
        real_results = (
            'Text message.\n',
            'Message.'
        )

        for msg, real_result in zip(msgs, real_results):
            with self.subTest(msg=msg, real_result=real_result):
                outfile = io.StringIO()
                cl.outfile = outfile
                client.recv_text(msg, cl)
                self.assertEqual(outfile.getvalue(), real_result)


class TestSendHanlders(unittest.TestCase):
    def test_send_hello(self):
        """Test if correct message is sent."""
        cl = client.Client(um.Mock(), um.Mock(), um.Mock(), um.Mock(), um.Mock(), 'nickname')
        cl.writer = um.Mock()
        client.send_hello(cl)
        cl.writer.write.assert_called_with(b'#type\nhello\n#nick\nnickname\n#\n')

    def test_send_text(self):
        """Test if correct message is sent."""
        cl = client.Client(um.Mock(), um.Mock(), um.Mock(), um.Mock(), um.Mock(), 'nickname')
        msg_args = b'Text message.'
        cl.writer = um.Mock()
        client.send_text(cl, msg_args)
        cl.writer.write.assert_called_with(b'#type\ntext\n#text\nnickname: Text message.\n#\n')

    def test_send_active(self):
        """Test if correct message is sent."""
        cl = client.Client(um.Mock(), um.Mock(), um.Mock(), um.Mock(), um.Mock(), 'nickname')
        cl.writer = um.Mock()
        client.send_active(cl)
        cl.writer.write.assert_called_with(b'#type\nactive\n#\n')


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

        handlers = message.get_handlers(mock_module, 'recv_')
        self.assertDictEqual(handlers, {b'hello': mock_module.recv_hello, b'text': mock_module.recv_text})
