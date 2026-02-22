#!/usr/bin/env python3
"""
Academic Literature Crawler - Semantic Scholar (Primary) + Google Scholar (Fallback)

Supports two directive types from references-searcher:
- SEED: Snowball search (find papers citing a seed paper)
- QUERY: Direct keyword search

Usage:
    python scholar_crawler.py --input search_plan.md [--max-results 10]
    python scholar_crawler.py --queries "query1" "query2" [--max-results 10]
"""

import sys
import os
import re
import json
import time
import argparse
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from scholarly import scholarly, ProxyGenerator
    SCHOLARLY_AVAILABLE = True
except ImportError:
    SCHOLARLY_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("ERROR: pandas library required but not installed.", file=sys.stderr)
    sys.exit(1)

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    print("WARNING: rank_bm25 not installed. Install with: pip install rank_bm25", file=sys.stderr)


@dataclass
class SearchDirective:
    directive_type: str
    raw_query: str
    seed_info: Optional[str] = None
    filter_info: Optional[str] = None
    sort_info: Optional[str] = None
    line_number: int = 0
    
    def __repr__(self):
        if self.directive_type == 'SEED':
            sort_str = f" | SORT: '{self.sort_info}'" if self.sort_info else ""
            return f"SEED: '{self.seed_info}' | FILTER: '{self.filter_info}'{sort_str}"
        else:
            sort_str = f" | SORT: '{self.sort_info}'" if self.sort_info else ""
            return f"QUERY: '{self.raw_query}'{sort_str}"


@dataclass
class FilterConditions:
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    keywords: List[str] = field(default_factory=list)
    
    def matches(self, paper: Dict) -> bool:
        year = paper.get('year', 0)
        
        if self.year_min is not None and year > 0 and year < self.year_min:
            return False
        if self.year_max is not None and year > 0 and year > self.year_max:
            return False
        
        return True
    
    def compute_bm25_score(self, paper: Dict) -> float:
        if not self.keywords or not BM25_AVAILABLE:
            return 0.0
        
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')
        text = (title + ' ' + abstract).lower()
        
        if not text.strip():
            return 0.0
        
        tokenized_corpus = [text.split()]
        bm25 = BM25Okapi(tokenized_corpus)
        
        query = ' '.join(self.keywords).lower().split()
        scores = bm25.get_scores(query)
        
        return scores[0] if len(scores) > 0 else 0.0


class BM25Scorer:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
    
    def compute_scores(self, papers: List[Dict], keywords: List[str]) -> List[Dict]:
        if not keywords or not papers:
            for paper in papers:
                paper['bm25_score'] = 0.0
            return papers
        
        if not BM25_AVAILABLE:
            for paper in papers:
                title = paper.get('title', '').lower()
                abstract = paper.get('abstract', '').lower()
                score = 0
                for kw in keywords:
                    kw_lower = kw.lower()
                    if kw_lower in title:
                        score += 3
                    score += min(abstract.count(kw_lower), 3)
                paper['bm25_score'] = float(score)
            return papers
        
        corpus = []
        for paper in papers:
            title = paper.get('title', '')
            abstract = paper.get('abstract', '')
            text = (title + ' ' + abstract).lower()
            corpus.append(text.split())
        
        bm25 = BM25Okapi(corpus)
        query = ' '.join(keywords).lower().split()
        scores = bm25.get_scores(query)
        
        for i, paper in enumerate(papers):
            paper['bm25_score'] = float(scores[i]) if i < len(scores) else 0.0
        
        return papers


def map_sort_value(sort_value: Optional[str]) -> Optional[str]:
    """
    Map SORT tag values to Semantic Scholar API sort parameters.
    
    Args:
        sort_value: SORT tag value from directive (citation, relevance, influence, recency)
    
    Returns:
        Semantic Scholar API sort parameter string
    """
    if not sort_value:
        return None
    
    sort_mapping = {
        'citation': 'citationCount:desc',
        'relevance': None,
        'influence': 'citationCount:desc',
        'recency': 'year:desc'
    }
    
    return sort_mapping.get(sort_value.lower(), None)


