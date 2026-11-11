"""Owner-approved $15 per-provider UTC-day allowance for the local advisor.

Raised from $5 on November 8, 2026 (owner approval in chat, 21:35 ET) for the
20-persona live evaluation; the fixed policy file must match this constant.

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


APPROVED_CAP = 15 * NANO
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
                or set(policy) != {'version', 'daily_cap_nano_usd', 'reset_timezone', 'scope'}
                or type(policy['version']) is not int or policy['version'] != 2
                or policy['scope'] != 'provider'
                or type(policy['daily_cap_nano_usd']) is not int
                or policy['daily_cap_nano_usd'] != APPROVED_CAP
                or policy['reset_timezone'] != 'UTC'):
            raise BudgetError('Use the approved $15 per-provider UTC-day local advisor policy.')
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
        with budget.db() as db:
            # A side table preserves the pinned engine's exact ledger schema
            # and every historical charge. New reservations get explicit tags.
            db.execute('''CREATE TABLE IF NOT EXISTS advisor_charge_models(
                charge_id TEXT PRIMARY KEY, model TEXT NOT NULL,
                provider TEXT NOT NULL, attribution TEXT NOT NULL)''')
            budget._attribute_legacy(db)
        return budget

    @staticmethod
    def _attribute_legacy(db):
        rows = db.execute('''SELECT c.id,c.reserved,c.measured,c.status,c.input_bound,c.output_bound,
                              c.input_tokens,c.cached_tokens,c.output_tokens
            FROM ai_charges c LEFT JOIN advisor_charge_models m ON m.charge_id=c.id
            WHERE m.charge_id IS NULL''').fetchall()
        for key, reserved, measured, status, ib, ob, i, c, o in rows:
            matches = []
            for model, spec in MODELS.items():
                # Historical reservations used either ordinary input pricing
                # or the later cache-write maximum. Both signatures are retained.
                reservation = (ob == spec.output_tokens and reserved in {
                    ib * spec.input_rate + ob * spec.output_rate,
                    ib * max(spec.input_rate, spec.cache_write_rate) + ob * spec.output_rate})
                imported = (status == 'settled' and i == ib and o == ob and c is not None
                    and reserved == measured
                    and measured == (i-c) * spec.input_rate + c * spec.cached_rate + o * spec.output_rate)
                if reservation or imported:
                    matches.append(model)
            if len(matches) == 1:
                model = matches[0]
                db.execute('INSERT INTO advisor_charge_models VALUES(?,?,?,?)',
                           (key, model, MODELS[model].provider, 'legacy_unique_rate_match'))
        # Ambiguous records remain unassigned and visible; never guess a provider.

    @staticmethod
    def record_model(db, key, model):
        db.execute('INSERT INTO advisor_charge_models VALUES(?,?,?,?)',
                   (key, model, MODELS[model].provider, 'reserved_model'))

    def verify_model(self, db, key, model):
        self._attribute_legacy(db)
        row = db.execute('SELECT model,provider FROM advisor_charge_models WHERE charge_id=?', (key,)).fetchone()
        if row != (model, MODELS[model].provider):
            raise BudgetError('The AI usage receipt belongs to a different or unknown model.')

    @staticmethod
    def _scoped_amounts(db, day, provider):
        rows = db.execute('''SELECT c.charged,c.measured,c.status FROM ai_charges c
            LEFT JOIN advisor_charge_models m ON m.charge_id=c.id
            WHERE m.provider IS ? AND (c.day=? OR (c.day<? AND
                (c.status IN ('reserved','uncertain') OR c.finished_day=?)))''',
            (provider, day, day, day)).fetchall()
        return (sum(row[0] for row in rows), sum(row[1] or 0 for row in rows),
                sum(row[0] for row in rows if row[2] in {'reserved','uncertain'}), len(rows))

    def amounts_for_model(self, db, day, model):
        self._attribute_legacy(db)
        if self._scoped_amounts(db, day, None)[0]:
            raise BudgetError('Historical AI usage needs provider reconciliation before another paid request.')
        return self._scoped_amounts(db, day, MODELS[model].provider)

    @staticmethod
    def limit_message(model):
        return f"Daylight's $15 daily {MODELS[model].provider} allowance has been reached. It resets at 00:00 UTC."

    def provider_summaries(self):
        representatives = {spec.provider: model for model, spec in MODELS.items()}
        return {provider: self.summary(model) for provider, model in representatives.items()}

    def check_rates(self, model):
        if model == 'gpt-5.4':
            return super().check_rates(model)
        # Share the existing review expiry and fail-closed spending policy.
        super().check_rates('gpt-5.4')
        if model not in MODELS:
            raise BudgetError('Use a reviewed AI model.')

    def settle_model(self, key, response, model):
        with self.db() as db:
            self.verify_model(db, key, model)
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
        if model not in MODELS:
            raise BudgetError('Use a reviewed AI model.')
        provider = MODELS[model].provider
        day = self.day()
        reason, ready = '', True
        cap = self.daily_cap_nano_usd
        unattributed = 0
        try:
            self.check_rates(model)
            with self.db() as db:
                self._clock(db, day)
                self._attribute_legacy(db)
                total, measured, held, count = self._scoped_amounts(db, day, provider)
                unattributed = self._scoped_amounts(db, day, None)[0]
                if unattributed:
                    ready = False
                    reason = 'Historical AI usage needs provider reconciliation before another paid request.'
                blocked = db.execute("SELECT value FROM ai_meta WHERE key='blocked'").fetchone()
                if blocked:
                    reason = 'AI usage needs reconciliation. Paid requests are paused.'
                    ready = False
        except (BudgetError, sqlite3.Error, OSError):
            ready = False
            reason = 'AI pricing or the persistent budget could not be verified. Paid requests are paused.'
            try:
                with self.db() as db:
                    total, measured, held, count = self._scoped_amounts(db, day, provider)
            except Exception:
                total, measured, held, count = cap, 0, cap, 0
        remaining = max(0, cap - total)
        if ready and remaining == 0:
            ready = False
            reason = self.limit_message(model)
        return {
            'day': day, 'timezone': 'UTC', 'provider': provider, 'limitScope': 'provider',
            'resetAt': (datetime.fromisoformat(day).replace(tzinfo=timezone.utc) + timedelta(days=1)).isoformat(),
            'dailyLimitUsd': cap // NANO, 'estimatedUsd': measured / NANO,
            'maxInputTokens': INPUT_TOKENS, 'maxOutputTokens': MODELS[model].output_tokens,
            'reservedOrUncertainUsd': held / NANO, 'accountedUsd': total / NANO,
            'remainingUsd': remaining / NANO, 'requestCount': count,
            'canRequest': ready, 'reason': reason,
            'unattributedUsd': unattributed / NANO,
            'pricingVerifiedAt': self.rates['verified_at'], 'pricingValidUntil': self.rates['valid_until'],
            'label': 'Local provider allowance, not provider account credits. USD estimates plus unresolved holds; not an invoice.',
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
                total, *_ = self.amounts_for_model(db, day, model)
                cap = self.daily_cap_nano_usd
                if (total >= cap if self.finish_admitted_turn else total + amount > cap):
                    raise BudgetError(self.limit_message(model))
                db.execute('INSERT INTO ai_charges VALUES(?,?,NULL,?,?,NULL,?,?,?,NULL,NULL,NULL)',
                           (key, day, amount, amount, 'reserved', i, o))
                self.record_model(db, key, model)
            return key
        except sqlite3.Error:
            raise BudgetError('The persistent AI budget is unavailable. No paid request was started.') from None
