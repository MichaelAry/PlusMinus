"""Navigate from PlusMinus tokens to the actual compiler and VM implementation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceTarget:
    file: str
    anchor: str
    label: str


@dataclass(frozen=True)
class LanguageSymbol:
    description: str
    compiler: SourceTarget
    runtime: SourceTarget | None = None


def compiler(anchor):
    if anchor.startswith('void Compiler::parseOperand'):
        file = 'src/compiler/expressions.cpp'
    elif anchor.startswith('void Compiler::parse') and anchor.split('::parse', 1)[1].startswith(
        ('Expr', 'Compare', 'Sum', 'Term', 'Factor')):
        file = 'src/compiler/expressions.cpp'
    else:
        file = 'src/compiler/statements.cpp'
    return SourceTarget(file, anchor, 'Compiler / syntax')


def runtime(anchor):
    return SourceTarget('src/vm/executor.cpp', anchor, 'VM / execution')


SYMBOLS = {
    'if': LanguageSymbol('Conditional branch: emits Jz/Jmp instructions.', compiler('void Compiler::parseIf()'), runtime('case OpCode::Jz:')),
    'else': LanguageSymbol('Alternative branch of an if statement.', compiler('void Compiler::parseIf()'), runtime('case OpCode::Jmp:')),
    'while': LanguageSymbol('Loop compiled to conditional/backward jumps.', compiler('void Compiler::parseWhile()'), runtime('case OpCode::Jz:')),
    'func': LanguageSymbol('Function declaration with parameters.', compiler('void Compiler::parseFunctionDef('), runtime('case OpCode::FuncDef:')),
    'proc': LanguageSymbol('Procedure declaration.', compiler('void Compiler::parseFunctionDef('), runtime('case OpCode::ProcDef:')),
    'return': LanguageSymbol('Return from a function.', compiler('if (checkKeyword("return"))'), runtime('case OpCode::Return:')),
    'go': LanguageSymbol('Invoke a function in a native thread.', compiler('if (checkKeyword("go"))'), runtime('case OpCode::GoCall:')),
    'sync': LanguageSymbol('Wait for VM threads to complete.', compiler('if (checkKeyword("sync"))'), runtime('case OpCode::Sync:')),
    'lock': LanguageSymbol('Acquire a named mutex.', compiler('if (checkKeyword("lock"))'), runtime('case OpCode::Lock:')),
    'unlock': LanguageSymbol('Release a named mutex.', compiler('if (checkKeyword("unlock"))'), runtime('case OpCode::Unlock:')),
    'int': LanguageSymbol('Optional type annotation, interpreted as a dynamic VM value.', compiler('if (checkKeyword("int"))')),
    'float': LanguageSymbol('Optional type annotation, stored as a double.', compiler('else if (checkKeyword("float"))')),
    'double': LanguageSymbol('Optional type annotation for a double.', compiler('else if (checkKeyword("double"))')),
    'print': LanguageSymbol('Print values to VM output.', compiler('void Compiler::parseOperand()'), runtime('if (c.name == "print")')),
    'len': LanguageSymbol('Length of an array.', compiler('void Compiler::parseOperand()'), runtime('else if (c.name == "len")')),
    'resize': LanguageSymbol('Resize an array.', compiler('void Compiler::parseOperand()'), runtime('else if (c.name == "resize")')),
    'sin': LanguageSymbol('Sine built-in.', compiler('void Compiler::parseOperand()'), runtime('else if (c.name == "sin")')),
    'cos': LanguageSymbol('Cosine built-in.', compiler('void Compiler::parseOperand()'), runtime('else if (c.name == "cos")')),
    'pow': LanguageSymbol('Exponentiation built-in.', compiler('void Compiler::parseOperand()'), runtime('else if (c.name == "pow")')),
    'fact': LanguageSymbol('Factorial built-in.', compiler('void Compiler::parseOperand()'), runtime('else if (c.name == "fact")')),
    'multifact': LanguageSymbol('Multifactorial built-in.', compiler('void Compiler::parseOperand()'), runtime('else if (c.name == "multifact")')),
}

_WORD = re.compile(r'[A-Za-z_][A-Za-z_0-9]*')


def keyword_at(source: str, position: int) -> str | None:
    """Ignore keywords occurring in strings, line comments or block comments."""
    if position < 0 or position >= len(source):
        return None
    match = next((m for m in _WORD.finditer(source) if m.start() <= position < m.end()), None)
    if match is None or match.group() not in SYMBOLS:
        return None
    state = 'code'
    i = 0
    while i < match.start():
        char = source[i]
        following = source[i+1] if i+1 < len(source) else ''
        if state == 'code':
            if char == '/' and following == '/':
                state = 'line'; i += 2; continue
            if char == '/' and following == '*':
                state = 'block'; i += 2; continue
            if char == '"':
                state = 'string'
        elif state == 'line':
            if char == '\n':
                state = 'code'
        elif state == 'block':
            if char == '*' and following == '/':
                state = 'code'; i += 2; continue
        else:
            if char == '\\':
                i += 2; continue
            if char == '"':
                state = 'code'
        i += 1
    return match.group() if state == 'code' else None


def source_targets(keyword: str) -> tuple[SourceTarget, ...]:
    symbol = SYMBOLS.get(keyword)
    if symbol is None:
        return ()
    return (symbol.compiler,) + ((symbol.runtime,) if symbol.runtime else ())


def locate_target(root: Path, target: SourceTarget) -> tuple[Path, int]:
    root = Path(root).resolve()
    path = (root / target.file).resolve()
    allowed = {
        (root / item).resolve() for item in (
            'Parser.h', 'ide/runner.cpp',
            'include/plusminus/value.hpp', 'include/plusminus/bytecode.hpp',
            'include/plusminus/compiler.hpp', 'include/plusminus/vm.hpp',
            'include/plusminus/api.hpp',
            'src/compiler/compiler.cpp', 'src/compiler/scanner.cpp',
            'src/compiler/statements.cpp', 'src/compiler/expressions.cpp',
            'src/vm/vm.cpp', 'src/vm/executor.cpp', 'src/api.cpp',
        )
    }
    if path not in allowed:
        raise ValueError('Editing is restricted to interpreter C++ source files')
    if not path.is_file():
        raise FileNotFoundError(str(path))
    content = path.read_text(encoding='utf-8-sig')
    offset = content.find(target.anchor)
    if offset < 0:
        raise ValueError(f'Cannot locate C++ anchor: {target.anchor}')
    return path, content.count('\n', 0, offset)+1


def editable_checkout(root: Path) -> bool:
    return all((Path(root)/p).is_file() for p in ('include/plusminus/api.hpp', 'src/compiler/statements.cpp', 'src/vm/executor.cpp', 'ide/runner.cpp', 'launch.py'))
