#!/usr/bin/env python3

import os
import sys
import subprocess
import time

from functools import reduce

# -----------------------------------------------------------------------------

DEFAULT_TAB_WIDTH = 4

PYTHON_COMMAND = 'python3'

# -----------------------------------------------------------------------------


class SxSyntaxError(BaseException):
    def __init__(self, name, line, msg):
        super().__init__(f'{name}:{line}: syntax error: {msg}')


# -----------------------------------------------------------------------------


class String(str):
    def __init__(self, *args):
        if args:
            arg0 = args[0]
            if isinstance(arg0, String):
                self.name = arg0.name
                self.line = arg0.line
                self.offset = arg0.offset
                return
        self.name = None
        self.line = None
        self.offset = None

    def __add__(self, rhs):
        return String.create(self.name, self.line, self.offset, super().__add__(rhs))

    def setparam(self, name, line, offset):
        self.name = name
        self.line = line
        self.offset = offset
        return self

    @ staticmethod
    def create(name, line, offset, data=''):
        return String(data).setparam(name, line, offset)


class ReadStream:
    def __init__(self, name, stream=None):
        self.stdin = name == '-'
        self.bstream = bool(stream)
        self.name = '[STDIN]' if self.stdin else name
        self.stream = (stream if stream else
                       sys.stdin if self.stdin else open(name))
        self.lines = []
        self.line = ''
        self.number = 0
        self.offset = 0
        self.pending = []

    def __iter__(self):
        return self

    def __next__(self):
        char = self.getchar()
        if char is None:
            raise StopIteration
        return char

    def __enter__(self):
        if not self.stdin and not self.bstream:
            self.stream.__enter__()
        return self

    def __exit__(self, etype, value, trace):
        if not self.stdin and not self.bstream:
            return self.stream.__exit__(etype, value, trace)
        return None

    def getline(self):
        line = self.stream.readline()
        if line:
            self.lines.append(line)
            self.line = line
            self.number += 1
            self.offset = 0
        return line

    def getchar(self):
        if self.pending:
            return self.pending.pop()
        if self.offset >= len(self.line):
            if not self.getline():
                return None
        offset = self.offset
        self.offset = offset + 1
        return String.create(self.name, self.number, offset, self.line[offset])

    def putchar(self, char):
        self.pending.append(char)
        return self

    def readchar(self, count):
        chars = tuple(self.getchar() for _ in range(count))
        return (''.join(filter(lambda v: v, chars)), chars)

    def writechar(self, chars):
        self.pending += reversed(chars)
        return self

    def emptychar(self):
        return String.create(self.name, self.number, self.offset, '')

    def read(self):
        return self.stream.read()


class WriteStream:
    def __init__(self, name, stream=None):
        self.stdout = name == '-'
        self.bstream = bool(stream)
        self.name = '[STDOUT]' if self.stdout else name
        self.stream = (stream if stream else
                       (sys.stdout if self.stdout else open(name, 'w')))

    def __enter__(self):
        if not self.stdout and not self.bstream:
            self.stream.__enter__()
        return self

    def __exit__(self, etype, value, trace):
        if not self.stdout and not self.bstream:
            return self.stream.__exit__(etype, value, trace)
        return None

    def write(self, data):
        return self.stream.write(data)


# -----------------------------------------------------------------------------


class SxElement():
    BRACKET = {'': '', '(': ')', '[': ']', '{': '}'}

    def __init__(self, bracket, value=None):
        self.open = bracket
        self.close = SxElement.BRACKET[bracket]
        self.children = []
        self.value = value

    def __len__(self):
        return len(self.children)

    def __iter__(self):
        return iter(self.children)

    def has_value(self):
        return self.value

    def is_type(self, char):
        return self.value and char == self.value[0]

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
            vtype, vstr = self.value
            vstr = vstr.replace('\t', '\\t')
            vstr = vstr.replace('\n', '\\n')
            print(f'{indent}type:{vtype}, data:{vstr}')


