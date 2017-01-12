# -*- coding: utf-8 -*-

# Static Site Generator powered by markdown and jinja2
# Copyright (c) 2012-2016 MIZUGUCHI Yasuhiko
# based on http://obraz.pirx.ru/
# install requirements: Jinja2, PyYAML, pyquery, pandoc(from cabal), asciidoctor

import sys, os, io, re, traceback, errno, subprocess
import shutil, fnmatch, yaml
from contextlib import contextmanager
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, PackageLoader
from jinja2.exceptions import TemplateSyntaxError
from pathlib import Path
from pyquery import PyQuery as pq


DEBUG = False
PAGE_ENCODING = 'UTF-8'
DEFAULT_TEMPLATE = 'default.j2.html'
MARKDOWN_TEMPLATE = 'markdown.j2.html'
ASCIIDOC_TEMPLATE = 'asciidoc.j2.html'
DOCX_TEMPLATE = 'reference.docx'
IGNORE_LIST = ['.', '.*','_', '*~', '#*#'] # TODO load ignore file
GENERATE_DOCX = False

def makedirs(directory):
    if os.path.exists(directory):
        return
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass

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
    sys.stderr.write(f'{message}\n')
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
            p = os.path.relpath(os.path.join(path, file), basedir)

            if ignore_list and not is_ignored(p, ignore_list):
                continue

            yield Path(p)

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

def generate_title_toc(body):
    q = pq(body)
    title = q('title').text()
    out = pq('<ul class="toc"></ul>')

    def get_last_child(e, level):
        if level==0:
            return e
        if level>0:
            ee = e.children('ul:last-child')
            if not ee:
                #e.append('<li>no title</li>')
                e.append('<ul></ul>')
                ee = e.children('ul:last-child')
            return get_last_child(ee, level-1)

    for tag in q('h1, h2, h3').items():
        level = int(tag[0].tag[1])-1
        assert(0<=level)
        aname = tag.attr('id')
        pp = get_last_child(out, level)
        pp.append(f'<li><a href="#{aname}">{tag.text()}</a></li>')

    return title, out.wrap('<div id="toc"></div>').html()


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

    def get_template(self, name):
        return self.env.get_template(name)

    def render(self, template, metadata):
        try:
            t = self.env.get_template(template)
            # env.from_string()
            return t.render(**metadata)
        except TemplateSyntaxError as e:
            raise Exception(f"{e.filename}:{e.lineno}: {e.name}, {e.message}")

    def lastmodified(self):
        "return if one of the template is updated."
        lm = Path(__file__).stat().st_mtime
        if self.templatedir:
            lm = max(lm, max(self.templatedir.joinpath(path).stat().st_mtime for path in all_files(self.templatedir, IGNORE_LIST)))
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

def asciidoc_convert(src, extra_args=[], cwd=None):
    args = ['asciidoctor', '-o', '-', '-']
    # args = ['asciidoc', '-a' 'mathjax', '-s', '-o', '-', '-']
    args.extend(extra_args)
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    data,error = p.communicate(src)
    return data, error

class PageBase:
    """
        Page knows dstpath, but don't know destination directory.
        basedir = base directory
        srcpath = src path
        srcfile = basepath + srcpath
        dstfiles = dst_basedir + dstpaths
    """
    def __init__(self, basedir, srcpath):
        self.basedir = Path(basedir)
        self.srcpath = Path(srcpath)
        self.srcfile = self.basedir.joinpath(srcpath)
        self.url = str(self.srcpath)

    def generate(self, dstbasedir):
        raise NotImplemented()

    def dstpaths(self):
        raise NotImplemented()

    def __repr__(self):
        return f"PageBase({self.srcfile})"

class PageFile(PageBase):
    def __init__(self, basepath, srcpath):
        super().__init__(basepath, srcpath)
        self.dstpath = srcpath

    def generate(self, dstbasedir):
        df = dstbasedir.joinpath(self.dstpath)
        makedirs(df.parent)
        shutil.copy(self.srcfile, df)

    def dstpaths(self):
        return [self.dstpath]

class PageTemplated(PageBase):
    def __init__(self, basedir, srcpath, template_engine, default_template):
        super().__init__(basedir, srcpath)
        self.dstpath = srcpath.with_suffix('.html')
        self.depth = len(self.dstpath.parts)-1
        self.root = '/'.join(['..'] * (self.depth)) if self.depth>0 else '.'
        self.template_engine = template_engine
        self.default_template = default_template

        """
        parts = [(link, name)]

        ex.
        a/b/c.html
        (../../index.html, Index) 0
        (../index.html, a) 1
        (./index.html, b) 2
        (., c) 3

        ex.
        a/b/index.html
        (../../index.html, Index) 0
        (../index.html, a) 1
        (./index.html, b) 2

        ex.
        index.html
        (./index.html, Index) 0

        """

        self.depth = len(self.dstpath.parts)-1
        names = ['Index'] + list(self.dstpath.with_suffix('').parts)
        self.parts = []
        for i, name in enumerate(names):
            if name=='index':
                break
            link = '/'.join(['..']*(self.depth-i)) + '/index.html'
            self.parts.append((link, name))

    def dstpaths(self):
        return [self.dstpath]

    def render_template(self, contents, metadata={}):
        metadata['contents'] = contents
        metadata['url'] = self.url
        metadata['root'] = self.root
        metadata['path'] = self.dstpath
        metadata['parts'] = self.parts
        metadata['mtime'] = self.srcfile.stat().st_mtime

        template = metadata.get('template') or self.default_template
        return self.template_engine.render(template, metadata)

