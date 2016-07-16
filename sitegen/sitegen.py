# -*- coding: utf-8 -*-

# Static Site Generator powered by markdown and jinja2
# Copyright (c) 2012-2016 MIZUGUCHI Yasuhiko
# based on http://obraz.pirx.ru/
# install requirements: Jinja2, PyYAML, pandoc(from cabal)

import sys
import io
import traceback
import os
import re
import shutil
import fnmatch
from contextlib import contextmanager
import errno
import yaml
import subprocess
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PackageLoader
from jinja2.exceptions import TemplateSyntaxError

from html.parser import HTMLParser

DEBUG = False
PAGE_ENCODING = 'UTF-8'
DEFAULT_TEMPLATE = 'default.j2.html'
IGNORE_LIST = ['.', '.*','_', '*~', '#*#']

def makedirs(directory):
    if os.path.exists(directory):
        return
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass

class File:
    def __init__(self, basedir, path):
        self.basedir = basedir
        self.path = path
        self.filename = os.path.join(basedir, path)
        self.basename = os.path.basename(self.filename)
        self.dirname = os.path.dirname(self.filename)
        _, self.suffix = os.path.splitext(self.basename)

    def exists(self):
        return os.path.exists(self.filename)

    def mtime(self):
        return os.path.getmtime(self.filename)

    def open(self):
        return open(self.filename, 'rb')

    def makedirs(self):
        makedirs(self.dirname)

    def remove(self):
        try:
            os.remove(self.filename)
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass

    def change_ext(self, ext):
        """
          ex. ext = '.docx' or 'docx'
        """
        a, _ = os.path.splitext(self.path)
        e = ext.lstrip('.')
        return File(self.basedir,'{}.{}'.format(a,e))

    def abspath(self):
        return os.path.abspath(self.filename)

def load_metadata(source):
    """
    split file contents into metadata and remaining contents

    metadata is yaml formatted data at head tagged by two '---' lines

        ---
        yaml formatted metadata
        ---
        contents
    """
    SPLIT = r'^---+\s*'
    metadata = {}
    line_offset = 0
    content = source

    i = 0
    lines = source.splitlines()

    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if re.match(SPLIT, lines[i]):
            i += 1
            yaml_start = i
            while i < len(lines):
                if re.match(SPLIT, lines[i]):
                    yaml_end = i
                    i += 1
                    break
                i += 1
            metadata = yaml.load('\n'.join(lines[yaml_start:yaml_end])) or metadata
            line_offset = yaml_end+1
            content = '\n'.join(lines[line_offset:])
        else:
            break
    return metadata, line_offset, content

