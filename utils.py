# -*- coding: utf-8 -*-
# @Time    : 2021/10/13 12:16 
# @Author  : Yong Cao
# @Email   : yongcao_epic@hust.edu.cn
import os
import time

import requests

_global_dict = {}
_log_callback = None

PATH_CONTROL_CHARS = "\u202a\u202b\u202c\u202d\u202e\u200e\u200f\ufeff"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DOWNLOAD_RETRY_COUNT = 3
SESSION_REFRESH_INTERVAL = 20


def _init():
    # 初始化一个全局的字典
    global _global_dict
    _global_dict = {
        "progress_bar_num": 0,
        "progress_bar_max": 0,
        "progress_bar_status": "",
        "progress_bar_done": False,
    }


def set_value(key, value):
    _global_dict[key] = value


def get_value(key):
    try:
        return _global_dict[key]
    except KeyError as e:
        print(e)


def set_logger(callback):
    global _log_callback
    _log_callback = callback


def log_message(message=""):
    text = str(message)
    print(text, flush=True)
    if _log_callback:
        _log_callback(text)


def log_named_list(title, names):
    if not names:
        return
    log_message(title)
    for index, name in enumerate(names, start=1):
        log_message("  {}. {}".format(index, name))


def reset_progress(total=0, status=""):
    set_value("progress_bar_num", 0)
    set_value("progress_bar_max", total)
    set_value("progress_bar_status", status)
    set_value("progress_bar_done", False)


def update_progress(current=None, total=None, status=None):
    if current is not None:
        set_value("progress_bar_num", current)
    if total is not None:
        set_value("progress_bar_max", total)
    if status is not None:
        set_value("progress_bar_status", status)


def finish_progress(status=None):
    if status is not None:
        set_value("progress_bar_status", status)
    set_value("progress_bar_done", True)


def _build_download_session():
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    response = session.get("https://ieeexplore.ieee.org", timeout=10)
    response.raise_for_status()
    return session


def _is_pdf_content(content):
    return content.startswith(b"%PDF-")


def _is_valid_pdf_file(path):
    try:
        with open(path, "rb") as f:
            return _is_pdf_content(f.read(5))
    except OSError:
        return False


def is_valid_pdf_file(path):
    return _is_valid_pdf_file(path)


def clean_input_path(path):
    if path is None:
        return path
    return path.strip().strip(PATH_CONTROL_CHARS).strip().strip('"').strip("'")


def _infer_output_dir(paper_info):
    for item in paper_info.values():
        papername = item.get("name")
        if papername:
            return os.path.dirname(os.path.abspath(papername))
    return os.getcwd()


def write_download_summary(
    paper_info,
    paper_downloaded,
    already_exist,
    failed_papers,
    already_exist_papers,
    downloaded_papers=None,
    elapsed_seconds=None,
):
    output_dir = _infer_output_dir(paper_info)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    summary_path = os.path.join(output_dir, "download_summary_{}.txt".format(timestamp))
    downloaded_papers = downloaded_papers or []
    elapsed_seconds = float(elapsed_seconds or 0)

    def _section_lines(title, names):
        lines = ["{} ({})".format(title, len(names))]
        if names:
            for index, name in enumerate(names, start=1):
                lines.append("  {}. {}".format(index, name))
        else:
            lines.append("  (none)")
        lines.append("")
        return lines

    lines = [
        "IEEE Downloader Summary",
        "Generated at: {}".format(time.strftime("%Y-%m-%d %H:%M:%S")),
        "",
        "Total papers: {}".format(len(paper_info)),
        "Downloaded: {}".format(paper_downloaded),
        "Already existed: {}".format(already_exist),
        "Failed: {}".format(len(failed_papers)),
        "Elapsed seconds: {:.2f}".format(elapsed_seconds),
        "",
    ]
    lines.extend(_section_lines("Downloaded papers", downloaded_papers))
    lines.extend(_section_lines("Skipped existing papers", already_exist_papers))
    lines.extend(_section_lines("Failed papers", failed_papers))

    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError as exc:
        log_message("写入下载汇总失败: {}".format(exc))
        return None
    return summary_path



def get_window_size(win, update=True):
    """ 获得窗体的尺寸 """
    if update:
        win.update()
    return win.winfo_width(), win.winfo_height(), win.winfo_x(), win.winfo_y()


def center_window(win, width=None, height=None):
    """ 将窗口屏幕居中 """
    screenwidth = win.winfo_screenwidth()
    screenheight = win.winfo_screenheight()
    if width is None:
        width, height = get_window_size(win)[:2]
    size = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 3)
    win.geometry(size)


