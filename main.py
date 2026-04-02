# -*- coding: utf-8 -*-
# @Time    : 2021/10/13 12:34 
# @Author  : Yong Cao
# @Email   : yongcao_epic@hust.edu.cn
import os
from download_paper_by_URLfile import organize_info_by_txt
from download_paper_by_pageURL import organize_info_by_query
from utils import downLoad_paper


if __name__ == '__main__':
    ############### 配置1 ##################
    mode = "search"  # "txt" or "search"
    dst_dir = "./save"
    ############### END ##################
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)

    if mode == "txt":
        ############### 配置2 ##################
        url_txt = "url.txt"  # txt mode is needed.
        ############### END ##################
        # 封装下载url和论文名称
        status, paper_info = organize_info_by_txt(dst_dir, url_txt)
        if not status:
            raise SystemExit("URL txt file not found.")
        # 下载论文
        downLoad_paper(paper_info)
    else:
        ############### 配置3 ##################
        queryText = "dialog system"
        pageNumber = [3]
        save_papername_with_year = True
        ############### END ##################
        status, paper_info = organize_info_by_query(queryText, pageNumber, dst_dir, save_papername_with_year)
        if not status:
            raise SystemExit("Failed to fetch paper list from IEEE Xplore.")
        downLoad_paper(paper_info, show_bar=True)
