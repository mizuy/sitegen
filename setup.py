import os
from setuptools import setup, find_packages

version = '2.0.0'

README = os.path.join(os.path.dirname(__file__), 'README.md')
long_description = open(README).read() + '\n\n'

classifiers = """\
Development Status :: 4 - Beta
Environment :: Console
Intended Audience :: Developers
License :: OSI Approved :: MIT License
Topic :: Internet :: WWW/HTTP :: Site Management
Programming Language :: Python
Operating System :: Unix
"""

setup(name='sitegen',
      version=version,
      description=("simple static site generator."),
      classifiers = filter(None, classifiers.split("\n")),
      keywords='static site generator markdown',
      author='mizuy',
      author_email='mizugy@gmail.com',
      url='http://github.com/mizuy/sitegen',
      license='MIT',
      packages=find_packages(),
      install_requires=['Jinja2',  'PyYAML', 'pyquery', 'tqdm'],
      entry_points=\
"""
[console_scripts]
sitegen = sitegen:main
""")

#dependency_links=['https://github.com/mizuy/Python-Markdown/tarball/master#egg=Markdown-dev'],
