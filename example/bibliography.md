---
   template: markdown_src.j2.html
   bibliography: my.bib
   csl: nature.csl
---

% Bibliography example

## bibliography example

metadataのbibliographyに相対パスでbibtex fileを指定する。

CSLを指定したい場合は、$HOME/.csl 以下において、metadataのcslで指定する。Referenceは自動的にページの最後に列挙される。

文章中で、このような形でpandocリファレンスを引用すると.... Oxidative Bisulfite Sequencing[@Booth:2012fh].

## References

ここに自動的にbibliographyが列挙される。
