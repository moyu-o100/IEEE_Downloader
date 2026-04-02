# -*- coding: utf-8 -*-
# @Time    : 2021/10/12 22:49 
# @Author  : Yong Cao
# @Email   : yongcao_epic@hust.edu.cn
import os
import re
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm

from utils import clean_input_path, downLoad_paper, finish_progress, log_message, reset_progress, update_progress


SEARCH_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://ieeexplore.ieee.org",
    "Referer": "https://ieeexplore.ieee.org/",
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

LOOKUP_CACHE_DIR = ".cache"
LOOKUP_CACHE_FILE = "ieee_lookup_cache.json"
LOOKUP_MAX_WORKERS = 6

_search_session_local = threading.local()


def _read_txt_file(url_file):
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            with open(url_file, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(url_file, "r") as f:
        return f.read()


def _sanitize_title(title):
    rstr = r"[\=\(\)\,\/\\\:\*\?\？\"\<\>\|\'']"
    return re.sub(rstr, '', title).strip()


def _normalize_title(title):
    return re.sub(r"\s+", " ", title).strip().lower()


def _extract_year(text):
    match = re.search(r"\b(19|20)\d{2}\b", text)
    if match:
        return match.group(0)
    return None


def _build_ieee_search_session():
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    response = session.get("https://ieeexplore.ieee.org", timeout=10)
    response.raise_for_status()
    return session


def _get_thread_search_session():
    session = getattr(_search_session_local, "session", None)
    if session is None:
        session = _build_ieee_search_session()
        _search_session_local.session = session
    return session


def _lookup_cache_path():
    return os.path.join(LOOKUP_CACHE_DIR, LOOKUP_CACHE_FILE)


def _load_lookup_cache():
    cache_path = _lookup_cache_path()
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    if isinstance(cache, dict):
        return cache
    return {}


def _save_lookup_cache(cache):
    cache_path = _lookup_cache_path()
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2, sort_keys=True)
    except OSError:
        return


def _cache_key_for_doi(doi):
    return "doi:" + doi.lower()


def _cache_key_for_title(title):
    return "title:" + _normalize_title(title)


def _get_cached_record(cache, doi=None, title=None):
    if doi:
        record = cache.get(_cache_key_for_doi(doi))
        if record:
            return record
    if title:
        record = cache.get(_cache_key_for_title(title))
        if record:
            return record
    return None


def _store_cached_record(cache, record, doi=None, title=None):
    cached_record = {
        "articleNumber": record.get("articleNumber"),
        "articleTitle": record.get("articleTitle"),
        "publicationYear": record.get("publicationYear"),
    }
    if not cached_record["articleNumber"]:
        return
    if doi:
        cache[_cache_key_for_doi(doi)] = cached_record
    if title:
        cache[_cache_key_for_title(title)] = cached_record


def _search_record(session, query_text, retries=3):
    payload = {
        "queryText": query_text,
        "pageNumber": "1",
        "rowsPerPage": 3,
        "returnFacets": ["ALL"],
        "returnType": "SEARCH",
    }
    for attempt in range(retries):
        try:
            response = session.post(
                "https://ieeexplore.ieee.org/rest/search",
                headers=SEARCH_HEADERS,
                data=json.dumps(payload),
                timeout=20,
            )
            if response.status_code >= 500 and attempt < retries - 1:
                time.sleep(1 + attempt)
                continue
            response.raise_for_status()
            records = response.json().get("records", [])
            if records:
                return records[0]
            return None
        except requests.RequestException:
            if attempt == retries - 1:
                return None
            time.sleep(1 + attempt)
    return None


def _build_paper_item(dst_dir, title, arnumber, year=None, paper_name_with_year=None):
    papername = _sanitize_title(title)
    if not papername:
        return None
    if paper_name_with_year and year:
        papername = year + ' ' + papername
    return {
        "name": os.path.join(dst_dir, papername + ".pdf"),
        "url": "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=" + arnumber + "&ref=",
    }


def _build_citation_context(block):
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return None
    title_match = re.search(r'"(.*?)"', lines[0])
    if not title_match:
        return None
    doi_match = re.search(r"\bdoi:\s*([^\s,]+)", block, flags=re.IGNORECASE)
    return {
        "title": title_match.group(1),
        "doi": doi_match.group(1).rstrip(".,;") if doi_match else None,
        "year": _extract_year(block),
    }


def _parse_legacy_block(dst_dir, block, paper_name_with_year=None):
    content = [line.strip() for line in block.splitlines() if line.strip()]
    if not content:
        return None
    title_match = re.search(r'"(.*?)"', content[0])
    url_line = next((line for line in content if "URL" in line and "arnumber=" in line), None)
    if not title_match or not url_line:
        return None
    arnumber_match = re.search(r"arnumber=(\d+)", url_line)
    if not arnumber_match:
        return None
    year = _extract_year(block)
    return _build_paper_item(
        dst_dir,
        title_match.group(1),
        arnumber_match.group(1),
        year=year,
        paper_name_with_year=paper_name_with_year,
    )


