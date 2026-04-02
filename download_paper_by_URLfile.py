# -*- coding: utf-8 -*-
# @Time    : 2021/10/12 22:49 
# @Author  : Yong Cao
# @Email   : yongcao_epic@hust.edu.cn
import os
import re
import json
import time

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
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if not lines:
        return None
    title_match = re.search(r'"(.*?)"', lines[0])
    if not title_match:
        return None
    doi_match = re.search(r"\bdoi:\s*([^\s,]+)", block, flags=re.IGNORECASE)
    query_text = doi_match.group(1).rstrip(".,;") if doi_match else title_match.group(1)
    record = _search_record(session, query_text)
    if not record:
        title_only = title_match.group(1)
        if query_text != title_only:
            record = _search_record(session, title_only)
        if not record:
            return None
    year = record.get("publicationYear") or _extract_year(block)
    arnumber = record.get("articleNumber")
    if not arnumber:
        return None
    return _build_paper_item(
        dst_dir,
        record.get("articleTitle") or title_match.group(1),
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
    paper_info = {}
    session = None
    total = len(lines)
    log_message("开始解析引文文件: {}".format(url_file))
    reset_progress(total=total, status="正在解析文件...")
    for index, line in enumerate(tqdm(lines, disable=True), start=1):
        paper_item = _parse_legacy_block(dst_dir, line, paper_name_with_year=paper_name_with_year)
        if paper_item is None:
            if session is None:
                try:
                    session = _build_ieee_search_session()
                except requests.RequestException:
                    finish_progress("解析失败: 无法连接 IEEE Xplore")
                    return False, paper_info
            paper_item = _parse_citation_block(dst_dir, line, session, paper_name_with_year=paper_name_with_year)
        if paper_item is not None:
            paper_info[len(paper_info)] = paper_item
            status = "解析进度:{}/{} 已识别:{}篇".format(index, total, len(paper_info))
        else:
            status = "解析进度:{}/{} 未匹配到论文".format(index, total)
        update_progress(index, total, status)
        log_message(status)
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
