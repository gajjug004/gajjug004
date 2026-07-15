"""Check that the SVG cards stay aligned no matter how big the numbers get.

Every row in the right-hand panel must render to exactly PANEL_COLS characters. That holds
only while each value's reserve is wide enough to keep leader dots; once a value outgrows
its reserve, justify_format() collapses the dots and the row's right edge walks left. That
failure is invisible in a diff and obvious on the rendered profile, so assert it here.

Run: python test_today.py
"""
import os
import shutil
import tempfile

os.environ.setdefault('ACCESS_TOKEN', 'dummy')
os.environ.setdefault('USER_NAME', 'dummy')

from lxml import etree  # noqa: E402

import today  # noqa: E402

PANEL_COLS = 66
SPACER_COLS = 2  # the bare ". " rows between sections
CARDS = ['dark_mode.svg', 'light_mode.svg']
SVG = '{http://www.w3.org/2000/svg}'


def row_widths(path):
    """Character width of each panel row: tspans carrying x= start a new row.

    The panel is found as the <text> that is not the portrait, rather than by a hardcoded
    x -- the layout derives its geometry from the art's size, so the panel moves whenever
    the portrait is regenerated at different dimensions.
    """
    root = etree.parse(path).getroot()
    panels = [t for t in root.iter(SVG + 'text') if t.get('class') != 'ascii']
    assert len(panels) == 1, f'expected one panel text element, found {len(panels)}'
    panel_x = panels[0].get('x')
    rows, width = [], None
    for span in panels[0]:
        text = (span.text or '') + (span.tail or '').strip('\n')
        if span.get('x') == panel_x:  # new row
            if width is not None:
                rows.append(width)
            width = len(text)
        else:
            width += len(text)
    rows.append(width)
    return rows


def check(stats, label):
    assert set(stats) == set(today.RESERVE), (
        f'{label}: stats keys do not match today.RESERVE: '
        f'{set(stats) ^ set(today.RESERVE)}')
    with tempfile.TemporaryDirectory() as tmp:
        for card in CARDS:
            dest = os.path.join(tmp, card)
            shutil.copy(card, dest)
            today.svg_overwrite(dest, stats)
            for i, w in enumerate(row_widths(dest)):
                if w == SPACER_COLS:  # deliberate ". " spacer row
                    continue
                assert w == PANEL_COLS, (
                    f'{label}: {card} row {i} is {w} cols, expected {PANEL_COLS}')
    print(f'  ok: {label}')


def main():
    print('SVG layout invariants:')

    # Today's actual numbers.
    check({'age_data': '5 years, 7 months, 7 days', 'repo_data': 38, 'contrib_data': 92,
           'org_data': 'frappe, bwhtech', 'star_data': 1, 'follower_data': 5,
           'commit_data': 494, 'pr_data': 96, 'issue_data': 9,
           'loc_data': '222,778', 'loc_add': '299,038', 'loc_del': '76,260'},
          'current values')

    # The headroom today.py's reserves claim to cover.
    check({'age_data': '88 years, 11 months, 30 days', 'repo_data': 999, 'contrib_data': 999,
           'org_data': 'frappe, bwhtech, and-some-long-org-names', 'star_data': 99_999,
           'follower_data': 9_999, 'commit_data': 99_999, 'pr_data': 9_999,
           'issue_data': 9_999, 'loc_data': '9,999,999', 'loc_add': '9,999,999',
           'loc_del': '9,999,999'},
          'max supported values')

    # And the floor, where the dots do the most work.
    check({'age_data': '1 year, 1 month, 1 day', 'repo_data': 0, 'contrib_data': 0,
           'org_data': '', 'star_data': 0, 'follower_data': 0, 'commit_data': 0,
           'pr_data': 0, 'issue_data': 0, 'loc_data': '0', 'loc_add': '0', 'loc_del': '0'},
          'zero values')

    print('All layout checks passed.')


if __name__ == '__main__':
    main()
