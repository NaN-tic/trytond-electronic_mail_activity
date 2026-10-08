"""Extract the participants of internally forwarded messages."""

import re
import unicodedata
from html.parser import HTMLParser


def match_contact_name(name, parties):
    """Narrow email matches only when the display name provides evidence.

    An exact name takes precedence over a prefix containing at least two words.
    Keep all candidates on a missing/unrecognized name so callers can surface
    the ambiguity instead of guessing. A pipe suffix denotes an organization.
    """
    parties = [party for party in parties if party.active]
    if len(parties) < 2:
        return parties

    def words(value):
        value = unicodedata.normalize('NFKD', (value or '').partition('|')[0])
        value = ''.join(c for c in value if not unicodedata.combining(c))
        return re.findall(r'[^\W_]+', value.casefold())

    header = words(name)
    if not header:
        return parties
    exact = []
    partial = []
    for party in parties:
        candidate = words(party.name)
        if candidate == header:
            exact.append(party)
        elif min(len(header), len(candidate)) >= 2:
            size = min(len(header), len(candidate))
            if header[:size] == candidate[:size]:
                partial.append(party)
    return exact or partial or parties


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
        elif previous and (raw[:1].isspace() or previous == 'subject'):
            # Inline forwards can wrap subjects without RFC header indentation.
            headers[previous] += ' ' + line
        else:
            if headers.get('from'):
                yield headers
            headers = None
    if headers and headers.get('from'):
        yield headers