class Lexer:
    def __init__(self, stream, **option):
        self.charset_space = set(map(chr, range(33)))
        self.charset_wstop = self.charset_space | set('()[]{}\'"')
        self.char_type = {chr(n): self.getword for n in range(0x21, 0x80)}
        self.char_type.update({'"': self.getdquote, "'": self.getquote})
        self.char_type.update({chr(c): self.getspace for c in range(0, 33)})
        self.char_type.update({c: self.getbracketopen for c in '([{'})
        self.char_type.update({c: self.getbracketclose for c in '}])'})
        self.escape_map = {'t': '\t', 'n': '\n'}

        self.stream = stream
        self.debug = option['debug']

    # 'o': open
    # 'c': close
    # 's': space
    # 'q': quoted
    # 'w': word?

    def gettoken(self):
        char = self.stream.getchar()
        return self.char_type[min(char, '\x7F')](char) if char else None

    def getspace(self, space):
        for char in iter(self.stream.getchar, None):
            if char not in self.charset_space:
                self.stream.putchar(char)
                break
            space += char
        return ('s', space)

    def getword(self, word):
        stop = self.charset_wstop
        for char in iter(self.stream.getchar, None):
            if char in stop:
                self.stream.putchar(char)
                break
            word += char
        return ('w', word)

    def getbracketopen(self, char):
        return ('o', char)

    def getbracketclose(self, char):
        return ('c', char)

    def getquote(self, qch):
        qstr = self.stream.emptychar()
        escape = False
        for char in self.stream:
            if escape:
                escape = False
                qstr += self.escape_map.get(char, char)
            elif char == '\\':
                escape = True
            elif char == qch:
                return ('q', qstr)
            else:
                qstr += char
        raise NotImplementedError

    def getdquote(self, qch):
        nstr, nchr = self.stream.readchar(3)
        if nstr == '""[':
            return self.getlongquote()
        self.stream.writechar(nchr)
        return self.getquote(qch)

    def getlongquote(self):
        stream = self.stream
        qstr = stream.emptychar()
        for char in stream:
            if char == ']':
                nstr, nchr = stream.readchar(3)
                if nstr == '"""':
                    return ('q', qstr)
                stream.writechar(nchr)
            qstr += char
        raise NotImplementedError


class Parser(Lexer):
    def __init__(self, stream, **option):
        super().__init__(stream, **option)
        last = SxElement('')
        stack = [last]
        for token in iter(self.gettoken, None):
            ttype, tstr = token
            if ttype == 'o':
                last = SxElement(tstr)
                stack.append(last)
                continue
            if ttype == 'c':
                if tstr != stack[-1].close:
                    raise SxSyntaxError(
                        self.stream.name,
                        self.stream.line,
                        f'unmatched: "{stack[-1].open} ... {tstr}"')
                nest = stack.pop()
                last = stack[-1]
                last.append(nest)
                continue
            last.append(SxElement('', token))
        if len(stack) != 1:
            raise SxSyntaxError(
                self.stream.name,
                self.stream.line,
                f'missing "{stack[-1].close}"')
        self.tree = stack.pop()

    def dump(self):
        return self.tree.dump()


# -----------------------------------------------------------------------------


class Element:
    def __init__(self, tag=None, attribute=None, text=None, children=None):
        self.tag = tag
        self.attribute = attribute
        self.text = text
        self.children = children if children else []

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

    def __init__(self, *_):
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


class RubyMap:
    def __init__(self):
        self.child = {}
        self.value = []

    def get(self, key):
        rmap = self
        for kchr in key:
            rmap = rmap.child.get(kchr)
            if rmap is None:
                return None
        return rmap.value

    def set(self, key, value):
        rmap = self
        for kchr in key:
            child = rmap.child.get(kchr)
            if not child:
                child = RubyMap()
                rmap.child[kchr] = child
            rmap = child
        rmap.value = value


