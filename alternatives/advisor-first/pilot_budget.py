"""D99 cumulative spending and participant accounting on an isolated ledger."""
from pathlib import Path
import sqlite3
from statistics import median

from ai_budget import BudgetError, DailyBudget, NANO
from advisor_budget import AdvisorDailyBudget
from guest_profiles import ProfileError
from pilot_access import participant


class PilotBudget(AdvisorDailyBudget):
    finish_admitted_turn = False

    @property
    def daily_cap_nano_usd(self):
        # Compatibility with the pinned budget interface. The pilot never resets.
        return 100 * NANO

    @classmethod
    def open(cls, access, *, initialize=False):
        path = access.root / 'model-usage.sqlite3'
        if path.is_symlink() or path.exists() == initialize:
            raise ValueError('Initialize a fresh pilot ledger or open the existing one.')
        budget = AdvisorDailyBudget.adopt(DailyBudget(path),
                                          pricing_review_path=Path(__file__).with_name('pricing-review.json'))
        budget.__class__ = cls
        budget.access = access
        with budget.db() as db:
            if initialize:
                db.execute('''CREATE TABLE pilot_charge_owner (
                    charge_id TEXT PRIMARY KEY, participant TEXT NOT NULL)''')
            budget._total(db)
        return budget

    @staticmethod
    def limit_message(model):
        return 'This request exceeds the remaining $100 pilot budget. Manual guidance is available.'

    def assert_issue_allowed(self):
        key = participant.get()
        try:
            allowed = key is not None and self.access.chat_enabled(key)
        except (OSError, sqlite3.Error, ProfileError):
            allowed = False
        if not allowed:
            raise BudgetError('Pilot chat is paused or access has expired.')

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

    def record_model(self, db, key, model):
        owner = participant.get()
        if owner is None:
            raise BudgetError('A pilot participant is required for accounting.')
        super().record_model(db, key, model)
        db.execute('INSERT INTO pilot_charge_owner VALUES (?,?)', (key, owner))

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
            with self.db() as db:
                ready = (not db.execute("SELECT 1 FROM ai_meta WHERE key='blocked'").fetchone()
                         and self._total(db)[0] < self.daily_cap_nano_usd)
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
