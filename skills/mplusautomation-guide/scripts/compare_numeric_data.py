"""Compare aligned numeric CSV or free-format data without exposing row identifiers."""
import csv
from decimal import Decimal, InvalidOperation
import hashlib
from itertools import zip_longest
from pathlib import Path


def file_hash(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def compare_numeric_data(left, right, *, key, left_names=None, right_names=None,
                         columns=None, left_missing=('',), right_missing=('',), atol='0'):
    """Explicit names select whitespace format; omitted names select CSV with header.

    Keys must be unique, numeric, nonmissing and in identical order. Reorder an
    isolated copy explicitly before calling when alignment differs. The caller
    supplies missing tokens from the actual data contract, not inferred defaults.
    """
    paths = [Path(left), Path(right)]
    hashes = [file_hash(path) for path in paths]
    tolerance = Decimal(str(atol))
    if not tolerance.is_finite() or tolerance < 0:
        raise ValueError('Invalid absolute tolerance')

    def rows(handle, supplied):
        if supplied is None:
            reader = csv.reader(handle)
            names = next(reader)
        else:
            names = list(supplied)
            reader = (line.split() for line in handle if line.strip())
        if not names or len(set(names)) != len(names) or key not in names:
            raise ValueError('Invalid or duplicate schema columns')
        return names, reader

    def number(token, missing):
        if token in missing:
            return None
        try:
            result = Decimal(token)
        except InvalidOperation:
            raise ValueError('Nonnumeric value in selected columns') from None
        if not result.is_finite():
            raise ValueError('Undeclared nonfinite value')
        return result

    with paths[0].open(encoding='utf-8-sig', newline='') as fa, paths[1].open(encoding='utf-8-sig', newline='') as fb:
        na, ra = rows(fa, left_names)
        nb, rb = rows(fb, right_names)
        selected = list(columns) if columns is not None else [name for name in na if name in nb and name != key]
        if not selected or len(set(selected)) != len(selected) or any(n not in na or n not in nb for n in selected):
            raise ValueError('Selected columns must exist uniquely in both schemas')
        indices = [(name, na.index(name), nb.index(name)) for name in selected]
        counts = {name: dict(changed=0, missing_changed=0, max_absolute_difference=Decimal(0)) for name in selected}
        seen = set()
        count = 0
        for count, (a, b) in enumerate(zip_longest(ra, rb), start=1):
            if a is None or b is None:
                raise ValueError('Row counts differ')
            if len(a) != len(na) or len(b) != len(nb):
                raise ValueError('Row width differs from declared schema')
            ka = number(a[na.index(key)], left_missing)
            kb = number(b[nb.index(key)], right_missing)
            if ka is None or kb is None or ka != kb or ka in seen:
                raise ValueError('Missing, duplicate, or misaligned row keys')
            seen.add(ka)
            for name, ia, ib in indices:
                va, vb = number(a[ia], left_missing), number(b[ib], right_missing)
                stat = counts[name]
                if va is None or vb is None:
                    different = (va is None) != (vb is None)
                    stat['missing_changed'] += int(different)
                else:
                    delta = abs(va - vb)
                    stat['max_absolute_difference'] = max(stat['max_absolute_difference'], delta)
                    different = delta > tolerance
                stat['changed'] += int(different)
    if count == 0:
        raise ValueError('Empty data is not comparison evidence')
    if hashes != [file_hash(path) for path in paths]:
        raise ValueError('Data changed during comparison')
    for stat in counts.values():
        stat['max_absolute_difference'] = str(stat['max_absolute_difference'])
    return dict(rows=count, key_order_equal=True, atol=str(tolerance),
        left=dict(path=str(paths[0]), sha256=hashes[0], columns=len(na)),
        right=dict(path=str(paths[1]), sha256=hashes[1], columns=len(nb)),
        left_only_columns=[name for name in na if name not in nb],
        right_only_columns=[name for name in nb if name not in na],
        columns_compared=len(selected), changed_columns={n:s for n,s in counts.items() if s['changed']},
        maximum_differences={n:s['max_absolute_difference'] for n,s in counts.items()})
