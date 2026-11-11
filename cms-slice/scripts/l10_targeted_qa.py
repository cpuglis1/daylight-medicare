"""Render sparse and material evidence pages; retain OCR as a review aid only."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess

from PIL import Image, ImageOps, ImageDraw

from l10_targeted_intake import ROOT, PACKET, OUT, guard, read, write, sha


def render(item):
    case, page, doc, reason = item
    stem = PACKET / 'qa' / f'{case}-p{page:04d}'
    png = stem.with_suffix('.png'); txt = stem.with_suffix('.txt')
    if not png.exists():
        subprocess.run(['pdftoppm', '-f', str(page), '-l', str(page), '-r', '110', '-singlefile', '-png',
                        str(ROOT / doc['retained_path']), str(stem)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if not txt.exists():
        subprocess.run(['tesseract', str(png), str(stem), '--psm', '6'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env={**os.environ, 'OMP_THREAD_LIMIT': '1'})
    text = txt.read_text()
    return {'case': case, 'page': page, 'reason': reason, 'png': str(png.relative_to(ROOT)), 'png_sha256': sha(png),
            'ocr_text': str(txt.relative_to(ROOT)), 'ocr_sha256': sha(txt),
            'ocr_characters': len(text.strip()), 'ocr_is_not_accepted_evidence': True,
            'possible_money': '$' in text, 'source_pdf_sha256': doc['sha256']}


def qa():
    guard(); (PACKET / 'qa').mkdir(exist_ok=True)
    docs = {r['case']: r for r in read(PACKET / 'intake.json')['documents']}
    selected = {}
    for case, doc in docs.items():
        for page in doc['low_text_pages']:
            selected[(case, page)] = 'sparse_native_text'
    for r in read(OUT / 'conditions.json'):
        selected[(r['case'], r['source_page'])] = 'material_condition'
    for r in read(OUT / 'approval-letters.json'):
        selected[(r['case'], r['source_page'])] = 'approval_letter'
    schedules = read(OUT / 'schedules.json')
    for case in docs:
        s = next(s for s in schedules if s['case'] == case and s['status'] == 'APPROVED')
        for page in s['source_pages']:
            selected[(case, page)] = 'representative_approved_schedule'
    items = [(c, p, docs[c], why) for (c, p), why in sorted(selected.items())]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(render, items))
    write(PACKET / 'rendered-pages.json', records)
    sheets = []
    for case in docs:
        rows = [r for r in records if r['case'] == case]
        for offset in range(0, len(rows), 30):
            group = rows[offset:offset + 30]
            sheet = Image.new('RGB', (1500, ((len(group) + 4) // 5) * 425), 'white')
            draw = ImageDraw.Draw(sheet)
            for i, row in enumerate(group):
                with Image.open(ROOT / row['png']) as source:
                    thumb = ImageOps.contain(source.convert('RGB'), (294, 395))
                    x, y = (i % 5) * 300, (i // 5) * 425
                    sheet.paste(thumb, (x, y + 22))
                    draw.text((x + 4, y + 3), f"{case} p{row['page']} {row['reason'][:16]}", fill='black')
            path = PACKET / 'qa' / f'{case}-sheet-{offset // 30 + 1}.png'
            sheet.save(path)
            sheets.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'case': case,
                           'source_pages': [r['page'] for r in group]})
    write(PACKET / 'contact-sheets.json', sheets)
    print({'rendered_pages': len(records), 'contact_sheets': len(sheets),
           'sparse_pages_with_possible_money': [(r['case'], r['page']) for r in records if r['reason'] == 'sparse_native_text' and r['possible_money']]}, flush=True)


if __name__ == '__main__':
    qa()
