#!/usr/bin/env python3
"""Rebuild the dated national mayor snapshot from public source documents.

Requires Python 3.10+, openpyxl, and Poppler's pdftotext command.
The output path is explicit so refreshing sources cannot silently replace live data.
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import unicodedata
import urllib.request

ORIGIN = 'https://jichisoken.jp'
PDF_URL = ORIGIN + '/file/jichitaisenkyo/No142_010-025_20260514.pdf'
DIRECTORY_URL = 'https://code4fukui.github.io/localgovjp/localgovjp.json'
EXCEL_URLS = {
    2021: ORIGIN + '/file/jichitaisenkyo/2021_shikucyouson_20221220.xlsx',
    2022: ORIGIN + '/file/jichitaisenkyo/2022_shikucyouson_20260514.xlsx',
    2023: ORIGIN + '/file/jichitaisenkyo/2023_shikucyouson_20240422.xlsx',
    2024: ORIGIN + '/file/jichitaisenkyo/2024_shikucyouson_20250219.xlsx',
    2025: ORIGIN + '/file/jichitaisenkyo/2025_shikucyouson_20260106.xlsx',
}
ALIASES = {'六ケ所村': '六ヶ所村', '尾村': '葛尾村', '駒ケ根市': '駒ヶ根市',
           '飛驒市': '飛騨市', '城市': '葛城市', '諌早市': '諫早市', '沖繩市': '沖縄市'}
AS_OF = '2025-04-30'


def fetch(url, target):
    if not target.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'Localpoliticians source importer/1.0'})
        with urllib.request.urlopen(request, timeout=60) as response:
            target.write_bytes(response.read())
    return target


def compact(value):
    return re.sub(r'\s', '', str(value or ''))


def build(cache):
    import openpyxl
    directory = json.loads(fetch(DIRECTORY_URL, cache / 'localgovjp.json').read_text())
    # This source labels designated-city wards as "市名 区名"; those are not
    # independent municipalities. Tokyo's 23 special wards remain included.
    cities = [{'code': row['lgcode'][:5], 'name': row['city'], 'pref': row['pref'],
               'officialURL': row['url']} for row in directory if ' ' not in row['city']]
    if len(cities) != 1741 or len({row['code'] for row in cities}) != 1741:
        raise ValueError('Municipality directory changed; review before regenerating this dated snapshot')
    pdf = fetch(PDF_URL, cache / 'mayors-2025.pdf')
    raw = cache / 'mayors-raw.txt'
    subprocess.run(['pdftotext', '-raw', str(pdf), str(raw)], check=True)
    text = raw.read_text()
    # Four entries place the registered name, public name, and term count on
    # separate lines. Display the public name inside parentheses.
    text = re.sub(r'([^\n]+[市区町村])\n([^\n]+)\n\(([^\n]+)\)\n([１２３４５６７８９０]+)',
                  lambda match: match[1] + ' ' + match[3] + ' ' + match[4], text)
    parsed = {}
    pref = None
    for line in text.splitlines():
        value = unicodedata.normalize('NFKC', compact(line))
        for old, new in ALIASES.items():
            if value.startswith(old):
                value = new + value[len(old):]
                break
        if value.startswith('▼'):
            pref = value[1:]
            continue
        matches = sorted([city for city in cities if city['pref'] == pref and value.startswith(city['name'])],
                         key=lambda city: -len(city['name']))
        if not matches:
            continue
        city = matches[0]
        match = re.fullmatch(r'(.+?)(\d+)', value[len(city['name']):])
        if not match:
            raise ValueError('Unparsed mayor row: ' + value)
        if city['code'] in parsed:
            raise ValueError('Duplicate municipality: ' + city['code'])
        parsed[city['code']] = (match[1], int(match[2]))
    if len(parsed) != 1741:
        missing = [city['name'] for city in cities if city['code'] not in parsed]
        raise ValueError('Incomplete PDF extraction: ' + ', '.join(missing))

    # The PDF's embedded font loses or repeats some glyphs. Use the latest
    # election winner in the five annual workbooks as the spelling evidence.
    # Never use the workbooks' date cells as election dates: some have a year
    # differing from the explicit election-year column.
    history = {}
    for year, url in EXCEL_URLS.items():
        workbook = openpyxl.load_workbook(fetch(url, cache / f'{year}-history.xlsx'), data_only=True)
        sheet = next(sheet for sheet in workbook if '首長' in sheet.title)
        rows = sheet.values
        headers = next(rows)
        for values in rows:
            row = dict(zip(headers, values))
            code = str(row.get('5桁コード') or '')
            if row.get('当落') == '当' and code:
                history[code] = (compact(row['立候補者名']), year)
        workbook.close()
    result = []
    for city in cities:
        name, terms = parsed[city['code']]
        evidence = PDF_URL
        if city['code'] in history:
            name, year = history[city['code']]
            evidence = f'{ORIGIN}/jichitaisenkyo/{year}/'
        if '（' in name:
            name = name.split('（', 1)[1].split('）', 1)[0]
        if not name or '�' in name:
            raise ValueError('Unresolved name: ' + city['name'])
        result.append({'code': city['code'], 'name': city['name'], 'pref': city['pref'],
                       'mayor': {'name': name, 'asOf': AS_OF, 'sourceURL': PDF_URL,
                                 'quality': '資料時点（現職未確認）',
                                 'sourceTitle': '地方自治総合研究所 全国首長名簿2025',
                                 'nameEvidenceURL': evidence, 'terms': terms},
                       'officialURL': city['officialURL'], 'officialURLSource': DIRECTORY_URL,
                       'officialURLQuality': 'J-LIS等を元にしたCode for Fukui公開データ'})
    result.sort(key=lambda row: row['code'])
    return {'meta': {'asOf': AS_OF, 'retrievedAt': datetime.date.today().isoformat(), 'count': len(result),
                     'sourceURL': ORIGIN + '/jichitaisenkyo/2025/',
                     'method': '全国首長名簿2025 PDFの全1741自治体を全国自治体コードに照合。PDF文字欠落を2021–2025年Excel選挙結果の当選者と照合し補完。資料時点の在職者であり現職を保証しない。',
                     'officialURLSource': 'Code for Fukui localgovjp（国土地理院・J-LISを元に作成、CC0、2026-07-09 URL更新）',
                     'officialURLSourceURL': 'https://github.com/code4fukui/localgovjp'}, 'municipalities': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=pathlib.Path, default=pathlib.Path('/tmp/localpoliticians-national'))
    parser.add_argument('--output', type=pathlib.Path, required=True, help='Review output before replacing data/national.json')
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    data = build(args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f"Wrote {len(data['municipalities'])} municipalities to {args.output}")


if __name__ == '__main__':
    main()
