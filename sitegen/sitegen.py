# -*- coding: utf-8 -*-

# Static Site Generator powered by markdown and jinja2
# Copyright (c) 2012-2017 MIZUGUCHI Yasuhiko
# based on http://obraz.pirx.ru/
# install requirements: Jinja2, PyYAML, pyquery, pandoc(from cabal), asciidoctor

import sys, os, io, re, traceback, errno, subprocess
import shutil, fnmatch, yaml, concurrent.futures
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
CONFIG_YAML = 'config.yaml'
DOCX_TEMPLATE = 'reference.docx'
IGNORE_LIST = ['.', '.*','_', '*~', '#*#'] # TODO load ignore file
GENERATE_DOCX = False
PANTABLE = shutil.which('pantable')

def makedirs(directory):
    if os.path.exists(directory):
        return
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass

def remove(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)

def log(message):
    sys.stderr.write(f'{message}\n')
    sys.stderr.flush()

@contextmanager
def report_exceptions():
    try:
        yield
    except KeyboardInterrupt:
        raise KeyboardInterrupt()
    except Exception:
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

def walk_files(basedir):
    for p in Path(basedir).glob('**/*'):
        if p.is_file():
            yield p

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

    def render(self, template, metadata):
        try:
            t = self.env.get_template(template)
            return t.render(**metadata)
        except TemplateSyntaxError as e:
            raise Exception(f"{e.filename}:{e.lineno}: {e.name}, {e.message}")

    @property
    def lastmodified(self):
        "return if one of the template is updated."
        lm = Path(__file__).stat().st_mtime
        if not self.templatedir:
            return lm
        return max(lm, max(p.stat().st_mtime for p in walk_files(self.templatedir)))

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
        self.dstpath = self.srcpath
        self.srcfile = basedir / srcpath
        self.url = str(self.dstpath)
        self.depth = len(self.dstpath.parts)-1
        self.root = '/'.join(['..'] * (self.depth)) if self.depth>0 else '.'

    def generate(self, dstbasedir):
        raise NotImplemented()

    def __repr__(self):
        return f"PageBase({self.srcfile})"

    def need_update(self, lastmodified, dstdir):
        """
        return if dstination file (at basedirectory dstdir) needs update or not
        """
        update = False
        ds = (dstdir / d for d in self.dstpaths)
        for d in ds:
            if not d.is_file():
                update = True
            else:
                if d.stat().st_mtime < lastmodified:
                    update = True
        return update

    @property
    def lastmodified(self):
        return self.srcfile.stat().st_mtime
    @property
    def dstpaths(self):
        return [self.dstpath]

    @property
    def search_json(self):
        return None
        return {'url': self.url, 'title': self.srcpath.stem, 'content': ''}

class PageFile(PageBase):
    def __init__(self, basepath, srcpath):
        super().__init__(basepath, srcpath)

    def generate(self, dstbasedir):
        df = dstbasedir.joinpath(self.dstpath)
        makedirs(df.parent)
        shutil.copy(self.srcfile, df)

class PageTemplated(PageBase):
    def __init__(self, basedir, srcpath, template_engine, default_template):
        super().__init__(basedir, srcpath)
        self.dstpath = srcpath.with_suffix('.html')
        self.url = str(self.dstpath)
        self.template_engine = template_engine
        self.default_template = default_template

        """
        parts = [(link, name)]

        ex.
        a/b/c.html (dd=3)
        (../../../index.html, Index) 0
        (../../index.html, a) 1
        (../index.html, b) 2
        (., c) 3

        ex.
        a/b/index.html (dd=3)
        (../../../index.html, Index) 0
        (../../index.html, a) 1
        (../index.html, b) 2
        (., b) 3

        a/b.html (dd=2)
        (../index.html, Index) 0
        (./index.html, a) 1
        (., b) 2

        a.html (dd=1)
        (./index.html, Index) 0
        (., a)

        index.html (dd=1)
        (., Index) 0

        """

        def rel_parent(n):
            if n==0:
                return '.'
            elif n==1:
                return './index.html'
            else:
                return '../'*(n-1)+'index.html'

        pp = list(self.dstpath.with_suffix('').parts)
        dd = len(pp)
        names = ['Home'] + pp
        if names[-1]=='index':
            names.pop()
        self.parts = [(rel_parent(dd-i), name) for i,name in enumerate(names)]

    def render_template(self, contents, metadata={}):
        metadata['contents'] = contents
        metadata['url'] = self.url
        metadata['root'] = self.root
        metadata['path'] = self.dstpath
        metadata['parts'] = self.parts
        metadata['mtime'] = self.srcfile.stat().st_mtime

        template = metadata.get('template') or self.default_template
        return self.template_engine.render(template, metadata)

R_M = re.compile(r'\A\s*^---+\s*$(.*?)^---+\s*$(.*)\Z', re.M|re.DOTALL)
def load_metadata(source):
    m = R_M.match(source)
    if m:
        return yaml.load(m[1]) or {}, m[2]
    else:
        return {}, source

