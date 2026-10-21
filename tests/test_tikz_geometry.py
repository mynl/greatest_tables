"""Where the TikZ rules land, measured in the compiled PDF.

The other TikZ tests compare TeX source; nothing there can see a rule drawn
through a label. This module compiles fixtures with tectonic, opens the PDF
with pdfplumber (word boxes and line segments, in points) and checks the
geometry the renderer promises:

- no vertical rule crosses a word, and each clears the words beside it;
- a vertical ends on the bottom frame rule, and starts on the top frame rule
  or, between groups that share a label above, on that label's underline;
- body rules fall where the rule policy says, at every ``max_rule_depth``.

The fixtures are set in Times by ``Etcher``'s standalone preamble, the face
the width estimates are exact for, so a failure here is geometry, not font.
"""

import shutil
import subprocess
from functools import cache
from pathlib import Path

import pandas as pd
import pytest

from greater_tables import Etcher, HouseStyle, TableSpec, build, render_tikz
from greater_tables.render.policy import rule_slot

from registry import fixtures

pdfplumber = pytest.importorskip('pdfplumber')
pytestmark = pytest.mark.skipif(shutil.which('tectonic') is None,
                                reason='tectonic not available')

FIX = fixtures()
CLEARANCE = 1.0         # pt: the least room a vertical leaves a word
TOUCH = 0.6             # pt: how close a rule end must be to the rule it meets
HEAD_ROOM = 3.0         # pt: the least room between a heading and the rule below

# shapes with vertical rules: the stub rule, column-group breaks, or both
VERTICAL = ['plain', 'row-mi-2', 'row-mi-3', 'row-mi-4', 'deep-stub',
            'subtotals', 'col-mi-2', 'col-mi-3', 'both-mi', 'loss-lab',
            'long-spanner', 'long-headings']


@pytest.fixture(scope='session')
def pdf_dir(tmp_path_factory):
    return tmp_path_factory.mktemp('geometry')


@cache
def _geometry(pdf: Path):
    with pdfplumber.open(pdf) as p:
        page = p.pages[0]
        segs = page.lines + page.rects
        verticals = [s for s in segs if abs(s['x1'] - s['x0']) < 1.0
                     and s['bottom'] - s['top'] > 5]
        horizontals = [s for s in segs if s['bottom'] - s['top'] < 1.5
                       and s['x1'] - s['x0'] > 5]
        words = page.extract_words(x_tolerance=1)
    return verticals, horizontals, words


def geometry(name, pdf_dir, **style):
    """Compile fixture ``name`` and return its measured parts."""
    data, spec = FIX[name]
    tag = '-'.join(f'{k}{v}' for k, v in sorted(style.items()))
    tex = render_tikz(build(data, spec), HouseStyle(**style))
    pdf = Etcher(tex, file_name='-'.join(filter(None, (name, tag))),
                 base_path=pdf_dir).compile()
    return _geometry(pdf)


def levels(horizontals):
    """Distinct rule heights, top to bottom, each as its (top, bottom) span."""
    out = []
    for h in sorted(horizontals, key=lambda h: h['top']):
        if out and h['top'] - out[-1][1] < TOUCH:
            out[-1] = (out[-1][0], max(out[-1][1], h['bottom']))
        else:
            out.append((h['top'], h['bottom']))
    return out


@pytest.mark.parametrize('name', VERTICAL)
def test_verticals_clear_every_word(name, pdf_dir):
    verticals, _h, words = geometry(name, pdf_dir)
    for v in verticals:
        x = (v['x0'] + v['x1']) / 2
        beside = [w for w in words if w['top'] < v['bottom'] and v['top'] < w['bottom']]
        for w in beside:
            gap = x - w['x1'] if w['x1'] <= x else w['x0'] - x if w['x0'] >= x else -1.0
            assert gap >= CLEARANCE, (
                f'{name}: vertical at x={x:.2f} is {gap:.2f}pt from '
                f'{w["text"]!r} [{w["x0"]:.2f}, {w["x1"]:.2f}]')