def format_citation_gbt7714(paper: Dict) -> str:
    """
    Format a paper citation in GB/T 7714-2015 standard format.
    
    Supports:
    - Journal articles [J]
    - Conference papers [C]
    - Books [M]
    - Theses [D]
    - Other documents [R]
    
    Args:
        paper: Dictionary containing paper metadata with keys:
            - authors: List of author names or string
            - title: Paper title
            - year: Publication year
            - venue: Journal/conference name
            - volume: Journal volume
            - issue: Journal issue
            - pages: Page range
            - doi: DOI identifier
    
    Returns:
        Formatted citation string in GB/T 7714 format
    """
    def format_authors(authors_data) -> str:
        if not authors_data:
            return ''
        if isinstance(authors_data, str):
            authors_list = [a.strip() for a in authors_data.replace(';', ',').split(',') if a.strip()]
        else:
            authors_list = list(authors_data)
        
        if not authors_list:
            return ''
        
        formatted = []
        for author in authors_list[:3]:
            name = str(author).strip()
            if not name:
                continue
            if any('\u4e00' <= c <= '\u9fff' for c in name):
                formatted.append(name)
            else:
                parts = name.split()
                if len(parts) >= 2:
                    last = parts[0]
                    initials = ''.join(p[0].upper() + '.' for p in parts[1:] if p)
                    formatted.append(f"{last} {initials}" if initials else last)
                else:
                    formatted.append(name)
        
        result = ', '.join(formatted)
        if len(authors_list) > 3:
            if any('\u4e00' <= c <= '\u9fff' for c in str(authors_list[0])):
                result += ', 等'
            else:
                result += ', et al'
        return result
    
    def detect_publication_type(paper: Dict) -> str:
        venue = str(paper.get('venue', '') or '').lower()
        title = str(paper.get('title', '') or '').lower()
        
        thesis_keywords = ['thesis', 'dissertation', '博士', '硕士', '学位论文']
        if any(kw in title or kw in venue for kw in thesis_keywords):
            return 'D'
        
        conference_keywords = ['conference', 'proceedings', 'workshop', 'symposium', '会议', '研讨会']
        if any(kw in venue for kw in conference_keywords):
            return 'C'
        
        book_keywords = ['press', 'publisher', '出版社']
        if any(kw in venue for kw in book_keywords):
            return 'M'
        
        if paper.get('volume') or paper.get('issue') or paper.get('pages'):
            return 'J'
        
        return 'J'
    
    authors = format_authors(paper.get('authors', []))
    title = paper.get('title', '') or ''
    year = paper.get('year', '') or ''
    venue = paper.get('venue', '') or ''
    volume = paper.get('volume', '') or ''
    issue = paper.get('issue', '') or ''
    pages = paper.get('pages', '') or ''
    doi = paper.get('doi', '') or ''
    
    pub_type = detect_publication_type(paper)
    
    parts = []
    
    if authors:
        parts.append(authors)
    
    if title:
        parts.append(f"{title}[{pub_type}]")
    
    if venue:
        if pub_type in ['M', 'D']:
            parts.append(venue)
        else:
            venue_parts = [venue]
            if year:
                venue_parts.append(str(year))
            if volume:
                vol_str = str(volume)
                if issue:
                    vol_str += f"({issue})"
                venue_parts.append(vol_str)
            if pages:
                venue_parts.append(str(pages))
            parts.append(', '.join(venue_parts))
    elif year:
        parts.append(str(year))
    
    if doi:
        parts.append(f"https://doi.org/{doi}")
    
    return '. '.join(parts)


