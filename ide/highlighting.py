"""Syntax-aware Qt highlighters for PlusMinus and native C++ sources.

Multiline block comments are stateful; strings and comments take precedence
over lexical word/number rules to avoid colouring tokens in literals.
"""
import re
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat


def fmt(color, bold=False, italic=False):
    result = QTextCharFormat()
    result.setForeground(QColor(color))
    if bold:
        result.setFontWeight(QFont.Weight.Bold)
    result.setFontItalic(italic)
    return result


class StatefulHighlighter(QSyntaxHighlighter):
    def __init__(self, document, cpp=False):
        super().__init__(document)
        self.cpp = cpp
        self.rules = []
        self.comment_style = fmt('#77879B', italic=True)
        self.string_style = fmt('#A8CDA9')
        self._string = re.compile(r'"(?:\\.|[^"\\])*"')
        self._line_comment = re.compile(r'//[^\n]*')
        self._block_start = re.compile(r'/\*')
        self._block_end = re.compile(r'\*/')
        if cpp:
            words = [
                (r'\b(?:class|struct|enum|namespace|template|typename|public|private|protected|virtual|override|const|constexpr|static|inline|void|bool|double|float|int|auto|return|break|continue|if|else|while|for|switch|case|try|catch|throw|using|new|delete|true|false|nullptr)\b', '#AFC5FF', True),
                (r'\b(?:size_t|std|string|vector|unordered_map|mutex|thread|shared_ptr|unique_ptr)\b', '#95B7D5', False),
                (r'\b[A-Za-z_]\w*(?=\s*\()', '#E2C79A', False),
                (r'#[ \t]*(?:include|define|pragma|ifdef|ifndef|endif|else|elif)\b.*', '#CBB996', False),
            ]
        else:
            words = [
                (r'\b(?:if|else|while|func|proc|return|go|sync|lock|unlock)\b', '#AFC5FF', True),
                (r'\b(?:int|float|double)\b', '#95B7D5', True),
                (r'\b(?:print|len|resize|plot|point|line|clear|complex|re|im|conj|arg|abs|cabs|sin|cos|tan|asin|acos|atan|atan2|sqrt|cbrt|exp|log|log10|floor|ceil|round|min|max|hypot|clamp|lerp|deg|rad|sign|pow|fact|multifact|pi|e)\b', '#91CDC0', True),
                (r'\b[A-Za-z_]\w*(?=\s*\()', '#E2C79A', False),
            ]
        for regex, color, bold in words:
            self.rules.append((re.compile(regex), fmt(color, bold)))
        self.rules.extend([
            (re.compile(r'\b(?:0[xX][\da-fA-F]+|\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\b'), fmt('#BDD59A')),
            (re.compile(r'(?:\+\+|--|==|!=|<=|>=|&&|\|\||[-+*/%^<>=!&|])'), fmt('#D8ADD2')),
        ])

    def highlightBlock(self, text):
        # Paint lexical tokens, then override with literal/comment formats.
        for regex, formatting in self.rules:
            for match in regex.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), formatting)
        for match in self._string.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self.string_style)
        self.setCurrentBlockState(0)
        pos = 0
        if self.previousBlockState() == 1:
            end = text.find('*/')
            if end < 0:
                self.setFormat(0, len(text), self.comment_style)
                self.setCurrentBlockState(1)
                return
            self.setFormat(0, end + 2, self.comment_style)
            pos = end + 2
        # Earliest comment wins, except markers occurring inside a string.
        strings = [(m.start(), m.end()) for m in self._string.finditer(text)]
        def in_string(start):
            return any(a <= start < b for a, b in strings)
        while pos < len(text):
            line = text.find('//', pos)
            block = text.find('/*', pos)
            markers = [(at, kind) for at, kind in ((line, 'line'), (block, 'block'))
                       if at >= 0 and not in_string(at)]
            if not markers:
                break
            start, kind = min(markers)
            if kind == 'line':
                self.setFormat(start, len(text) - start, self.comment_style)
                break
            end = text.find('*/', start + 2)
            if end < 0:
                self.setFormat(start, len(text) - start, self.comment_style)
                self.setCurrentBlockState(1)
                break
            self.setFormat(start, end + 2 - start, self.comment_style)
            pos = end + 2


class PlusMinusHighlighter(StatefulHighlighter):
    def __init__(self, document):
        super().__init__(document, cpp=False)


class CppHighlighter(StatefulHighlighter):
    def __init__(self, document):
        super().__init__(document, cpp=True)
