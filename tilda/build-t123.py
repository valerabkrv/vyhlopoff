#!/usr/bin/env python3
"""
Сборка одностраничного сайта в код для блока T123 (HTML-код) в Tilda.

    python3 build-t123.py index.html --out tilda/site-t123.html \
        --scope vf --img-base https://user.github.io/repo/img/

Что делает:
  * вырезает <style> и содержимое <body> из исходного index.html;
  * УБИРАЕТ комментарии из CSS — иначе комментарий прилипает к следующему
    селектору и правило перестаёт работать (это ломало первую сборку);
  * вешает `.<scope> ` на каждый селектор, кроме :root / html / body —
    чтобы CSS Тильды не ломал сайт и наоборот;
  * оборачивает разметку в <div class="<scope>">;
  * подставляет абсолютные адреса картинок вместо относительных img/...;
  * ограничивает $ и $$ в JS этим блоком (var ROOT = .vf);
  * считает размер и предупреждает о лимите Тильды (100 000 байт на T123).
"""
import argparse, re, sys

KEEP_AS_IS = ('@keyframes', '@font-face', '@charset', '@import')


def matching_brace(css, j):
    depth = 0
    for k in range(j, len(css)):
        if css[k] == '{':
            depth += 1
        elif css[k] == '}':
            depth -= 1
            if depth == 0:
                return k
    return len(css) - 1


def scope_css(css, scope):
    def prefix(sel):
        out = []
        for p in (x.strip() for x in sel.split(',')):
            if not p:
                continue
            out.append(p if p in (':root', 'html', 'body') else '.%s %s' % (scope, p))
        return ', '.join(out)

    res, i, n = [], 0, len(css)
    while i < n:
        j = css.find('{', i)
        if j == -1:
            res.append(css[i:])
            break
        head = css[i:j].strip()
        if head.startswith('@media') or head.startswith('@supports'):
            k = matching_brace(css, j)
            res.append('\n' + head + '{' + scope_css(css[j + 1:k], scope) + '}')
            i = k + 1
        elif head.startswith(KEEP_AS_IS):
            k = matching_brace(css, j)
            res.append('\n' + css[i:k + 1].strip())
            i = k + 1
        else:
            k = css.find('}', j)
            res.append('\n' + prefix(head) + '{' + css[j + 1:k].strip() + '}')
            i = k + 1
    return ''.join(res)


def cut_modal(body):
    """Убирает <div class="modal" id="modal">...</div> целиком (в Тильде вместо неё блок BF502N)."""
    i = body.find('<div class="modal" id="modal">')
    if i == -1:
        return body
    depth, j = 0, i
    while j < len(body):
        if body.startswith('<div', j):
            depth += 1
        elif body.startswith('</div>', j):
            depth -= 1
            if depth == 0:
                j += len('</div>')
                break
        j += 1
    return body[:i] + body[j:]


def build(src_path, scope, img_base, popup='', extra_css=''):
    src = open(src_path, encoding='utf-8').read()

    style = re.search(r'<style>(.*?)</style>', src, re.S)
    body = re.search(r'<body[^>]*>(.*?)</body>', src, re.S)
    if not style or not body:
        sys.exit('Не нашёл <style> или <body> в ' + src_path)
    style, body = style.group(1), body.group(1)

    fonts = re.search(r'(<link rel="preconnect".*?rel="stylesheet">)', src, re.S)
    fonts = fonts.group(1) if fonts else ''

    style = re.sub(r'/\*.*?\*/', '', style, flags=re.S)     # обязательно до scope_css
    css = scope_css(style, scope)

    if img_base:
        body = body.replace('src="img/', 'src="' + img_base)
        body = body.replace('poster="img/', 'poster="' + img_base)

    if popup:
        body = cut_modal(body)
        body = re.sub(
            r'<button([^>]*?)\sdata-modal\b([^>]*)>(.*?)</button>',
            lambda m: '<a class="%s" href="#popup:%s">%s</a>' % (
                (re.search(r'class="([^"]*)"', m.group(1) + m.group(2)) or
                 type('x', (), {'group': lambda self, i: 'btn'})()).group(1),
                popup, m.group(3)),
            body, flags=re.S)

    body = body.replace(
        "var $=function(s,c){return (c||document).querySelector(s)};",
        "var ROOT=document.querySelector('.%s')||document;\n  "
        "var $=function(s,c){return (c||ROOT).querySelector(s)};" % scope)
    body = body.replace(
        "var $$=function(s,c){return Array.prototype.slice.call((c||document).querySelectorAll(s))};",
        "var $$=function(s,c){return Array.prototype.slice.call((c||ROOT).querySelectorAll(s))};")

    note = ('<!-- Код для блока T123 (HTML-код) в Tilda.\n'
            '     Картинки и видео: %s\n'
            '     Чтобы держать их в Тильде: Настройки сайта -> Файлы,\n'
            '     затем заменить этот адрес на выданный Тильдой. -->\n' % (img_base or '—'))

    extra = ''
    if extra_css:
        extra = '\n<style>\n/* стили блоков Тильды — без области видимости */\n' + \
                open(extra_css, encoding='utf-8').read().strip() + '\n</style>'

    return (note + fonts + '\n<style>' + css + '\n</style>' + extra +
            '\n<div class="%s">\n' % scope + body.strip() + '\n</div>\n')


def check(out, scope):
    problems = []
    if '/*' in re.search(r'<style>(.*?)</style>', out, re.S).group(1):
        problems.append('в CSS остались комментарии')
    css = re.search(r'<style>(.*?)</style>', out, re.S).group(1)
    for sel in re.findall(r'(?m)^([^@{\n][^{\n]*)\{', css):
        s = sel.strip()
        if not (s.startswith('.' + scope) or s in (':root', 'html', 'body')
                or s.startswith(('body,', 'html,', ':root,'))):
            problems.append('селектор без области видимости: ' + s[:60])
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--out', required=True)
    ap.add_argument('--scope', default='vf', help='класс-обёртка, по умолчанию vf')
    ap.add_argument('--img-base', default='', help='абсолютный адрес папки с картинками')
    ap.add_argument('--popup', default='', help='id поп-апа Тильды: кнопки data-modal станут ссылками #popup:<id>, своя модалка вырежется')
    ap.add_argument('--extra-css', default='', help='файл с CSS, который добавится КАК ЕСТЬ (без области видимости) — для стилизации блоков Тильды')
    a = ap.parse_args()

    out = build(a.src, a.scope, a.img_base, a.popup, a.extra_css)
    problems = check(out, a.scope)
    open(a.out, 'w', encoding='utf-8').write(out)

    size = len(out.encode('utf-8'))
    print('%s — %d байт (лимит T123 = 100 000, запас %d)' % (a.out, size, 100000 - size))
    if size > 100000:
        print('!! НЕ ВЛЕЗЕТ в блок T123. Убрать лишнее или разбить на два блока.')
    for p in problems:
        print('!!', p)
    if not problems:
        print('проверки пройдены')


if __name__ == '__main__':
    main()
