---
   template: markdown_src.j2.html
   bibliography: my.bib
   csl: nature.csl
---
% Markdown

## Table of Contents
[TOC]


## Setext-style headers

~~~~~~~~~~~~~~~~
A level-one header
==================

A level-two header
------------------

# Atx-style headers

## A level-two header

### A level-three header ###
~~~~~~~~~~~~~~~~

## Table of contents

    [TOC]


## Block quotations

> This is a block quote. This
> paragraph has two lines.
>
> 1. This is a list inside a block quote.
> 2. Second item.

> This is a block quote. This
paragraph has two lines.

> 1. This is a list inside a block quote.
2. Second item.

> This is a block quote.
>
> > A block quote within a block quote.

> This is a block quote.
>> Nested.

## Indented code blocks

    if (a > 3) {
      moveShip(5 * gravity, DOWN);
    }
    

## Fenced code blocks

コードブロック

~~~~~~~.python
if (a > 3) {
  moveShip(5 * gravity, DOWN);
}
~~~~~~~

raw tagによるブロック

<pre id="mycode" class="haskell numberLines" startFrom="100">
  <code>
    qsort []     = []
    qsort (x:xs) = qsort (filter (< x) xs) ++ [x] ++
                   qsort (filter (>= x) xs)
  </code>
</pre>

ハイライトを指定

```haskell
qsort [] = []
```

別の指定法

``` {.python}
if (a > 3) {
  moveShip(5 * gravity, DOWN);
}
```

## Bullet lists

普通のリスト

* one
* two
* three

間が空いてもいい

* one

* two

* three

2行にまたがる要素

* here is my first
  list item.
* and my second.

Nested

* fruits
    + apples
        - macintosh
        - red delicious
    + pears
    + peaches
* vegetables
    + brocolli
    + chard

数字

1.  one
2.  two
3.  three


## Definition lists

Term 1
:   Definition 1

Term 2 with *inline markup*
:   Definition 2
    Second paragraph of definition 2.
  
## Horizontal lines

*  *  *  *

---------------

## Table

  model             |     対象              |     Predictor        
--------------------|-----------------------|----------------------
one-way ANOVA       |     1 量的変数        | 1 カテゴリー変数
two-way ANOVA       |     1 量的変数        | 2 カテゴリー変数
単回帰              |     1 量的変数        | 1 量的変数
重回帰              |     1 量的変数        | 2つ以上の量的変数
ロジスティック回帰  |     1 カテゴリー変数  | 1つ以上の量的変数

## inline

This text is __emphasized with underscores__, and this
is *emphasized with asterisks*.

This is * not emphasized *, and \*neither is this\*.

This ~~is deleted text.~~

H~2~O is a liquid.  2^10^ is 1024.

What is the difference between `>>=` and `>>`?

Here is a literal backtick `` ` ``.
This is a backslash followed by an asterisk: `\*`.

<http://google.com>
<sam@green.eggs.ham>

This is an [inline link](/url), and here's [one with
a title](http://fsf.org "click here for a good time!").

[my label 1]: /foo/bar.html  "My title, optional"
[my label 2]: /foo
[my label 3]: http://fsf.org (The free software foundation)
[my label 4]: /bar#special  'A title in single quotes'

[my label 5]: <http://foo.bar.baz>

[my label 3]: http://fsf.org "The free software foundation"
  
  
  Here is [my link][FOO]

[Foo]: /bar/baz

See [my website][], or [my website].

[my website]: http://foo.bar.baz

See the [Introduction](#introduction).

![shark](shark.jpg "Chura-umi suizoku-kan")

[kame]

[kame]: kame.jpg

<!-- // ![url image](http://en.wikipedia.org/wiki/File:Tumor_Mesothelioma2_legend.jpg) -->


## math

$$ Contractility = \frac{dP}{dt} $$

$$
Contractility = \frac{dP}{\frac{dP}{dt}\frac{dP}{dt}}
$$

Now we can easily make beautiful inline math like $\mathrm{pr}_{\theta}(x) = |\langle x|\psi\rangle|^2$ or display math like

$$
\langle x_{\theta}|n\rangle = \frac{e^{-in\theta}}{\sqrt{2^n n! \sqrt{\pi}}} H_n(x) e^{-x^2/2}
$$

[more example](mathjax.html)

## bibliography

metadataのbibliographyに相対パスでbibtex fileを指定する。

CSLを指定したい場合は、$HOME/.csl 以下において、metadataのcslで指定する。Referenceは自動的にページの最後に列挙される。

Oxidative Bisulfite Sequencing[@Booth:2012fh].

## footnote

Here is a footnote reference,[^1] and another.[^longnote]

[^1]: Here is the footnote.

[^longnote]: Here's one with multiple blocks.

    Subsequent paragraphs are indented to show that they belong to the previous footnote.

    $$ \frac{dx}{dt} = -kx$$

        indented block

    The whole paragraph can be indented, or just the first
    line.  In this way, multi-paragraph footnotes work like
    multi-paragraph list items.

This paragraph won't be part of the note, because it
isn't indented.

## References

ここに自動的にbibliographyが列挙される。