class ConfigYaml:
    def __init__(self, metadata, path):
        self.metadata = metadata
        self.path = path

    def get_path(self, name):
        a = self.metadata.get(name)
        if not a:
            return None
        return self.path.parent.joinpath(a).resolve()

    @classmethod
    def from_file(cls, path):
        try:
            m = yml.load(open(path).read())
            return ConfigYaml(m, path)
        except:
            return ConfigYaml({}, Path('.'))

class PageMarkdown(PageTemplated):
    def __init__(self, basedir, srcpath, template_engine, global_config):
        super().__init__(basedir, srcpath, template_engine, MARKDOWN_TEMPLATE)
        self.dstpathdocx = self.dstpath.with_suffix('.docx')
        self.gy = global_config

    @property
    def search_json(self):
        source = open(self.srcfile, 'r').read()
        metadata, content = load_metadata(source)
        content = re.sub(r'\s+',' ',content)
        return {'url': self.url,
                'title': self.srcpath.stem,
                'content': self.srcpath.stem+' '+content}

    def generate(self, dstbasedir):
        source = open(self.srcfile, 'r').read()
        metadata, content = load_metadata(source)

        pantable = ['-F', str(PANTABLE)] if PANTABLE else []
        extra_args=['-s', '--mathjax'] + pantable

        y = ConfigYaml(metadata, self.srcpath)
        for pp in ['bibliography', 'csl']:
            t = y.get_path(pp) or self.gy.get_path(pp)
            if t:
                extra_args.append(f'--{pp}={t}')

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
        metadata['source'] = source

        dstfile = dstbasedir.joinpath(self.dstpath)
        makedirs(dstfile.parent)
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

    @property
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
            body = pq(s)('body').html().replace('[TOC]', toc)

        metadata['title'] = title
        metadata['toc'] = toc
        metadata['source'] = source

        with open(dstfile, 'wb') as f:
            f.write(self.render_template(body, metadata).encode(PAGE_ENCODING))

        if error:
            log(error)

def is_ignored(filepath, ignore_list=IGNORE_LIST):
    for ignore in ignore_list:
        if any(fnmatch.fnmatch(part, ignore) for part in filepath.parts):
            return True
    return False

def walk_site(basedir):
    for path in walk_files(basedir):
        if is_ignored(path):
            continue
        yield path.relative_to(basedir)

class Site:
    def __init__(self, srcdir, templatedir=None):
        self.srcdir = Path(srcdir)
        self.template_engine = TemplateEngine(templatedir)
        self.pages = []
        self.config = ConfigYaml.from_file(CONFIG_YAML)

        dstpaths = []
        for srcpath in walk_site(srcdir):
            suffix = srcpath.suffix

            with report_exceptions():
                if suffix in ['.md', '.markdown']:
                    page = PageMarkdown(srcdir, srcpath, self.template_engine, self.config)
                elif suffix in ['.adoc', '.asc', '.asciidoc']:
                    page = PageAsciidoc(srcdir, srcpath, self.template_engine)
                else:
                    page = PageFile(srcdir, srcpath)

                for d in page.dstpaths:
                    if d in dstpaths:
                        log(f'WARNING: destination file overlapped: {d} from {page.srcpath}')
                    dstpaths.append(d)

                self.pages.append(page)

        log(f'Loaded {len(self.pages)} files')

    def generate(self, dstdir, indexupdate=None):
        dstdir = Path(dstdir)
        searchindex_path = 'searchindex.js'
        searchindex_update = False

        makedirs(dstdir)
        current_dst = set(walk_site(dstdir))
        next_dst = {Path(searchindex_path)}|{d for page in self.pages for d in page.dstpaths}
        deleted_dst = current_dst - next_dst

        if len(deleted_dst) > 0:
            log(f'delete {len(deleted_dst)} abandoned files from destination directory')
            for f in deleted_dst:
                log(f'delete {f}')
                remove(dstdir/f)
            searchindex_update = True

        tl = self.template_engine.lastmodified

        def g(page):
            sm = max(page.lastmodified, tl)
            if page.need_update(sm, dstdir):
                log(f'generating {page.url}...')
                with report_exceptions():
                    page.generate(dstdir)
                return True
            return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(g, page) for page in self.pages]
            searchindex_update |= any(f.result() for f in concurrent.futures.as_completed(futures))

        if indexupdate and searchindex_update:
            log(f'making search index: {searchindex_path}')
            open(dstdir/searchindex_path,'w').write(self.search_index(self.pages))

    def search_index(self, pages):
        import json
        jj = [page.search_json for page in pages if page.search_json]
        return f"var data={json.dumps(jj)}"

def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(prog='sitegen', description='generating html static site from markdown documents')
    parser.add_argument("inputdir", help="input directory")
    parser.add_argument("-o", "--output", dest="outputdir", help="output directory", default="_output")
    parser.add_argument("-t", "--template", dest="templatedir", help="template directory", default=None)
    parser.add_argument("-i", dest="index_update",action='store_true', help="update search index")

    args = parser.parse_args()

    if not args.inputdir:
        parser.error('no input directory')
        return

    site = Site(args.inputdir, args.templatedir)
    site.generate(args.outputdir, args.index_update)
