"""Cumulative hosted-demo accounting. The ledger outlives browser visits."""
import os
from dataclasses import replace
from pathlib import Path
import sqlite3
from statistics import median

from ai_budget import BudgetError, DailyBudget, NANO
from advisor_budget import AdvisorDailyBudget
from guest_profiles import ProfileError
from pilot_access import HISTORY_NOTICE, participant


PRICING_REVIEW_ENV = 'DAYLIGHT_PRICING_REVIEW'


def pricing_review_path():
    """D199: the hosted services may read a root-managed review file so the weekly price
    re-check does not need a new code release. The 7-day review limit is unchanged."""
    override = os.environ.get(PRICING_REVIEW_ENV, '').strip()
    if not override:
        return Path(__file__).with_name('pricing-review.json')
    path = Path(override)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError('Use an absolute, regular pricing review file.')
    return path


class PilotBudget(AdvisorDailyBudget):
    finish_admitted_turn = False
    invite_cap = 2 * NANO

    @property
    def daily_cap_nano_usd(self):
        # Compatibility with the pinned budget interface. The pilot never resets.
        return (50 if getattr(self, 'hosted_policy', None) else 20) * NANO

    def configure_hosted(self, policy):
        if policy not in {'owner', 'accelerator'}:
            raise ValueError('Use an explicit hosted budget policy.')
        self.hosted_policy = policy
        self.invite_cap = (5 if policy == 'accelerator' else 2) * NANO
        self.link_cap = (50 if policy == 'accelerator' else 20) * NANO
        # D208: the accelerator is spend-bounded, without a conversation-count cap.
        # Authentication, expiry, revocation and per-session reset limits still apply.
        self.access.unlimited_shared_admissions = policy == 'accelerator'
        self.service_tier = 'ultrafast' if policy == 'accelerator' else 'default'
        self.max_input_tokens = 272000  # refuse long-context surcharge, never underreserve
        if policy == 'accelerator':
            self.access.restart_limit = 4
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS pilot_session_roots (participant TEXT PRIMARY KEY, root TEXT NOT NULL)')
            # Operator-only reset receipts. They never change actual charges or
            # the cumulative global ceiling, and have no participant HTTP route.
            db.execute('''CREATE TABLE IF NOT EXISTS pilot_allowance_credits (
                scope TEXT NOT NULL CHECK(scope IN ('link','session')), owner TEXT NOT NULL,
                charged_baseline INTEGER NOT NULL CHECK(charged_baseline>=0),
                PRIMARY KEY(scope,owner))''')

    def model_spec(self, model, tier=None):
        spec = super().model_spec(model, tier)
        if getattr(self, 'service_tier', 'default') != 'ultrafast':
            return spec
        if model != 'gpt-6.1-sol':
            raise BudgetError('Ultrafast is reviewed only for GPT-6.1 Sol.')
        multiplier = {'default': 1, 'priority': 2, 'fast': 2, 'ultrafast': 6}.get(tier or 'ultrafast', 6)
        return replace(spec, input_rate=spec.input_rate*multiplier,
                       cached_rate=spec.cached_rate*multiplier, output_rate=spec.output_rate*multiplier,
                       cache_write_rate=spec.cache_write_rate*multiplier)

    def receipt_tiers(self, model):
        if getattr(self, 'service_tier', 'default') == 'ultrafast':
            return {'default', 'priority', 'fast', 'ultrafast'}
        return super().receipt_tiers(model)

    @classmethod
    def open(cls, access, *, initialize=False, ledger_path=None):
        # Both hosted environments must supply the same absolute durable path.
        path = Path(ledger_path) if ledger_path is not None else access.root / 'model-usage.sqlite3'
        if not path.is_absolute():
            raise ValueError('Use an absolute persistent ledger path.')
        if path.is_symlink() or path.exists() == initialize:
            raise ValueError('Initialize a fresh pilot ledger or open the existing one.')
        budget = AdvisorDailyBudget.adopt(DailyBudget(path), pricing_review_path=pricing_review_path())
        budget.__class__ = cls
        budget.access = access
        with budget.db() as db:
            if initialize:
                db.execute('''CREATE TABLE pilot_charge_owner (
                    charge_id TEXT PRIMARY KEY, participant TEXT NOT NULL)''')
                db.execute('CREATE TABLE pilot_visit_link (participant TEXT PRIMARY KEY, link_id TEXT NOT NULL)')
            budget._total(db)
        return budget

    @staticmethod
    def limit_message(model):
        return 'This reply would exceed the demo allowance. You can still browse the guide.'

    def assert_issue_allowed(self):
        key = participant.get()
        try:
            allowed = key is not None and self.access.chat_enabled(key)
            if allowed and getattr(self,'requires_history_consent',False):
                allowed = self.access.visit_policy(key)[1] == HISTORY_NOTICE
        except (OSError, sqlite3.Error, ProfileError):
            allowed = False
        if not allowed:
            raise BudgetError('Pilot chat is paused or access has expired.')

    def migrate_shared_links(self):
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS pilot_visit_link (participant TEXT PRIMARY KEY, link_id TEXT NOT NULL)')

    def allowance_credit(self, db, scope, owner):
        if getattr(self, 'hosted_policy', None) != 'accelerator':
            return 0
        row = db.execute('SELECT charged_baseline FROM pilot_allowance_credits WHERE scope=? AND owner=?',
                         (scope, owner)).fetchone()
        return row[0] if row else 0

    def _link_spend(self, db, owner):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='pilot_visit_link'").fetchone():
            return 0
        total = db.execute('''SELECT coalesce(sum(c.charged),0) FROM ai_charges c
            JOIN pilot_charge_owner o ON c.id=o.charge_id
            JOIN pilot_visit_link v ON v.participant=o.participant
            WHERE v.link_id=(SELECT link_id FROM pilot_visit_link WHERE participant=?)''',
            (owner,)).fetchone()[0]
        link = db.execute('SELECT link_id FROM pilot_visit_link WHERE participant=?', (owner,)).fetchone()
        return max(0, total - self.allowance_credit(db, 'link', link[0] if link else None))

    @staticmethod
    def _total(db):
        total, settled, held, count, missing = db.execute('''SELECT
            coalesce(sum(c.charged),0), coalesce(sum(c.measured),0),
            coalesce(sum(CASE WHEN c.status IN ('reserved','uncertain') THEN c.charged ELSE 0 END),0),
            count(*), count(*)-count(o.participant)
            FROM ai_charges c LEFT JOIN pilot_charge_owner o ON o.charge_id=c.id''').fetchone()
        if missing:
            raise BudgetError('Pilot accounting needs reconciliation.')
        return total, settled, held, count

    def amounts_for_model(self, db, day, model):
        self.assert_issue_allowed()
        return self._total(db)

    def _invite_spend(self, db, owner):
        if getattr(self, 'hosted_policy', None) == 'accelerator':
            root = self.access.session_root(owner)
            total = db.execute('''SELECT coalesce(sum(c.charged),0) FROM ai_charges c
                JOIN pilot_charge_owner o ON c.id=o.charge_id
                LEFT JOIN pilot_session_roots s ON s.participant=o.participant
                WHERE o.participant=? OR s.root=?''', (root, root)).fetchone()[0]
            return max(0, total - self.allowance_credit(db, 'session', root))
        return db.execute('''SELECT coalesce(sum(c.charged),0) FROM ai_charges c
            JOIN pilot_charge_owner o ON c.id=o.charge_id WHERE o.participant=?''',
            (owner,)).fetchone()[0]

    def messaging_available(self, owner):
        try:
            with self.db() as db:
                return (not db.execute("SELECT 1 FROM ai_meta WHERE key='blocked'").fetchone()
                        and self._total(db)[0] < self.daily_cap_nano_usd
                        and self._invite_spend(db, owner) < self.invite_cap
                        and self._link_spend(db, owner) < getattr(self, 'link_cap', 20 * NANO))
        except (BudgetError, ProfileError, OSError, sqlite3.Error):
            return False

    def record_model(self, db, key, model):
        owner = participant.get()
        if owner is None:
            raise BudgetError('A pilot participant is required for accounting.')
        if getattr(self, 'hosted_policy', None) == 'accelerator':
            root = self.access.session_root(owner)
            db.execute('INSERT INTO pilot_session_roots VALUES (?,?) ON CONFLICT(participant) DO NOTHING', (owner, root))
            if db.execute('SELECT root FROM pilot_session_roots WHERE participant=?', (owner,)).fetchone() != (root,):
                raise BudgetError('Session accounting needs reconciliation.')
        link, _, _ = self.access.visit_policy(owner)
        if link:
            db.execute('INSERT INTO pilot_visit_link VALUES (?,?) ON CONFLICT(participant) DO NOTHING', (owner, link))
            if db.execute('SELECT link_id FROM pilot_visit_link WHERE participant=?', (owner,)).fetchone() != (link,):
                raise BudgetError('Invitation accounting needs reconciliation.')
        super().record_model(db, key, model)
        db.execute('INSERT INTO pilot_charge_owner VALUES (?,?)', (key, owner))
        # Still inside reserve's BEGIN IMMEDIATE transaction. Refusal rolls
        # back the reservation and both attribution rows before provider I/O.
        self.check_invite_allowance(db, 0, model)

    def check_invite_allowance(self, db, additional, model):
        if self._invite_spend(db, participant.get()) + additional > self.invite_cap:
            raise BudgetError(self.limit_message(model))
        if self._link_spend(db, participant.get()) + additional > getattr(self, 'link_cap', 20 * NANO):
            raise BudgetError(self.limit_message(model))

    def verify_model(self, db, key, model):
        super().verify_model(db, key, model)
        row = db.execute('SELECT participant FROM pilot_charge_owner WHERE charge_id=?', (key,)).fetchone()
        if not row or row[0] != participant.get():
            raise BudgetError('Pilot receipt belongs to a different participant.')

    def summary(self, model='gpt-5.4'):
        ready = False
        try:
            self.check_rates(model)
            self.assert_issue_allowed()
            ready = self.messaging_available(participant.get())
        except (BudgetError, OSError, sqlite3.Error):
            pass
        return {'canRequest': ready, 'reason': '' if ready else 'Pilot chat is paused.'}

    def participant_usage(self):
        """Operator-only numeric report. Never returned by a participant route."""
        with self.db() as db:
            self._total(db)
            return db.execute('''SELECT o.participant, count(*), coalesce(sum(c.measured),0),
                coalesce(sum(CASE WHEN c.status IN ('reserved','uncertain') THEN c.charged ELSE 0 END),0),
                coalesce(sum(c.input_tokens),0), coalesce(sum(c.output_tokens),0)
                FROM pilot_charge_owner o JOIN ai_charges c ON c.id=o.charge_id
                WHERE c.status<>'cancelled' GROUP BY o.participant ORDER BY o.participant''').fetchall()

    def visit_usage(self, owner):
        """Cumulative visit receipt recorded alongside each turn, without secrets."""
        with self.db() as db:
            self._total(db)
            rows = db.execute('''SELECT c.id,c.status,c.charged,c.measured,c.input_tokens,c.output_tokens
                FROM ai_charges c JOIN pilot_charge_owner o ON c.id=o.charge_id
                WHERE o.participant=? ORDER BY c.id''', (owner,)).fetchall()
            fields = ('receipt','status','accounted_nano_usd','measured_nano_usd','input_tokens','output_tokens')
            return {'scope': 'visit_cumulative', 'charges': [dict(zip(fields,row)) for row in rows]}

    def session_costs(self):
        visits = self.access.observed_visits()
        usage = {key: (settled, held) for key, _, settled, held, _, _ in self.participant_usage()}
        complete = [usage.get(key, (0, 0))[0] for key, done in visits.items() if done]
        settled = sum(row[0] for row in usage.values())
        return {
            'visits': len(visits), 'completed': len(complete),
            'settled_nano_usd': settled, 'held_nano_usd': sum(row[1] for row in usage.values()),
            'incomplete_or_unclassified_nano_usd': settled - sum(complete),
            'median_completed_nano_usd': median(complete) if complete else None,
            'max_completed_nano_usd': max(complete, default=None),
            'all_spend_per_completed_nano_usd': settled / len(complete) if complete else None,
        }

    def reconcile(self, provider_total_nano_usd):
        """Compare a finalized cumulative total for the dedicated pilot project."""
        if type(provider_total_nano_usd) is not int or provider_total_nano_usd < 0:
            raise ValueError('Provide a nonnegative provider total in nano-USD.')
        with self.db() as db:
            total, settled, held, _ = self._total(db)
        difference = provider_total_nano_usd - settled
        return {
            'status': 'unresolved_charges' if held else ('difference' if difference else 'matched'),
            'provider_nano_usd': provider_total_nano_usd, 'settled_nano_usd': settled,
            'accounted_nano_usd': total, 'held_nano_usd': held, 'difference_nano_usd': difference,
        }
