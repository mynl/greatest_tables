"""Python-side DOM transcriber — the mirror of js/transcript.mjs.

Renders a TableDoc with render_html (css='none', allow_html=False — matching
the walker harness defaults: html cells as source text, math as \\(tex\\))
and parses the fragment with stdlib html.parser into the same JSONL format:
meta line, then one line per cell {s, r, c, tag, [rowspan], [colspan],
classes(sorted), text}. Byte-compared against tests/golden/transcript.
"""

import json
from html.parser import HTMLParser

from greater_tables import Cell, HouseStyle, TableDoc
from greater_tables.render.html import render_html

_SECTION = {'thead': 'head', 'tbody': 'body', 'tfoot': 'foot'}


class _Walk(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = []
        self.section = None
        self.row = -1
        self.col = 0
        self.cell = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in _SECTION:
            self.section = _SECTION[tag]
            self.row = -1
        elif tag == 'tr' and self.section:
            self.row += 1
            self.col = 0
        elif tag in ('td', 'th') and self.section:
            rec = {'s': self.section, 'r': self.row, 'c': self.col, 'tag': tag}
            rowspan = int(a.get('rowspan', 1))
            colspan = int(a.get('colspan', 1))
            if rowspan > 1:
                rec['rowspan'] = rowspan
            if colspan > 1:
                rec['colspan'] = colspan
            rec['classes'] = sorted((a.get('class') or '').split())
            self.cell = rec
            self.text = []
            self.col += colspan

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.cell['text'] = ''.join(self.text)
            self.records.append(self.cell)
            self.cell = None
        elif tag in _SECTION:
            self.section = None

    def handle_data(self, data):
        if self.cell is not None:
            self.text.append(data)


def transcribe(doc: TableDoc, style: HouseStyle | None = None) -> str:
    """Transcript of the Python HTML rendering, walker-harness format.

    ``style`` mirrors ``js/transcript.mjs --max-rule-depth``: the committed
    goldens use the default policy, and the tests compare both
    implementations live under non-default ones.
    """
    caption = doc.caption.text if isinstance(doc.caption, Cell) else doc.caption
    meta = {'caption': caption, 'label': doc.label, 'hash': doc.hash,
            'notes': list(doc.notes)}
    walker = _Walk()
    walker.feed(render_html(doc, css='none', allow_html=False, style=style))
    lines = [json.dumps(meta, ensure_ascii=False, separators=(',', ':'))]
    order = {'head': 0, 'body': 1, 'foot': 2}
    for rec in sorted(walker.records, key=lambda x: order[x['s']]):
        lines.append(json.dumps(rec, ensure_ascii=False, separators=(',', ':')))
    return '\n'.join(lines) + '\n'