def _parse_citation_block(dst_dir, block, session, paper_name_with_year=None):
    context = _build_citation_context(block)
    if context is None:
        return None
    record = _resolve_citation_record(context, session)
    if not record:
        return None
    return _build_paper_item_from_record(dst_dir, context, record, paper_name_with_year)


def _resolve_citation_record(context, session=None):
    if session is None:
        session = _get_thread_search_session()
    query_text = context["doi"] or context["title"]
    record = _search_record(session, query_text)
    if not record and context["doi"]:
        record = _search_record(session, context["title"])
    return record


def _build_paper_item_from_record(dst_dir, context, record, paper_name_with_year=None):
    arnumber = record.get("articleNumber")
    if not arnumber:
        return None
    year = record.get("publicationYear") or context.get("year")
    title = record.get("articleTitle") or context["title"]
    return _build_paper_item(
        dst_dir,
        title,
        arnumber,
        year=year,
        paper_name_with_year=paper_name_with_year,
    )


def organize_info_by_txt(dst_dir, url_file, paper_name_with_year=None):
    dst_dir = clean_input_path(dst_dir)
    url_file = clean_input_path(url_file)
    if not os.path.exists(url_file):
        return False, None
    lines = [block.strip() for block in re.split(r"\r?\n\r?\n+", _read_txt_file(url_file)) if block.strip()]
    total = len(lines)
    resolved_items = {}
    cache = _load_lookup_cache()
    lookup_tasks = []
    completed = 0
    recognized = 0
    log_message("开始解析引文文件: {}".format(url_file))
    reset_progress(total=total, status="正在解析文件...")
    for index, line in enumerate(tqdm(lines, disable=True), start=1):
        paper_item = _parse_legacy_block(dst_dir, line, paper_name_with_year=paper_name_with_year)
        if paper_item is not None:
            resolved_items[index] = paper_item
            completed += 1
            recognized += 1
            status = "解析进度:{}/{} 已识别:{}篇 (URL直读)".format(completed, total, recognized)
            update_progress(completed, total, status)
            log_message(status)
            continue

        context = _build_citation_context(line)
        if context is None:
            completed += 1
            status = "解析进度:{}/{} 已识别:{}篇 (未匹配到论文)".format(completed, total, recognized)
            update_progress(completed, total, status)
            log_message(status)
            continue

        cached_record = _get_cached_record(cache, doi=context["doi"], title=context["title"])
        if cached_record:
            paper_item = _build_paper_item_from_record(dst_dir, context, cached_record, paper_name_with_year)
            if paper_item is not None:
                resolved_items[index] = paper_item
                recognized += 1
            completed += 1
            status = "解析进度:{}/{} 已识别:{}篇 (缓存命中)".format(completed, total, recognized)
            update_progress(completed, total, status)
            log_message(status)
            continue

        lookup_tasks.append((index, context))

    if lookup_tasks:
        log_message("未命中缓存，开始并发查询 IEEE Xplore: {} 篇".format(len(lookup_tasks)))
        max_workers = min(LOOKUP_MAX_WORKERS, len(lookup_tasks))
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = {
                    executor.submit(_resolve_citation_record, context): (index, context)
                    for index, context in lookup_tasks
                }
                for future in as_completed(future_to_task):
                    index, context = future_to_task[future]
                    record = None
                    try:
                        record = future.result()
                    except requests.RequestException:
                        record = None
                    if record:
                        _store_cached_record(cache, record, doi=context["doi"], title=context["title"])
                        paper_item = _build_paper_item_from_record(dst_dir, context, record, paper_name_with_year)
                        if paper_item is not None:
                            resolved_items[index] = paper_item
                            recognized += 1
                            result_note = "在线解析"
                        else:
                            result_note = "解析失败"
                    else:
                        result_note = "未匹配到论文"
                    completed += 1
                    status = "解析进度:{}/{} 已识别:{}篇 ({})".format(completed, total, recognized, result_note)
                    update_progress(completed, total, status)
                    log_message(status)
        except requests.RequestException:
            finish_progress("解析失败: 无法连接 IEEE Xplore")
            return False, None

    paper_info = {}
    for index in sorted(resolved_items.keys()):
        paper_item = resolved_items[index]
        if paper_item is not None:
            paper_info[len(paper_info)] = paper_item
    _save_lookup_cache(cache)
    finish_progress("解析完成，共识别{}篇论文".format(len(paper_info)))
    return len(paper_info) > 0, paper_info


if __name__ == '__main__':
    # 配置存储文件夹
    dst_dir = "./save"
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)
    # 封装下载url和论文名称
    url_txt = "url.txt"
    paper_info = organize_info_by_txt(dst_dir, url_txt, True)
    # 下载论文
    downLoad_paper(paper_info)