def remove(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass

def log(message):
    sys.stderr.write('{0}\n'.format(message))
    sys.stderr.flush()

def print_exception_traceback():
    import sys
    e, m, tb = sys.exc_info()
    print('exception traceback:'.ljust(80, '='))
    for tbi in traceback.format_tb(tb):
        print(tbi)
    print('  %s' % str(m))
    print(''.rjust(80, '='))
    if DEBUG:
        import pdb
        pdb.post_mortem(tb)

@contextmanager
def report_exceptions():
    try:
        yield
    except KeyboardInterrupt:
        raise KeyboardInterrupt()
    except Exception:
        print_exception_traceback()

def is_ignored(filename, ignore_list):
    for ignore in ignore_list:
        if any(fnmatch.fnmatch(part, ignore) for part in filename.split(os.path.sep)):
            return False
    return True

def all_files(basedir, ignore_list=None):
    for path, dirs, files in os.walk(basedir):
        for file in files:
            abspath = os.path.join(path, file)
            relpath = os.path.relpath(abspath, basedir)

            if ignore_list and not is_ignored(relpath, ignore_list):
                continue

            yield abspath, relpath


class HeadElement:
    def __init__(self, level=0, aname=None, data=""):
        self.level = level
        self.aname = aname
        self.data = data
        self.children = []

    def add_data(self, data):
        self.data += data

    def add_child(self, aname=None, data=""):
        e = HeadElement(self.level+1, aname, data)
        self.children.append(e)
        return e

    def get_child_last(self, level):
        if level==self.level:
            return self
        else:
            assert(level > self.level)
            if not self.children:
                self.add_child(None, "no title")
            return self.children[-1].get_child_last(level)

    def write(self, out):
        out.write('<li>')

        text = self.data
        if len(self.data) > 10 and ';' in self.data:
            text = self.data.split(';')[0]

        if self.aname:
            out.write('<a href="#{}">{}</a>'.format(self.aname, text))
        else:
            out.write('{}'.format(text))
        if self.children:
            out.write('<ul class="nav">\n')
            self.write_children(out)
            out.write('</ul>\n')
        out.write('</li>\n')

    def write_children(self, out):
        for c in self.children:
            c.write(out)

class TocParser(HTMLParser):
    def __init__(self, input):
        HTMLParser.__init__(self)
        self._current = None
        self.heads = HeadElement()
        self.feed(input)

    def handle_starttag(self, tag, attrs):
        m = re.match('h(\d)',tag)
        if not m:
            return

        level = int(m.group(1))
        assert(0 < level)

        attrs = { k:v for (k,v) in attrs }

        aname = attrs.get('id')

        # parent
        parent = self.heads.get_child_last(level-1)
        e = parent.add_child(aname)

        self._current = e

    def handle_endtag(self, tag):
        m = re.match('h(\d)',tag)
        if not m:
            return
        self._current = None

    def handle_data(self, data):
        if self._current:
            self._current.add_data(data)

    def get_toc(self):
        out = io.StringIO()
        self.heads.write_children(out)
        return out.getvalue()

class TemplateEngine:
    def __init__(self, templatedir=None):
        self.templatedir = templatedir
        self.defaultloader = PackageLoader("sitegen", "templates")
        if templatedir:
            loader = ChoiceLoader([
                FileSystemLoader(templatedir),
                self.defaultloader])
        else:
            loader = self.defaultloader

        self.env = Environment(loader=loader)

    def render(self, template, metadata):
        try:
            t = self.env.get_template(template)
            # env.from_string()
            return t.render(**metadata)
        except TemplateSyntaxError as e:
            raise Exception("{0}:{1}: {2}, {3}".format(e.filename, e.lineno, e.name, e.message))

    def lastmodified(self):
        "return if one of the template is updated."
        lm = os.path.getmtime(os.path.abspath(__file__))
        if self.templatedir:
            lm = max(lm, max(os.path.getmtime(abspath) for abspath, relpath in all_files(self.templatedir, IGNORE_LIST)))
        return lm

class Pandoc:
    # based on https://github.com/bebraw/pypandoc/blob/master/pypandoc/pypandoc.py
    def __init__(self):
        self.src_fmts, self.dst_fmts = self.get_formats()

    def check_format(self, src_format, dst_format):
        if src_format not in self.src_fmts:
            raise RuntimeError('Invalid src format! Expected one of these: ' + ', '.join(self.src_fmts))
        if dst_format not in self.dst_fmts:
            raise RuntimeError('Invalid dst format! Expected one of these: ' + ', '.join(self.dst_fmts))

    def convert(self, src, src_format, dst_format, extra_args=[], cwd=None):
        self.check_format(src_format,dst_format)

        args = ['pandoc', '--from='+src_format, '--to='+dst_format]
        args.extend(extra_args)
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
        data,error = p.communicate(src)
        return data, error

    def convert_write(self, src, src_format, dst_filename, dst_format, extra_args=[], cwd=None):
        self.check_format(src_format,dst_format)
        args = ['pandoc', '--from='+src_format, '--to='+dst_format, '-o',dst_filename]
        args.extend(extra_args)
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
        data,error = p.communicate(src)
        return data, error

    def get_formats(self):
        '''
        Dynamic preprocessor for Pandoc formats.
        Return 2 lists. "from_formats" and "to_formats".
        '''
        p = subprocess.Popen(['pandoc', '-h'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        t = p.communicate()[0]
        help_text = t.decode('ascii').splitlines(False)
        txt = ' '.join(help_text[1:help_text.index('Options:')])

        aux = txt.split('Output formats: ')
        in_ = aux[0].split('Input formats: ')[1].split(',')
        out = aux[1].split(',')

        return [f.strip() for f in in_], [f.strip() for f in out]

pandoc = Pandoc()

class Site:
    """
        Site generate a list of pages from basedir
    """
    def __init__(self, basedir, template_engine):
        self.basedir = basedir
        self.template_engine = template_engine

        # todo load .ignore file
        self.pages = {}

        log('Loading source files...')

        for abspath, relpath in all_files(basedir, IGNORE_LIST):
            srcfile = File(basedir, relpath)

            with report_exceptions():
                if srcfile.suffix in ['.md', '.markdown']:
                    page = PageMarkdown(srcfile, template_engine)
                else:
                    page = PageFile(srcfile)
                self.pages[page.dstpath] = page

        log('Loaded {0} files'.format(len(self.pages)))

    def __iter__(self):
        for p in self.pages.values():
            yield p

    def get_page(self, path):
        return self.pages.get(path)

class PageBase:
    """
        Page knows dstpath, but don't know destination directory.
    """
    def __init__(self, srcfile, dstpath=None):
        self.srcfile = srcfile
        self.dstpath = dstpath or srcfile.path
        self.url = os.path.sep + self.dstpath
        self.basename = os.path.basename(self.url)

    def dependencies(self):
        """
        return path of all templates and includes which are refered by this page directly or indirectly
        """
        return []

    def dstfile(self, dstbasedir):
        return File(dstbasedir, self.dstpath)

    def generate(self, dstbasedir):
        dstfile = self.dstfile(dstbasedir)
        dstfile.makedirs()
        self._write(dstfile)

    def another_dstfiles(self, dstbasedir):
        return []

    def _write(self, dstfile):
        raise NotImplemented()


class PageFile(PageBase):
    def __init__(self, srcfile):
        super(PageFile, self).__init__(srcfile)

    def _write(self, dstfile):
        shutil.copy(self.srcfile.filename, dstfile.filename)

class PageTemplated(PageBase):
    def __init__(self, srcfile, template_engine):
        super(PageTemplated, self).__init__(srcfile, srcfile.change_ext('html').path)
        self.depth = len(self.url.strip('/').split('/')) - 1
        self.root = '/'.join(['..'] * (self.depth)) if self.depth>0 else '.'
        self.template_engine = template_engine

        def link(depth):
            if depth==0:
                return './' + self.basename
            elif depth==1:
                return './index.html'
            else:
                return '/'.join(['..'] * (depth-1)) + '/index.html'

        p, _ = os.path.splitext(self.url)
        p = ['Index'] + p.strip('/').split('/')

        self.parts = [(link(i), pp) for i,pp in enumerate(p[::-1])][::-1]
        if self.basename == 'index.html':
            self.parts.pop()

    def render_template(self, contents, metadata={}):
        metadata['contents'] = contents
        metadata['url'] = self.url
        metadata['root'] = self.root
        metadata['path'] = self.dstpath
        metadata['parts'] = self.parts
        metadata['mtime'] = self.srcfile.mtime()

        template = metadata.get('template') or DEFAULT_TEMPLATE
        return self.template_engine.render(template, metadata)

    def _write(self, dstfile):
        contents = self.srcfile.open().read().decode(PAGE_ENCODING)
        metadata = {}
        render = self.render_template(contents, metadata)
        with open(dstfile.filename, 'wb') as f:
            f.write(render.encode(PAGE_ENCODING))

class PageMarkdown(PageTemplated):
    def __init__(self, srcfile, template_engine):
        super(PageMarkdown, self).__init__(srcfile, template_engine)

    def _write(self, dstfile):
        with report_exceptions():
            source =  open(self.srcfile.filename, 'r').read()
            metadata, offset, content = load_metadata(source)
            extra_args=['--mathjax',
                        '--data-dir='+os.path.abspath(os.path.dirname(__file__)),
                        '--template=vars',
                        '--toc']
            if 'bibliography' in metadata:
                bib = os.path.abspath(os.path.join(self.srcfile.dirname, metadata['bibliography']))
                extra_args.append('--bibliography='+bib)
            if 'csl' in metadata:
                csl = metadata['csl']
                extra_args.append('--csl='+csl)

            s,error = pandoc.convert(content.encode(PAGE_ENCODING), 'markdown', 'html5', extra_args, cwd=self.srcfile.dirname)
            if not s.strip():
                title = 'ERROR'
                toc = ''
                body = '<pre>{}</pre>'.format(error.decode(PAGE_ENCODING))
            else:
                title, toc, body = s.decode(PAGE_ENCODING).split('<><><><>')
                title = title.strip()

                body = body.replace('<table>','<table class="table table-hover table-condensed table-bordered">') # TODO: dirty ad-hoc
                body = body.replace('[TOC]', toc)

                toc = TocParser(body).get_toc().strip()
                if error:
                    log(error)

            if title:
                metadata['title'] = title
            metadata['toc'] = toc
            metadata['offset'] = offset
            metadata['source'] = source

            with open(dstfile.filename, 'wb') as f:
                f.write(self.render_template(body, metadata).encode(PAGE_ENCODING))

            dd = dstfile.change_ext('docx')
            ref = os.path.abspath('reference.docx')
            s,error = pandoc.convert_write(content.encode(PAGE_ENCODING), 'markdown', dd.abspath(), 'docx',
                                           extra_args=['--reference-docx={}'.format(ref)], cwd=self.srcfile.dirname)
            if error:
                log(error)

    def another_dstfiles(self, dstbasedir):
        dstfile = self.dstfile(dstbasedir)
        return [dstfile.change_ext('docx')]

class SiteGenerator:
    def __init__(self, srcdir, dstdir, templatedir=None):
        #self.dependencies = []
        self.dstdir = dstdir
        self.template_engine = TemplateEngine(templatedir)
        self.site = Site(srcdir, self.template_engine)

    def generate(self):
        makedirs(self.dstdir)
        current_dst = set(abspath for abspath, relpath in all_files(self.dstdir))

        next_dst = set()
        for page in self.site:
            next_dst.add(page.dstfile(self.dstdir).filename)
            for i in page.another_dstfiles(self.dstdir):
                next_dst.add(i.filename)

        deleted_dst = current_dst - next_dst
        log('delete {0} abandoned files from destination directory'.format(len(deleted_dst)))
        for f in deleted_dst:
            log('delete {0}'.format(f))
            remove(f)

        tl = self.template_engine.lastmodified()

        for page in self.site:
            src = page.srcfile
            dst = page.dstfile(self.dstdir)

            # TODO: more accurate dependency graph.
            if dst.exists() and dst.mtime() > max(src.mtime(), tl):
                continue

            try:
                log('generating {0}...'.format(page.url))
                page.generate(self.dstdir)
            except KeyboardInterrupt:
                print('Keyboard interrupted.')
                return
            except:
                dst.remove()
                log('error while generating {0}'.format(page.url))
                print_exception_traceback()


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(prog='sitegen', description='generating html static site from markdown documents')
    parser.add_argument("inputdir", help="input directory")
    parser.add_argument("-o", "--output", dest="outputdir", help="output directory", default="_output")
    parser.add_argument("-t", "--template", dest="templatedir", help="template directory", default=None)

    args = parser.parse_args()

    inputdir = args.inputdir
    outputdir = args.outputdir

    if not inputdir:
        parser.error('no input directory')
        return

    sg = SiteGenerator(inputdir, outputdir, args.templatedir)
    sg.generate()
