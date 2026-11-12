"""Owner-approved $5 UTC-day policy for the local advisor service only.

The pinned engine remains unchanged. ``adopt`` upgrades its existing budget
instance so every agent and the HTTP handler keep the same object and ledger.
The local review refreshes pricing dates for this service. Ledger transactions,
pricing checks, settlements, uncertain holds and UTC clock guards are inherited.
"""
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import secrets
import sqlite3

from ai_budget import BudgetError, DailyBudget, NANO, token_int
from request_limits import INPUT_TOKENS, OUTPUT_TOKENS
from advisor_models import MODELS


APPROVED_CAP = 5 * NANO
DEFAULT_POLICY = Path(__file__).with_name('budget-policy.json')
LOGGER = logging.getLogger(__name__)


class AdvisorDailyBudget(DailyBudget):
    # Owner-approved local testing policy: check today's accounted usage when
    # admitting a turn, then let its bounded stages/recovery finish. The final
    # turn may cross the threshold; this is not a worst-case spending ceiling.
    finish_admitted_turn = True

    @property
    def daily_cap_nano_usd(self):
        # There is no environment, request or caller-selected cap override.
        return APPROVED_CAP

    @classmethod
    def adopt(cls, budget, *, policy_path=DEFAULT_POLICY, pricing_review_path=None):
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
        if pricing_review_path is not None:
            try:
                review = json.loads(Path(pricing_review_path).read_text())
                if not isinstance(review, dict) or set(review) != {'verified_at', 'valid_until'}:
                    raise ValueError('Expected review dates only.')
                for timestamp in review.values():
                    datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
            except (OSError, ValueError, TypeError):
                raise BudgetError('The local advisor AI pricing review is invalid.') from None
            budget.rates = {**budget.rates, **review}
        # Both are ordinary Python classes with the same instance layout.
        # Preserve object identity: guide_server also closes over this instance.
        budget.__class__ = cls
        return budget

    def check_rates(self, model):
        if model == 'gpt-5.4':
            return super().check_rates(model)
        # Share the existing review expiry and fail-closed spending policy.
        super().check_rates('gpt-5.4')
        if model not in MODELS:
            raise BudgetError('Use a reviewed AI model.')

    def settle_model(self, key, response, model):
        if model == 'gpt-5.4':
            return self.settle(key, response)
        spec = MODELS[model]
        try:
            usage = response['usage']
            details = usage['input_tokens_details']
            inputs = token_int(usage['input_tokens'])
            cached = token_int(details['cached_tokens'])
            written = token_int(details.get('cache_write_tokens', 0))
            outputs = token_int(usage['output_tokens'])
            # Sol uses the Responses API's default 30-minute lifetime. Cache
            # reads and writes are disjoint portions of the total input.
            writes = details.get('cache_write_tokens_details')
            cache_valid = not written or bool(spec.cache_write_rate)
            if 'cache_write_tokens_details' in details:
                cache_valid = (cache_valid and token_int(writes['ttl_30m_tokens']) == written
                               and token_int(writes['ttl_12h_tokens']) == 0)
            cost = ((inputs - cached - written) * spec.input_rate + cached * spec.cached_rate
                    + written * spec.cache_write_rate + outputs * spec.output_rate)
            tier = 'standard' if spec.provider == 'Anthropic' else 'default'
            valid = (response['model'] == model and response['service_tier'] in {tier, 'default'}
                     and response['status'] in {'completed', 'incomplete'}
                     and token_int(usage['total_tokens']) == inputs + outputs
                     and cached + written <= inputs and cache_valid)
            failure = 'receipt_mismatch' if not valid else 'reservation_bounds'
        except (KeyError, TypeError, BudgetError):
            valid = False
            failure = 'receipt_fields'
        with self.db() as db:
            row = db.execute('SELECT reserved,status,input_bound,output_bound FROM ai_charges WHERE id=?', (key,)).fetchone()
            if not row:
                raise BudgetError('AI reservation could not be found.')
            if row[1] == 'settled':
                return
            if valid and inputs <= row[2] and outputs <= row[3] and cost <= row[0]:
                db.execute("""UPDATE ai_charges SET status='settled',finished_day=?,charged=?,measured=?,
                              input_tokens=?,cached_tokens=?,output_tokens=? WHERE id=?""",
                           (self.day(), cost, cost, inputs, cached, outputs, key))
                return
            db.execute("UPDATE ai_charges SET status='uncertain' WHERE id=?", (key,))
            db.execute("INSERT OR REPLACE INTO ai_meta VALUES('blocked','unverified usage')")
        LOGGER.warning('Daylight usage verification model=%s code=%s', model, failure)
        raise BudgetError('AI usage could not be verified. The reservation remains held.')

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
        if ready and remaining == 0:
            ready = False
            reason = 'The shared $5 daily AI limit has been reached. It resets at 00:00 UTC.'
        return {
            'day': day, 'timezone': 'UTC',
            'resetAt': (datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(days=1)).isoformat(),
            'dailyLimitUsd': cap // NANO, 'estimatedUsd': measured / NANO,
            'maxInputTokens': INPUT_TOKENS, 'maxOutputTokens': OUTPUT_TOKENS,
            'reservedOrUncertainUsd': held / NANO, 'accountedUsd': total / NANO,
            'remainingUsd': remaining / NANO, 'requestCount': count,
            'canRequest': ready, 'reason': reason,
            'pricingVerifiedAt': self.rates['verified_at'], 'pricingValidUntil': self.rates['valid_until'],
            'label': 'USD estimates from measured tokens; held amounts include requests without final usage. Not an invoice.',
        }

    def reserve(self, input_tokens, output_tokens, model):
        self.check_rates(model)
        i, o = token_int(input_tokens), token_int(output_tokens)
        spec = MODELS[model]
        if i < 1 or o != spec.output_tokens:
            raise BudgetError('Use a verified input count and the configured output allowance.')
        amount = i * max(spec.input_rate, spec.cache_write_rate) + o * spec.output_rate
        key, day = secrets.token_hex(24), self.day()
        try:
            with self.db() as db:
                self._clock(db, day)
                if db.execute("SELECT value FROM ai_meta WHERE key='blocked'").fetchone():
                    raise BudgetError('AI usage needs reconciliation. Manual guidance remains available.')
                total, *_ = self._amounts(db, day)
                if total >= self.daily_cap_nano_usd:
                    raise BudgetError('The shared $5 daily AI limit has been reached. It resets at 00:00 UTC.')
                db.execute('INSERT INTO ai_charges VALUES(?,?,NULL,?,?,NULL,?,?,?,NULL,NULL,NULL)',
                           (key, day, amount, amount, 'reserved', i, o))
            return key
        except sqlite3.Error:
            raise BudgetError('The persistent AI budget is unavailable. No paid request was started.') from None