def downLoad_paper(paper_info, show_bar=False):
    log_message("")
    log_message("")
    log_message("执行开始".center(len(paper_info) + 28, '-'))
    succeed = True
    paper_downloaded = 0
    already_exist = 0
    downloaded_papers = []
    already_exist_papers = []
    failed_papers = []
    start = time.perf_counter()
    total = len(paper_info)
    reset_progress(total=total, status="开始下载...")
    session = _build_download_session()
    try:
        for i, item in enumerate(paper_info.keys(), start=1):
            if i > 1 and (i - 1) % SESSION_REFRESH_INTERVAL == 0:
                session.close()
                session = _build_download_session()
            papername = paper_info[item]['name']
            paperurl = paper_info[item]['url']
            basename = os.path.basename(papername)
            # 文件存储
            if os.path.exists(papername):
                if _is_valid_pdf_file(papername):
                    already_exist += 1
                    already_exist_papers.append(basename)
                    update_progress(i, total, "已存在: {}".format(basename))
                    t = time.perf_counter() - start
                    log_message("下载进度:{:>3.0f}% ({}/{}) 已存在 {} 用时:{:.2f}s".format(
                        (i / total) * 100 if total else 100, i, total, basename, t
                    ))
                    continue
                os.remove(papername)
            download_ok = False
            last_error = None
            for attempt in range(1, DOWNLOAD_RETRY_COUNT + 1):
                try:
                    status = "下载中: {}".format(basename)
                    if attempt > 1:
                        status = "重试({}/{}): {}".format(attempt, DOWNLOAD_RETRY_COUNT, basename)
                        log_message(status)
                    update_progress(i - 1, total, status)
                    r = session.get(
                        paperurl,
                        headers={"Referer": "https://ieeexplore.ieee.org/"},
                        timeout=30,
                    )
                    r.raise_for_status()
                    if not _is_pdf_content(r.content):
                        raise ValueError("Downloaded file is not a PDF.")
                    with open(papername, 'wb+') as f:
                        f.write(r.content)
                        paper_downloaded += 1
                        downloaded_papers.append(basename)
                    # 停一下防禁ip
                    time.sleep(1)
                    update_progress(i, total, "已下载: {}".format(basename))
                    download_ok = True
                    break
                except Exception as e:
                    last_error = e
                    if os.path.exists(papername) and not _is_valid_pdf_file(papername):
                        os.remove(papername)
                    if attempt < DOWNLOAD_RETRY_COUNT:
                        update_progress(i - 1, total, "下载失败，准备重试: {}".format(basename))
                        try:
                            session.close()
                        except Exception:
                            pass
                        time.sleep(2 * attempt)
                        session = _build_download_session()
            if not download_ok:
                log_message(last_error)
                log_message("unknown name! parser error {}".format(papername))
                succeed = False
                failed_papers.append(basename)
                update_progress(i, total, "下载失败: {}".format(basename))
            c = (i / total) * 100 if total else 100
            t = time.perf_counter() - start
            state = "已下载" if download_ok else "下载失败"
            log_message("下载进度:{:>3.0f}% ({}/{}) {} {} 用时:{:.2f}s".format(c, i, total, state, basename, t))
    finally:
        try:
            session.close()
        except Exception:
            pass
    update_progress(total, total)
    if failed_papers:
        finish_progress("下载结束，失败{}篇".format(len(failed_papers)))
    else:
        finish_progress("下载完成")
    # if show_bar:
    #     del root
    log_message("执行结束".center(len(paper_info)+28,'-'))
    log_message("-"*50)
    log_message("Downloaded {} papers and {} paper already exists.".format(paper_downloaded, already_exist))
    log_named_list("已跳过的论文：", already_exist_papers)
    if failed_papers:
        log_message("Failed to download {} papers.".format(len(failed_papers)))
        log_named_list("下载失败的论文：", failed_papers)
    summary_path = write_download_summary(
        paper_info,
        paper_downloaded=paper_downloaded,
        already_exist=already_exist,
        failed_papers=failed_papers,
        already_exist_papers=already_exist_papers,
        downloaded_papers=downloaded_papers,
        elapsed_seconds=time.perf_counter() - start,
    )
    if summary_path:
        log_message("下载汇总已保存: {}".format(summary_path))
    log_message("-" * 50)
    return succeed, paper_downloaded, already_exist, failed_papers, already_exist_papers
