#!/usr/bin/env python3
"""Bake the Russian UI layer into the bundled FreqUI index.html.

FreqUI has no i18n, so the only way to get a Russian interface without forking
the app is to inject a small DOM translator into the page it serves.

Usage:
    inject-ui-translation.py <path-to-index.html> <path-to-ru-translate.js>
"""
import sys

MARKER = 'ru-translate-injected'


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    index_path, js_path = sys.argv[1], sys.argv[2]

    with open(js_path, encoding='utf-8') as fh:
        script = fh.read()

    if MARKER not in script:
        print(f'ERROR: {js_path} is missing the {MARKER} marker')
        return 1

    with open(index_path, encoding='utf-8') as fh:
        html = fh.read()

    if MARKER in html:
        print(f'already injected: {index_path}')
        return 0

    if '</head>' not in html:
        print(f'ERROR: no </head> in {index_path}')
        return 1

    html = html.replace('</head>', '<script>\n' + script + '\n</script>\n</head>', 1)

    with open(index_path, 'w', encoding='utf-8') as fh:
        fh.write(html)

    print(f'injected Russian UI layer into {index_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
