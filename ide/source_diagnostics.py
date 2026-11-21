"""Source-positioned lexical diagnostics with explicit confidence levels.

These checks are not AST/type analysis. The C++ compiler provides authoritative
syntax errors through runner diagnostics; this module catches cheap editing mistakes.
"""
from __future__ import annotations
import re
from analytics import analyze_source, sanitize_source


MATCHES = {')':'(', ']':'[', '}':'{'}
OPEN = set(MATCHES.values())


def position(source, offset):
    offset = max(0, min(len(source), offset))
    line = source.count('\n', 0, offset) + 1
    previous = source.rfind('\n', 0, offset)
    return line, offset - previous


def diagnostic(source, offset, severity, code, message):
    line, column = position(source, offset)
    return {'severity':severity, 'code':code, 'line':line, 'column':column,
            'message':message, 'phase':'static', 'confidence':'lexical'}


def analyze_diagnostics(source):
    masked, _ = sanitize_source(source)
    stack, issues = [], []
    for offset, symbol in enumerate(masked):
        if symbol in OPEN:
            stack.append((symbol, offset))
        elif symbol in MATCHES:
            if not stack or stack[-1][0] != MATCHES[symbol]:
                issues.append(diagnostic(source, offset, 'error', 'PM1002',
                                         f'Unexpected closing bracket {symbol}'))
            else:
                stack.pop()
    for symbol, offset in stack:
        issues.append(diagnostic(source, offset, 'error', 'PM1001',
                                 f'Unclosed bracket {symbol}'))
    info = analyze_source(source)
    if info['go_calls'] and not info['sync']:
        found = re.search(r'\bgo\b', masked)
        if found:
            issues.append(diagnostic(source, found.start(), 'warning', 'PM3001',
                                     'Concurrent call without explicit sync: review thread lifetime'))
    if info['locks'] and info['locks'] != len(re.findall(r'\bunlock\b',masked)):
        found = re.search(r'\block\b', masked)
        if found:
            issues.append(diagnostic(source, found.start(), 'warning', 'PM3002',
                                     'Lock/unlock counts differ; inspect synchronization paths'))
    if info['max_nesting'] >= 5:
        issues.append(diagnostic(source, 0, 'info', 'PM4001',
                                 f'High block nesting: {info["max_nesting"]}'))
    return sorted(issues, key=lambda x: (x['line'],x['column'],x['code']))
