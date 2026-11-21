#!/usr/bin/env python3
"""Discover original TEST_METHOD declarations and generate C++ adapters."""
import re
import sys
from pathlib import Path

GROUPS = ("arithmetic","control_flow","bytecode","arrays","builtins","concurrency","functions")

def discover(text):
    result = []
    current = None
    for match in re.finditer(r'\bTEST_CLASS\((\w+)\)|\bTEST_METHOD\((\w+)\)', text):
        if match.group(1):
            current = match.group(1)
        elif current:
            result.append((current, match.group(2)))
        else:
            raise ValueError("TEST_METHOD occurs before TEST_CLASS")
    return result

def generate(root, destination):
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for group in GROUPS:
        source = root / 'tests' / 'cpp' / (group + '_tests.cpp')
        declarations = discover(source.read_text(encoding='utf-8-sig'))
        lines = [
            '#include "tests/cpp/' + source.name + '"',
            '#include "registry.hpp"',
            'namespace {',
            'const bool registered = []() {',
        ]
        for cls, method in declarations:
            slow = cls in ('AsyncPerformance', 'MultiCoreScaling')
            lines.append(
                '    pmtests::add("' + cls + '.' + method + '", "' + group +
                '", "tests/cpp/' + source.name + '", [](){ ParserTests::' +
                cls + ' instance; instance.' + method + '(); }, ' +
                ('true' if slow else 'false') + ');')
            count += 1
        lines.extend(['    return true;', '}();', '}'])
        (destination / (group + '_tests_registration.cpp')).write_text(
            '\n'.join(lines) + '\n', encoding='utf-8')
    if count != 225:
        raise RuntimeError(f'Expected 225 tests, found {count}')
    print(f'Generated {count} tests')

if __name__ == '__main__':
    generate(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
