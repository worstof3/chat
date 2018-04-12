"""
Module defines functions to help creating, reading and handling messages.

Functions:
create_message -- Create message from byte content and type.
read_message -- Return message content.
read_type -- Return message byte type and rest of it.
get_handlers -- Map types of messages to handlers.
get_msg_types -- Map names of message types to bytes.
"""
import inspect


def create_message(content, msg_type):
    """
    Create message from byte content and type.

    Created message is in following form:
    First three bytes are binary representation of length of rest of the message.
    Next there is binary content.
    Last byte is type of message.

    Args:
    content -- Content of the message.
    msg_type -- Type of message (byte).

    Returns:
    Message in form described above.
    """
    msg_len = len(content) + 1
    len_bytes = msg_len.to_bytes(3, 'big')
    full_message = b''.join((len_bytes, content, msg_type))
    return full_message


def read_message(message):
    """
    Read message content.

    Right now this function only decodes content, but it may change in the future.

    Args:
    message -- Encoded message content.
    """
    content = message.decode()
    return content


def read_type(message):
    """
    Return message byte type and rest of it.

    Args:
    message -- Encoded message.

    Returns:
    Tuple (message type, rest of message)
    """
    msg_type, msg_bytes = message[-1:], message[:-1]
    return msg_type, msg_bytes


def get_handlers(msg_types, module):
    """
    Map types of messages to handlers.

    Function reads handlers from module. It assumes that name of handler of message with type msg_type has form
    recv_msg_type.

    Args:
    msg_types -- Types of messages.
    module -- Module to read handlers from.

    Returns:
    Map types of messages to handlers.
    """
    functions = inspect.getmembers(module, inspect.isfunction)
    handlers = {}
    for name, f in functions:
        if name.startswith('recv_'):
            msg_type = msg_types[name[5:]]
            handlers[msg_type] = f
    return handlers


def get_msg_types(module):
    """
    Map names of message types to bytes.

    Function reads names of all functions, which start with recv_ and maps them to subsequent bytes (first function
    is mapped to \x00, second to \x01, etc.)

    Returns:
    Mapping types of messages to bytes.
    """
    functions = inspect.getmembers(module, inspect.isfunction)
    msg_types = {}
    for name, f in functions:
        if name.startswith('recv_'):
            msg_types[name[5:]] = len(msg_types).to_bytes(1, 'big')
    return msg_types
