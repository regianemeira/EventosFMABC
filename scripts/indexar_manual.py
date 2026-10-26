#!/usr/bin/env python3
"""Gera o índice textual local para a Central de Conhecimento FMABC.

Uso:
  python scripts/indexar_manual.py --input static/docs/manual_cerimonial_eventos_fmabc_2023.pdf \
      --output data/manual_eventos_index.json

Dependência de desenvolvimento: PyMuPDF (pip install -r requirements-manual-index.txt).
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import fitz

SECTIONS = [
    '1. INTRODUÇÃO','2. CLASSIFICAÇÃO','3. MODO DE PARTICIPAÇÃO','4. NOMENCLATURA','5. TIPOLOGIA',
    '6. PLANEJAMENTO, ORGANIZAÇÃO E EXECUÇÃO DE EVENTOS','7. ATRIBUIÇÕES','8. PROGRAMAÇÃO VISUAL',
    '9. DIVULGAÇÃO','10. CONVITES','11. ESTRUTURA FMABC','12. CERIMONIAL E PROTOCOLO',
    '13. PRECEDÊNCIA','14. ANEXOS','15. REFERÊNCIAS BIBLIOGRÁFICAS'
]

def norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()
    return re.sub(r'\s+', ' ', s).strip()

def clean_page(page_number: int, text: str) -> str:
    lines = []
    raw_lines = text.splitlines()
    for idx, line in enumerate(raw_lines):
        value = line.strip()
        if not value:
            continue
        normalized = norm(value)
        if 'CENTRO UNIVERSITARIO FMABC' in normalized or 'MANTIDO PELA FUNDACAO DO ABC' in normalized:
            continue
        if value.isdigit() and value == str(page_number) and (idx < 9 or idx > max(0, len(raw_lines) - 9)):
            continue
        lines.append(value.replace('\uf0b7', '•'))
    return re.sub(r'\s+', ' ', ' '.join(lines)).strip()

def split_atoms(text: str) -> list[str]:
    text = text.replace('•', '\n•')
    atoms = []
    for piece in re.split(r'\n|(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÜÇ0-9(])', text):
        piece = piece.strip(' \t\r\n')
        if not piece:
            continue
        if len(piece) > 520:
            current = ''
            for part in re.split(r'(?<=[,:])\s+', piece):
                if current and len(current) + len(part) + 1 > 450:
                    atoms.append(current); current = part
                else:
                    current = (current + ' ' + part).strip()
            if current:
                atoms.append(current)
        else:
            atoms.append(piece)
    return atoms

def build(input_pdf: Path, output_json: Path) -> None:
    pdf = fitz.open(input_pdf)
    pages, chunks = [], []
    current_section = 'Manual de Cerimonial e Eventos FMABC (2023)'
    current_annex = None
    for pno, page in enumerate(pdf, start=1):
        raw = page.get_text('text', sort=True)
        full = clean_page(pno, raw)
        normalized_full = norm(full)
        annex_match = re.search(r'(?im)^\s*ANEXO\s+(\d+)\s*[–-]\s*([^\n]+)', raw)
        if annex_match:
            name = re.sub(r'\s+', ' ', annex_match.group(2)).strip(' -–')
            current_annex = f"Anexo {annex_match.group(1)} — {name}"
        heading_hits = sorted(
            (normalized_full.find(norm(section)), section.title())
            for section in SECTIONS if norm(section) in normalized_full
        )
        # Páginas que continuam texto de outro capítulo herdam o contexto anterior.
        if current_annex and pno >= 31 and '15. REFERÊNCIAS BIBLIOGRÁFICAS' not in full.upper():
            page_section = current_annex
        elif heading_hits and heading_hits[0][0] < 130:
            page_section = heading_hits[0][1]
        else:
            page_section = current_section
        pages.append({'page': pno, 'section': page_section, 'text': full})

        group, current = [], ''
        for atom in split_atoms(full):
            if current and len(current) + len(atom) + 1 > 430:
                group.append(current)
                current = atom
            else:
                current = (current + ' ' + atom).strip()
        if current:
            group.append(current)
        if not group and full:
            group = [full[:430]]

        section_state = page_section
        for ordinal, body in enumerate(group, 1):
            normalized_body = norm(body)
            body_hits = sorted(
                (normalized_body.find(norm(candidate)), candidate.title())
                for candidate in SECTIONS if norm(candidate) in normalized_body
            )
            if body_hits and body_hits[0][0] < 100 and not page_section.startswith('Anexo '):
                section_state = body_hits[0][1]
            chunk_section = current_annex if page_section.startswith('Anexo ') else section_state
            chunks.append({'id': f'p{pno}-c{ordinal}', 'page': pno, 'section': chunk_section, 'text': body})
            if body_hits:
                section_state = max(body_hits, key=lambda pair: pair[0])[1]

        if page_section.startswith('Anexo '):
            current_section = page_section
        elif heading_hits:
            current_section = max(heading_hits, key=lambda pair: pair[0])[1]
        else:
            current_section = page_section

    payload = {
        'title': 'Manual de Cerimonial e Eventos do Centro Universitário FMABC',
        'version_year': 2023,
        'pdf_pages': len(pdf),
        'source_filename': input_pdf.name,
        'generated_at': __import__('datetime').date.today().isoformat(),
        'pages': pages,
        'chunks': chunks,
    }
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Índice criado: {len(pages)} páginas, {len(chunks)} trechos -> {output_json}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True, help='PDF do manual atualizado')
    parser.add_argument('--output', type=Path, required=True, help='Destino do JSON indexado')
    args = parser.parse_args()
    build(args.input, args.output)
