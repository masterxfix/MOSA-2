"""Bounded coordinate-preserving PDF extraction, independent of issuers and SQL."""
from io import BytesIO
import logging
import re
import unicodedata

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 200
MAX_CHARACTERS = 2000000

def read_pdf(raw):
    if not raw.startswith(b'%PDF-') or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('PDF_SIGNATURE_OR_BOUND')
    import pdfplumber
    logging.getLogger('pdfminer').disabled = True
    try:
        with pdfplumber.open(BytesIO(raw), unicode_norm='NFKC') as document:
            if document.doc.is_extractable is False or not 1 <= len(document.pages) <= MAX_PAGES:
                raise ValueError('PDF_DOCUMENT_BOUND')
            pages=[];total=0
            for index,page in enumerate(document.pages,1):
                words=page.dedupe_chars(tolerance=1).extract_words(x_tolerance=2,y_tolerance=3,keep_blank_chars=False)
                total+=sum(len(w['text']) for w in words)
                if total>MAX_CHARACTERS:raise ValueError('PDF_DOCUMENT_BOUND')
                lines=[]
                for word in sorted(words,key=lambda w:(w['bottom'],w['x0'])):
                    if not lines or abs(word['bottom']-lines[-1]['bottom'])>3:
                        lines.append(dict(bottom=word['bottom'],words=[]))
                    lines[-1]['words'].append(word)
                for line in lines:
                    line['words'].sort(key=lambda w:w['x0'])
                    line['text']=' '.join(w['text'] for w in line['words'])
                pages.append(dict(number=index,width=page.width,height=page.height,lines=lines,
                                  text='\n'.join(line['text'] for line in lines)))
            return pages
    except ValueError:raise
    except Exception:raise ValueError('PDF_EXTRACTION') from None

def clean_label(text):
    text=unicodedata.normalize('NFKC',text).casefold().strip()
    text=re.sub(r'\([^)]*(?:\$|aud|million|thousand)[^)]*\)','',text)
    return re.sub(r'[\s\d*†‡]+$','',re.sub(r'\s+',' ',text)).strip()

def highlights_tables(pages):
    """Locate a titled table and map years from aligned header coordinates, never chart order."""
    tables=[]
    for page in pages:
        lines=page['lines']
        for title_index,title in enumerate(lines):
            if not re.fullmatch(r'financial\s+highlights',title['text'].strip(),re.I):continue
            for header_index in range(title_index+1,min(title_index+9,len(lines))):
                header=lines[header_index]
                years={}
                for w in header['words']:
                    m=re.fullmatch(r'(?:FY)?(202[0-9])',w['text'],re.I)
                    if m:
                        year=int(m[1])
                        if year in years:raise ValueError('PDF_YEAR_COLUMNS')
                        years[year]=w
                if len(years)<2:continue
                if set(years)!={2025,2024}:raise ValueError('PDF_YEAR_COLUMNS')
                ordered=sorted(years,key=lambda y:years[y]['x0'])
                centers=[(years[y]['x0']+years[y]['x1'])/2 for y in ordered]
                extra=[w for w in header['words'] if w['x0']>years[ordered[-1]]['x1'] and re.search(r'%|change|growth',w['text'],re.I)]
                left=years[ordered[0]]['x0']-25
                middle=(centers[0]+centers[1])/2
                right=(centers[1]+(extra[0]['x0']+extra[0]['x1'])/2)/2 if extra else page['width']
                rows=[]
                for line in lines[header_index+1:]:
                    if rows and line['bottom']-rows[-1]['bottom']>45:break
                    label=' '.join(w['text'] for w in line['words'] if w['x1']<=left)
                    cells={ordered[0]:[],ordered[1]:[]}
                    for w in line['words']:
                        center=(w['x0']+w['x1'])/2
                        if left<=center<middle:cells[ordered[0]].append(w['text'])
                        elif middle<=center<right:cells[ordered[1]].append(w['text'])
                    rows.append(dict(label=label,cells={y:' '.join(ws) for y,ws in cells.items()},
                                     bottom=line['bottom'],x0=min(w['x0'] for w in line['words'])))
                tables.append(dict(page=page['number'],header=header['text'],
                    context=' '.join(line['text'] for line in lines[title_index:header_index+2]),rows=rows))
                break
    if not tables:raise ValueError('PDF_HIGHLIGHTS_TABLE')
    return tables
