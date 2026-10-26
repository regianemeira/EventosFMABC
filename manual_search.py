"""Busca textual local, fundamentada exclusivamente no Manual de Eventos da FMABC.

Esta primeira versão não usa internet nem um modelo generativo. Ela recupera trechos literais
indexados do PDF e devolve as páginas de origem, evitando inventar respostas para lacunas.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "data" / "manual_eventos_index.json"

STOPWORDS = set("""
a ao aos aquela aquelas aquele aqueles aquilo as assim ate com como contra da das de dela delas dele deles depois do dos e ela elas ele eles em entre era essa essas esse esses esta estas este estes eu foi foram ha isso isto ja lhe lhes mais mas me mesma mesmas mesmo mesmos meu meus minha minhas muita muitas muito muitos na nas nem nesse nesta neste no nos nossa nossas nosso nossos num numa nunca o os ou para pela pelas pelo pelos por porque qual quais quando quanto quantos quantas que quem se sem sendo seu seus si sob sobre sua suas tao tem tendo ter teu teus toda todas todo todos tu tua tuas um uma umas uns voce voces à às é são ser faz fazem fazer devo deve devem preciso precisa precisam pode podem poderia poderia informacao informacoes assunto assuntos conteudo conteúdos manual documento documentos dizer disser dizia dizem nada algo alguma algum procurar pergunte pergunta perguntas consultar consulte saber saiba responde resposta respostas
""".split())

# Estas equivalências servem somente para localizar passagens; o conteúdo de resposta continua
# sendo extraído do PDF e não é completado com conhecimento externo.
SEARCH_SYNONYMS = {
    "ti": ["tecnologia da informação", "rede", "internet", "transmissão"],
    "infraestrutura": ["estrutura", "espaço", "equipamentos"],
    "limpeza": ["higiene", "sanitários", "limpar"],
    "prazo": ["antecedência", "antecedencia", "dias antes"],
    "convite": ["convites", "rsvp"],
    "foto": ["fotográfica", "fotografica", "imagens", "registro fotográfico"],
    "colacao": ["colação de grau", "sessão solene"],
    "prazo": ["antecedência", "dias", "mínimo"],
    "apoiar": ["apoio", "suporte", "assessoria"],
    "pedir": ["solicitar", "solicitação"],
    "divulgacao": ["comunicação", "divulgar"],
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().replace("\uf0b7", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _light_stem(term: str) -> str:
    """Normalização leve de plurais comuns do português para melhorar a busca local."""
    if len(term) > 5 and term.endswith("oes"):
        return term[:-3] + "ao"  # organizações -> organizacao; informações -> informacao
    if len(term) > 4 and term.endswith("ais"):
        return term[:-3] + "al"  # oficiais -> oficial
    if len(term) > 4 and term.endswith("eis"):
        return term[:-3] + "el"  # responsáveis -> responsavel
    if len(term) > 3 and term.endswith("s") and not term.endswith(("ss", "us", "is")):
        return term[:-1]
    return term


def tokenize(text: str) -> list[str]:
    return [_light_stem(t) for t in normalize(text).split() if t not in STOPWORDS and (len(t) > 1 or t.isdigit())]


@lru_cache(maxsize=1)
def load_index() -> dict:
    if not INDEX_PATH.exists():
        return {"title": "Manual de Cerimonial e Eventos FMABC", "version_year": 2023, "pdf_pages": 67, "chunks": []}
    with INDEX_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _expanded_terms(terms: list[str]) -> list[str]:
    expanded = list(terms)
    for term in terms:
        for synonym in SEARCH_SYNONYMS.get(term, []):
            expanded.extend(tokenize(synonym))
    return list(dict.fromkeys(expanded))


def _select_excerpt(text: str, question_terms: set[str], limit: int = 800) -> str:
    """Choose the most query-relevant short passage inside a retrieved chunk."""
    # Keep headings with the text that follows them, while separating bullet sections and sentences.
    parts = re.split(r"(?=•\s)|(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÜÇ0-9•])", text)
    parts = [re.sub(r"\s+", " ", part).strip() for part in parts if part.strip()]
    if not parts:
        return text[:limit]
    candidates = []
    for start in range(len(parts)):
        for width in (1, 2):
            subset = parts[start:start + width]
            if not subset:
                continue
            joined = " ".join(subset)
            matches = len(question_terms.intersection(tokenize(joined)))
            # Prefer compact excerpts when they support the same number of query terms.
            candidates.append((matches, -len(joined), joined))
    best = max(candidates, default=(0, 0, text), key=lambda item: (item[0], item[1]))[2]
    if len(best) > limit:
        best = best[:limit - 1].rsplit(" ", 1)[0] + "…"
    return best


def search_manual(question: str, max_results: int = 3) -> list[dict]:
    """Retrieve relevant literal text chunks; each result includes its PDF page citation."""
    raw_terms = tokenize(question)
    if not raw_terms:
        return []
    terms = _expanded_terms(raw_terms)
    chunks = load_index().get("chunks", [])
    if not chunks:
        return []

    tokenized = [tokenize(c.get("text", "")) for c in chunks]
    doc_freq: dict[str, int] = {}
    for tokens in tokenized:
        for term in set(tokens):
            doc_freq[term] = doc_freq.get(term, 0) + 1
    total_docs = len(chunks)
    avg_len = sum(map(len, tokenized)) / max(total_docs, 1)
    original_phrase = normalize(question)
    ranked = []
    for chunk, tokens in zip(chunks, tokenized):
        if not tokens:
            continue
        freqs: dict[str, int] = {}
        for token in tokens:
            freqs[token] = freqs.get(token, 0) + 1
        score = 0.0
        matched = set()
        for term in terms:
            tf = freqs.get(term, 0)
            if not tf:
                continue
            matched.add(term)
            idf = math.log(1 + (total_docs - doc_freq.get(term, 0) + 0.5) / (doc_freq.get(term, 0) + 0.5))
            denom = tf + 1.2 * (0.25 + 0.75 * len(tokens) / max(avg_len, 1))
            score += idf * (tf * 2.2) / denom
        normalized_chunk = normalize(chunk.get("text", ""))
        if original_phrase and len(original_phrase) >= 7 and original_phrase in normalized_chunk:
            score += 3.5
        if not score:
            continue
        meaningful_query_terms = set(raw_terms)
        matched_original = meaningful_query_terms.intersection(freqs)
        match_ratio = len(matched_original) / max(1, len(meaningful_query_terms))
        # For longer questions, avoid presenting pages matching only one incidental word.
        min_matches = 1 if len(meaningful_query_terms) <= 2 else 2
        if len(matched_original) < min_matches and not (original_phrase and original_phrase in normalized_chunk):
            continue
        ranked.append((score, match_ratio, chunk))

    ranked.sort(key=lambda item: (item[0], item[1], -int(item[2].get("page", 999))), reverse=True)
    results = []
    seen_pages = set()
    for score, ratio, chunk in ranked:
        page = int(chunk.get("page", 1))
        if page in seen_pages:
            continue
        excerpt = _select_excerpt(chunk.get("text", ""), set(terms), limit=800)
        results.append({
            "page": page,
            "section": chunk.get("section") or "Manual de Eventos",
            "text": excerpt,
            "source": f"Manual de Cerimonial e Eventos FMABC (2023), página {page} do PDF.",
            "pdf_anchor": f"#page={page}",
            "score": round(score, 3),
        })
        seen_pages.add(page)
        if len(results) >= max_results:
            break
    # Low-evidence guard: do not pretend to answer if overlap is very weak.
    if results and len(raw_terms) >= 4 and not any(
        set(raw_terms).intersection(tokenize(r[2].get("text", ""))) for r in ranked[:1]
    ):
        return []
    return results
