#!/usr/bin/env python3

import os
import re
import sys
import subprocess

from enum import Enum
from functools import reduce

# -----------------------------------------------------------------------------

PYTHON_COMMAND = 'python3'
TAB_WIDTH = 4

# -----------------------------------------------------------------------------


class SyntaxError(BaseException):
    def __init__(self, name, lnum, msg):
        super().__init__(f'{name}:{lnum}: syntax error: {msg}')


# -----------------------------------------------------------------------------


class String(str):
    def __init__(self, *args, **kwargs):
        self.name = None
        self.lnum = None
        self.lpos = None

    def __add__(self, rhs):
        return String.create(self.name, self.lnum, self.lpos, super().__add__(rhs))

    def setparam(self, name, lnum, lpos):
        self.name = name
        self.lnum = lnum
        self.lpos = lpos
        return self

    @ staticmethod
    def create(name, lnum, lpos, s=''):
        return String(s).setparam(name, lnum, lpos)


class Stream:
    def __init__(self, name, stream=None):
        self.name = name if name != '-' else '[STDIN]'
        self.stream = (stream if stream else
                       (sys.stdin if name == '-' else open(name)))
        self.lines = []
        self.line = ''
        self.lnum = 0
        self.lpos = 0
        self.pending = []

    def __iter__(self):
        return self

    def __next__(self):
        c = self.getchar()
        if c is None:
            raise StopIteration
        return c

    def getline(self):
        line = self.stream.readline()
        if line:
            self.lines.append(line)
            self.line = line
            self.lnum += 1
            self.lpos = 0
        return line

    def getchar(self):
        if self.pending:
            return self.pending.pop()
        if self.lpos >= len(self.line):
            if not self.getline():
                return None
        lpos = self.lpos
        self.lpos = lpos + 1
        return String.create(self.name, self.lnum, lpos, self.line[lpos])

    def putchar(self, c):
        self.pending.append(c)
        return self

    def read(self, n):
        t = tuple(self.getchar() for _ in range(n))
        return (''.join(t), t)

    def write(self, s):
        self.pending += reversed(s)
        return self

    def emptychar(self):
        return String.create(self.name, self.lnum, self.lpos, '')


# -----------------------------------------------------------------------------


class SxElement():
    def __init__(self, bracket, value=None):
        self.open = bracket
        self.close = Lexer.BRACKET[bracket]
        self.children = []
        self.value = value

    def __len__(self):
        return self.children.__len__()

    def __iter__(self):
        return self.children.__iter__()

    def has_value(self):
        return self.value != None

    def is_type(self, c):
        return self.value and c == self.value[0]

    def get_value(self):
        return self.value

    def get_string(self):
        return self.value and self.value[1] or ''

    def append(self, value):
        return self.children.append(value)

    def dump(self, level=0):
        indent = '  ' * level
        if self.open:
            print(f'{indent}{self.open}')
        for child in self.children:
            child.dump(level + 1)
        if self.close:
            print(f'{indent}{self.close}')
        if self.value:
            tt, ts = self.value
            ts = ts.replace('\t', '\\t')
            ts = ts.replace('\n', '\\n')
            print(f'{indent}type:{tt}, data:{ts}')


class Lexer:
    WSTOP = '()[]{}\'"'
    BRACKET = {'': '', '(': ')', '[': ']', '{': '}'}

    def __init__(self, stream, **option):
        self.WSTOP = Lexer.WSTOP
        self.stream = stream
        self.debug = option['debug']

    def __iter__(self):
        return self

    def __next__(self):
        token = self.gettoken()
        if token is None:
            raise StopIteration
        return token

    # 'o': open
    # 'c': close
    # 's': space
    # 'q': quoted
    # 'w': word?

    def gettoken(self):
        ch = self.stream.getchar()
        if ch is None:
            return None
        if ch == '"':
            s, t = self.stream.read(3)
            if s == '""[':
                return self.getlongquote()
            self.stream.write(t)
            return self.getquote(ch)
        if ch == "'":
            return self.getquote(ch)
        if ch in '([{':
            return ('o', ch)
        if ch in ')]}':
            return ('c', ch)
        if ord(ch) < 33:
            return self.getspace(ch)
        return self.getword(ch)

    def getspace(self, space):
        for ch in self.stream:
            if ord(ch) >= 33:
                self.stream.putchar(ch)
                break
            space += ch
        return ('s', space)

    def getword(self, word):
        stop = self.WSTOP
        for ch in self.stream:
            if ord(ch) < 33 or ch in stop:
                self.stream.putchar(ch)
                break
            word += ch
        return ('w', word)

    def getquote(self, qch):
        qstr = self.stream.emptychar()
        escape = False
        for ch in self.stream:
            if escape:
                escape = False
                qstr += ch
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == qch:
                return ('q', qstr)
            qstr += ch
        raise NotImplementedError

    def getlongquote(self):
        stream = self.stream
        qstr = stream.emptychar()
        for ch in stream:
            if ch == ']':
                s, t = stream.read(3)
                if s == '"""':
                    return ('q', qstr)
                stream.write(t)
            qstr += ch
        raise NotImplementedError


