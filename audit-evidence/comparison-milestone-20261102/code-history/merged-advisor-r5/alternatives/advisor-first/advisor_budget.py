"""Owner-approved $5 UTC-day policy for the local advisor service only.

The pinned engine remains unchanged. ``adopt`` upgrades its existing budget
instance so every agent and the HTTP handler keep the same object and ledger.
Only the cap-dependent summary/reservation methods differ; ledger transactions,
pricing checks, settlements, uncertain holds and UTC clock guards are inherited.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
import sqlite3

from ai_budget import BudgetError, DailyBudget, NANO, token_int


APPROVED_CAP = 5 * NANO
DEFAULT_POLICY = Path(__file__).with_name('budget-policy.json')


class AdvisorDailyBudget(DailyBudget):
    @property
    def daily_cap_nano_usd(self):
        # There is no environment, request or caller-selected cap override.
        return APPROVED_CAP

    @classmethod
    def adopt(cls, budget, *, policy_path=DEFAULT_POLICY):
        try:
            policy = json.loads(Path(policy_path).read_text())
        except (OSError, ValueError, TypeError):
            raise BudgetError('The reviewed local advisor AI budget policy is unavailable.') from None
        if (not isinstance(policy, dict)
                or set(policy) != {'version', 'daily_cap_nano_usd', 'reset_timezone'}
                or type(policy['version']) is not int or policy['version'] != 1
                or type(policy['daily_cap_nano_usd']) is not int
                or policy['daily_cap_nano_usd'] != APPROVED_CAP
                or policy['reset_timezone'] != 'UTC'):
            raise BudgetError('Use the approved $5 UTC-day local advisor AI policy.')
        if type(budget) not in {DailyBudget, cls}:
            raise BudgetError('The local advisor policy requires the reviewed shared budget.')
        # Both are ordinary Python classes with the same instance layout.
        # Preserve object identity: guide_server also closes over this instance.
        budget.__class__ = cls
        return budget

    def summary(self, model='gpt-5.4'):
        day = self.day()
        reason, ready = '', True
        cap = self.daily_cap_nano_usd
        try:
            self.check_rates(model)
            with self.db() as db:
                self._clock(db, day)
                total, measured, held, count = self._amounts(db, day)
                blocked = db.execute("SELECT value FROM ai_meta WHERE key='blocked'").fetchone()
                if blocked:
                    reason = 'AI usage needs reconciliation. Paid requests are paused.'
                    ready = False
        except (BudgetError, sqlite3.Error, OSError):
            ready = False
            reason = 'AI pricing or the persistent budget could not be verified. Paid requests are paused.'
            try:
                with self.db() as db:
                    total, measured, held, count = self._amounts(db, day)
            except Exception:
                total, measured, held, count = cap, 0, cap, 0
        remaining = max(0, cap - total)
        if ready and remaining < 900 * 15000:
            ready = False
            reason = 'The shared daily AI allowance is used. Manual guidance remains available until 00:00 UTC.'
        return {
            'day': day, 'timezone': 'UTC',
            'resetAt': (datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(days=1)).isoformat(),
            'dailyLimitUsd': cap // NANO, 'estimatedUsd': measured / NANO,
            'reservedOrUncertainUsd': held / NANO, 'accountedUsd': total / NANO,
            'remainingUsd': remaining / NANO, 'requestCount': count,
            'canRequest': ready, 'reason': reason,
            'pricingVerifiedAt': self.rates['verified_at'], 'pricingValidUntil': self.rates['valid_until'],
            'label': 'USD estimates from measured tokens; held amounts include requests without final usage. Not an invoice.',
        }

    def reserve(self, input_tokens, output_tokens, model):
        self.check_rates(model)
        i, o = token_int(input_tokens), token_int(output_tokens)
        if not 1 <= i <= 8000 or o != 900:
            raise BudgetError('AI request exceeds the reviewed token limits. Use a shorter question or manual guidance.')
        amount = i * 2500 + o * 15000
        key, day = secrets.token_hex(24), self.day()
        try:
            with self.db() as db:
                self._clock(db, day)
                if db.execute("SELECT value FROM ai_meta WHERE key='blocked'").fetchone():
                    raise BudgetError('AI usage needs reconciliation. Manual guidance remains available.')
                total, *_ = self._amounts(db, day)
                if total + amount > self.daily_cap_nano_usd:
                    raise BudgetError('This request could exceed the shared $5 daily AI limit. Try after 00:00 UTC or use manual guidance.')
                db.execute('INSERT INTO ai_charges VALUES(?,?,NULL,?,?,NULL,?,?,?,NULL,NULL,NULL)',
                           (key, day, amount, amount, 'reserved', i, o))
            return key
        except sqlite3.Error:
            raise BudgetError('The persistent AI budget is unavailable. No paid request was started.') from None
