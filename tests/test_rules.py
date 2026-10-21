"""Rule policy: the slot function, and that all four renderers obey it.

The four-renderer agreement test is the point of this file. Three copies of
the depth comparison had already drifted (text.py drew a depth-3 rule the
others suppressed at 5+ stub levels) without any test noticing, because the
goldens only cover the default policy at 3 stub levels or fewer.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from greater_tables import (
    Cell, Column, HeadCell, HouseStyle, Row, TableDoc, TableSpec, build,
    render_html, render_text, render_tikz,
)
from greater_tables.render.policy import (
    N_RULE_SLOTS, rule_slot, vrule_slot,
)

from transcribe import transcribe

ROOT = Path(__file__).parent.parent
NODE = shutil.which('node')
_TEXT_RULE = re.compile(r'^ *─+$')
# a booktabs rule between body rows; \cmidrulesep must not count
_TIKZ_RULE = re.compile(r'\\c?midrule\[')


# --------------------------------------------------------------- unit table

@pytest.mark.parametrize('n_stub,expected', [
    (1, []),                    # single level: a change is just "next row"
    (2, [0]),
    (3, [0, 1]),
    (4, [0, 1, 2]),
    (5, [0, 1, 2]),             # slots run out before the hierarchy does
    (6, [0, 1, 2]),
])
def test_auto_drops_the_innermost_level(n_stub, expected):
    ruled = [d for d in range(6) if rule_slot(d, n_stub, 'auto') is not None]
    assert ruled == expected


def test_none_never_rules():
    assert all(rule_slot(d, 4, None) is None for d in range(5))


def test_no_break_never_rules():
    assert rule_slot(None, 4, 'auto') is None
    assert rule_slot(None, 4, 3) is None


def test_explicit_int_is_literal():
    """An int ignores the n_stub-2 bound — a 1-level index can rule every row."""
    assert rule_slot(0, 1, 0) == 0          # 'auto' would give None here
    assert rule_slot(0, 2, 0) == 0
    assert rule_slot(1, 2, 0) is None       # still capped at the depth given


def test_deep_breaks_reuse_the_lightest_slot():
    """Past the last slot the weight saturates: no gt-break-3, no IndexError."""
    assert [rule_slot(d, 5, 3) for d in range(5)] == [0, 1, 2, 2, None]
    assert all(s is None or s < N_RULE_SLOTS
               for s in (rule_slot(d, 6, 9) for d in range(6)))


def test_bad_policy_raises():
    with pytest.raises(ValueError, match="must be 'auto'"):
        rule_slot(0, 3, 'deep')


def test_vrule_slot():
    assert vrule_slot(0) == 0
    assert vrule_slot(1) == 1
    assert vrule_slot(2) is None            # default cap
    assert vrule_slot(2, 3) == 2            # three weights, as horizontals have
    assert vrule_slot(3, 3) == 2            # saturates at the last slot
    assert vrule_slot(0, None) is None
    assert vrule_slot(None) is None


# ------------------------------------------------- four-renderer agreement

def _stub_frame(levels: int) -> pd.DataFrame:
    idx = pd.MultiIndex.from_product(
        [list('AB')] * levels, names=[f'L{k}' for k in range(levels)])
    if levels == 1:
        idx = pd.Index(list('AB'), name='L0')
    return pd.DataFrame({'v': range(len(idx))}, index=idx)


def _expected(doc, policy) -> int:
    return sum(rule_slot(r.break_depth, doc.n_stub_levels, policy) is not None
               for i, r in enumerate(doc.body) if i > 0)


@pytest.mark.parametrize('levels', [1, 2, 3, 4, 5])
@pytest.mark.parametrize('policy', ['auto', None, 0, 1, 3])
def test_renderers_agree_with_the_policy(levels, policy):
    doc = build(_stub_frame(levels), TableSpec())
    style = HouseStyle(max_rule_depth=policy)
    want = _expected(doc, policy)

    assert render_html(doc, css='none', style=style).count('gt-break-') == want

    text = render_text(doc, style)
    assert sum(bool(_TEXT_RULE.match(ln)) for ln in text.splitlines()) == want

    # zero every other rule weight so the remaining rules are break rules only
    bare = HouseStyle(max_rule_depth=policy,
                      frame_rule=0, head_rule=0, stub_rule=0, total_rule=0,
                      spanner_rule=0, vrule_widths=(0, 0, 0))
    assert len(_TIKZ_RULE.findall(render_tikz(doc, bare))) == want


@pytest.mark.skipif(NODE is None, reason='node not available')
@pytest.mark.parametrize('flag,policy', [('0', 0), ('none', None), ('3', 3)])
def test_walker_agrees_under_non_default_policy(flag, policy, tmp_path):
    """Python vs walker, live, off the default — the committed transcripts
    only ever cover 'auto', so this is the only check on the JS port."""
    out = tmp_path / 'transcript'
    subprocess.run([NODE, str(ROOT / 'js' / 'transcript.mjs'),
                    '--out', str(out), '--max-rule-depth', flag],
                   check=True, cwd=ROOT, capture_output=True)
    style = HouseStyle(max_rule_depth=policy)
    ir_dir = ROOT / 'tests' / 'golden' / 'ir'
    for path in sorted(ir_dir.glob('*.json')):
        doc = TableDoc.read(path.read_bytes())
        assert transcribe(doc, style) == \
            (out / f'{path.stem}.jsonl').read_text(encoding='utf-8'), path.stem


# ------------------------------------------------------- first-row guard

def _doc_with_break_on_first_row() -> TableDoc:
    """Hand-authored: an engine document never puts a depth on row 0."""
    cols = (Column(key='c0', name=('g',), dtype='string', align='l',
                   role='stub', level=0),
            Column(key='c1', name=('s',), dtype='string', align='l',
                   role='stub', level=1),
            Column(key='c2', name=('v',), dtype='int', align='r'))
    row = Row(cells=(Cell(text='A'), Cell(text='x'), Cell(text='1')),
              break_depth=0)
    return TableDoc(n_stub_levels=2, n_head_levels=1, columns=cols,
                    head=((HeadCell(text='g'), HeadCell(text='s'),
                           HeadCell(text='v')),),
                    body=(row, row), foot=(row,))


def test_first_row_of_each_section_never_rules():
    doc = _doc_with_break_on_first_row()
    # body row 0, foot row 0 suppressed; body row 1 draws
    assert render_html(doc, css='none').count('gt-break-') == 1
    text = render_text(doc)
    assert sum(bool(_TEXT_RULE.match(ln)) for ln in text.splitlines()) == 1
    bare = HouseStyle(frame_rule=0, head_rule=0,
                      stub_rule=0, total_rule=0, spanner_rule=0,
                      vrule_widths=(0, 0, 0))
    assert len(_TIKZ_RULE.findall(render_tikz(doc, bare))) == 1