class ScholarCrawler:
    SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper/search"
    SEMANTIC_SCHOLAR_CITATIONS_API = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
    SEMANTIC_SCHOLAR_PAPER_API = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
    
    def __init__(self, delay_range: Tuple[float, float] = (1.1, 1.1), max_retries: int = 3, 
                 api_key: Optional[str] = None):
        self.delay_range = delay_range
        self.max_retries = max_retries
        
        self.api_key = api_key or os.environ.get('SEMANTIC_SCHOLAR_API_KEY', '')
        
        if not self.api_key:
            config_path = Path(__file__).parent.parent / 'config.json'
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        self.api_key = config.get('semantic_scholar_api_key', '')
                except Exception:
                    pass
        
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        if self.api_key:
            print(f"INFO: Semantic Scholar API key configured (rate limit: 100 requests/5min)", file=sys.stderr)
        
        if SCHOLARLY_AVAILABLE:
            self._setup_scholarly()
    
    def _setup_scholarly(self):
        try:
            scholarly.set_timeout(30)
            scholarly.set_retries(2)
        except Exception as e:
            print(f"WARNING: Failed to setup scholarly: {e}", file=sys.stderr)
    
    def _apply_delay(self):
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {'User-Agent': random.choice(self.user_agents)}
        if self.api_key:
            headers['x-api-key'] = self.api_key
        return headers
    
    def parse_filter(self, filter_str: str) -> FilterConditions:
        conditions = FilterConditions()
        
        if not filter_str:
            return conditions
        
        year_patterns = [
            (r'Year\s*>\s*(\d{4})', 'year_min'),
            (r'Year\s*<\s*(\d{4})', 'year_max'),
            (r'Year\s*>=\s*(\d{4})', 'year_min'),
            (r'Year\s*<=\s*(\d{4})', 'year_max'),
        ]
        
        for pattern, attr in year_patterns:
            match = re.search(pattern, filter_str, re.IGNORECASE)
            if match:
                setattr(conditions, attr, int(match.group(1)))
        
        keyword_pattern = r'"([^"]+)"'
        keywords = re.findall(keyword_pattern, filter_str)
        for kw in keywords:
            if not kw.lower().startswith('year'):
                conditions.keywords.append(kw)
        
        bare_keywords = re.findall(r'\b([a-zA-Z]{3,})\b', filter_str)
        for kw in bare_keywords:
            if kw.lower() not in ['year', 'and', 'or', 'not'] and kw not in conditions.keywords:
                conditions.keywords.append(kw)
        
        return conditions
    
    def extract_directives_from_md(self, md_file: Path) -> List[SearchDirective]:
        human_directives = []
        auto_directives = []
        
        try:
            content = md_file.read_text(encoding='utf-8')
            
            human_zone = re.search(r'# 🧑‍💻 人类最高指令区.*?---', content, re.DOTALL)
            if human_zone:
                human_section = human_zone.group(0)
                human_directives = self._parse_directives_from_text(human_section, is_human=True)
                print(f"INFO: Found {len(human_directives)} directives in Human Override Zone", file=sys.stderr)
            
            auto_directives = self._parse_directives_from_text(content, is_human=False)
            
            seen_keys = set()
            for d in human_directives:
                seen_keys.add(f"{d.directive_type}:{d.raw_query}")
            
            filtered_auto = []
            for d in auto_directives:
                key = f"{d.directive_type}:{d.raw_query}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    filtered_auto.append(d)
            
            final_directives = human_directives + filtered_auto
            
            seed_count = sum(1 for d in final_directives if d.directive_type == 'SEED')
            query_count = sum(1 for d in final_directives if d.directive_type == 'QUERY')
            print(f"INFO: Extracted {len(final_directives)} directives ({seed_count} SEED, {query_count} QUERY)", file=sys.stderr)
            
        except Exception as e:
            print(f"ERROR: Failed to extract directives from {md_file}: {e}", file=sys.stderr)
        
        return final_directives
    
    def _parse_directives_from_text(self, text: str, is_human: bool = False) -> List[SearchDirective]:
        directives = []
        
        seed_pattern = r'(\d+)\.\s*SEED:\s*"([^"]+)"\s*\|\s*FILTER:\s*(.+?)(?:\s*\|\s*SORT:\s*"([^"]+)")?(?=\n|$)'
        for match in re.finditer(seed_pattern, text):
            line_num = int(match.group(1))
            seed_info = match.group(2).strip()
            filter_info = match.group(3).strip()
            sort_info = match.group(4).strip() if match.group(4) else None
            
            if filter_info.startswith('"') and filter_info.endswith('"') and filter_info.count('"') == 2:
                filter_info = filter_info[1:-1]
            
            directive = SearchDirective(
                directive_type='SEED',
                raw_query=f'SEED: "{seed_info}" | FILTER: "{filter_info}"',
                seed_info=seed_info,
                filter_info=filter_info,
                sort_info=sort_info,
                line_number=line_num
            )
            directives.append(directive)
        
        query_pattern = r'(\d+)\.\s*QUERY:\s*(.+?)(?:\s*\|\s*SORT:\s*"([^"]+)")?(?=\n|$)'
        for match in re.finditer(query_pattern, text):
            line_num = int(match.group(1))
            query_str = match.group(2).strip()
            sort_info = match.group(3).strip() if match.group(3) else None
            
            if query_str.startswith('"') and query_str.endswith('"') and query_str.count('"') == 2:
                query_str = query_str[1:-1]
            
            if '在此处添加' in query_str or query_str == '...':
                continue
            
            directive = SearchDirective(
                directive_type='QUERY',
                raw_query=query_str,
                sort_info=sort_info,
                line_number=line_num
            )
            directives.append(directive)
        
        if not directives:
            legacy_pattern = r'(\d+)\.\s*`([^`]+)`'
            for match in re.finditer(legacy_pattern, text):
                line_num = int(match.group(1))
                query_str = match.group(2).strip()
                
                if '在此处添加' in query_str or query_str == '...':
                    continue
                
                seed_match = re.match(r'SEED:\s*"([^"]+)"\s*\|\s*FILTER:\s*"([^"]*)"', query_str, re.IGNORECASE)
                if seed_match:
                    directive = SearchDirective(
                        directive_type='SEED',
                        raw_query=query_str,
                        seed_info=seed_match.group(1),
                        filter_info=seed_match.group(2),
                        line_number=line_num
                    )
                    directives.append(directive)
                    continue
                
                query_match = re.match(r'QUERY:\s*(.+)', query_str, re.IGNORECASE)
                if query_match:
                    extracted_query = query_match.group(1).strip()
                    if extracted_query.startswith('"') and extracted_query.endswith('"'):
                        extracted_query = extracted_query[1:-1]
                    directive = SearchDirective(
                        directive_type='QUERY',
                        raw_query=extracted_query,
                        line_number=line_num
                    )
                    directives.append(directive)
                    continue
                
                directive = SearchDirective(
                    directive_type='QUERY',
                    raw_query=query_str,
                    line_number=line_num
                )
                directives.append(directive)
        
        return directives
    
    def _parse_seed_info(self, seed_info: str) -> Dict[str, str]:
        parts = seed_info.split()
        author = parts[0] if parts else ''
        year = ''
        for p in reversed(parts):
            if p.isdigit() and len(p) == 4:
                year = p
                break
        title_keywords = [p for p in parts if not p.isdigit() and p != author][:-1] if len(parts) > 2 else []
        return {'author': author, 'year': year, 'title_keywords': title_keywords}
    
    def _match_seed_paper(self, paper: Dict, seed_parts: Dict[str, str]) -> int:
        score = 0
        title = paper.get('title', '').lower()
        authors = paper.get('authors', [])
        year = paper.get('year', 0)
        
        if seed_parts['year'] and str(year) == seed_parts['year']:
            score += 50
        
        if seed_parts['author'] and authors:
            first_author = authors[0].get('name', '').lower() if authors else ''
            if seed_parts['author'].lower() in first_author:
                score += 30
        
        if seed_parts['title_keywords']:
            for kw in seed_parts['title_keywords']:
                if kw.lower() in title:
                    score += 5
        
        return score
    
    def search_by_seed(self, seed_info: str, filter_info: str, max_results: int = 10, sort_info: str = None) -> List[Dict]:
        papers = []
        
        if not REQUESTS_AVAILABLE:
            print("WARNING: requests library not available for SEED search", file=sys.stderr)
            return papers
        
        try:
            self._apply_delay()
            
            search_params = {
                'query': seed_info,
                'limit': 10,
                'fields': 'paperId,title,authors,year,citationCount'
            }
            
            response = requests.get(
                self.SEMANTIC_SCHOLAR_API, 
                params=search_params, 
                headers=self._get_headers(), 
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"WARNING: Failed to find seed paper '{seed_info}' (status {response.status_code})", file=sys.stderr)
                return papers
            
            data = response.json()
            if not data.get('data'):
                print(f"WARNING: No seed paper found for '{seed_info}'", file=sys.stderr)
                return papers
            
            seed_parts = self._parse_seed_info(seed_info)
            candidates = data['data']
            
            best_paper = None
            best_score = -1
            
            for candidate in candidates:
                score = self._match_seed_paper(candidate, seed_parts)
                if score > best_score:
                    best_score = score
                    best_paper = candidate
            
            if not best_paper:
                best_paper = candidates[0]
            
            paper_id = best_paper.get('paperId')
            seed_title = best_paper.get('title', '')
            
            if best_score < 50:
                print(f"WARNING: Low confidence match (score={best_score}) for SEED '{seed_info}'", file=sys.stderr)
            
            print(f"INFO: Found seed paper: {seed_title[:50]}... (ID: {paper_id}, score={best_score})", file=sys.stderr)
            
            self._apply_delay()
            
            paper_detail_url = self.SEMANTIC_SCHOLAR_PAPER_API.format(paper_id=paper_id)
            paper_detail_params = {
                'fields': 'title,authors,year,abstract,citationCount,url,venue,publicationDate,externalIds,journal'
            }
            
            seed_paper_detail = None
            try:
                detail_response = requests.get(
                    paper_detail_url,
                    params=paper_detail_params,
                    headers=self._get_headers(),
                    timeout=30
                )
                if detail_response.status_code == 200:
                    seed_paper_detail = detail_response.json()
            except Exception as e:
                print(f"WARNING: Failed to get seed paper details: {e}", file=sys.stderr)
            
            if seed_paper_detail:
                seed_authors = seed_paper_detail.get('authors', [])
                seed_author_names = [a.get('name', '') for a in seed_authors]
                seed_abstract = seed_paper_detail.get('abstract', '') or ''
                if seed_abstract:
                    seed_abstract = ' '.join(seed_abstract.split())[:500]
                
                seed_external_ids = seed_paper_detail.get('externalIds', {}) or {}
                seed_journal = seed_paper_detail.get('journal', {}) or {}
                
                seed_paper_info = {
                    'title': seed_paper_detail.get('title', seed_title),
                    'authors': seed_author_names,
                    'year': seed_paper_detail.get('year', 0) if seed_paper_detail.get('year') else 0,
                    'abstract': seed_abstract,
                    'citations': seed_paper_detail.get('citationCount', 0) or 0,
                    'url': seed_paper_detail.get('url', ''),
                    'venue': seed_paper_detail.get('venue', '') or '',
                    'doi': seed_external_ids.get('DOI', '') or '',
                    'volume': seed_journal.get('volume', '') or '',
                    'issue': seed_journal.get('issue', '') or '',
                    'pages': seed_journal.get('pages', '') or '',
                    'source': 'Semantic Scholar (SEED_SOURCE)',
                    'seed_paper': seed_info,
                    'filter_applied': filter_info,
                    'sort_method': sort_info or 'default',
                    'is_seed_source': True
                }
                papers.append(seed_paper_info)
                print(f"INFO: Added seed paper itself to results: {seed_title[:40]}...", file=sys.stderr)
            
            self._apply_delay()
            
            citations_url = self.SEMANTIC_SCHOLAR_CITATIONS_API.format(paper_id=paper_id)
            citations_params = {
                'limit': max_results * 2,
                'fields': 'title,authors,year,abstract,citationCount,url,venue,publicationDate,externalIds,journal'
            }
            
            response = requests.get(
                citations_url, 
                params=citations_params, 
                headers=self._get_headers(), 
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"WARNING: Failed to get citations (status {response.status_code})", file=sys.stderr)
                return papers
            
            citations_data = response.json()
            raw_citations_count = len(citations_data.get('data', []))
            print(f"INFO: Citations API returned {raw_citations_count} raw citations for paper {paper_id}", file=sys.stderr)
            
            filter_conditions = self.parse_filter(filter_info)
            
            for item in citations_data.get('data', []):
                citing_paper = item.get('citingPaper', {})
                
                authors = citing_paper.get('authors', [])
                author_names = [a.get('name', '') for a in authors]
                
                external_ids = citing_paper.get('externalIds', {}) or {}
                journal_info = citing_paper.get('journal', {}) or {}
                
                paper_info = {
                    'title': citing_paper.get('title', ''),
                    'authors': author_names,
                    'year': citing_paper.get('year', 0) if citing_paper.get('year') else 0,
                    'abstract': citing_paper.get('abstract', '') or '',
                    'citations': citing_paper.get('citationCount', 0) or 0,
                    'url': citing_paper.get('url', ''),
                    'venue': citing_paper.get('venue', '') or '',
                    'doi': external_ids.get('DOI', '') or '',
                    'volume': journal_info.get('volume', '') or '',
                    'issue': journal_info.get('issue', '') or '',
                    'pages': journal_info.get('pages', '') or '',
                    'source': 'Semantic Scholar (SEED)',
                    'seed_paper': seed_info,
                    'filter_applied': filter_info,
                    'sort_method': sort_info or 'default'
                }
                
                if paper_info['abstract']:
                    paper_info['abstract'] = ' '.join(paper_info['abstract'].split())[:500]
                
                if filter_conditions.matches(paper_info):
                    papers.append(paper_info)
            
            if papers and filter_conditions.keywords:
                scorer = BM25Scorer()
                papers = scorer.compute_scores(papers, filter_conditions.keywords)
                
                seed_papers = [p for p in papers if p.get('is_seed_source')]
                other_papers = [p for p in papers if not p.get('is_seed_source')]
                
                if sort_info == 'recency':
                    other_papers.sort(key=lambda x: (-x.get('year', 0), -x.get('bm25_score', 0)))
                else:
                    other_papers.sort(key=lambda x: (-x.get('bm25_score', 0), -x.get('citations', 0)))
                
                other_papers = other_papers[:max_results - len(seed_papers)]
                papers = seed_papers + other_papers
            else:
                seed_papers = [p for p in papers if p.get('is_seed_source')]
                other_papers = [p for p in papers if not p.get('is_seed_source')]
                other_papers = other_papers[:max_results - len(seed_papers)]
                papers = seed_papers + other_papers
            
            seed_count = len([p for p in papers if p.get('is_seed_source')])
            citing_count = len(papers) - seed_count
            print(f"INFO: SEED search found {seed_count} seed paper(s) + {citing_count} citing papers for '{seed_info[:30]}...' (BM25 scored)", file=sys.stderr)
            
        except Exception as e:
            print(f"WARNING: SEED search failed: {e}", file=sys.stderr)
        
        return papers
    
    def search_semantic_scholar(self, query: str, max_results: int = 10, 
                                    sort_by: str = None, exact_title: bool = False) -> List[Dict]:
        papers = []
        
        if not REQUESTS_AVAILABLE:
            print("WARNING: requests library not available for Semantic Scholar", file=sys.stderr)
            return papers
        
        try:
            self._apply_delay()
            
            search_query = query
            if exact_title:
                search_query = f'title:"{query}"'
            
            params = {
                'query': search_query,
                'limit': min(max_results * 2, 50),
                'fields': 'title,authors,year,abstract,citationCount,url,venue,publicationDate,externalIds,journal'
            }
            
            if sort_by:
                params['sort'] = sort_by
            
            response = requests.get(
                self.SEMANTIC_SCHOLAR_API, 
                params=params, 
                headers=self._get_headers(), 
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for item in data.get('data', []):
                    authors = item.get('authors', [])
                    author_names = [a.get('name', '') for a in authors]
                    
                    external_ids = item.get('externalIds', {}) or {}
                    journal_info = item.get('journal', {}) or {}
                    
                    paper_info = {
                        'title': item.get('title', ''),
                        'authors': author_names,
                        'year': item.get('year', 0) if item.get('year') else 0,
                        'abstract': item.get('abstract', '') or '',
                        'citations': item.get('citationCount', 0) or 0,
                        'url': item.get('url', ''),
                        'venue': item.get('venue', '') or '',
                        'doi': external_ids.get('DOI', '') or '',
                        'volume': journal_info.get('volume', '') or '',
                        'issue': journal_info.get('issue', '') or '',
                        'pages': journal_info.get('pages', '') or '',
                        'source': 'Semantic Scholar',
                        'seed_paper': '',
                        'filter_applied': ''
                    }
                    
                    if paper_info['abstract']:
                        paper_info['abstract'] = ' '.join(paper_info['abstract'].split())[:500]
                    
                    papers.append(paper_info)
                
                print(f"INFO: Semantic Scholar found {len(papers)} papers for query: {query[:50]}...", file=sys.stderr)
            else:
                print(f"WARNING: Semantic Scholar API returned status {response.status_code}", file=sys.stderr)
                
        except Exception as e:
            print(f"WARNING: Semantic Scholar search failed: {e}", file=sys.stderr)
        
        return papers
    
    def search_google_scholar(self, query: str, max_results: int = 10) -> List[Dict]:
        if not SCHOLARLY_AVAILABLE:
            print("WARNING: scholarly library not available for Google Scholar", file=sys.stderr)
            return []
        
        papers = []
        
        try:
            gs_delay = random.uniform(5, 10)
            time.sleep(gs_delay)
            
            search_query = scholarly.search_pubs(query)
            
            for i in range(max_results):
                try:
                    paper = next(search_query)
                    
                    paper_info = {
                        'title': paper.get('bib', {}).get('title', ''),
                        'authors': paper.get('bib', {}).get('author', []),
                        'year': int(paper.get('bib', {}).get('pub_year', 0)) if paper.get('bib', {}).get('pub_year', '').isdigit() else 0,
                        'abstract': paper.get('bib', {}).get('abstract', ''),
                        'citations': paper.get('num_citations', 0),
                        'url': paper.get('pub_url', ''),
                        'venue': paper.get('bib', {}).get('venue', ''),
                        'doi': '',
                        'volume': '',
                        'issue': '',
                        'pages': '',
                        'source': 'Google Scholar',
                        'seed_paper': '',
                        'filter_applied': ''
                    }
                    
                    if paper_info['abstract']:
                        paper_info['abstract'] = ' '.join(paper_info['abstract'].split())[:500]
                    
                    papers.append(paper_info)
                    
                    if i < max_results - 1:
                        time.sleep(random.uniform(2, 4))
                    
                except StopIteration:
                    break
                except Exception as e:
                    print(f"WARNING: Error fetching paper {i+1}: {e}", file=sys.stderr)
            
            print(f"INFO: Google Scholar found {len(papers)} papers for query: {query[:50]}...", file=sys.stderr)
            
        except Exception as e:
            print(f"WARNING: Google Scholar search failed: {e}", file=sys.stderr)
        
        return papers
    
    def search_with_fallback(self, query: str, max_results: int = 10, no_fallback: bool = False,
                             sort_by: str = None, exact_title: bool = False) -> List[Dict]:
        papers = self.search_semantic_scholar(query, max_results, sort_by, exact_title)
        
        if not no_fallback and len(papers) < max_results // 2 and SCHOLARLY_AVAILABLE:
            print(f"INFO: Falling back to Google Scholar for query: {query[:50]}...", file=sys.stderr)
            gs_papers = self.search_google_scholar(query, max_results - len(papers))
            
            seen_titles = {p.get('title', '').lower() for p in papers}
            for p in gs_papers:
                if p.get('title', '').lower() not in seen_titles:
                    papers.append(p)
                    seen_titles.add(p.get('title', '').lower())
        
        return papers
    
    def execute_directive(self, directive: SearchDirective, max_results: int = 10, 
                          no_fallback: bool = False, google_only: bool = False,
                          sort_by: str = None, exact_title: bool = False) -> List[Dict]:
        effective_sort = map_sort_value(directive.sort_info) or sort_by
        
        if directive.directive_type == 'SEED':
            return self.search_by_seed(
                directive.seed_info, 
                directive.filter_info, 
                max_results,
                directive.sort_info
            )
        else:
            if google_only:
                return self.search_google_scholar(directive.raw_query, max_results)
            else:
                return self.search_with_fallback(directive.raw_query, max_results, no_fallback, 
                                                  effective_sort, exact_title)
    
    def filter_and_rank_papers(self, papers: List[Dict], query_group: str,
                               current_year: int = None,
                               min_citations_old: int = 10) -> List[Dict]:
        if current_year is None:
            current_year = datetime.now().year
        
        recent_year_threshold = current_year - 1
        filtered_papers = []
        
        for paper in papers:
            year = paper.get('year', 0)
            citations = paper.get('citations', 0)
            is_seed_source = paper.get('is_seed_source', False)
            
            keep_paper = False
            
            if is_seed_source:
                keep_paper = True
            elif year >= recent_year_threshold:
                keep_paper = True
            elif year > 0 and citations > min_citations_old:
                keep_paper = True
            elif year == 0 and citations > min_citations_old:
                keep_paper = True
            
            if keep_paper:
                paper['query_group'] = query_group
                
                bm25_score = paper.get('bm25_score', 0)
                year_score = max(0, (year - 2000) / 20)
                citation_score = min(citations / 1000, 5)
                
                if bm25_score > 0:
                    paper['relevance_score'] = bm25_score + citation_score * 0.3 + year_score * 0.2
                else:
                    paper['relevance_score'] = citation_score + year_score * 0.5
                
                filtered_papers.append(paper)
        
        has_bm25 = any(p.get('bm25_score', 0) > 0 for p in filtered_papers)
        if has_bm25:
            filtered_papers.sort(key=lambda x: (-x.get('bm25_score', 0), -x.get('relevance_score', 0)))
        else:
            filtered_papers.sort(key=lambda x: (-x.get('citations', 0), -x.get('year', 0)))
        
        print(f"INFO: Filtered to {len(filtered_papers)} papers for '{query_group[:40]}...'", file=sys.stderr)
        
        return filtered_papers
    
    def generate_csv(self, all_papers: List[Dict], output_path: Path):
        if not all_papers:
            print("WARNING: No papers to export to CSV", file=sys.stderr)
            return None
        
        data = []
        for paper in all_papers:
            authors = paper.get('authors', [])
            if isinstance(authors, list):
                authors_str = '; '.join(authors)
            else:
                authors_str = str(authors)
            
            abstract = paper.get('abstract', '')
            if len(abstract) > 200:
                abstract_summary = abstract[:200] + '...'
            else:
                abstract_summary = abstract
            
            data.append({
                'Query_Group': paper.get('query_group', ''),
                'Directive_Type': 'SEED' if paper.get('seed_paper') else 'QUERY',
                'Seed_Paper': paper.get('seed_paper', ''),
                'Filter_Applied': paper.get('filter_applied', ''),
                'Sort_Method': paper.get('sort_method', ''),
                'Title': paper.get('title', ''),
                'Authors': authors_str,
                'Year': paper.get('year', ''),
                'Citations': paper.get('citations', 0),
                'BM25_Score': round(paper.get('bm25_score', 0), 2),
                'Abstract_Summary': abstract_summary,
                'Link': paper.get('url', ''),
                'Venue': paper.get('venue', ''),
                'DOI': paper.get('doi', ''),
                'Volume': paper.get('volume', ''),
                'Issue': paper.get('issue', ''),
                'Pages': paper.get('pages', ''),
                'Citation_GB': format_citation_gbt7714(paper),
                'Source': paper.get('source', ''),
                'Relevance_Score': round(paper.get('relevance_score', 0), 2)
            })
        
        df = pd.DataFrame(data)
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"INFO: Saved {len(df)} papers to {output_path}", file=sys.stderr)
            return output_path
        except Exception as e:
            print(f"ERROR: Failed to save CSV: {e}", file=sys.stderr)
            return None
    
    def generate_report(self, all_papers: List[Dict], output_path: Path):
        if not all_papers:
            print("WARNING: No papers to generate report", file=sys.stderr)
            return None
        
        top_papers = sorted(all_papers, key=lambda x: (-x.get('relevance_score', 0), -x.get('citations', 0)))[:3]
        
        seed_count = sum(1 for p in all_papers if p.get('seed_paper'))
        query_count = len(all_papers) - seed_count
        
        report_lines = [
            "# Academic Literature Crawler Report",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total papers collected: {len(all_papers)}",
            f"- SEED search results: {seed_count}",
            f"- QUERY search results: {query_count}",
            "",
            "## Top 3 Must-Read Papers",
            ""
        ]
        
        for i, paper in enumerate(top_papers, 1):
            authors = paper.get('authors', [])
            if isinstance(authors, list):
                authors_str = ', '.join(authors[:3]) + (' et al.' if len(authors) > 3 else '')
            else:
                authors_str = str(authors)
            
            directive_type = 'SEED' if paper.get('seed_paper') else 'QUERY'
            
            report_lines.extend([
                f"### {i}. {paper.get('title', 'Untitled')}",
                f"- **Type**: {directive_type}",
                f"- **Authors**: {authors_str}",
                f"- **Year**: {paper.get('year', 'Unknown')}",
                f"- **Citations**: {paper.get('citations', 0)}",
                f"- **BM25 Score**: {paper.get('bm25_score', 0):.2f}",
                f"- **Venue**: {paper.get('venue', 'Unknown')}",
                f"- **Source**: {paper.get('source', 'Unknown')}",
                f"- **Relevance Score**: {paper.get('relevance_score', 0):.2f}",
                f"- **Link**: {paper.get('url', '')}",
                "",
                f"**Abstract Summary**:",
                f"{paper.get('abstract', 'No abstract available.')[:300]}...",
                ""
            ])
        
        query_groups = {}
        for paper in all_papers:
            group = paper.get('query_group', 'Unknown')
            query_groups[group] = query_groups.get(group, 0) + 1
        
        report_lines.extend([
            "## Query Group Statistics",
            ""
        ])
        
        for group, count in query_groups.items():
            report_lines.append(f"- **{group}**: {count} papers")
        
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            print(f"INFO: Saved report to {output_path}", file=sys.stderr)
            return output_path
        except Exception as e:
            print(f"ERROR: Failed to save report: {e}", file=sys.stderr)
            return None


