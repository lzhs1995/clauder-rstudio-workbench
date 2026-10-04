"""Small, platform-neutral gates for manuscript result acceptance.

These gates classify evidence; they do not choose model identities, reconstruct
missing data, establish nesting, or approve a manuscript.
"""
from collections import Counter
from decimal import Decimal, InvalidOperation
import math


def count_comparisons(records):
    """Count candidate comparisons separately from manuscript cells.

    A cell ID must be scoped by a document version and table/row/column. A
    comparison ID additionally identifies the producer/model/parameter variant.
    """
    cells=set();comparisons=set();states=Counter()
    for row in records:
        if not all(row.get(k) for k in ('cell_id','comparison_id','status')):
            raise ValueError('Missing cell, comparison identity or status')
        if row['comparison_id'] in comparisons:
            raise ValueError('Duplicate comparison identity')
        cells.add(row['cell_id']);comparisons.add(row['comparison_id'])
        states[row['status']]+=1
    if not comparisons:
        raise ValueError('Empty evidence cannot establish acceptance')
    return dict(comparisons=len(comparisons),unique_cells=len(cells),states=dict(states))


def compare_displayed_number(shown, printed):
    """Distinguish a rounding boundary from an established disagreement.

    `printed` is a finite decimal from a source output, not a full-precision
    estimate. Resolve boundary cases with the actual export/rounding contract.
    """
    shown=str(shown).strip().replace(',','')
    printed=str(printed).strip().replace(',','')
    try:
        a,b=Decimal(shown),Decimal(printed)
    except InvalidOperation:
        raise ValueError('Expected two finite decimal numbers') from None
    if not (a.is_finite() and b.is_finite()):
        raise ValueError('Expected two finite decimal numbers')
    if a==b:return 'equal_printed_value'
    unit=Decimal(1).scaleb(a.as_tuple().exponent)
    difference=abs(a-b)
    if difference==unit/2:return 'rounding_boundary_requires_export_rule'
    return 'equal_at_display_precision' if difference<unit/2 else 'different'


def lrt_evidence_gate(*, statistic, degrees_of_freedom, scaling_correction=1,
                      nested_verified=False, data_contract_verified=False,
                      multiple_imputation=False, pooling_verified=False):
    """Refuse to treat a returned p-value as proof of an admissible LRT."""
    reasons=[]
    values=(statistic,degrees_of_freedom,scaling_correction)
    try:
        statistic,degrees_of_freedom,scaling_correction=map(float,values)
    except (ValueError,TypeError):
        return dict(accepted=False,reasons=['missing_or_nonnumeric_test_evidence'])
    if not all(math.isfinite(v) for v in (statistic,degrees_of_freedom,scaling_correction)):
        reasons.append('nonfinite_test_evidence')
    if statistic<0:reasons.append('negative_difference_statistic')
    if degrees_of_freedom<=0:reasons.append('nonpositive_degrees_of_freedom')
    if scaling_correction<=0:reasons.append('nonpositive_scaling_correction')
    if not nested_verified:reasons.append('nesting_not_verified')
    if not data_contract_verified:reasons.append('sample_and_likelihood_contract_not_verified')
    if multiple_imputation and not pooling_verified:reasons.append('imputation_pooling_not_verified')
    return dict(accepted=not reasons,reasons=reasons)