class Parser(Lexer):
    def __init__(self, stream, **option):
        super().__init__(stream, **option)
        last = SxElement('')
        stack = [last]
        for token in self:
            tt, ts = token
            if tt == 'o':
                last = SxElement(ts)
                stack.append(last)
                continue
            if tt == 'c':
                if ts != stack[-1].close:
                    raise SyntaxError(
                        self.stream.name,
                        self.stream.lnum,
                        f'unmatched: "{stack[-1].open} ... {ts}"')
                nest = stack.pop()
                last = stack[-1]
                last.append(nest)
                continue
            last.append(SxElement('', token))
        if len(stack) != 1:
            raise SyntaxError(
                self.stream.name,
                self.stream.lnum,
                f'missing "{stack[-1].close}"')
        self.tree = stack.pop()

    def dump(self):
        return self.tree.dump()


# -----------------------------------------------------------------------------


class Element:
    def __init__(self, tag=None, attribute=None, text=None, children=[]):
        self.tag = tag
        self.attribute = attribute
        self.text = text
        self.children = children

    def __repr__(self):
        return (f'<Element:tag={repr(self.tag)},'
                f'attribute={repr(self.attribute)},'
                f'text={repr(self.text)},'
                f'children={repr(self.children)}>')


class Text(str):
    TEXT = 0
    INDENT = 1
    ENTER = 2
    LEAVE = 3
    REINDENT = 4

    def __init__(self, *args, **kwargs):
        self.mode = Text.TEXT

    def setparam(self, mode):
        self.mode = mode
        return self

    @staticmethod
    def create(mode, text=''):
        return Text(text).setparam(mode)

    @staticmethod
    def create_indent(text=''):
        return Text(text).setparam(Text.INDENT)

    @staticmethod
    def create_enter(text=''):
        return Text(text).setparam(Text.ENTER)

    @staticmethod
    def create_leave(text=''):
        return Text(text).setparam(Text.LEAVE)

    @staticmethod
    def create_reindent(text=''):
        return Text(text).setparam(Text.REINDENT)