def main():
    parser = argparse.ArgumentParser(description="Academic Literature Crawler - Supports SEED and QUERY directives")
    parser.add_argument("--input", "-i", type=str, 
                       help="Path to search plan .md file to extract directives from")
    parser.add_argument("--queries", "-q", nargs="+", type=str,
                       help="Direct list of search queries (treated as QUERY type)")
    parser.add_argument("--max-results", "-m", type=int, default=20,
                       help="Maximum results per query (default: 20, increased to capture more papers)")
    parser.add_argument("--output-dir", "-o", type=str, default="./",
                       help="Output directory (default: current directory)")
    parser.add_argument("--delay-min", type=float, default=1.1,
                       help="Minimum delay between requests in seconds (default: 1.1, matches 1 RPS limit)")
    parser.add_argument("--delay-max", type=float, default=1.1,
                       help="Maximum delay between requests in seconds (default: 1.1, matches 1 RPS limit)")
    parser.add_argument("--test-mode", action="store_true",
                       help="Test mode - don't actually search, just parse directives")
    parser.add_argument("--google-only", action="store_true",
                       help="Use Google Scholar only (not recommended)")
    parser.add_argument("--no-fallback", action="store_true",
                       help="Only use Semantic Scholar, disable Google Scholar fallback")
    parser.add_argument("--api-key", type=str, default="",
                       help="Semantic Scholar API key for higher rate limits")
    parser.add_argument("--sort-by", type=str, default=None,
                       choices=["relevance", "citationCount:desc", "citationCount:asc", "year:desc", "year:asc"],
                       help="Sort results by: relevance (default), citationCount:desc, year:desc, etc.")
    parser.add_argument("--exact-title", action="store_true",
                       help="Search for exact title match (useful for finding specific papers)")
    
    args = parser.parse_args()
    
    if not PANDAS_AVAILABLE:
        print("ERROR: pandas library is required. Install with: pip install pandas", file=sys.stderr)
        sys.exit(1)
    
    if not REQUESTS_AVAILABLE:
        print("ERROR: requests library is required. Install with: pip install requests", file=sys.stderr)
        sys.exit(1)
    
    directives = []
    query_source = ""
    
    if args.queries:
        for i, q in enumerate(args.queries, 1):
            directives.append(SearchDirective(
                directive_type='QUERY',
                raw_query=q,
                line_number=i
            ))
        query_source = "command line"
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        
        crawler = ScholarCrawler(delay_range=(args.delay_min, args.delay_max), api_key=args.api_key)
        directives = crawler.extract_directives_from_md(input_path)
        query_source = input_path.name
        
        if not directives:
            print("ERROR: No directives found in input file", file=sys.stderr)
            sys.exit(1)
    else:
        print("ERROR: Must provide either --input or --queries", file=sys.stderr)
        parser.print_help()
        sys.exit(1)
    
    print(f"INFO: Processing {len(directives)} directives from {query_source}", file=sys.stderr)
    
    if args.test_mode:
        print("\n" + "="*60)
        print("TEST MODE: Directives to be processed:")
        print("="*60)
        for d in directives:
            print(f"  {d.line_number}. {d}")
        print(f"\nTotal: {len(directives)} directives")
        print(f"Papers per directive: {args.max_results}")
        print(f"Expected total papers: {len(directives) * args.max_results}")
        return
    
    crawler = ScholarCrawler(delay_range=(args.delay_min, args.delay_max), api_key=args.api_key)
    
    all_papers = []
    
    for i, directive in enumerate(directives, 1):
        print(f"\nDirective {i}/{len(directives)}: {directive}", file=sys.stderr)
        
        if directive.directive_type == 'SEED':
            query_group = f"SEED_{i}: {directive.seed_info[:30]}..."
        else:
            query_group = f"QUERY_{i}: {directive.raw_query[:30]}..."
        
        papers = crawler.execute_directive(
            directive, 
            args.max_results,
            no_fallback=args.no_fallback,
            google_only=args.google_only,
            sort_by=args.sort_by,
            exact_title=args.exact_title
        )
        
        for p in papers:
            p['query_group'] = query_group
            p['sort_method'] = directive.sort_info or 'default'
        
        filtered_papers = crawler.filter_and_rank_papers(papers, query_group)
        all_papers.extend(filtered_papers)
    
    print(f"\nINFO: Total papers collected: {len(all_papers)}", file=sys.stderr)
    
    output_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    csv_path = output_dir / f"literature_review_{timestamp}.csv"
    report_path = output_dir / f"crawler_report_{timestamp}.md"
    
    csv_file = crawler.generate_csv(all_papers, csv_path)
    report_file = crawler.generate_report(all_papers, report_path)
    
    seed_count = sum(1 for p in all_papers if p.get('seed_paper'))
    query_count = len(all_papers) - seed_count
    
    print("\n" + "="*60, file=sys.stderr)
    print("CRAWLER SUMMARY", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print(f"Directives processed: {len(directives)}", file=sys.stderr)
    print(f"Total papers collected: {len(all_papers)}", file=sys.stderr)
    print(f"  - SEED search results: {seed_count}", file=sys.stderr)
    print(f"  - QUERY search results: {query_count}", file=sys.stderr)
    if csv_file:
        print(f"CSV output: {csv_file}", file=sys.stderr)
    if report_file:
        print(f"Report output: {report_file}", file=sys.stderr)
    print("="*60, file=sys.stderr)


if __name__ == "__main__":
    main()