class GenHTML(Parser):
    class BuildTextStats:
        def __init__(self):
            self.text = ''
            self.level = 0
            self.indent = ''
            self.newline = ''

    TAG_SINGLE = {
        'area',
        'base', 'bgsound',
        'col',
        'embed',
        'frame',
        'hr',
        'image',
        'keygen',
        'link',
        'menuitem', 'meta',
        'param',
        'source',
        'track',
    }

    TAG_EMBED = {
        'a', 'abbr', 'acronym', 'audio',
        'b', 'bdi', 'bdo', 'big', 'blink', 'button',
        'canvas', 'cite', 'code',
        'data', 'del', 'dfn',
        'em',
        'font',
        'i', 'ins',
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
    }

    TAG_EMBED_SINGLE = {
        'br',
        'img', 'input',
        'wbr',
    }

    TAG_INDIVIDUAL = {
        'title',
    }

    TAG_ALTCODE = {
        'script',
        'style',
    }

    # --------------------

    @staticmethod
    def qstrip(qstr):
        if len(qstr) >= 2 and qstr[0] == qstr[-1] and qstr[0] in ('\'', '"'):
            return qstr[1:-1]
        return qstr

    @staticmethod
    def encode(estr):
        return (estr.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))

    @staticmethod
    def run(command, stdin):
        return subprocess.run(args=[command, '-'], input=stdin.encode('utf-8'),
                              capture_output=True, check=True).stdout.decode()

    # --------------------

    def __init__(self, stream, **option):
        super().__init__(stream, **option)

        self.tag_flowcontrol = {
            '@unless': self.build_unless,
            '@when': self.build_when,
            '@while': self.build_while,
        }
        self.tag_command = {
            '!doctype': self.build_doctype,
            '@comment': self.build_comment,
            # '#comment': self.build_none,
            '$date': self.build_date,
            '@ruby': self.build_ruby,
            '#ruby': self.build_ruby_dict,
            '$ruby': self.build_ruby_auto,
            '@python': self.build_python_exec,
            '$python': self.build_python_run,
        }
        self.open_type = {
            '(': self.parse_element_tag,
            '[': self.parse_element_attribute,
            '{': self.parse_element_data,
            '': self.parse_element_text,
        }

        self.tag_table = {}
        self.tag_table.update({tag: self.build_element_embed for tag in self.TAG_EMBED})
        self.tag_table.update({tag: self.build_element_embed_single for tag in self.TAG_EMBED_SINGLE})
        self.tag_table.update({tag: self.build_element_single for tag in self.TAG_SINGLE})
        self.tag_table.update({tag: self.build_element_individual for tag in self.TAG_INDIVIDUAL})

        self.altindent = option['altindent'] if 'altindent' in option else True
        self.tab_width = option['tab_width'] if 'tab_width' in option else DEFAULT_TAB_WIDTH

        self.globals = {}
        self.locals = {}
        self.rubymap = RubyMap()

        self.root = None
        self.text_indent = Text.create(Text.INDENT)
        self.text_enter = Text.create(Text.ENTER)
        self.text_leave = Text.create(Text.LEAVE)
        self.text_newline = Text('\n')

        self.plain = False

    # --------------------

    def untabify(self, line):
        tab = self.tab_width
        if not line.count('\t'):
            return line
        rline = line.lstrip()
        lline = ''
        for char in line[:len(line) - len(rline)]:
            lline += char if char != '\t' else ' ' * (tab - len(lline) % tab)
        return lline + rline

    def reindent(self, indent, text):
        lines = [self.untabify(s) for s in text.split('\n')]
        while lines and not lines[+0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        cut = min([80, *[len(l) - len(l.lstrip()) for l in lines if l]])
        return ''.join((indent + l[cut:] + '\n' if l.strip() else '\n') for l in lines)

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

    def pyvalue(self, name):
        return self.locals[name] if name and name in self.locals else None

    # --------------------

    def update_ruby_dict(self, text):
        rpdata = text.split(':', 1)
        keys = rpdata[0].strip()
        smap = self.rubymap.get(keys)
        if smap is None and len(rpdata) == 1:
            return None
        if len(rpdata) > 1:
            vals = [v.strip() for v in rpdata[1].split(',')]
            if len(vals) == 1:
                smap = [[keys, vals[0]]]
            else:
                smap = [[v, (vals[n] if n < len(vals) else '')]
                        for n, v in enumerate(keys)]
        self.rubymap.set(keys, smap)
        return smap

    def update_ruby_dict_file(self, path):
        with open(path, encoding='utf-8') as dicfp:
            for line in dicfp.readlines():
                line = line.strip()
                if line and line[0] != '#':
                    self.update_ruby_dict(line)

    # --------------------

    def generate(self):
        cwd = None
        path = self.stream.name
        if path and path != '-':
            wdir = os.path.dirname(path)
            if wdir:
                cwd = os.getcwd()
                os.chdir(wdir)
        self.root = self.parse_element(self.tree)
        text = self.build(self.root) if self.root else ''
        if cwd:
            os.chdir(cwd)
        return text

    # --------------------

    def parse_element(self, element):
        return self.open_type[element.open](element)

    def parse_element_children(self, children):
        return [self.parse_element(child) for child in children]

    def parse_element_tag(self, element):
        elements = element.children
        tag = elements[0].get_string()
        allchildren = self.parse_element_children(elements[1:])
        attributes = [c for c in allchildren if c.tag is None and c.attribute]
        if tag in self.tag_flowcontrol:
            attribute = [c.attribute for c in attributes]
        else:
            attribute = reduce(lambda p, v: p + v.attribute, attributes, [])
        children = [c for c in allchildren if c.tag or not c.attribute]
        return Element(tag=tag, attribute=attribute, children=children)

    def parse_element_attribute(self, element):
        elements = element.children
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

    def parse_element_data(self, element):
        return Element(text=self.parse_element_source(element.children))

    def parse_element_text(self, element):
        text = element.get_string() if not element.is_type('s') else ''
        children = self.parse_element_children(element.children)
        return Element(text=text, children=children)

    def parse_element_source(self, param):
        return ''.join(ReadStream(code.get_string()).read()
                       for code in param if not code.is_type('s'))

    def parse_dump(self, element, level=0):
        indent = '  ' * level
        print(f'{indent}Element(tag={repr(element.tag)},'
              f' attribute={repr(element.attribute)},'
              f' text={repr(element.text)})')
        for child in element.children:
            self.parse_dump(child, level + 1)

    # --------------------

    def build(self, element):
        html = self.build_text(self.build_element(element))
        if html and html[-1] != '\n':
            html += '\n'
        return html

    def build_element(self, element):
        tag = element.tag
        ltag = tag.lower() if tag else ''

        flowcontrol = self.tag_flowcontrol.get(ltag)
        if flowcontrol:
            name, updater = self.build_flowcontrol(element)
            return flowcontrol(element.children, name, updater) if name else []

        attribute = self.build_attribute_list(element.attribute)

        if not ltag:
            children = self.get_element_children(element)
            text = element.text
            if text:
                children.append(Text(text if self.plain else self.encode(text)))
            return children

        if ltag[0] in '!#$@':
            return self.tag_command.get(ltag, self.build_none)(tag, attribute, element)

        stag, etag = (f'<{tag}{self.build_attribute_text(attribute)}>', f'</{tag}>')

        if ltag in self.TAG_ALTCODE:
            text = self.get_element_children_text(element)
            return [self.text_indent,
                    Text(stag), self.text_newline,
                    self.text_enter, Text.create_reindent(text),
                    self.text_leave, self.text_indent,
                    Text(etag), self.text_newline]

        children = self.get_element_children(element)
        return (self.tag_table.get(ltag, self.build_element_normal)(ltag, stag, etag, children))

    def build_element_embed(self, ltag, stag, etag, children):
        return ([Text(stag)] if ltag in self.TAG_SINGLE else
                [Text(stag), *children, Text(etag)])

    def build_element_embed_single(self, _ltag, stag, _etag, _children):
        return [Text(stag)]

    def build_element_single(self, _ltag, stag, _etag, _children):
        return [self.text_indent, Text(stag)]

    def build_element_individual(self, _ltag, stag, etag, children):
        return [self.text_indent, Text(stag), *children, Text(etag), self.text_newline]

    def build_element_normal(self, _ltag, stag, etag, children):
        return [self.text_indent, Text(stag), self.text_enter, *children,
                self.text_leave, Text(etag), self.text_newline]

    def get_element_children(self, element):
        return self.build_element_children(element.children)

    def get_element_children_text(self, element):
        plain = self.plain
        self.plain = True
        text = self.build_text(self.get_element_children(element))
        self.plain = plain
        return text

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
            smap = self.update_ruby_dict(param)
            if smap is None:
                text.append(Text(param.split(':', 1)[0]))
            else:
                text += self.build_text_ruby(smap)
        return text

    def build_attribute_list(self, attributes):
        rlist = []
        for elements in (attributes if attributes else []):
            attr = ''.join(self.build_text(self.build_element(element)) for element in elements)
            adata = attr.split('=', 1)
            value = self.qstrip(adata[1] if len(adata) > 1 else '')
            rlist.append([adata[0], value])
        return rlist

    def build_attribute_text(self, attributes):
        return ''.join(f' {name}="{self.encode(value)}"' for name, value in attributes)

    def build_text(self, texts):
        rtext = ''
        level = 0
        indent = ''
        newline = ''
        for text in texts:
            if text.mode == Text.TEXT:
                if not newline and '\n' in text:
                    newline = '\n'
                rtext += text
            elif text.mode == Text.INDENT:
                if rtext and rtext[-1] != '\n':
                    rtext += '\n'
                rtext += indent + text
            elif text.mode == Text.ENTER:
                newline = ''
                level += 1
                indent = '  ' * level
                rtext += text
            elif text.mode == Text.LEAVE:
                level -= 1
                indent = '  ' * level
                if newline:
                    if rtext[-1] != '\n':
                        rtext += newline
                    rtext += indent
                rtext += text
                newline = '\n'
            elif text.mode == Text.REINDENT:
                rtext += self.reindent(indent, text)
        return rtext

    def build_text_ruby(self, param):
        return [Text(f'{self.encode(rbase)}'
                     '<rp>(</rp>'
                     f'<rt>{self.encode(rtext)}</rt>'
                     '<rp>)</rp>')
                for rbase, rtext in param]

    # --------------------

    def build_none(self, _tag, _attribute, _element):
        return []

    def build_doctype(self, tag, _attribute, element):
        doctype = self.get_element_children_text(element).strip()
        doctype = ' ' + doctype if doctype else doctype
        return [self.text_indent, Text(f'<{tag}{doctype}>'), self.text_newline]

    def build_comment(self, _tag, _attribute, element):
        text = self.get_element_children_text(element)
        return [self.text_indent, Text('<!-- '), Text(text), Text(' -->')]

    def build_date(self, _tag, _attribute, element):
        text = self.get_element_children_text(element)
        return [Text(time.strftime(text if text else '%Y/%m/%d %H:%M:%S'))]

    def build_ruby(self, tag, attribute, element):
        tag, attribute = tag[1:], self.build_attribute_text(attribute)
        ruby = self.build_element_ruby(element.children)
        return [Text(f'<{tag}{attribute}>'), *ruby, Text(f'</{tag}>')]

    def build_ruby_dict(self, _tag, attribute, element):
        for name, value in attribute:
            if name.lower() == 'dict':
                self.update_ruby_dict_file(value)
        self.get_element_children_text(element)
        return []

    def build_ruby_auto(self, tag, attribute, element):
        tag, attribute = tag[1:], self.build_attribute_text(attribute)
        stag = Text(f'<{tag}{attribute}>')
        etag = Text(f'</{tag}>')

        text = []
        for child in element.children:
            if child.tag:
                text += self.build_element(child)
                continue
            base = child.text
            if not base:
                continue

            bpos = 0
            pending = ''
            check = ''
            mpos = self.rubymap
            enter = False
            while bpos < len(base):
                bchr = base[bpos]
                msub = mpos.child.get(bchr)
                if msub:
                    if pending:
                        if enter:
                            text.append(etag)
                            enter = False
                        text.append(Text(self.encode(pending)))
                        pending = ''
                    check += bchr
                    bpos += 1
                    mpos = msub
                    continue

                if not check:
                    pending += bchr
                    bpos += 1
                    continue

                if not enter:
                    text.append(stag)
                    enter = True
                text += self.build_text_ruby(mpos.value)
                check = ''
                mpos = self.rubymap

            if check:
                if not enter:
                    text.append(stag)
                    enter = True
                text += self.build_text_ruby(mpos.value)
            if enter:
                text.append(etag)
            if pending:
                text.append(Text(self.encode(pending)))

        return text

    # --------------------

    def build_flowcontrol(self, element):
        params = [[e.text for el in attr for e in el]
                  for attr in element.attribute]
        if not (params and params[0]):
            return (None, None)
        name = params[0][0]
        for statement in params[0][1:]:
            self.pyexec(statement)

        def updater():
            text = self.build_element_children(element.children)
            for param in params[1:]:
                for statement in param:
                    self.pyexec(statement)
            return text
        return (name, updater)

    def build_unless(self, _elements, name, updater):
        return updater() if not self.pyvalue(name) else []

    def build_when(self, _elements, name, updater):
        return updater() if self.pyvalue(name) else []

    def build_while(self, _elements, name, updater):
        text = []
        while self.pyvalue(name):
            text += updater()
        return text

    # --------------------

    def build_python(self, elements, callback):
        return reduce(lambda p, e:
                      p + (self.build_element(e) if e.tag else
                           [Text(callback(e.text))]),
                      elements, [])

    def build_python_exec(self, _tag, _attribute, element):
        return self.build_python(element.children, self.exec)

    def build_python_run(self, _tag, _attribute, element):
        return self.build_python(element.children,
                                 lambda s: self.run(PYTHON_COMMAND,
                                                    self.reindent('', s)))

    # --------------------

    def dprint(self, *args):
        sys.stderr.write(' '.join(str(arg) for arg in args))

    def dprintn(self, *args):
        sys.stderr.write(' '.join(str(arg) for arg in args) + '\n')


# -----------------------------------------------------------------------------


if __name__ == '__main__':
    import argparse

    def main():
        parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--debug', action='store_true', default=False)
        parser.add_argument('-a', '--altindent', action='store_false', default=True)
        parser.add_argument('--tab-width', metavar='N', type=int, default=DEFAULT_TAB_WIDTH)
        parser.add_argument('inpfile', metavar='INP', nargs='?', default='-')
        parser.add_argument('outfile', metavar='OUT', nargs='?', default='-')

        args = parser.parse_args()

        with ReadStream(args.inpfile) as stream:
            genhtml = GenHTML(stream,
                              debug=args.debug,
                              altindent=args.altindent,
                              tab_width=args.tab_width)

        html = genhtml.generate()

        with WriteStream(args.outfile) as stream:
            stream.write(html)

    main()

# -----------------------------------------------------------------------------