@pytest.mark.parametrize('name', VERTICAL)
def test_verticals_meet_the_rules(name, pdf_dir):
    verticals, horizontals, _w = geometry(name, pdf_dir)
    spans = levels(horizontals)
    frame_top, frame_bottom = spans[0], spans[-1]

    def on(y, span):
        return span[0] - TOUCH <= y <= span[1] + TOUCH

    for v in verticals:
        x = (v['x0'] + v['x1']) / 2
        assert on(v['bottom'], frame_bottom), (
            f'{name}: vertical at x={x:.2f} ends at {v["bottom"]:.2f}, '
            f'bottom frame at {frame_bottom}')
        assert any(on(v['top'], s) for s in spans), (
            f'{name}: vertical at x={x:.2f} starts at {v["top"]:.2f}, '
            f'on no rule')


@pytest.mark.parametrize('depth', ['auto', 0, 1, None])
def test_body_rules_follow_the_policy(depth, pdf_dir):
    """Frame, head rule and bottom frame, plus one rule per qualifying break."""
    data, spec = FIX['row-mi-3']
    doc = build(data, spec)
    style = HouseStyle(max_rule_depth=depth)
    expected = sum(
        1 for row in doc.body[1:]
        if (slot := rule_slot(row.break_depth, doc.n_stub_levels, depth)) is not None
        and style.hrule_widths[slot])
    _v, horizontals, _w = geometry('row-mi-3', pdf_dir, max_rule_depth=depth)
    assert len(levels(horizontals)) == 3 + expected


def test_headerless_table_has_one_top_rule(pdf_dir):
    """With no head there is no head rule: the frame alone above the body."""
    _v, horizontals, _w = geometry('headerless', pdf_dir)
    assert len(levels(horizontals)) == 2


# shapes with a head: spanned ones put underlines between the frame and the
# head rule, one rule height per level above the leaf
HEADED = ['plain', 'row-mi-3', 'col-mi-2', 'col-mi-3', 'both-mi', 'loss-lab',
          'long-spanner', 'long-headings']
SPANNED = ['col-mi-2', 'col-mi-3', 'both-mi', 'loss-lab', 'long-spanner']


def head_rule(name, horizontals):
    """The head rule's (top, bottom): one level per header row below the frame."""
    data, spec = FIX[name]
    return levels(horizontals)[build(data, spec).n_head_levels]


@pytest.mark.parametrize('name', HEADED)
def test_room_under_the_head(name, pdf_dir):
    """The head once sat 1.6pt above its rule, which read as cramped."""
    _v, horizontals, words = geometry(name, pdf_dir)
    top, _bottom = head_rule(name, horizontals)
    gap = top - max(w['bottom'] for w in words if w['bottom'] < top)
    assert gap >= HEAD_ROOM, f'{name}: {gap:.2f}pt between the head and its rule'


@pytest.mark.parametrize('name', SPANNED)
def test_spanner_underlines_reach_the_stub_rule(name, pdf_dir):
    """The first group's underline starts at the stub rule, not half an em in."""
    verticals, horizontals, _w = geometry(name, pdf_dir)
    stub = min((v['x0'] + v['x1']) / 2 for v in verticals)
    frame = levels(horizontals)[0]
    top, _bottom = head_rule(name, horizontals)
    under = [h for h in horizontals
             if frame[1] + TOUCH < h['top'] and h['bottom'] < top - TOUCH]
    left = min(h['x0'] for h in under)
    assert abs(left - stub) <= TOUCH, f'underline starts at {left:.2f}, stub rule at {stub:.2f}'


# A document that makes H the default for tables, as house style does, around
# one sideways table. Etcher strips the container, so this compiles directly.
SIDEWAYS_DOC = r"""\documentclass[11pt]{article}
\usepackage[a4paper,margin=2.5cm]{geometry}
\usepackage{newtxtext}\usepackage{booktabs}\usepackage{array}\usepackage{xcolor}
\usepackage{tikz}
\usepackage{float}\floatplacement{table}{H}\usepackage{rotating}
\begin{document}
Before the table.

%s

After the table.
\end{document}
"""


