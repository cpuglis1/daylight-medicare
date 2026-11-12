"""D146 candidate arithmetic. Monetary state is in integer US cents."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

METHOD = 'd146-retail-average/1'


class EstimateHold(ValueError):
    """A consequential input or method is outside the candidate scope."""


def money(value):
    return int((value * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Fill:
    day: date
    order: int
    rxcui: str
    price_cents: int
    deductible_applies: bool
    copay_cents: int | None
    coinsurance: Decimal | None
    minimum_cents: int = 0
    maximum_cents: int = 0


def calculate(fills, *, deductible, standard_deductible, threshold, benefit):
    """Run a single shared ledger in date and explicitly reported same-day order.

    Enhanced coverage has additional TrOOP credits. Support it only when
    conservative bounds prove those credits cannot alter any payment.
    """
    member = gross = paid_deductible = 0
    ledger = []
    for fill in sorted(fills, key=lambda row: (row.day, row.order)):
        price = fill.price_cents
        remaining = max(0, deductible - paid_deductible)
        if member >= standard_deductible:
            remaining = 0
        if benefit == 'EA':
            if gross + price >= threshold:
                raise EstimateHold('enhanced_troop_threshold_unresolved')
            # Before the DS threshold, a deductible-applicable fill is safe
            # only when supplemental credits cannot waive any deductible cents.
            if fill.deductible_applies and remaining and gross + min(price, remaining) > standard_deductible:
                raise EstimateHold('enhanced_deductible_credit_unresolved')
        if member >= threshold:
            ded = initial = 0
            phase = 'catastrophic'
        else:
            ded = min(price, remaining, threshold - member) if fill.deductible_applies else 0
            basis = price - ded
            share = fill.copay_cents
            if share is None:
                share = money(Decimal(basis) / 100 * fill.coinsurance)
                share = max(fill.minimum_cents, share)
                if fill.maximum_cents:
                    share = min(fill.maximum_cents, share)
            # A nonzero fixed copay or bound on a deductible-straddling
            # claim needs a plan-specific split rule. Plain coinsurance is
            # applied to the balance after the deductible.
            if (0 < ded < price and ded < threshold - member
                    and (fill.copay_cents or fill.minimum_cents or fill.maximum_cents)):
                raise EstimateHold('deductible_split_rule_unresolved')
            initial = min(basis, share, threshold - member - ded)
            phase = 'deductible_and_initial' if ded and initial else 'deductible' if ded else 'initial'
        paid_deductible += ded
        member += ded + initial
        gross += price
        ledger.append({'date': fill.day.isoformat(), 'order': fill.order, 'rxcui': fill.rxcui,
                       'phase': phase, 'average_fill_cents': price, 'deductible_cents': ded,
                       'initial_cents': initial, 'member_cents': ded + initial,
                       'threshold_reached': member == threshold})
    return {'drug_spending_cents': member, 'ledger': ledger}
