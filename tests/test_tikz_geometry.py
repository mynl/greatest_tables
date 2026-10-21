"""Where the TikZ rules land, measured in the compiled PDF.

The other TikZ tests compare TeX source; nothing there can see a rule drawn
through a label. This module compiles fixtures with tectonic, opens the PDF
with pdfplumber (word boxes and line segments, in points) and checks the
geometry both engines promise:

- no vertical rule crosses a word, and each clears the words beside it;
- a vertical ends on the bottom frame rule, and starts on the top frame rule
  or, between groups that share a label above, on that label's underline;
- body rules fall where the rule policy says, at every ``max_rule_depth``.

The fixtures are set in Times by ``Etcher``'s standalone preamble, the face
the width estimates are exact for, so a failure here is geometry, not font.
"""

import shutil
from functools import cache
from pathlib import Path

import pytest

from greater_tables import Etcher, HouseStyle, build, render_tikz
from greater_tables.render.policy import rule_slot

from registry import fixtures

pdfplumber = pytest.importorskip('pdfplumber')
pytestmark = pytest.mark.skipif(shutil.which('tectonic') is None,
                                reason='tectonic not available')

FIX = fixtures()
ENGINES = ('matrix', 'tabular')
CLEARANCE = 1.0         # pt: the least room a vertical leaves a word
TOUCH = 0.6             # pt: how close a rule end must be to the rule it meets

# shapes with vertical rules: the stub rule, column-group breaks, or both
VERTICAL = ['plain', 'row-mi-2', 'row-mi-3', 'row-mi-4', 'deep-stub',
            'subtotals', 'col-mi-2', 'col-mi-3', 'both-mi', 'loss-lab',
            'long-spanner', 'long-headings']

# Two matrix defects, recorded rather than fixed because the matrix output is
# held byte-identical to 6.1.0 (see HouseStyle.tikz_engine): every vertical
# runs through the full head, so at a break of depth 1 or more it crosses the
# spanner label above, and every vertical stops about 1.4pt short of the
# bottom frame. The tabular engine, the default, does neither.
MATRIX_SPANNER = pytest.mark.xfail(
    strict=True, reason='matrix verticals cross spanner labels at depth >= 1')
MATRIX_SHORT = pytest.mark.xfail(
    strict=True, reason='matrix verticals stop short of the bottom frame')


def cases(names, matrix_mark=None):
    """(name, engine) pairs, with the known matrix defects marked."""
    out = []
    for n in names:
        for e in ENGINES:
            mark = matrix_mark if e == 'matrix' else None
            if (n, e) == ('col-mi-3', 'matrix'):
                mark = MATRIX_SPANNER
            out.append(pytest.param(n, e, marks=mark) if mark else (n, e))
    return out


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


def geometry(name, engine, pdf_dir, **style):
    """Compile fixture ``name`` in ``engine`` and return its measured parts."""
    data, spec = FIX[name]
    tag = '-'.join(f'{k}{v}' for k, v in sorted(style.items()))
    tex = render_tikz(build(data, spec), HouseStyle(tikz_engine=engine, **style))
    pdf = Etcher(tex, file_name=f'{name}-{engine}{tag}', base_path=pdf_dir).compile()
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


@pytest.mark.parametrize('name, engine', cases(VERTICAL))
def test_verticals_clear_every_word(name, engine, pdf_dir):
    verticals, _h, words = geometry(name, engine, pdf_dir)
    for v in verticals:
        x = (v['x0'] + v['x1']) / 2
        beside = [w for w in words if w['top'] < v['bottom'] and v['top'] < w['bottom']]
        for w in beside:
            gap = x - w['x1'] if w['x1'] <= x else w['x0'] - x if w['x0'] >= x else -1.0
            assert gap >= CLEARANCE, (
                f'{name}/{engine}: vertical at x={x:.2f} is {gap:.2f}pt from '
                f'{w["text"]!r} [{w["x0"]:.2f}, {w["x1"]:.2f}]')


@pytest.mark.parametrize('name, engine', cases(VERTICAL, MATRIX_SHORT))
def test_verticals_meet_the_rules(name, engine, pdf_dir):
    verticals, horizontals, _w = geometry(name, engine, pdf_dir)
    spans = levels(horizontals)
    frame_top, frame_bottom = spans[0], spans[-1]

    def on(y, span):
        return span[0] - TOUCH <= y <= span[1] + TOUCH

    for v in verticals:
        x = (v['x0'] + v['x1']) / 2
        assert on(v['bottom'], frame_bottom), (
            f'{name}/{engine}: vertical at x={x:.2f} ends at {v["bottom"]:.2f}, '
            f'bottom frame at {frame_bottom}')
        assert any(on(v['top'], s) for s in spans), (
            f'{name}/{engine}: vertical at x={x:.2f} starts at {v["top"]:.2f}, '
            f'on no rule')


@pytest.mark.parametrize('engine', ENGINES)
@pytest.mark.parametrize('depth', ['auto', 0, 1, None])
def test_body_rules_follow_the_policy(engine, depth, pdf_dir):
    """Frame, head rule and bottom frame, plus one rule per qualifying break."""
    data, spec = FIX['row-mi-3']
    doc = build(data, spec)
    style = HouseStyle(max_rule_depth=depth)
    expected = sum(
        1 for row in doc.body[1:]
        if (slot := rule_slot(row.break_depth, doc.n_stub_levels, depth)) is not None
        and style.hrule_widths[slot])
    _v, horizontals, _w = geometry('row-mi-3', engine, pdf_dir, max_rule_depth=depth)
    assert len(levels(horizontals)) == 3 + expected


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
def test_engines_leave_the_same_room_under_the_head(name, pdf_dir):
    """The tabular head once sat 1.7pt tighter on its rule than the matrix's."""
    gaps = {}
    for engine in ENGINES:
        _v, horizontals, words = geometry(name, engine, pdf_dir)
        top, _bottom = head_rule(name, horizontals)
        gaps[engine] = top - max(w['bottom'] for w in words if w['bottom'] < top)
    assert abs(gaps['tabular'] - gaps['matrix']) < 0.5, gaps


@pytest.mark.parametrize('name', SPANNED)
@pytest.mark.parametrize('engine', ENGINES)
def test_spanner_underlines_reach_the_stub_rule(name, engine, pdf_dir):
    """The first group's underline starts at the stub rule, not half an em in."""
    verticals, horizontals, _w = geometry(name, engine, pdf_dir)
    stub = min((v['x0'] + v['x1']) / 2 for v in verticals)
    frame = levels(horizontals)[0]
    top, _bottom = head_rule(name, horizontals)
    under = [h for h in horizontals
             if frame[1] + TOUCH < h['top'] and h['bottom'] < top - TOUCH]
    left = min(h['x0'] for h in under)
    assert abs(left - stub) <= TOUCH, f'underline starts at {left:.2f}, stub rule at {stub:.2f}'