# Each face as a document would load it: fontspec by font file, which tectonic
# resolves from its bundle, with the bold italic that stub headers set in.
FACE_PREAMBLES = {
    'times': r'\usepackage[T1]{fontenc}\usepackage{newtxtext}',
    **{name: r'\usepackage{fontspec}\setmainfont{%s}[BoldFont=%s,'
             r'ItalicFont=%s,BoldItalicFont=%s]' % files for name, files in {
        'stix-two': ('STIXTwoText-Regular.otf', 'STIXTwoText-Bold.otf',
                     'STIXTwoText-Italic.otf', 'STIXTwoText-BoldItalic.otf'),
        'latin-modern': ('lmroman10-regular.otf', 'lmroman10-bold.otf',
                         'lmroman10-italic.otf', 'lmroman10-bolditalic.otf'),
        'lato': ('Lato-Regular.ttf', 'Lato-Bold.ttf', 'Lato-Italic.ttf',
                 'Lato-BoldItalic.ttf'),
        'fira-sans': ('FiraSans-Regular.otf', 'FiraSans-Bold.otf',
                      'FiraSans-Italic.otf', 'FiraSans-BoldItalic.otf'),
    }.items()}}

FACE_DOC = r"""\documentclass[11pt]{article}
\usepackage[a4paper,margin=2.5cm]{geometry}
%s
\usepackage{booktabs}\usepackage{array}\usepackage{xcolor}\usepackage{float}
\usepackage{tikz}
\begin{document}
%s
\end{document}
"""

# labels at their natural width, long headings, bold rows, prose under a
# budget, markdown's bold, italic and code, and the number that once broke at
# its hyphen in Fira Sans
FACE_TABLES = [('loss-lab', {}), ('long-head-ratios', {}), ('subtotals', {}),
               ('long-head-groups', {}), ('wrap-low', {'max_table_width_em': 30}),
               ('markdown', {}), ('markdown-df', {})]
SCIENTIFIC = (pd.DataFrame({'estimate': [1.25, 0.5], 'err': [-1.95e-05, 3.2e-06]},
                           index=pd.Index(['first', 'second'], name='case')),
              TableSpec(formatters={'err': '.2e'}))


@pytest.mark.parametrize('face', list(FACE_PREAMBLES))
def test_text_holds_in_its_face(face, tmp_path):
    """Set in its own face with ``tikz_font`` naming it, no cell sized at its
    natural width wraps: nothing hyphenates, "Unit 1" stays on one line, and
    a number in e notation does not break at its hyphen."""
    tables = [(*FIX[name], style) for name, style in FACE_TABLES]
    tables.append((*SCIENTIFIC, {}))
    body = '\n\n'.join(
        render_tikz(build(data, spec), HouseStyle(
            tikz_font=face, tikz_latex='H', **style))
        for data, spec, style in tables)
    src = tmp_path / f'{face}.tex'
    src.write_text(FACE_DOC % (FACE_PREAMBLES[face], body), encoding='utf-8')
    subprocess.run([shutil.which('tectonic'), '--outdir', str(tmp_path), str(src)],
                   capture_output=True, check=False)
    with pdfplumber.open(tmp_path / f'{face}.pdf') as p:
        pages = [page.extract_words(x_tolerance=1) for page in p.pages]
    # Lato's hyphen extracts as U+2010
    words = [w['text'].replace('‐', '-') for page in pages for w in page]
    assert '-1.95e-05' in words
    assert not [w for w in words if w.endswith('-')]
    for page in pages:
        for w in page:
            if w['text'] == 'Unit':
                assert any(v['text'] in ('1', '2') and abs(v['top'] - w['top']) < 2
                           and 0 < v['x0'] - w['x1'] < 8 for v in page), \
                    f'{face}: "Unit" wrapped from its number'


