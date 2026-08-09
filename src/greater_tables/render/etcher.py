"""Etcher: compile TikZ LaTeX to PDF (and optionally SVG).

The standalone template carries what both TikZ engines need: ``tikz`` with
the matrix/calc libraries for the ``matrix of nodes`` engine, and
``booktabs`` + ``array`` for the one-node ``tabular`` engine. An embedding
document must supply the same — Quarto's default template already does.


greater_tables salvage, modernized: **tectonic** is the default engine (fast,
self-caching — the 5.x ``.fmt`` precompilation dance is gone entirely), with
classic ``pdflatex`` as a fallback. Success is judged by the PDF existing,
not the exit code — MiKTeX's pdflatex exits 1 on recoverable issues while
still producing output. House rules honored: no hardcoded tool paths, no
``.bat`` side files, no ``os.startfile``, pathlib throughout, logging not
print. Outputs cache by content hash.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from pathlib import Path

from .tikz import TIKZ_PREAMBLE

__all__ = ['Etcher']

logger = logging.getLogger(__name__)


class Etcher:
    """Compile a TeX blob containing a tikzpicture to PDF/SVG files.

    Parameters
    ----------
    tex
        LaTeX source containing one ``tikzpicture`` (e.g. ``render_tikz``
        output; any surrounding table environment is stripped — standalone
        cannot host floats).
    file_name
        Output stem; content hash when omitted (deterministic caching).
    base_path
        Working directory; outputs land in ``base_path/'tikz'``.
    tex_engine
        ``'tectonic'`` (default) or ``'pdflatex'`` — name or full path.
    pdf2svg
        Converter executable for ``compile(svg=True)``.
    font_size
        Standalone document point size.
    """

    _document = r"""\documentclass[{font_size}pt, border=5mm]{{standalone}}
\usepackage{{newtxtext,newtxmath}}
\usepackage{{amsfonts}}
\usepackage{{amsmath}}
\usepackage{{url}}
\usepackage{{booktabs}}
\usepackage{{array}}
\usepackage{{tikz}}
\usepackage{{color}}
\usetikzlibrary{{arrows,calc,positioning,matrix,shapes.geometric,backgrounds,fit}}
{preamble}
\def\dfrac{{\displaystyle\frac}}
\def\dint{{\displaystyle\int}}
\begin{{document}}
{tikz_begin}{tikz_code}{tikz_end}
\end{{document}}
"""

    def __init__(self, tex: str, *, file_name: str = '',
                 base_path: str | Path | None = None,
                 tex_engine: str = 'tectonic', pdf2svg: str = 'pdf2svg',
                 font_size: int = 11):
        self.tex = tex
        self.font_size = font_size
        self.tex_engine = tex_engine
        self.pdf2svg = pdf2svg
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.out_path = self.base_path / 'tikz'
        self.out_path.mkdir(parents=True, exist_ok=True)
        stem = file_name or hashlib.sha256(tex.encode()).hexdigest()[:12]
        self.file_path = self.out_path / stem

    def compile(self, *, svg: bool = False) -> Path:
        """Compile to PDF (and SVG when requested); return the output path."""
        parts = re.split(r'(\\begin{tikz(?:cd|picture)}'
                         r'|\\end{tikz(?:cd|picture)})', self.tex)
        if len(parts) < 4:
            raise ValueError('no tikzpicture found in input')
        tikz_begin, tikz_code, tikz_end = parts[1:4]
        tex_path = self.file_path.with_suffix('.tex')
        tex_path.write_text(self._document.format(
            font_size=self.font_size, preamble=TIKZ_PREAMBLE,
            tikz_begin=tikz_begin, tikz_code=tikz_code, tikz_end=tikz_end),
            encoding='utf-8', newline='\n')

        pdf_path = tex_path.with_suffix('.pdf')
        if Path(self.tex_engine).stem == 'tectonic':
            self._run([self.tex_engine, '--outdir', str(self.out_path),
                       str(tex_path)])
        else:
            self._run([self.tex_engine, '-interaction=nonstopmode',
                       f'--output-directory={self.out_path}', str(tex_path)],
                      cwd=self.out_path)
            for ext in ('.aux',):
                side = tex_path.with_suffix(ext)
                if side.exists():
                    side.unlink()
        if not pdf_path.exists():
            raise RuntimeError(
                f'{self.tex_engine} produced no PDF — see '
                f'{tex_path.with_suffix(".log")}')
        if not svg:
            return pdf_path
        svg_path = tex_path.with_suffix('.svg')
        self._run([self.pdf2svg, str(pdf_path), str(svg_path)],
                  strict=True)
        return svg_path

    def display(self):
        """Show the compiled SVG inline (Jupyter; lazy IPython import)."""
        from IPython.display import SVG, display
        display(SVG(str(self.file_path.with_suffix('.svg'))))

    def _run(self, cmd: list[str], cwd: Path | None = None,
             strict: bool = False) -> None:
        """Run a tool; nonzero exit logs (or raises when strict).

        TeX engines report recoverable issues via exit codes while still
        producing output, so the caller judges success by the artifact.
        """
        logger.info('running: %s', ' '.join(cmd))
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.stdout:
            logger.debug('output tail: %s', result.stdout.strip()[-250:])
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or '').strip()[-500:]
            if strict:
                raise RuntimeError(
                    f'{cmd[0]} failed ({result.returncode}): {tail}')
            logger.warning('%s exited %s: %s', cmd[0], result.returncode, tail)
