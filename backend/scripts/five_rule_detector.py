"""Local, PDF-only detectors for mutation rules 6, 18, 22, 24 and 28.

The detector never receives a mother PDF or mutation plan. PyMuPDF is used only
for text and geometry extraction; it does not modify or rasterize the input.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pymupdf

RULES = (6, 18, 22, 24, 28)
TITLES = {6: '摘要连续内容重复', 18: '公式引用目标不存在', 22: '文献引用目标不存在',
          24: '参考文献未被正文引用', 28: '目录页码与正文不一致'}
_CITATION = re.compile(r'\[(\d+(?:\s*[-–,，、]\s*\d+)*)\]')
_FORMULA_REFERENCE = re.compile(r'(?:公式|(?<!公)式|equation|eq\.?)[\s:：]*[（(]\s*(\d+(?:\s*[.．-]\s*\d+)+)\s*[)）]', re.I)
_DISPLAY_FORMULA = re.compile(r'^[（(]\s*(\d+(?:\s*[.．-]\s*\d+)+)\s*[)）]$')
_TOC_ENTRY = re.compile(r'^\s*(.+?)(?:(?:\.\s*){2,}|…{2,}|⋯{2,}|·{2,})\s*(\d{1,4})\s*$')
_REF_LABEL = re.compile(r'^\s*\[(\d+)\]')
_CHAPTER = re.compile(r'^(?:第\s*(?:\d+|[一二三四五六七八九十]+)\s*章|1[\s.．]+[^0-9]|introduction|引言|绪论)', re.I)


@dataclass(frozen=True)
class Line:
    page: int  # one based physical PDF page
    text: str
    bbox: tuple[float, float, float, float]
    page_width: float
    page_height: float


def extract_lines(pdf_path: Path) -> tuple[list[Line], int]:
    lines = []
    with pymupdf.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, 1):
            for block in page.get_text('dict', sort=True)['blocks']:
                if block['type'] != 0:
                    continue
                for raw in block['lines']:
                    content = ''.join(span['text'] for span in raw['spans']).strip()
                    if content:
                        lines.append(Line(page_number, content, tuple(raw['bbox']),
                                          page.rect.width, page.rect.height))
        return lines, len(pdf)


def _compact(text: str) -> str:
    return re.sub(r'[^\w\u4e00-\u9fff]', '', text).casefold()


def _heading(text: str) -> str:
    return re.sub(r'\s+', '', text).casefold()


def _finding(rule: int, line: Line, message: str, token: str = '', **extra) -> dict:
    x0, y0, x1, y1 = (round(v, 2) for v in line.bbox)
    rect = {'x1': x0, 'y1': y0, 'x2': x1, 'y2': y1,
            'width': round(line.page_width, 2), 'height': round(line.page_height, 2),
            'page_number': line.page}
    return {'rule_id': str(rule), 'page': line.page, 'bbox': [x0, y0, x1, y1],
            'text_excerpt': line.text[:220], 'token': token, 'message': message,
            'location': {'type': 'pdf_bbox', 'page_number': line.page,
                         'bounding_rect': rect, 'rects': [rect], 'text_excerpt': line.text[:220]},
            **extra}


def _result(findings: list[dict] | None = None, reason: str = '') -> dict:
    if reason:
        return {'status': 'unsupported', 'reason': reason, 'findings': []}
    return {'status': 'completed', 'findings': findings or []}


def _visual_rows(lines: list[Line]) -> list[Line]:
    """Join PDF fragments on the same visual row using geometry, then x order."""
    by_page = defaultdict(list)
    for line in lines:
        by_page[line.page].append(line)
    rows = []
    for page, page_lines in by_page.items():
        groups = []
        for line in sorted(page_lines, key=lambda item: (item.bbox[1] + item.bbox[3]) / 2):
            center = (line.bbox[1] + line.bbox[3]) / 2
            group = next((group for group in groups if abs(center - sum((item.bbox[1] + item.bbox[3]) / 2 for item in group) / len(group)) <= 8), None)
            if group is None:
                groups.append([line])
            else:
                group.append(line)
        for group in groups:
            group.sort(key=lambda item: item.bbox[0])
            bbox = (min(item.bbox[0] for item in group), min(item.bbox[1] for item in group),
                    max(item.bbox[2] for item in group), max(item.bbox[3] for item in group))
            rows.append(Line(page, ' '.join(item.text for item in group), bbox,
                             group[0].page_width, group[0].page_height))
    return rows


def _toc_pages(lines: list[Line], page_count: int) -> set[int]:
    by_page = defaultdict(list)
    for row in _visual_rows(lines):
        by_page[row.page].append(row.text)
    pages = set()
    max_candidate = min(60, max(2, int(page_count * .5)))
    headings_by_page = {}
    for page, texts in by_page.items():
        if page > max_candidate:
            continue
        entries = [_TOC_ENTRY.match(text) for text in texts]
        headings = [match.group(1).strip() for match in entries if match]
        headings_by_page[page] = headings
        chapter_like = sum(bool(re.match(r'^(?:第\s*(?:\d+|[一二三四五六七八九十]+)\s*章|\d+(?:[.．]\d+)*\s+)', text)) for text in headings)
        if len(headings) >= 3 and chapter_like >= 2:
            pages.add(page)
    if pages:
        for direction, boundary in ((-1, min(pages)), (1, max(pages))):
            page = boundary + direction
            while 1 <= page <= max_candidate:
                headings = headings_by_page.get(page, [])
                if not headings or all(re.match(r'^[图表]\s*\d', text) for text in headings):
                    break
                pages.add(page)
                page += direction
    return pages


def _body_start(lines: list[Line], toc_pages: set[int]) -> int:
    after_toc = max(toc_pages, default=0)
    for line in lines:
        if line.page > after_toc and _CHAPTER.match(line.text.strip()):
            return line.page
    return after_toc + 1


def _reference_start(lines: list[Line], body_start: int, page_count: int) -> int | None:
    by_page = defaultdict(list)
    for line in lines:
        by_page[line.page].append(line)
    for line in lines:
        if line.page < body_start:
            continue
        if _heading(line.text) not in {'参考文献', 'references', 'bibliography'}:
            continue
        nearby = by_page[line.page] + by_page[line.page + 1]
        if sum(bool(_REF_LABEL.match(item.text)) for item in nearby) >= 2:
            return line.page
    return None


def _body_lines(lines: list[Line], body_start: int, ref_start: int | None,
                toc_pages: set[int]) -> list[Line]:
    return [line for line in lines if line.page >= body_start
            and (ref_start is None or line.page < ref_start) and line.page not in toc_pages]


def _abstract_lines(lines: list[Line], body_start: int) -> list[Line]:
    start = None
    for i, line in enumerate(lines):
        if line.page >= body_start:
            break
        if _heading(line.text) in {'摘要', '中文摘要', 'abstract'} or (line.text.strip() == '摘' and i + 1 < len(lines) and lines[i + 1].page == line.page and lines[i + 1].text.strip() == '要'):
            start = i + (2 if line.text.strip() == '摘' else 1)
            break
    if start is None:
        return []
    extracted = []
    for line in lines[start:]:
        compact = _heading(line.text)
        if line.page >= body_start or re.match(r'^(关键词|关键字|keywords?|abstract|英文摘要)', compact):
            break
        if compact not in {'摘要', '中文摘要', '摘', '要'}:
            extracted.append(line)
    return extracted


def _rule_6(abstract: list[Line], body: list[Line]) -> dict:
    if len(abstract) < 3 or not body:
        return _result(reason='未可靠识别中文摘要或正文')
    normalized_body = ''.join(_compact(line.text) for line in body)
    findings = []
    for i in range(len(abstract) - 2):
        chunk = ''.join(_compact(line.text) for line in abstract[i:i + 3])
        if len(chunk) < 55 or chunk not in normalized_body:
            continue
        source = next((line for line in body if len(_compact(line.text)) >= 12
                       and _compact(line.text) in chunk), None)
        if source is None:
            continue
        if findings and findings[-1]['page'] == abstract[i].page and findings[-1]['related_page'] == source.page:
            continue
        findings.append(_finding(6, abstract[i], '摘要中连续三行与正文文字完全重复',
                                 token=chunk[:30], related_page=source.page))
    return _result(findings)


def _rule_18(body: list[Line]) -> dict:
    displayed = set()
    for line in body:
        marker = _DISPLAY_FORMULA.match(line.text.strip())
        if marker and (line.bbox[0] > line.page_width * .55 or len(line.text.strip()) < 20):
            displayed.add(re.sub(r'\s+', '', marker.group(1)).replace('．', '.'))
    if not displayed:
        return _result(reason='未可靠识别独立公式编号')
    findings = []
    seen = set()
    for line in body:
        for match in _FORMULA_REFERENCE.finditer(line.text):
            number = re.sub(r'\s+', '', match.group(1)).replace('．', '.')
            key = (line.page, number, line.bbox[1])
            if number not in displayed and key not in seen:
                findings.append(_finding(18, line, f'公式引用 {number} 在公式编号中不存在', token=number))
                seen.add(key)
    return _result(findings)


def _references(lines: list[Line], ref_start: int | None) -> list[tuple[int, Line]]:
    if ref_start is None:
        return []
    entries = []
    for line in lines:
        if line.page < ref_start:
            continue
        if _heading(line.text) in {'致谢', '附录', 'acknowledgements', 'appendix'}:
            break
        match = _REF_LABEL.match(line.text)
        if match:
            entries.append((int(match.group(1)), line))
    return entries


def _citation_numbers(text: str) -> list[tuple[int, str]]:
    found = []
    for match in _CITATION.finditer(text):
        inner = match.group(1)
        numbers = [int(s) for s in re.findall(r'\d+', inner)]
        if len(numbers) > 1 and (0 in numbers or max(numbers) - min(numbers) > 50):
            continue
        if len(numbers) == 2 and re.search(r'[-–]', inner) and numbers[1] - numbers[0] in range(1, 51):
            numbers = list(range(numbers[0], numbers[1] + 1))
        found.extend((number, match.group(0)) for number in numbers)
    return found


def _rules_22_24(body: list[Line], entries: list[tuple[int, Line]]) -> tuple[dict, dict]:
    if len(entries) < 2:
        reason = '未可靠识别编号参考文献表'
        return _result(reason=reason), _result(reason=reason)
    labels = {number for number, _ in entries}
    citations = defaultdict(list)
    for line in body:
        for number, marker in _citation_numbers(line.text):
            citations[number].append((line, marker))
    missing_targets = []
    for number, appearances in citations.items():
        if number not in labels:
            line, marker = appearances[0]
            missing_targets.append(_finding(22, line, f'正文引用 {marker} 无对应参考文献', token=str(number)))
    uncited = [_finding(24, line, f'参考文献 [{number}] 未在正文引用', token=str(number))
               for number, line in entries if number not in citations]
    return _result(missing_targets), _result(uncited)


def _heading_candidates(body: list[Line]) -> dict[str, int]:
    by_page = defaultdict(list)
    for line in body:
        by_page[line.page].append(line)
    candidates = {}
    for page, page_lines in by_page.items():
        for i, line in enumerate(page_lines):
            if line.bbox[1] > line.page_height * .9:
                continue
            for width in (1, 2, 3):
                seq = page_lines[i:i + width]
                if len(seq) != width or any(seq[j].bbox[1] - seq[j - 1].bbox[1] > 45 for j in range(1, len(seq))):
                    break
                key = _compact(''.join(item.text for item in seq))
                if 2 <= len(key) <= 110 and key not in candidates:
                    candidates[key] = page
    return candidates


def _rule_28(lines: list[Line], toc_pages: set[int], body: list[Line]) -> dict:
    entries = []
    for line in _visual_rows([item for item in lines if item.page in toc_pages]):
        match = _TOC_ENTRY.match(line.text)
        if match:
            heading = _compact(match.group(1))
            if len(heading) >= 2:
                entries.append((heading, int(match.group(2)), line))
    if len(entries) < 5:
        return _result(reason='未可靠识别至少五条目录页码')
    headings = _heading_candidates(body)
    matches = []
    for heading, shown, line in entries:
        pages = [page for key, page in headings.items() if key == heading or
                 (len(heading) >= 4 and key.startswith(heading) and len(key) - len(heading) <= 12)]
        if pages:
            matches.append((shown, min(pages), line))
    if len(matches) < 5:
        return _result(reason='目录与正文匹配的标题不足五条')
    offsets = Counter(physical - shown for shown, physical, _ in matches)
    offset, support = offsets.most_common(1)[0]
    if support < max(3, int(len(matches) * .6)):
        return _result(reason='无法可靠确定目录页码与 PDF 物理页的偏移')
    findings = []
    for shown, physical, line in matches:
        actual = physical - offset
        if shown != actual:
            findings.append(_finding(28, line, f'目录页码 {shown} 与正文实际页码 {actual} 不一致',
                                     token=str(shown), actual_page=actual, body_pdf_page=physical))
    return _result(findings)


def detect_lines(lines: list[Line], selected_rules=RULES, page_count: int | None = None) -> dict:
    selected = tuple(dict.fromkeys(int(rule) for rule in selected_rules))
    invalid = set(selected) - set(RULES)
    if invalid:
        raise ValueError(f'未知规则: {sorted(invalid)}')
    page_count = page_count or max((line.page for line in lines), default=0)
    ordered = sorted(lines, key=lambda line: line.page)  # retain PDF reading order within a page
    toc_pages = _toc_pages(ordered, page_count)
    body_start = _body_start(ordered, toc_pages)
    ref_start = _reference_start(ordered, body_start, page_count)
    body = _body_lines(ordered, body_start, ref_start, toc_pages)
    results = {}
    if 6 in selected:
        results['6'] = _rule_6(_abstract_lines(ordered, body_start), body)
    if 18 in selected:
        results['18'] = _rule_18(body)
    if 22 in selected or 24 in selected:
        citation_scope = [line for line in ordered if (ref_start is None or line.page < ref_start)
                          and line.page not in toc_pages]
        r22, r24 = _rules_22_24(citation_scope, _references(ordered, ref_start))
        if 22 in selected:
            results['22'] = r22
        if 24 in selected:
            results['24'] = r24
    if 28 in selected:
        toc_body = [line for line in ordered if line.page > max(toc_pages, default=0)
                    and line.page not in toc_pages]
        results['28'] = _rule_28(ordered, toc_pages, toc_body)
    return results


def detect_pdf(pdf_path: Path, selected_rules=RULES) -> dict:
    lines, pages = extract_lines(Path(pdf_path))
    return {'pdf': str(pdf_path), 'pages': pages,
            'rules': detect_lines(lines, selected_rules, pages)}


def main() -> None:
    parser = argparse.ArgumentParser(description='本地 PDF 五规则检测器')
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--rule', action='append', type=int, choices=RULES)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = detect_pdf(args.pdf, args.rule or RULES)
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding='utf-8')
    else:
        print(serialized)


if __name__ == '__main__':
    main()