# code sets in the document's monospace font, which tikz_font does not name:
# Etcher's newtx preamble, and house style's DejaVu Sans Mono, the widest
CODE = (pd.DataFrame({'code': ['`col_name`', '`lag_1` and `x`', '`np.log1p(x)`']}),
        TableSpec(show_index=False, markdown_cols='all'))
CODE_WORDS = ('col_name', 'lag_1', 'np.log1p(x)')
MONO_PREAMBLES = {
    'etcher': None,
    'dejavu': FACE_PREAMBLES['stix-two'] + r'\setmonofont{DejaVuSansMono.ttf}',
}


@pytest.mark.parametrize('mono', list(MONO_PREAMBLES))
def test_code_width_holds(mono, tmp_path):
    """A code run's estimate is never narrower than it sets, and at most
    20% wider; no code word wraps."""
    from greater_tables.render.tikz_layout import _MONO_MILLI
    tex = render_tikz(build(*CODE), HouseStyle(tikz_latex='H'))
    if MONO_PREAMBLES[mono] is None:
        pdf = Etcher(tex, file_name='code', base_path=tmp_path).compile()
    else:
        src = tmp_path / 'code.tex'
        src.write_text(FACE_DOC % (MONO_PREAMBLES[mono], tex), encoding='utf-8')
        subprocess.run([shutil.which('tectonic'), '--outdir', str(tmp_path), str(src)],
                       capture_output=True, check=False)
        pdf = tmp_path / 'code.pdf'
    with pdfplumber.open(pdf) as p:
        page = p.pages[0]
        words = {w['text']: w for w in page.extract_words(x_tolerance=1)}
        size = {round(c['x0'], 1): c['size'] for c in page.chars}
    for word in CODE_WORDS:
        assert word in words, f'{mono}: {word!r} wrapped or broke'
        w = words[word]
        actual = (w['x1'] - w['x0']) / size[round(w['x0'], 1)]
        estimate = _MONO_MILLI * len(word) / 1000
        assert actual <= estimate <= 1.2 * actual, (mono, word, actual, estimate)


@pytest.mark.parametrize('face', ['lato', 'fira-sans'])
def test_a_number_holds_in_the_wrong_face(face, tmp_path):
    """Sized in Times and set in a face whose digits run wider, a number
    overruns into the column gap rather than breaking, and keeps its right
    edge in line with the rest of its column."""
    data, spec = SCIENTIFIC
    tex = render_tikz(build(data, spec), HouseStyle(tikz_latex='H'))
    src = tmp_path / f'{face}.tex'
    src.write_text(FACE_DOC % (FACE_PREAMBLES[face], tex), encoding='utf-8')
    subprocess.run([shutil.which('tectonic'), '--outdir', str(tmp_path), str(src)],
                   capture_output=True, check=False)
    with pdfplumber.open(tmp_path / f'{face}.pdf') as p:
        words = {w['text'].replace('‐', '-'): w
                 for w in p.pages[0].extract_words(x_tolerance=1)}
    assert '-1.95e-05' in words
    assert words['-1.95e-05']['x1'] == pytest.approx(words['3.20e-06']['x1'], abs=0.3)


def test_sideways_table_survives_an_h_default(tmp_path):
    """Left without a placement, the sidewaystable took H and vanished."""
    data, spec = FIX['wide-lab']
    tex = render_tikz(build(data, spec), HouseStyle(
        tikz_container_env='sidewaystable', max_table_width_em=62))
    assert '\\begin{sidewaystable}[p]' in tex
    src = tmp_path / 'sideways.tex'
    src.write_text(SIDEWAYS_DOC % tex, encoding='utf-8')
    subprocess.run([shutil.which('tectonic'), '--outdir', str(tmp_path), str(src)],
                   capture_output=True, check=False)
    with pdfplumber.open(tmp_path / 'sideways.pdf') as p:
        assert len(p.pages) == 2                    # the text, then the table
        # rotated text extracts backwards, so count glyphs rather than read
        assert len(p.pages[1].chars) > 500
