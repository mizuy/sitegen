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
    sitegen src -o _site

## Environment setup and install

Mac OS X Lion, Brew's python.

    % python --version
    Python 2.7.3
    % which python
    /usr/local/bin/python
    % sudo easy_install virtualenv
    % virtualenv --version
    1.8.2
    % which virtualenv
    /usr/local/share/python/virtualenv

Virtualenv, setup.py

    % make virtualenv
    New python executable in env/bin/python
    Installing setuptools............done.
    Installing pip...............done.
    % source env/bin/activate
    (env)% python setup.py develop
    (env)% deactivate
    % make

## Pandoc

1. Install Haskell-platform
2. set $PATH to $CABALDIR
3. Install pandoc, pandoc-citeproc

    cabal install pandoc
    cabal install pandoc-citeproc

4. test run

    pandoc -v
    
## CSL

Please put your .csl file into ~/.csl/
