# Static site generator

## Directories

    - root
        + _template         : jinja2 template files
        + src               : source markdown files
            + index.md
            + subdir/others.md
            + css/default.css
            + image.jpg
        + _site             : ooutput html files

command:
    
    sitegen src -o _site --template=_templates -i

## Environment setup and install

Mac OS X Sierra, Brew's python, direnv

    > git clone https://github.com/mizuy/sitegen.git
    Cloning into 'sitegen'...
    > cd sitegen
    direnv: loading .envrc
    ./.envrc: line 1: venv/bin/activate: No such file or directory
    direnv: error exit status 1
    > make venv
    python3 -m venv venv
    venv/bin/pip3 install --editable .
    Obtaining file:///Users/mizuy/note/sitegen
    ...
    Successfully installed Jinja2-2.10 MarkupSafe-1.0 PyYAML-3.12 cssselect-1.0.3 lxml-4.1.1 pyquery-1.4.0 sitegen tqdm-4.19.5
    direnv: loading .envrc
    direnv: export +VIRTUAL_ENV ~PATH
    > make
    venv/bin/sitegen example -o _output -i
    Loaded 26 files
    100%|█████████████████████████████████████████████████████████████████| 26/26 [00:00<00:00, 89.25file/s]
    making search index: searchindex.js

## Pandoc

1. Install Haskell-platform
2. set $PATH to $CABALDIR
3. Install pandoc, pandoc-citeproc

    % cabal install pandoc
    % cabal install pandoc-citeproc

4. test run

    % pandoc -v
    pandoc 1.16.0.2

今は brew cask install haskell-platform ?? or brew install pandoc ??

    > pandoc -v
    pandoc 2.1.1
    Compiled with pandoc-types 1.17.3.1, texmath 0.10.1.1, skylighting 0.6
    Default user data directory: /Users/mizuy/.pandoc
    Copyright (C) 2006-2018 John MacFarlane
    Web:  http://pandoc.org
    This is free software; see the source for copying conditions.
    There is no warranty, not even for merchantability or fitness
    for a particular purpose.
