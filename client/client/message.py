"""
Module defines functions to help creating, reading and handling messages.

Messages are in the following format (\n are newlines added in processing):
#header1\n
section1\n
#header2\n
section2\n
.
.
.
#headerN\n
sectionN\n
#\n.
For example
#type\n
type_of_message\n
#content\n
content_of_message\n
#\n
Headers can't have newlines.
Newline and # characters in each section are escaped with backslash when message is created. In other words
the only newline and # characters, which are not escaped are the ones added in process of message creation. It's
acceptable to have # in header but not recommended.

Functions:
cut_message -- Cut message to sections defined by headers.
create_message -- Create message according to protocol described in module help.
get_handlers -- Read handlers of messages from module.
"""
import inspect


def cut_message(msg_lines):
    """
    Cut message to sections defined by headers.

    Each section is stored in returned dictionary. Dictionary key for each section is it's header (bytes object). Each
    newline escaped with backslash is stored without backslash and each newline not escaped is removed. Escaped
    # characters in each section are stored without backslash.

    Args:
    msg_lines -- Iterable of message lines. We assume only newline in each line is the one at the end.

    Returns:
    Dictionary with cut message.
    """
    sections = {}
    lines = iter(msg_lines)
    header = next(lines)[1:-1]

    while True:
        if not header:
            break
        header_lines = []
        for line in lines:
            if line.startswith(b'#'):
                break
            line = line.replace(b'\\#', b'#')
            if line.endswith(b'\\\n'):
                line = line[:-2] + b'\n'
            else:
                line = line[:-1]
            header_lines.append(line)
        sections[header] = b''.join(header_lines)
        header = line[1:-1]

    return sections


def create_message(**kwargs):
    """
    Create message according to protocol described in module help.

    Each key in kwargs is treated as header and corresponding value is section content. As described above each newline
    and # character in section content are escaped with backslash.

    Returns:
    Created message.
    """
    msg_lines = []
    for header, content in kwargs.items():
        msg_lines.append(b'#' + header.encode() + b'\n')
        content = content.replace(b'\n', b'\\\n').replace(b'#', b'\\#')
        msg_lines.append(content + b'\n')
    msg_lines.append(b'#\n')
    message = b''.join(msg_lines)
    return message


def get_handlers(module, pattern):
    """
    Read handlers of messages from module.

    Function reads handlers from module. It treats each function with name starting with pattern as handler and rest of
    its name is considered as message type.

    Args:
    module -- Module to read handlers from.
    pattern -- Beginning of function name.

    Returns:
    Map types of messages to handlers.
    """
    functions = inspect.getmembers(module, inspect.isfunction)
    handlers = {}
    for name, f in functions:
        if name.startswith(pattern):
            msg_type = name[len(pattern):]
            handlers[msg_type.encode()] = f
    return handlers
