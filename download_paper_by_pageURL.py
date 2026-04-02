# -*- coding: utf-8 -*-
# @Time    : 2021/10/13 10:37 
# @Author  : Yong Cao
# @Email   : yongcao_epic@hust.edu.cn
import json
import os
import re

import requests

from utils import downLoad_paper


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

SEARCH_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://ieeexplore.ieee.org",
    "Referer": "https://ieeexplore.ieee.org/",
}


def _build_ieee_session():
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    response = session.get("https://ieeexplore.ieee.org", timeout=10)
    response.raise_for_status()
    return session


def organize_info_by_query(queryText, pageNumber, save_dir, paper_name_with_year=None):
    paper_info = {}
    count = 0
    try:
        session = _build_ieee_session()
        for page in pageNumber:
            payload = {
                "queryText": queryText,
                "pageNumber": str(page),
                "returnFacets": ["ALL"],
                "returnType": "SEARCH",
            }
            toc_res = session.post(
                "https://ieeexplore.ieee.org/rest/search",
                headers=SEARCH_HEADERS,
                data=json.dumps(payload),
                timeout=20,
            )
            toc_res.raise_for_status()
            response = toc_res.json()
            if 'records' in response:
                for item in response['records']:
                    paper_info[count] = {}
                    paper_info[count]['url'] = "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=" + item['articleNumber'] + "&ref="
                    paper_info[count]['name'] = item['articleTitle']
                    rstr = r"[\=\(\)\,\/\\\:\*\?\？\"\<\>\|\'']"
                    if paper_name_with_year:
                        paper_info[count]['name'] = os.path.join(save_dir, item['publicationYear'] + ' ' + re.sub(rstr, '', paper_info[count]['name']) + '.pdf')
                    else:
                        paper_info[count]['name'] = os.path.join(save_dir, re.sub(rstr, '', paper_info[count]['name']) + '.pdf')
                    count += 1
    except requests.RequestException:
        return False, paper_info
    if len(paper_info) > 0:
        return True, paper_info
    else:
        return False, paper_info


if __name__ == '__main__':
    import utils
    utils._init()
    queryText = "dialog system"
    pageNumber = [3]
    save_dir = "save"
    _, paper_info = organize_info_by_query(queryText, pageNumber, save_dir, True)
    downLoad_paper(paper_info)