class GenHTML(Parser):
    TAG_SINGLE = {
        'area',
        'base', 'bgsound', 'br',
        'col',
        'embed',
        'frame',
        'hr',
        'image', 'img', 'input',
        'keygen',
        'link',
        'menuitem', 'meta',
        'param',
        'source',
        'track',
        'wbr',
    }

    TAG_EMBED = {
        'a', 'abbr', 'acronym', 'audio',
        'b', 'bdi', 'bdo', 'big', 'blink', 'br', 'button',
        'canvas', 'cite', 'code',
        'data', 'del', 'dfn',
        'em',
        'font',
        'i', 'img', 'input', 'ins',
        'kbd',
        'label',
        'mark', 'meter',
        'nobr',
        'output',
        'progress',
        'q',
        'rb', 'rbc', 'rp', 'rt', 'rtc', 'ruby',
        's', 'samp', 'small', 'spacer', 'span', 'strike', 'strong', 'sub', 'sup',
        'textarea', 'th', 'td', 'time', 'tt',
        'u',
        'var',
        'wbr',
    }

    TAG_INDIVIDUAL = {
        'title',
    }

    TAG_ALTCODE = {
        'script',
        'style',
    }

    TAG_ATTRIBUTE = {
        '@while',
    }

    @staticmethod
    def qstrip(s):
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ('\'', '"'):
            return s[1:-1]
        return s

    @staticmethod
    def escape(s):
        return (s.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))

    @staticmethod
    def reindent(indent, s):
        lines = s.split('\n')
        while lines and not lines[+0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        cut = min([80, *[len(l) - len(l.lstrip()) for l in lines]])
        return ''.join(indent + l[cut:] + '\n' for l in lines)

    @staticmethod
    def run(command, stdin):
        return subprocess.run(args=[command, '-'], input=stdin.encode('utf-8'),
                              capture_output=True, check=True).stdout.decode()

    def __init__(self, stream, **option):
        super().__init__(stream, **option)

        self.altindent = option['altindent'] if 'altindent' in option else True
        self.tab_width = option['tab_width'] if 'tab_width' in option else TAB_WIDTH

        self.globals = {}
        self.locals = {}
        self.rubymap = {}

        self.root = None
        self.text_indent = Text.create(Text.INDENT)
        self.text_enter = Text.create(Text.ENTER)
        self.text_leave = Text.create(Text.LEAVE)
        self.text_newline = Text('\n')

    def is_single(self, tag):
        return tag.lower() in self.TAG_SINGLE

    def is_embed(self, tag):
        return tag.lower() in self.TAG_EMBED

    def is_individual(self, tag):
        return tag.lower() in self.TAG_INDIVIDUAL

    def is_altcode(self, tag):
        return tag.lower() in self.TAG_ALTCODE

    def untabify(self, s):
        tab = self.tab_width
        def instab(pos): return ' ' * (tab - pos % tab)
        def inschr(ch, pos): return ch if ch != '\t' else instab(pos)
        return reduce(lambda v, c: v + inschr(c, len(v)), s, '')

    def exec(self, src):
        self.locals['HTML'] = None
        self.pyexec(src)
        return self.locals['HTML'] or ''

    def pyexec(self, src):
        src = self.reindent('', src)
        if not src:
            return
        if self.debug:
            self.dprintn(f'Python exec: {repr(src)}')
        exec(src, self.globals, self.locals)

    def generate(self):
        cwd = None
        path = self.stream.name
        if path and path != '-':
            wdir = os.path.dirname(path)
            if wdir:
                cwd = os.getcwd()
                os.chdir(wdir)
        self.root = self.parse_element(self.tree)
        if cwd:
            os.chdir(cwd)
        return self.root and self.build(self.root) or ''

    def parse_element(self, element):
        if element.open == '(':
            return self.parse_element_tag(element.children)
        if element.open == '[':
            return self.parse_element_attribute(element.children)
        if element.open == '{':
            return self.parse_element_data(element.children)
        text = element.get_string() if not element.is_type('s') else ''
        children = self.parse_element_children(element.children)
        return Element(text=text, children=children)

    def parse_element_children(self, children):
        return [self.parse_element(child) for child in children]

    def parse_element_tag(self, elements):
        tag = elements[0].get_string()
        allchildren = self.parse_element_children(elements[1:])
        attributes = [c for c in allchildren if c.tag is None and c.attribute]
        if tag in self.TAG_ATTRIBUTE:
            attribute = [c.attribute for c in attributes]
        else:
            attribute = reduce(lambda p, v: p + v.attribute, attributes, [])
        children = [c for c in allchildren if c.tag or not c.attribute]
        return Element(tag=tag, attribute=attribute, children=children)

    def parse_element_attribute(self, elements):
        params = []
        data = []
        for elem in elements:
            if not elem.has_value():
                raise NotImplementedError
            if not elem.is_type('s'):
                data.append(self.parse_element(elem))
                continue
            if data:
                params += [data]
                data = []
        if data:
            params += [data]
        return Element(attribute=params)

    def parse_element_data(self, elements):
        return Element(text=self.read_source(elements))

    def parse_dump(self, element, level=0):
        indent = '  ' * level
        print(f'{indent}Element(tag={repr(element.tag)},'
              f' attribute={repr(element.attribute)},'
              f' text={repr(element.text)})')
        for child in element.children:
            self.parse_dump(child, level + 1)

    def build(self, element):
        html = self.build_text(self.build_element(element))
        if html and html[-1] != '\n':
            html += '\n'
        return html

    def build_element(self, element):
        tag = element.tag
        ltag = tag.lower() if tag else ''

        def get_children():
            return self.build_element_children(element.children)

        def get_children_string():
            return self.build_text(get_children())

        if ltag == '@while':
            return self.build_while(element.attribute, element.children)

        attribute = self.build_attribute_text(element.attribute)

        if ltag and ltag[0] in '!#$@':
            if ltag == '!doctype':
                doctype = self.build_text(get_children()).strip()
                doctype = ' ' + doctype if doctype else doctype
                return [self.text_indent, Text(f'<{tag}{doctype}>'), self.text_newline]
            if ltag == '@comment':
                return [self.text_indent, Text('<!-- '),
                        Text(get_children_string()),
                        Text(' -->')]
            if ltag == '#comment':
                return []
            if ltag == '@ruby':
                ruby = self.build_element_ruby(element.children)
                return [Text(f'<ruby{attribute}>'), *ruby, Text('</ruby>')]
            if ltag == '@python':
                return self.build_python_exec(element.children)
            if ltag == '$python':
                return self.build_python_run(element.children)

            if self.debug:
                self.dprintn(f'NOT IMPLMENETED YET: {tag}')
            return []

        if not ltag:
            if element.attribute:
                raise Exception(f'Bug??\n  attribute={repr(element.attribute)}')
            children = get_children()
            text = element.text
            if text:
                children.append(Text(text))
            return children

        stag, etag = (f'<{tag}{attribute}>', f'</{tag}>')

        if ltag in self.TAG_EMBED:
            return ((ltag in self.TAG_SINGLE) and [Text(stag)] or
                    [Text(stag), *get_children(), Text(etag)])
        if ltag in self.TAG_SINGLE:
            return [self.text_indent, Text(stag)]
        if ltag in self.TAG_INDIVIDUAL:
            return [self.text_indent, Text(stag), *get_children(), Text(etag)]
        if ltag in self.TAG_ALTCODE:
            return [self.text_indent,
                    Text(stag), self.text_newline,
                    self.text_enter, Text.create_reindent(get_children_string()),
                    self.text_leave, self.text_indent,
                    Text(etag), self.text_newline]
        return [self.text_indent, Text(stag),
                self.text_enter, *get_children(),
                self.text_leave, Text(etag), self.text_newline]

    def build_element_children(self, children):
        return reduce(lambda p, v: p + self.build_element(v), children, [])

    def build_element_ruby(self, elements):
        text = []
        for element in elements:
            if element.tag:
                text += self.build_element(element)
                continue
            param = element.text
            if not param:
                continue
            p = param.split(':', 1)
            if len(p) == 1:
                t = self.rubymap.get(p[0])
                if not t:
                    continue
                p.append(t)

            k, v = p
            self.rubymap[k] = v

            s, t = p[0], p[1].split(',')
            r = []
            for n in range(len(t)):
                k, v = s[n], t[n]
                self.rubymap[k] = v
                text.append(Text(
                    f'{self.escape(k)}<rp>(</rp>'
                    f'<rt>{self.escape(v)}</rt>'
                    f'<rp>)</rp>'
                ))
        return text

    def build_while(self, attributes, elements):
        params = [[e.text for el in attr for e in el] for attr in attributes]
        text = []
        if params and params[0]:
            name = params[0][0]
            [self.pyexec(s) for s in params[0][1:]]
            while name in self.locals and self.locals[name]:
                text += self.build_element_children(elements)
                [self.pyexec(s) for param in params[1:] for s in param]
        return text

    def build_python(self, elements, callback):
        text = []
        for element in elements:
            if element.tag:
                text += self.build_element(element)
            else:
                text.append(Text(callback(element.text)))
        return text

    def build_python_exec(self, elements):
        return self.build_python(elements, lambda s: self.exec(s))

    def build_python_run(self, elements):
        def cb(s): return self.run(PYTHON_COMMAND, self.reindent('', s))
        return self.build_python(elements, cb)

    def build_attribute_text(self, attributes):
        if not attributes:
            return ''
        text = ''
        for elements in attributes:
            attr = ''.join(self.build_text(self.build_element(element)) for element in elements)
            adata = attr.split('=', 1)
            value = self.qstrip(adata[1] if len(adata) > 1 else '')
            text += f' {adata[0]}="{self.escape(value)}"'
        return text

    def build_text(self, texts):
        r = ''
        level = 0
        indent = ''
        newline = ''
        for text in texts:
            if text.mode == Text.TEXT:
                if '\n' in text:
                    newline = '\n'
                r += text
                continue
            if text.mode == Text.INDENT:
                if r and r[-1] != '\n':
                    r += '\n'
                r += indent + text
                continue
            if text.mode == Text.ENTER:
                newline = ''
                level += 1
                indent = '  ' * level
                r += text
                continue
            if text.mode == Text.LEAVE:
                level -= 1
                indent = '  ' * level
                if newline:
                    if r[-1] != '\n':
                        r += newline
                    r += indent
                r += text
                newline = '\n'
                continue
            if text.mode == Text.REINDENT:
                r += self.reindent(indent, text)
                continue
            raise Exception('Bug!!')
        return r

    def read_source(self, param):
        r = ''
        for code in param:
            if not code.is_type('s'):
                r += open(code.get_string()).read()
        return r

    def dprint(self, *args, **kwargs):
        sys.stderr.write(' '.join(str(arg) for arg in args))

    def dprintn(self, *args, **kwargs):
        sys.stderr.write(' '.join(str(arg) for arg in args) + '\n')


# -----------------------------------------------------------------------------


if __name__ == '__main__':
    def main():
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--debug', action='store_true', default=False)
        parser.add_argument('-a', '--altindent', action='store_false', default=True)
        parser.add_argument('--tab-width', metavar='N', type=int, default=TAB_WIDTH)
        parser.add_argument('inpfile', metavar='INP', nargs='?', default='-')
        parser.add_argument('outfile', metavar='OUT', nargs='?', default='-')

        args = parser.parse_args()

        stream = Stream(args.inpfile)
        genhtml = GenHTML(stream,
                          debug=args.debug,
                          altindent=args.altindent,
                          tab_width=args.tab_width)
        html = genhtml.generate()
        opath = args.outfile
        if not opath or opath == '-':
            sys.stdout.write(html)
        else:
            open(opath, 'w').write(html)

    main()

# -----------------------------------------------------------------------------
