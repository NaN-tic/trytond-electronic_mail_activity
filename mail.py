"""Extract the participants of internally forwarded messages."""

import re
from html.parser import HTMLParser


class HeaderText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'br', 'div', 'p', 'tr'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'div', 'p', 'tr'}:
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)


def forwarded_headers(text):
    """Read only header blocks following explicit forwarding separators."""
    marker = re.compile(
        r'^\s*(?:-{2,}\s*(?:forwarded message|original message|'
        r'mensaje reenviado|mensaje original|missatge reenviat|'
        r'missatge original).*|-*\s*begin forwarded message:)', re.I)
    labels = {
        'from': 'from', 'de': 'from', 'von': 'from',
        'to': 'to', 'para': 'to', 'a': 'to', 'per a': 'to',
        'cc': 'cc', 'c/c': 'cc',
        'subject': 'subject', 'asunto': 'subject', 'assumpte': 'subject',
        'date': 'date', 'fecha': 'date', 'data': 'date',
        'sent': 'date', 'enviado': 'date', 'enviat': 'date',
        }
    headers = None
    previous = None
    for raw in text.splitlines():
        line = re.sub(r'^\s*(?:>\s*)+', '', raw).strip()
        if marker.match(line):
            if headers and headers.get('from'):
                yield headers
            headers = {}
            previous = None
            continue
        if headers is None:
            continue
        if not line:
            if headers:
                if headers.get('from'):
                    yield headers
                headers = None
            continue
        label, sep, value = line.partition(':')
        key = labels.get(label.lower())
        if sep and key:
            headers[key] = value.strip()
            previous = key
        elif raw[:1].isspace() and previous:
            headers[previous] += ' ' + line
        else:
            if headers.get('from'):
                yield headers
            headers = None
    if headers and headers.get('from'):
        yield headers
