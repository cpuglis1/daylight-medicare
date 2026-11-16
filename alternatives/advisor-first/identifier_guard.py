"""HP-07: keep government, Medicare and payment identifiers out of Daylight.

Daylight never needs a Social Security number, Medicare number (MBI) or card
number before checkout (launch security spec section 5.3). This module only
detects them. Callers refuse the input, so the identifier is never sent to a
model, stored or logged. Results name categories only and never echo a value.

Two strengths:
- find_identifiers: for text a person submitted (messages and answers).
  Includes unseparated 9-digit SSNs and 13-19 digit card numbers (Luhn).
- find_transport_identifiers: a backstop on the whole outgoing model request,
  which also carries catalog text and system numbers. It uses only
  high-confidence shapes (separated SSNs, exact-alphabet MBIs, card numbers
  written in groups) so routine numbers cannot block a legitimate request.
"""
import re

IDENTIFIER_MESSAGE = ("Please remove Social Security, Medicare or card numbers. "
                      "Daylight doesn't need them, and this message was not sent or saved.")

# MBI alphabet: uppercase letters except S, L, O, I, B and Z (CMS format).
_L = 'AC-HJKMNP-RT-Y'
_EDGE_BEFORE = r'(?<![0-9A-Za-z])'
_EDGE_AFTER = r'(?![0-9A-Za-z])'

_MBI = re.compile(
    _EDGE_BEFORE + rf'[1-9][{_L}][{_L}0-9][0-9][- ]?[{_L}][{_L}0-9][0-9][- ]?[{_L}][{_L}][0-9]{{2}}' + _EDGE_AFTER,
    re.IGNORECASE)
_SSN_SEPARATED = re.compile(_EDGE_BEFORE + r'(\d{3})([- ])(\d{2})\2(\d{4})' + _EDGE_AFTER)
_SSN_PLAIN = re.compile(_EDGE_BEFORE + r'(\d{3})(\d{2})(\d{4})' + _EDGE_AFTER)
_CARD_ANY = re.compile(_EDGE_BEFORE + r'\d(?:[ -]?\d){12,18}' + _EDGE_AFTER)
_CARD_GROUPED = re.compile(_EDGE_BEFORE + r'\d{4}(?:[ -]\d{4}){2}[ -]\d{1,7}' + _EDGE_AFTER)
# Near-misses in text a person typed (15-profile run, November 13, 2026): a Medicare
# number with a typo or an invalid first character has the right shape but fails the
# exact alphabet, so it reached the model. Two looser rules, for submitted text only.
_MBI_LOOSE = re.compile(_EDGE_BEFORE + r'[0-9A-Za-z]{4}[- ][0-9A-Za-z]{3}[- ][0-9A-Za-z]{4}' + _EDGE_AFTER)
_CUE = re.compile(r"(?i)\b(medicare (?:number|no\.?|num|#|id|card number|claim number)|mbi|"
                  r"social security (?:number|no\.?|num|#)|ssn|my social)(?:\b|(?<=#))\W{0,3}(?:is|was|are)?\W{0,3}"
                  r"((?:[0-9A-Za-z]+[ -]?){1,6})")
_PHONE = re.compile(r'1?[2-9]\d{2}[2-9]\d{6}')


def _valid_ssn(area, group, serial):
    return area not in {'000', '666'} and not area.startswith('9') and group != '00' and serial != '0000'


def _luhn(digits):
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _cards(text, pattern):
    for match in pattern.finditer(text):
        digits = re.sub(r'[ -]', '', match.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits) and len(set(digits)) > 1:
            return True
    return False


def _ssns(text, pattern, separated):
    for match in pattern.finditer(text):
        area, group, serial = (match.group(1), match.group(3), match.group(4)) if separated else match.groups()
        if _valid_ssn(area, group, serial):
            return True
    return False


def find_identifiers(text):
    """Categories of identifiers in text a person submitted. Never returns values."""
    if not isinstance(text, str) or not text:
        return []
    found = []
    if _ssns(text, _SSN_SEPARATED, True) or _ssns(text, _SSN_PLAIN, False):
        found.append('ssn')
    if _MBI.search(text):
        found.append('medicare_number')
    if _cards(text, _CARD_ANY):
        found.append('payment_card')
    for kind in _near_misses(text):
        if kind not in found:
            found.append(kind)
    return found


def _near_misses(text):
    kinds = []
    for match in _MBI_LOOSE.finditer(text):
        code = re.sub(r'[ -]', '', match.group(0))
        if sum(c.isalpha() for c in code) >= 3 and sum(c.isdigit() for c in code) >= 4:
            kinds.append('medicare_number')
            break
    for match in _CUE.finditer(text):
        # The code is the run of pieces that carry a digit; it ends at the first plain word
        # ("... MK7 thanks", "... is on my card").
        code = ''
        for piece in re.split(r'[ -]', match.group(2)):
            if not any(c.isdigit() for c in piece):
                break
            code += piece
        if not 8 <= len(code) <= 13 or sum(c.isdigit() for c in code) < 4:
            continue
        if code.isdigit() and _PHONE.fullmatch(code):
            continue   # "Medicare's number is 1-800-633-4227" is a phone number
        kinds.append('ssn' if re.search(r'(?i)social|ssn', match.group(1)) else 'medicare_number')
    return kinds


def find_transport_identifiers(text):
    """High-confidence identifier categories in a whole outgoing model request."""
    if not isinstance(text, str) or not text:
        return []
    found = []
    if _ssns(text, _SSN_SEPARATED, True):
        found.append('ssn')
    if _MBI.search(text):
        found.append('medicare_number')
    if _cards(text, _CARD_GROUPED):
        found.append('payment_card')
    return found


def submitted_strings(value, depth=0):
    """Every string inside a submitted action, without keys' structure or numbers."""
    if depth > 6:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in submitted_strings(item, depth + 1)]
    if isinstance(value, (list, tuple)):
        return [s for item in value for s in submitted_strings(item, depth + 1)]
    return []
