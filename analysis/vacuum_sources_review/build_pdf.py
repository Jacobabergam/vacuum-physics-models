#!/usr/bin/env python3
"""Markdown (limited subset) -> styled PDF via reportlab, DejaVu fonts for full Unicode."""
import re, os
import matplotlib
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer,
                                Image, Table, TableStyle, HRFlowable, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

FDIR = os.path.join(matplotlib.get_data_path(), 'fonts', 'ttf')
for name, fn in [('DejaVu', 'DejaVuSans.ttf'), ('DejaVu-Bold', 'DejaVuSans-Bold.ttf'),
                 ('DejaVu-Italic', 'DejaVuSans-Oblique.ttf'),
                 ('DejaVu-BoldItalic', 'DejaVuSans-BoldOblique.ttf'),
                 ('DejaVu-Mono', 'DejaVuSansMono.ttf')]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FDIR, fn)))
pdfmetrics.registerFontFamily('DejaVu', normal='DejaVu', bold='DejaVu-Bold',
                              italic='DejaVu-Italic', boldItalic='DejaVu-BoldItalic')

INK, INK2, MUTED, GRID, SURFB = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#f6f5f2'
W = 6.7 * inch

S = {
 'h1': ParagraphStyle('h1', fontName='DejaVu-Bold', fontSize=16.5, leading=21,
                      textColor=INK, spaceAfter=10, spaceBefore=2),
 'h2': ParagraphStyle('h2', fontName='DejaVu-Bold', fontSize=12.5, leading=16,
                      textColor=INK, spaceBefore=16, spaceAfter=6),
 'h3': ParagraphStyle('h3', fontName='DejaVu-Bold', fontSize=10.5, leading=14,
                      textColor=INK2, spaceBefore=10, spaceAfter=4),
 'body': ParagraphStyle('body', fontName='DejaVu', fontSize=9.4, leading=13.6,
                        textColor=INK, spaceAfter=7, alignment=TA_LEFT),
 'eq': ParagraphStyle('eq', fontName='DejaVu', fontSize=9.8, leading=14.5, textColor=INK,
                      leftIndent=18, spaceBefore=2, spaceAfter=7, backColor=SURFB,
                      borderPadding=(5, 8, 5, 8)),
 'cap': ParagraphStyle('cap', fontName='DejaVu-Italic', fontSize=8.4, leading=11,
                       textColor=INK2, alignment=TA_CENTER, spaceBefore=2, spaceAfter=10),
 'cell': ParagraphStyle('cell', fontName='DejaVu', fontSize=8.4, leading=11.4, textColor=INK),
 'cellh': ParagraphStyle('cellh', fontName='DejaVu-Bold', fontSize=8.4, leading=11.4, textColor=INK),
 'li': ParagraphStyle('li', fontName='DejaVu', fontSize=9.4, leading=13.6, textColor=INK,
                      leftIndent=16, bulletIndent=4, spaceAfter=4),
}

def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def inline(s):
    s = esc(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'(?<![\w*])\*([^*\n]+?)\*(?![\w*])', r'<i>\1</i>', s)
    s = re.sub(r'`([^`]+)`', r'<font face="DejaVu-Mono" size="8.2">\1</font>', s)
    s = re.sub(r'(https?://[^\s<]+)', r'<link href="\1" color="#2a5b8f">\1</link>', s)
    return s

def build(md_path, pdf_path):
    lines = open(md_path).read().split('\n')
    story, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1; continue
        if ln.startswith('# ') and not ln.startswith('## '):
            story.append(Paragraph(inline(ln[2:]), S['h1'])); i += 1; continue
        if ln.startswith('## '):
            story.append(Paragraph(inline(ln[3:]), S['h2']))
            story.append(HRFlowable(width='100%', thickness=0.7, color=colors.HexColor(GRID), spaceAfter=6))
            i += 1; continue
        if ln.startswith('### '):
            story.append(Paragraph(inline(ln[4:]), S['h3'])); i += 1; continue
        if ln.strip() == '---':
            story.append(Spacer(1, 4)); i += 1; continue
        m = re.match(r'!\[(.*?)\]\((.*?)\)', ln.strip())
        if m:
            cap, path = m.groups()
            iw, ih = PILImage.open(path).size
            w = min(W, 6.7 * inch); h = w * ih / iw
            story.append(KeepTogether([Image(path, width=w, height=h),
                                       Paragraph(inline(cap), S['cap'])]))
            i += 1; continue
        if ln.startswith('> '):
            block = []
            while i < len(lines) and lines[i].startswith('>'):
                block.append(lines[i][1:].strip()); i += 1
            story.append(Paragraph('<br/>'.join(inline(b) for b in block if b), S['eq'])); continue
        if ln.strip().startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-{3,}:?', c) for c in cells):
                    rows.append(cells)
                i += 1
            ncol = max(len(r) for r in rows)
            data = [[Paragraph(inline(c), S['cellh'] if ri == 0 else S['cell'])
                     for c in r + [''] * (ncol - len(r))] for ri, r in enumerate(rows)]
            # column widths proportional to content length (bounded), summing to W
            lens = [max(min(len(r[j]) if j < len(r) else 0, 60) for r in rows) + 6
                    for j in range(ncol)]
            tot = sum(lens)
            cw = [max(0.09 * W, W * L / tot) for L in lens]
            cw = [w * W / sum(cw) for w in cw]
            t = Table(data, colWidths=cw, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(GRID)),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0efec')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
                ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5)]))
            story.append(t); story.append(Spacer(1, 8)); continue
        if re.match(r'^\s*[-*] ', ln):
            while i < len(lines) and re.match(r'^\s*[-*] ', lines[i]):
                story.append(Paragraph(inline(re.sub(r'^\s*[-*] ', '', lines[i])),
                                       S['li'], bulletText='•'))
                i += 1
            story.append(Spacer(1, 3)); continue
        if re.match(r'^\s*\d+\. ', ln):
            while i < len(lines) and re.match(r'^\s*\d+\. ', lines[i]):
                num = re.match(r'^\s*(\d+)\. ', lines[i]).group(1)
                story.append(Paragraph(inline(re.sub(r'^\s*\d+\. ', '', lines[i])),
                                       S['li'], bulletText=f'{num}.'))
                i += 1
            story.append(Spacer(1, 3)); continue
        # paragraph: join consecutive plain lines
        block = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r'^(#|\||> |!\[|---$|\s*[-*] |\s*\d+\. )', lines[i]):
            block.append(lines[i]); i += 1
        story.append(Paragraph(inline(' '.join(block)), S['body']))

    def footer(canv, doc):
        canv.saveState()
        canv.setFont('DejaVu', 7.6); canv.setFillColor(colors.HexColor(MUTED))
        canv.drawString(0.9 * inch, 0.55 * inch, 'Vacuum Degradation Sources — Ranked Review — July 2026')
        canv.drawRightString(letter[0] - 0.9 * inch, 0.55 * inch, f'page {doc.page}')
        canv.restoreState()

    doc = BaseDocTemplate(pdf_path, pagesize=letter,
                          leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                          topMargin=0.75 * inch, bottomMargin=0.85 * inch,
                          title='Dewar Vacuum Bakeout — Required Vacuum, Bake Duration, and Vacuum-Life Curves',
                          author='Prepared with Claude')
    fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='f')
    doc.addPageTemplates([PageTemplate(id='p', frames=[fr], onPage=footer)])
    doc.build(story)
    print('built', pdf_path)

if __name__ == '__main__':
    build('dewar_bakeout_reference.md', 'dewar_bakeout_reference.pdf')
