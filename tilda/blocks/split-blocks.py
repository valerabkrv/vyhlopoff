#!/usr/bin/env python3
"""
Разрезает index.html на отдельные блоки T123 для Тильды — по секциям сайта.

    python3 tilda/split-blocks.py index.html --outdir tilda/blocks \
        --scope vf --img-base https://valerabkrv.github.io/vyhlopoff/img/ \
        --popup zayavka --extra-css tilda/popup.css

На выходе пронумерованные файлы: 01-styles, 02-header, 03-hero, ... , NN-scripts.
Каждый вставляется в свой блок T123 в Тильде, порядок = порядок номеров.
"""
import argparse, os, re, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('bt', os.path.join(HERE, 'build-t123.py'))
bt = importlib.util.module_from_spec(spec); spec.loader.exec_module(bt)

# порядок и человеческие имена секций
SECTIONS = [
    ('HEADER',   'header',   'Шапка и мобильное меню'),
    ('HERO',     'hero',     'Первый экран'),
    ('MARQUEE',  'marquee',  'Бегущая строка'),
    ('PAIN',     'pain',     'Надоело искать где бензин'),
    ('SERVICES', 'services', 'Услуги сервиса'),
    ('CALC',     'calc',     'Калькулятор экономии'),
    ('ABOUT',    'about',    'Прошиваем для экономии'),
    ('WHY',      'why',      'Почему выбирают нас'),
    ('STEPS',    'steps',    '4 шага к экономии'),
    ('FAQ',      'faq',      'Честные ответы'),
    ('CONTACTS', 'contacts', 'Контакты и заявка'),
    ('FOOTER',   'footer',   'Подвал, кнопка вверх, липкая панель'),
]


def wrap(scope, name, title, inner):
    return ('<!-- %s | блок сайта ВЫХЛОПОFF. Порядок блоков менять можно, '
            'но «Стили» должны идти первыми, «Скрипты» — последними. -->\n'
            '<div class="%s">\n%s\n</div>\n' % (title, scope, inner.strip()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--scope', default='vf')
    ap.add_argument('--img-base', default='')
    ap.add_argument('--popup', default='')
    ap.add_argument('--extra-css', default='')
    a = ap.parse_args()

    src = open(a.src, encoding='utf-8').read()
    css = re.sub(r'/\*.*?\*/', '', re.search(r'<style>(.*?)</style>', src, re.S).group(1), flags=re.S)
    css = bt.scope_css(css, a.scope)
    fonts = ''.join(re.findall(r'<link rel="preconnect"[^>]*>|<link[^>]*fonts\.googleapis[^>]*>', src))
    body = re.search(r'<body>(.*?)</body>', src, re.S).group(1)

    if a.popup:
        body = bt.cut_modal(body)
        body = re.sub(r'<button([^>]*?)\sdata-modal\b([^>]*)>(.*?)</button>',
                      lambda m: '<a class="%s" href="#popup:%s">%s</a>' % (
                          re.search(r'class="([^"]*)"', m.group(1) + m.group(2)).group(1), a.popup, m.group(3)),
                      body, flags=re.S)
    if a.img_base:
        body = body.replace('src="img/', 'src="' + a.img_base).replace('poster="img/', 'poster="' + a.img_base)

    # JS: искать элементы во ВСЕХ блоках .vf, а не только в первом
    body = body.replace(
        "var ROOT=document.querySelector('.%s')||document;" % a.scope,
        "var ROOTS=[].slice.call(document.querySelectorAll('.%s'));\n"
        "  if(!ROOTS.length)ROOTS=[document];" % a.scope)
    body = body.replace(
        "var $=function(s,c){return (c||ROOT).querySelector(s)};",
        "var $=function(s,c){if(c)return c.querySelector(s);\n"
        "    for(var i=0;i<ROOTS.length;i++){var e=ROOTS[i].querySelector(s);if(e)return e}return null};")
    body = body.replace(
        "var $$=function(s,c){return Array.prototype.slice.call((c||ROOT).querySelectorAll(s))};",
        "var $$=function(s,c){if(c)return Array.prototype.slice.call(c.querySelectorAll(s));\n"
        "    var out=[];ROOTS.forEach(function(r){out=out.concat(Array.prototype.slice.call(r.querySelectorAll(s)))});return out};")

    script = re.search(r'(<script>.*?</script>)\s*$', body.strip(), re.S).group(1)
    body_wo_script = body[:body.rfind('<script>')]

    os.makedirs(a.outdir, exist_ok=True)
    for f in os.listdir(a.outdir):
        if f.endswith('.html'):
            os.remove(os.path.join(a.outdir, f))

    files = []

    # 01 — стили и шрифты (невидимый блок, ставится первым)
    extra = open(a.extra_css, encoding='utf-8').read().strip() if a.extra_css else ''
    styles = ('<!-- Стили и шрифты сайта ВЫХЛОПОFF. Этот блок должен быть ПЕРВЫМ на странице.\n'
              '     Ничего не выводит — только подключает шрифты и CSS. -->\n'
              + fonts + '\n<style>' + css + '\n</style>\n'
              + ('<style>\n/* стили поп-апа заявки — блок Тильды */\n' + extra + '\n</style>\n' if extra else ''))
    files.append(('01-styles.html', styles))

    # секции
    marks = {name: body_wo_script.find('<!-- ================= %s =' % name) for name, _, _ in SECTIONS}
    order = [(n, s, t) for n, s, t in SECTIONS if marks[n] != -1]
    for i, (name, slug, title) in enumerate(order):
        start = marks[name]
        end = marks[order[i + 1][0]] if i + 1 < len(order) else len(body_wo_script)
        chunk = body_wo_script[start:end]
        chunk = re.sub(r'<!-- ={17} \w+ ={17} -->\s*', '', chunk)
        files.append(('%02d-%s.html' % (i + 2, slug), wrap(a.scope, slug, title, chunk)))

    # последний — скрипты
    files.append(('%02d-scripts.html' % (len(order) + 2),
                  '<!-- Скрипты сайта ВЫХЛОПОFF: калькулятор, меню, появление секций.\n'
                  '     Этот блок должен быть ПОСЛЕДНИМ на странице. -->\n' + script + '\n'))

    total = 0
    for fname, content in files:
        path = os.path.join(a.outdir, fname)
        open(path, 'w', encoding='utf-8').write(content)
        n = len(content.encode('utf-8'))
        total += n
        flag = '  !! больше 100 000' if n > 100000 else ''
        print('%-22s %6d байт%s' % (fname, n, flag))
    print('---\nвсего %d блоков, %d байт' % (len(files), total))


if __name__ == '__main__':
    main()