class PageMarkdown(PageTemplated):
    def __init__(self, basedir, srcpath, template_engine):
        super().__init__(basedir, srcpath, template_engine, MARKDOWN_TEMPLATE)
        self.dstpathdocx = self.dstpath.with_suffix('.docx')

    def generate(self, dstbasedir):
        dstfile = dstbasedir.joinpath(self.dstpath)
        makedirs(dstfile.parent)

        pantable = ['-F', 'pantable']

        with report_exceptions():
            source =  open(self.srcfile, 'r').read()
            metadata, offset, content = load_metadata(source)
            extra_args=['-s', '--mathjax', '--data-dir='+os.path.abspath(os.path.dirname(__file__))] + pantable
            
            if 'bibliography' in metadata:
                bib = self.srcfile.parent.joinpath(metadata['bibliography']).resolve()
                extra_args.append(f'--bibliography={bib}')
            if 'csl' in metadata:
                csl = metadata['csl']
                extra_args.append('--csl='+csl)

            s,error = pandoc.convert(content.encode(PAGE_ENCODING), 'markdown', 'html5', extra_args, cwd=self.srcfile.parent)
            s = s.decode(PAGE_ENCODING)
            if not s.strip() or error:
                title = 'ERROR'
                toc = ''
                body = f'<pre>{error.decode(PAGE_ENCODING)}</pre><div>{s}</div>'
            else:
                title, toc = generate_title_toc(s)
                body = pq(s)('body').html()
                body = body.replace('[TOC]', toc)

            metadata['title'] = title
            metadata['toc'] = toc
            metadata['offset'] = offset
            metadata['source'] = source

            with open(dstfile, 'wb') as f:
                f.write(self.render_template(body, metadata).encode(PAGE_ENCODING))

            if GENERATE_DOCX:
                refer = Path('reference.docx').resolve()
                s,error = pandoc.convert_write(content.encode(PAGE_ENCODING),
                                               'markdown',
                                               self.dstbasedir.joinpath(self.dstpathdocx).resolve(),
                                               'docx',
                                               extra_args=[f"--reference-docx={refer}"]+pantable,
                                               cwd=self.srcfile.parent)
                if error:
                    log(error)

    def dstpaths(self):
        if GENERATE_DOCX:
            return [self.dstpath, self.dstpathdocx]
        else:
            return [self.dstpath]

class PageAsciidoc(PageTemplated):
    def __init__(self, basedir, srcpath, template_engine):
        super().__init__(basedir, srcpath, template_engine, ASCIIDOC_TEMPLATE)

    def generate(self, dstbasedir):
        dstfile = dstbasedir.joinpath(self.dstpath)
        makedirs(dstfile.parent)

        with report_exceptions():
            source = open(self.srcfile, 'r').read()
            metadata = {}

            s,error = asciidoc_convert(source.encode(PAGE_ENCODING), cwd=self.srcfile.parent)
            s = s.decode(PAGE_ENCODING)
            if not s.strip() or error:
                title = 'ERROR'
                toc = ''
                body = f'<pre>{error.decode(PAGE_ENCODING)}</pre><div>{s}</div>'
            else:
                title, toc = generate_title_toc(s)
                body = pq(s)('body').html()
                body = body.replace('[TOC]', toc)
                #body = toc + body

            metadata['title'] = title
            metadata['toc'] = toc
            metadata['source'] = source

            with open(dstfile, 'wb') as f:
                f.write(self.render_template(body, metadata).encode(PAGE_ENCODING))

            if error:
                log(error)

def sitegen(srcdir, dstdir, templatedir=None):
    srcdir = Path(srcdir)
    dstdir = Path(dstdir)
    template_engine = TemplateEngine(templatedir)
    pages = []

    dstpaths = []
    for srcpath in all_files(srcdir, IGNORE_LIST):
        suffix = srcpath.suffix

        with report_exceptions():
            if suffix in ['.md', '.markdown']:
                page = PageMarkdown(srcdir, srcpath, template_engine)
            elif suffix in ['.adoc', '.asc', '.asciidoc']:
                page = PageAsciidoc(srcdir, srcpath, template_engine)
            else:
                page = PageFile(srcdir, srcpath)

            for d in page.dstpaths():
                if d in dstpaths:
                    log(f'WARNING: destination file overlapped: {d} from {page.srcpath}')
                dstpaths.append(d)

            pages.append(page)

    log(f'Loaded {len(pages)} files')

    makedirs(dstdir)
    current_dst = set(all_files(dstdir))
    next_dst = {d for page in pages for d in page.dstpaths()}
    deleted_dst = current_dst - next_dst

    if len(deleted_dst) > 0:
        log(f'delete {len(deleted_dst)} abandoned files from destination directory')
        for f in deleted_dst:
            log(f'delete {f}')
            remove(f)

    tl = template_engine.lastmodified()

    for page in pages:
        src = page.srcfile
        sm = max(src.stat().st_mtime, tl)

        update = False
        for dst in page.dstpaths():
            dst = dstdir.joinpath(dst)

            if dst.exists() and (dst.stat().st_mtime > sm):
                pass
            else:
                update = True

        if update:
            log(f'generating {page.url}...')
            try:
                page.generate(dstdir)
            except KeyboardInterrupt:
                log('Keyboard interrupted.')
                return
            except:
                remove(dst)
                log('error while generating {page.url}')
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

    sitegen(inputdir, outputdir, args.templatedir)
