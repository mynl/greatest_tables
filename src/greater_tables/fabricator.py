"""Fabricate synthetic pandas DataFrames for tests and fixtures.

Port of greater_tables ``fabrications.py`` with fixes recorded in the 1.0.0
CHANGELOG entry. Fully deterministic under a seed: datetime columns derive
from a fixed ``now`` reference (default 2026-01-01), never the wall clock —
this is what makes golden-file fixtures possible.
"""

from __future__ import annotations

import hashlib
import re
from collections import deque
from collections.abc import Sequence
from importlib.resources import files
from itertools import cycle, islice, product
from math import prod
from pathlib import PurePosixPath

import numpy as np
import pandas as pd

__all__ = ['Fabricator', 'quick_fab']

DEFAULT_NOW = pd.Timestamp('2026-01-01')


def random_datetime_series(n: int, *, rng: np.random.Generator,
                           now: pd.Timestamp) -> pd.Series:
    """Generate ``n`` random datetimes ending at ``now``.

    A span unit (days/months/years) and length are drawn from ``rng``, then
    datetimes are sampled uniformly over ``[now - span, now]``.

    Parameters
    ----------
    n
        Number of datetimes.
    rng
        Source of randomness.
    now
        Fixed end-of-range reference; passing a constant makes the series
        deterministic under a seeded ``rng``.

    Returns
    -------
    pandas.Series
        ``datetime64[ns]`` values with nanosecond sampling.
    """
    unit = rng.choice(['days', 'months', 'years'])
    default_spans = {'days': 730, 'months': 120, 'years': 16}
    k = int(rng.integers(0, default_spans[unit]))
    start = now - pd.DateOffset(**{unit: k})
    u = rng.random(n)
    ns = start.value + (now.value - start.value) * u
    return pd.Series(pd.to_datetime(ns.astype('int64')), name='datetime')


class Fabricator:
    """Fabricate small synthetic DataFrames covering GT2's fixture space.

    Parameters
    ----------
    decorate : bool
        Append type hints (" year", " ratio", " date", " time") to generated
        metric names.
    pyarrow : bool
        Convert fabricated frames to pyarrow-backed dtypes.
    seed : int, optional
        RNG seed; one is drawn from entropy when omitted. Always pass a seed
        for fixtures.
    now : pandas.Timestamp or str
        Reference timestamp for date/time columns. Fixed default keeps
        seeded output identical across runs.

    Notes
    -----
    Column type codes for ``data_spec``::

        d   date                    r   ratio (small floats)
        f   float                   sN  string, N words
        h   hash                    t   time (minute grid)
        i   integer                 v   extreme-range float
        l   log float (wide range)  wN  string, random length ~N words
        p   path (filename)         x   TeX expression
                                    y   year
    """

    metric_roots = ['absorption', 'acceleration', 'account', 'activation', 'adjustment', 'allocation', 'amplitude', 'approval', 'asset', 'atom', 'attrition', 'balance', 'band', 'binding', 'cancellation', 'capacitance', 'capital', 'cashflow', 'category', 'cell', 'charge', 'claim', 'commission', 'compound', 'concentration', 'conductivity', 'constraint', 'consumption', 'conversion', 'correlation', 'cost', 'count', 'coverage', 'credit', 'current', 'debt', 'decay', 'decibel', 'deductible', 'deficit', 'deflator', 'demand', 'density', 'development', 'diffusion', 'discount', 'distribution', 'dividend', 'dose', 'duration', 'earnings', 'efficiency', 'elasticity', 'employment', 'energy', 'entropy', 'enzyme', 'estimate', 'excess', 'exhaustion', 'expense', 'exposure', 'failure', 'field', 'flux', 'force', 'frequency', 'funding', 'gdp', 'gene', 'gradient', 'growth', 'half_life', 'incidence', 'income', 'index', 'indicator', 'inequality', 'inflation', 'inhibition', 'input', 'intensity', 'investment',
                    'kurtosis', 'lapse', 'layer', 'leverage', 'liability', 'limit', 'loss', 'luminosity', 'margin', 'mass', 'molecule', 'momentum', 'mortality', 'neutron', 'noise', 'operating', 'output', 'penalty', 'photon', 'policy', 'portfolio', 'potential', 'power', 'preference', 'premium', 'pressure', 'price', 'productivity', 'profit', 'protein', 'proton', 'provision', 'radiation', 'rate', 'ratio', 'reaction', 'recovery', 'reflection', 'refraction', 'renewal', 'reserve', 'residual', 'resistance', 'return', 'revenue', 'risk', 'sample', 'savings', 'scenario', 'score', 'sector', 'settlement', 'severity', 'shock', 'shortfall', 'signal', 'skewness', 'spread', 'strain', 'stress', 'subsidy', 'supply', 'tail', 'tariff', 'tax', 'temperature', 'tension', 'term', 'threshold', 'trade', 'trend', 'turbulence', 'unemployment', 'uptake', 'utility', 'utilization', 'valuation', 'variance', 'velocity', 'viscosity', 'volatility', 'voltage', 'volume', 'wage', 'wavelength', 'wealth', 'weight', 'yield']

    def __init__(self, decorate: bool = False, pyarrow: bool = False,
                 seed: int | None = None,
                 now: pd.Timestamp | str = DEFAULT_NOW):
        self._last_args: dict = {}
        self.seed = int(seed if seed is not None
                        else np.random.SeedSequence().entropy)
        self.decorate = decorate
        self.pyarrow = pyarrow
        self.now = pd.Timestamp(now)
        self.rng = np.random.default_rng(self.seed)

        # word pools: metric-level names, general words, TeX expressions
        roots = self.metric_roots[:]
        self.rng.shuffle(roots)
        self._metric_namer = cycle(roots)

        data = files('greater_tables').joinpath('data')
        word_list = data.joinpath('words-12.md').read_text(
            encoding='utf-8').split('\n')
        shuffled = word_list[:]
        self.rng.shuffle(shuffled)
        self._word_gen = cycle(shuffled)
        self._word_list = word_list[:]

        with data.joinpath('tex_list.csv').open('r', encoding='utf-8') as f:
            tex_list = pd.read_csv(f, index_col=0)['expr'].to_list()
        # drop long words (would dominate width) and | (breaks tables)
        pat = re.compile(r'(?<!\\)\b[a-z]{4,}\b|\|')
        tex_list = [t for t in tex_list if not pat.search(t) and len(t) <= 50]
        self.rng.shuffle(tex_list)
        self._tex_gen = cycle(tex_list)

        # word counts for string index values sampled from this distribution
        self.index_value_lengths = [1] * 10 + [2] * 4 + [3]
        self.cache: deque = deque(maxlen=10)

    # ------------------------------------------------------------ reshaping
    @staticmethod
    def roll_columns(df: pd.DataFrame, levels: int = -1) -> pd.DataFrame:
        """Rotate the column MultiIndex levels by ``levels`` and re-sort."""
        idx = df.columns.reorder_levels(np.roll(range(df.columns.nlevels), levels))
        df = df.copy()
        df.columns = idx
        return df.sort_index(axis=1)

    @staticmethod
    def drop_singleton_levels(df: pd.DataFrame) -> pd.DataFrame:
        """Drop index/column levels holding a single value (keep at least one)."""
        if isinstance(df.index, pd.MultiIndex):
            drop = [i for i, lvl in enumerate(df.index.levels) if len(lvl) == 1]
            if len(drop) == df.index.nlevels:
                drop.pop()
            if drop:
                df = df.droplevel(drop)
        if isinstance(df.columns, pd.MultiIndex):
            drop = [i for i, lvl in enumerate(df.columns.levels) if len(lvl) == 1]
            if len(drop) == df.columns.nlevels:
                drop.pop()
            if drop:
                df = df.droplevel(drop, axis=1)
        return df

    # ------------------------------------------------------------- building
    def make(self, rows: int, data_spec, *, index_levels: int = 1,
             index_names=None, column_groups: int = 1, column_levels: int = 1,
             column_names=None, metric_name_spec='', missing: float = 0.0,
             simplify: bool = True, oversample: int = 1) -> pd.DataFrame:
        """Fabricate a DataFrame to a specification.

        Parameters
        ----------
        rows
            Number of body rows.
        data_spec
            Per-metric type codes (see class notes): a string like
            ``'s3sfid'``, a list of codes, or an int meaning that many floats.
        index_levels
            Row MultiIndex depth.
        index_names, column_names
            Level names; generated when omitted.
        column_groups, column_levels
            Column MultiIndex shape: total columns = metrics × groups.
        metric_name_spec
            ``''`` for generated names, a list of names, or a type-code spec
            whose generated values become the names.
        missing
            Proportion of values per column replaced with NaN.
        simplify
            Drop index/column levels that hold a single value. Note this can
            reduce the requested level count on small frames.
        oversample
            Fabricate ``oversample × rows`` then keep the first ``rows`` —
            more distinct index values at small sizes.

        Returns
        -------
        pandas.DataFrame
        """
        assert column_groups == 0 or column_levels <= column_groups, \
            'Column levels must be <= groups'
        assert index_names is None or len(index_names) == index_levels, \
            'Index names must have length index_levels'
        assert column_names is None or len(column_names) == column_levels, \
            'Column names must have length column_levels'

        self._last_args = dict(
            rows=rows, data_spec=data_spec, index_levels=index_levels,
            index_names=index_names, column_groups=column_groups,
            column_levels=column_levels, column_names=column_names,
            metric_name_spec=metric_name_spec, missing=missing,
            simplify=simplify, oversample=oversample)

        spec = self._parse_colspec(data_spec)
        metrics = len(spec)
        if oversample > 1:
            df = self.make(
                oversample * rows, spec, index_levels=index_levels,
                index_names=index_names, column_groups=column_groups,
                column_levels=column_levels, column_names=column_names,
                metric_name_spec=metric_name_spec, missing=missing,
                simplify=simplify, oversample=1)
            return df.iloc[:rows, :]

        inames = index_names or [f'i_{i}' for i in range(index_levels)]
        index = pd.MultiIndex.from_tuples(
            islice(product(*(self._generate_column('s', v)
                             for v in self.primes_for_product(rows, index_levels))),
                   rows),
            names=inames)

        if metric_name_spec == '':
            metric_names = [self.metric_name(t) for t in spec]
        elif isinstance(metric_name_spec, (list, tuple)):
            metric_names = [str(n).strip() for n in metric_name_spec]
            assert len(metric_names) == metrics, \
                f'metric_name_spec must have a name for each of {metrics} metrics'
        else:
            name_spec = self._parse_colspec(metric_name_spec)
            assert len(name_spec) == metrics, \
                'metric name spec not consistent with data spec'
            metric_names = [self._generate_column(dt, 1).iloc[0]
                            for dt in name_spec]

        if column_groups > 0:
            cnames = (column_names or
                      [f'c_{i}' for i in range(column_levels)]) + ['metric']
            pfp = self.primes_for_product(column_groups, column_levels)
            groups = islice(product(*(self._generate_column('s', v) for v in pfp)),
                            column_groups)
            tuples = [(*g, m) for g, m in product(groups, metric_names)]
            columns = pd.MultiIndex.from_tuples(tuples, names=cnames)
        else:
            column_groups = 1
            columns = pd.Index(metric_names, name='metric')

        df = pd.DataFrame(index=index, columns=columns)
        for c, dt in zip(df.columns, spec * column_groups):
            df[c] = self._generate_column(dt, rows).values

        if missing > 0:
            df = self._insert_missing(df, missing)
        if simplify:
            df = self.drop_singleton_levels(df)
        if self.pyarrow:
            df = df.convert_dtypes(dtype_backend='pyarrow')

        self.cache.appendleft(df)
        return df

    def another(self) -> pd.DataFrame:
        """Fabricate another DataFrame with the last ``make`` arguments."""
        return self.make(**self._last_args)

    def random(self, rows: int = 0, columns: int = 0, index_levels: int = 0,
               omit: str = '') -> pd.DataFrame:
        """Fabricate a DataFrame with randomly chosen shape and types.

        Parameters
        ----------
        rows, columns, index_levels
            0 means choose randomly.
        omit
            Type codes to exclude.

        Returns
        -------
        pandas.DataFrame
        """
        if columns == 0:
            metrics = int(self.rng.integers(1, 11))
            if metrics > 5:
                column_groups = column_levels = 1
            else:
                column_groups = int(self.rng.integers(1, 6 + 1))
                column_levels = int(self.rng.integers(1, column_groups + 1))
        else:
            column_groups = column_levels = 1
            metrics = columns
        index_levels = index_levels or int(self.rng.integers(1, 3 + 1))
        if rows == 0:
            rows = int(self.rng.integers(
                5 * (column_groups + index_levels),
                10 * (column_groups + index_levels) + 1))

        valid = [t for t in ['f', 's2', 's', 'i', 'l', 'f', 'f', 'd', 'f', 'i',
                             's3', 'l', 'h', 't', 'p', 'x', 'r', 'y']
                 if t not in omit]
        data_spec = ''.join(self.rng.choice(valid, size=metrics))
        missing = round(float(self.rng.uniform(0, 0.15)), 2)
        return self.make(rows=rows, data_spec=data_spec,
                         index_levels=index_levels,
                         column_groups=column_groups,
                         column_levels=column_levels, missing=missing)

    # ------------------------------------------------------------ internals
    def _parse_colspec(self, spec) -> list[str]:
        """Normalize a data spec to a list of type codes (idempotent)."""
        if isinstance(spec, int):
            return ['f'] * spec
        if isinstance(spec, (list, tuple)):
            return list(spec)
        return re.findall(r's\d+|w\d+|[a-z]', spec)

    def _make_sentences(self, n_sentences: int,
                        sentence_length: int | Sequence[int] = 10) -> list[str]:
        """Build sentences drawing roughly equally from the word pool."""
        lengths = ([sentence_length] * n_sentences
                   if isinstance(sentence_length, int)
                   else [int(x) for x in sentence_length])
        pool: list[str] = []
        while len(pool) < sum(lengths):
            block = list(self._word_list)
            self.rng.shuffle(block)
            pool.extend(block)
        sentences, position = [], 0
        for length in lengths:
            sentences.append(' '.join(pool[position:position + length]))
            position += length
        return sentences

    def _generate_column(self, dtype: str, n: int) -> pd.Series:
        """Generate ``n`` values of the given type code."""
        if dtype.startswith('s'):
            max_words = int(dtype[1:]) if len(dtype) > 1 else 1
            return pd.Series(self._make_sentences(n, max_words))
        if dtype.startswith('w'):
            mu = max(2, int(dtype[1:]) if len(dtype) > 1 else 2)
            # negative binomial word counts, high cv; parameterization matches
            # scipy's nbinom(n, p) that the original used
            m, v = mu - 1, 0.75 * mu / (mu - 1)
            if v ** 2 * m <= 1:
                v = 1 + 1 / m ** 0.5
            p = 1 / (v ** 2 * m)
            size = m / (v ** 2 * m - 1)
            lengths = self.rng.negative_binomial(size, p, size=n)
            return pd.Series(self._make_sentences(n, lengths))
        if dtype == 'f':
            return pd.Series(self.rng.normal(loc=100000, scale=250000, size=n))
        if dtype == 'r':
            return pd.Series(self.rng.normal(loc=0.5, scale=0.35, size=n))
        if dtype == 'l':
            scale = 10.0
            return pd.Series(np.exp(self.rng.normal(
                loc=-scale ** 2 / 2 + 15, scale=scale, size=n)))
        if dtype == 'v':
            sc = 5
            return pd.Series(np.exp(self.rng.normal(
                loc=-sc ** 2 / 2 + 10, scale=sc, size=n)))
        if dtype == 'i':
            return pd.Series(self.rng.normal(80_000, 35_000, size=n)).astype(int)
        if dtype == 'd':
            return random_datetime_series(n, rng=self.rng, now=self.now)
        if dtype == 'y':
            return pd.Series(self.rng.integers(1990, 2031, n))
        if dtype == 't':
            start = self.now - pd.Timedelta(days=365 * 2)
            minutes = self.rng.integers(0, 2 * 365 * 24 * 60, size=n)
            return pd.Series([start + pd.Timedelta(minutes=int(m))
                              for m in minutes])
        if dtype == 'h':
            return pd.Series([
                hashlib.blake2b(f'val{i}'.encode(), digest_size=32).hexdigest()
                for i in range(n)])
        if dtype == 'p':
            return pd.Series([str(PurePosixPath('/data') / self.word() / f'{i}.dat')
                              for i in range(n)])
        if dtype == 'x':
            return pd.Series([self.tex() for _ in range(n)])
        raise ValueError(f'Unknown dtype: {dtype}')

    def metric_name(self, type_hint: str) -> str:
        """Return a one-word metric name, optionally decorated by type."""
        nm = next(self._metric_namer)
        if self.decorate:
            suffix = {'y': ' year', 'r': ' ratio', 'd': ' date', 't': ' time'}
            nm += suffix.get(type_hint, '')
        return nm

    def word(self) -> str:
        """Return the next word from the shuffled pool (cycles eventually)."""
        return next(self._word_gen)

    def tex(self) -> str:
        """Return the next TeX expression from the shuffled pool."""
        return next(self._tex_gen)

    def _insert_missing(self, df: pd.DataFrame, prop: float) -> pd.DataFrame:
        """Replace ``prop`` of each column's values with NaN (at least one)."""
        n_rows = df.shape[0]
        if prop <= 0 or n_rows == 0:
            return df
        for col in df.columns:
            n_missing = max(1, int(np.floor(prop * n_rows)))
            rows = self.rng.choice(n_rows, size=n_missing, replace=False)
            df.iloc[rows, df.columns.get_loc(col)] = np.nan
        return df

    # ------------------------------------------------------------ primes
    @staticmethod
    def _is_prime(p: int) -> bool:
        if p < 2:
            return False
        if p == 2:
            return True
        if p % 2 == 0:
            return False
        return all(p % i for i in range(3, int(p ** 0.5) + 1, 2))

    @staticmethod
    def _next_prime(p: int) -> int:
        if p < 2:
            return 2
        p += 1 if p % 2 == 0 else 2
        while not Fabricator._is_prime(p):
            p += 2
        return p

    def primes_for_product(self, n: int, v: int,
                          shuffle: bool = False) -> list[int]:
        """Return ``v`` distinct primes whose product is at least ``n``.

        Used to size index-level cardinalities so their product covers the
        requested row count.
        """
        if n == 1:
            return [1]
        p0 = max(1, int(n ** (1 / v)))
        primes: list[int] = []
        p = Fabricator._next_prime(max(p0 - 1, 1))
        while len(primes) < v:
            primes.append(p)
            p = Fabricator._next_prime(p)
        while prod(primes := sorted(primes)) < n:
            primes[-1] = Fabricator._next_prime(primes[-1])
        if shuffle:
            self.rng.shuffle(primes)
        return primes


def quick_fab(rows: int = 10, data_spec: str = 's3sfid', *,
              seed: int | None = None, pyarrow: bool = False,
              **kwargs) -> pd.DataFrame:
    """One-stop fabrication of a DataFrame (see :meth:`Fabricator.make`)."""
    return Fabricator(pyarrow=pyarrow, seed=seed).make(rows, data_spec, **kwargs)
