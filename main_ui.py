# coding:utf-8
import _thread
import os
import queue
import time
import tkinter as tk
import tkinter.font as tkFont
from tkinter import filedialog, scrolledtext, ttk

from PIL import Image, ImageTk

import utils
from download_paper_by_URLfile import organize_info_by_txt
from download_paper_by_pageURL import organize_info_by_query
from utils import downLoad_paper, center_window


RESAMPLING_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
LOG_LINE_LIMIT = 1000


def show_confirm(message=""):
    utils.log_message(message)
    return True


def error_inform(message=""):
    utils.log_message("参数错误: {}".format(message))
    return None


def show_succeed_window(message=""):
    utils.log_message(message)
    return None


def show_fail_window(message=""):
    utils.log_message("失败: {}".format(message))
    return None


def show_begin_download(message=""):
    utils.log_message("开始任务:\n{}".format(message))
    return True


def tkimg_resized(img, w_box, h_box, keep_ratio=True):
    """对图片进行按比例缩放处理"""
    w, h = img.size

    if keep_ratio:
        if w > h:
            width = w_box
            height = int(h_box * (1.0 * h / w))

        if h >= w:
            height = h_box
            width = int(w_box * (1.0 * w / h))
    else:
        width = w_box
        height = h_box

    img1 = img.resize((width, height), RESAMPLING_LANCZOS)
    tkimg = ImageTk.PhotoImage(img1)
    return tkimg


def image_label(frame, img, width, height, keep_ratio=True):
    """输入图片信息，及尺寸，返回界面组件"""
    if isinstance(img, str):
        with Image.open(img) as opened_img:
            _img = opened_img.copy()
    else:
        _img = img
    lbl_image = tk.Label(frame, width=width, height=height)

    tk_img = tkimg_resized(_img, width, height, keep_ratio)
    lbl_image.image = tk_img
    lbl_image.config(image=tk_img)
    return lbl_image


def space(n):
    s = " "
    r = ""
    for i in range(n):
        r += s
    return r


def check_value_valid(mode, save_dir=None, url_path=None, keyword=None, page=None):
    save_dir = utils.clean_input_path(save_dir)
    url_path = utils.clean_input_path(url_path)
    if mode == 1:
        if not (save_dir and url_path):
            error_inform("请检查 论文保存文件夹 URL/引文文件路径 是否已输入")
            return False
    elif mode == 2:
        if not (save_dir and keyword and page):
            error_inform("请检查 论文保存文件夹 关键词 下载页数范围 是否已输入")
            return False
    return True


def check_page_valid(page):
    page_comma = []
    try:
        if ',' in page:
            for item in page.split(","):
                if "-" in item:
                    pages = item.split("-")
                    if len(pages) != 2:
                        show_fail_window("下载页数范围输入错误")
                        return False, None
                    page_comma.extend([item for item in range(int(pages[0].strip()), int(pages[1].strip()) + 1)])
                else:
                    page_comma.append(int(item.strip()))

        elif "-" in page:
            pages = page.split("-")
            if len(pages) != 2:
                show_fail_window("下载页数范围输入错误")
                return False, None
            page_comma.extend([item for item in range(int(pages[0].strip()), int(pages[1].strip()) + 1)])
        else:
            page_comma.append(int(page.strip()))
    except Exception as e:
        show_fail_window("下载页数范围输入错误")
        return False, None
    page = sorted(list(set(page_comma)))
    for item in page:
        if item < 1:
            show_fail_window("下载页数范围输入错误")
            return False, None
    return True, page


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.geometry("%dx%d" % (960, 840))  # 窗体尺寸
        self.root.iconbitmap("img/root.ico")  # 窗体图标
        self.root.title("IEEE论文批量下载工具_v1.0")
        self.log_queue = queue.Queue()
        center_window(self.root)
        # self.root.resizable(False, False)          # 设置窗体不可改变大小
        self.no_title = False
        self.show_title()
        self.body()
        utils.set_logger(self.enqueue_log)
        self.root.after(100, self.poll_log_queue)

    def body(self):

        # ---------------------------------------------------------------------
        # 标题栏
        # ---------------------------------------------------------------------
        f1 = tk.Frame(self.root)
        im1 = image_label(f1, "img/root.ico", 86, 86, False)
        im1.configure(bg="Teal")
        im1.bind('<Button-1>', self.show_title)
        im1.pack(side=tk.LEFT, anchor=tk.NW, fill=tk.Y)

        ft1 = tkFont.Font(family="微软雅黑", size=24, weight=tkFont.BOLD)
        tk.Label(f1, text="IEEE论文批量下载工具_v1.0", height=2, fg="white", font=ft1, bg="Teal") \
            .pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)

        im2 = image_label(f1, "img/exit.ico", 86, 86, False)
        im2.configure(bg="Teal")
        im2.bind('<Button-1>', self.close)
        im2.pack(side=tk.RIGHT, anchor=tk.NW, fill=tk.Y)

        f2 = tk.Frame(self.root)
        img_content = image_label(f2, "img/ieee.png", width=400, height=142, keep_ratio=False).pack(padx=10, pady=10)
        f1.pack(fill=tk.X)
        f2.pack()

        ft_title = tkFont.Font(family="微软雅黑", size=13, weight=tkFont.BOLD)
        ft_middle = tkFont.Font(family="微软雅黑", size=11)
        ft = tkFont.Font(family="微软雅黑", size=13)
        ft_small = tkFont.Font(family="微软雅黑", size=6)

        f3 = tk.Frame(self.root)
        tk.Label(f3, text="论文保存文件夹 ", font=ft, anchor='w').pack(side='left', padx=60)
        self.save_dir = tk.Text(f3, bg="white", font=ft, height=1, width=34)
        self.save_dir.pack(side=tk.LEFT)
        tk.Button(f3, text="选择文件夹", width=10, height=1, bg="lightsteelblue", font=ft_middle,
                  command=self.browse_save_dir).pack(side=tk.LEFT, padx=10)
        f3.pack(fill='both', expand=True)

        f_empty = tk.Frame(self.root)
        tk.Label(f_empty, text="", font=ft_small).pack(side='left')
        f_empty.pack(fill='both', expand=True)

        # 模式1
        f5 = tk.Frame(self.root)
        tk.Label(f5, text="方法 1 : 使用URL/Citation txt文件", font=ft_title, anchor='w').pack(side=tk.LEFT, padx=60)
        f5.pack(fill='both', expand=True)

        f_urltxt = tk.Frame(self.root)
        tk.Label(f_urltxt, text="URL/引文文件路径", font=ft, anchor='w', padx=60).pack(side=tk.LEFT)
        self.url_txt_path = tk.Text(f_urltxt, bg="white", font=ft, height=1, width=34)
        self.url_txt_path.pack(side=tk.LEFT)
        tk.Button(f_urltxt, text="选择文件", width=10, height=1, bg="lightsteelblue", font=ft_middle,
                  command=self.browse_url_file).pack(side=tk.LEFT, padx=10)
        tk.Button(f_urltxt, text="开始下载", width=10, height=1, bg="cadetblue", font=ft, command=self.begin_download_1) \
            .pack(side=tk.LEFT, anchor=tk.W, padx=20)
        tk.Label(f_urltxt, text="", font=ft).pack(side=tk.LEFT)
        f_urltxt.pack(fill='both', expand=True)
        f9 = tk.Frame(self.root)
        self.CheckVar1 = tk.IntVar()
        self.save_with_yesr_1 = tk.Checkbutton(f9, text="论文保存时自动添加年份前缀", font=ft_middle, variable=self.CheckVar1,
                                               onvalue=1, offvalue=0)
        self.save_with_yesr_1.pack(side=tk.LEFT, padx=60)
        f9.pack(fill='both', expand=True)

        f_empty2 = tk.Frame(self.root)
        tk.Label(f_empty2, text="", font=ft_small).pack(side='left')
        f_empty2.pack(fill='both', expand=True)

        # 模式2
        f6 = tk.Frame(self.root)
        tk.Label(f6, text="方法 2 : 在线查询", font=ft_title, anchor='w').pack(side=tk.LEFT, padx=60)
        f6.pack(fill='both', expand=True)
        f7 = tk.Frame(self.root)
        tk.Label(f7, text="关键词", font=ft, anchor='w').pack(side=tk.LEFT, padx=60)
        self.keyword = tk.Text(f7, bg="white", font=ft, height=1, width=20)
        self.keyword.pack(side=tk.LEFT)
        tk.Label(f7, text="下载页数范围", font=ft, anchor='w').pack(side=tk.LEFT, padx=40)
        self.page_range = tk.Text(f7, bg="white", font=ft, height=1, width=10)
        self.page_range.pack(side=tk.LEFT, padx=0)
        tk.Button(f7, text="开始下载", width=10, height=1, bg="cadetblue", font=ft, command=self.begin_download_2) \
            .pack(side=tk.LEFT, anchor=tk.W, padx=40)
        f7.pack(fill='both', expand=True)

        f8 = tk.Frame(self.root)
        self.CheckVar2 = tk.IntVar()
        self.save_with_yesr_2 = tk.Checkbutton(f8, text="论文保存时自动添加年份前缀", font=ft_middle, variable=self.CheckVar2,
                                               onvalue=1, offvalue=0)
        self.save_with_yesr_2.pack(side=tk.LEFT, padx=60)
        f8.pack(fill='both', expand=True)

        f_log_title = tk.Frame(self.root)
        tk.Label(f_log_title, text="日志", font=ft_title, anchor='w').pack(side=tk.LEFT, padx=60)
        tk.Button(f_log_title, text="清空日志", width=10, height=1, bg="lightsteelblue", font=ft_middle,
                  command=self.clear_log).pack(side=tk.RIGHT, padx=60)
        f_log_title.pack(fill='both', expand=True, pady=(10, 0))

        f_log = tk.Frame(self.root)
        self.log_box = scrolledtext.ScrolledText(f_log, width=100, height=12, font=("Consolas", 10), state=tk.DISABLED)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=60, pady=10)
        f_log.pack(fill=tk.BOTH, expand=True)

    def show_title(self, *args):
        self.root.overrideredirect(self.no_title)
        self.no_title = not self.no_title

    def set_text_value(self, widget, value):
        widget.delete(0.0, tk.END)
        widget.insert(0.0, value)

    def browse_url_file(self):
        file_path = filedialog.askopenfilename(
            title="选择 URL/引文 txt 文件",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not file_path:
            return
        self.set_text_value(self.url_txt_path, file_path)
        self.write_log("已选择文件: {}".format(file_path))

    def browse_save_dir(self):
        directory = filedialog.askdirectory(title="选择论文保存文件夹")
        if not directory:
            return
        self.set_text_value(self.save_dir, directory)
        self.write_log("已选择保存目录: {}".format(directory))

    def clear_log(self):
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.delete(1.0, tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def enqueue_log(self, message):
        self.log_queue.put(str(message))

    def write_log(self, message):
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, str(message) + "\n")
        line_count = int(self.log_box.index("end-1c").split(".")[0])
        if line_count > LOG_LINE_LIMIT:
            excess = line_count - LOG_LINE_LIMIT
            self.log_box.delete("1.0", "{}.0".format(excess + 1))
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    def flush_log_queue(self):
        while not self.log_queue.empty():
            self.write_log(self.log_queue.get_nowait())

    def poll_log_queue(self):
        try:
            self.flush_log_queue()
            if self.root.winfo_exists():
                self.root.after(100, self.poll_log_queue)
        except tk.TclError:
            return

    def download_1_thread(self):
        save_dir = utils.clean_input_path(self.save_dir.get(0.0, tk.END).split("\n")[0].strip())
        url_txt_path = utils.clean_input_path(self.url_txt_path.get(0.0, tk.END).split("\n")[0].strip())
        save_with_year = self.CheckVar1.get()
        confirm_message = "开始下载吗？\n\n保存目录:\n{}\n\nURL/引文文件:\n{}".format(save_dir, url_txt_path)
        if show_begin_download(confirm_message):
            is_valid = check_value_valid(mode=1, save_dir=save_dir, url_path=url_txt_path)
            if not is_valid:
                return
            # 配置存储文件夹
            import os
            if not os.path.exists(save_dir):
                os.mkdir(save_dir)
            utils.log_message("=" * 60)
            utils.log_message("准备开始下载，保存目录: {}".format(save_dir))
            utils.log_message("使用 URL/引文文件: {}".format(url_txt_path))
            utils.reset_progress(status="准备解析文件...")
            status, paper_info = organize_info_by_txt(save_dir, url_txt_path, paper_name_with_year=save_with_year)
            if not status:
                utils.finish_progress("URL/引文文件解析失败")
                utils.log_message("URL/引文文件解析失败...")
                return
            if self.all_downloaded(paper_info):
                info = "{}篇论文已存在，无需下载!".format(len(paper_info))
                utils.finish_progress(info)
                utils.log_message(info)
                return
            # 下载论文
            succeed, paper_downloaded, already_exist, failed_papers = downLoad_paper(paper_info)
            if succeed:
                info = "成功下载{}篇论文！".format(paper_downloaded + already_exist)
                utils.log_message(info)
            else:
                fail_count = len(failed_papers)
                utils.log_message("下载完成，但有{}篇失败。成功下载{}篇，已存在{}篇。".format(
                    fail_count, paper_downloaded, already_exist
                ))

    def create_progress_bar(self):
        if hasattr(self, 'pb_window'):
            self.pb_window.destroy()
        self.pb_window = tk.Toplevel()
        self.pb_window.geometry("360x170+600+300")
        self.pb_window.iconbitmap("img/root.ico")  # 窗体图标
        self.pb_window.title("任务进度")
        center_window(self.pb_window)
        self.progress_text = tk.StringVar(value="准备中...")
        tk.Label(self.pb_window, textvariable=self.progress_text, wraplength=320, justify="left").pack(padx=10, pady=15)
        self.download_pb = ttk.Progressbar(self.pb_window, length=200, mode="determinate", orient=tk.HORIZONTAL)
        self.download_pb.pack(padx=10, pady=10)
        self.download_pb["value"] = 0
        self.download_pb["maximum"] = max(utils.get_value("progress_bar_max") or 1, 1)

    def refresh_window(self):
        if not hasattr(self, 'pb_window'):
            return
        if not hasattr(self, 'download_pb'):
            return
        while True:
            try:
                current = utils.get_value("progress_bar_num") or 0
                maximum = utils.get_value("progress_bar_max") or 0
                status = utils.get_value("progress_bar_status") or "处理中..."
                done = utils.get_value("progress_bar_done") or False
                if self.pb_window and self.download_pb and self.pb_window.winfo_exists():
                    self.download_pb["maximum"] = max(maximum, 1)
                    self.download_pb["value"] = min(current, max(maximum, 1))
                    if hasattr(self, 'progress_text'):
                        self.progress_text.set(status)
                    self.pb_window.update()
                if done:
                    break
            except (RuntimeError, tk.TclError):
                break
            time.sleep(0.1)
        try:
            if hasattr(self, 'pb_window') and self.pb_window.winfo_exists():
                self.pb_window.destroy()
        except (RuntimeError, tk.TclError):
            return

    def begin_download_1(self):
        try:
            _thread.start_new_thread(self.download_1_thread, ())
        except:
            show_fail_window("Error: 无法启动线程")

    def all_downloaded(self, paperlist):
        if not paperlist:
            return False
        for key, value in paperlist.items():
            if not utils.is_valid_pdf_file(value['name']):
                return False
        return True

    def download_2_thread(self):
        save_dir = utils.clean_input_path(self.save_dir.get(0.0, tk.END).split("\n")[0].strip())
        keywords = self.keyword.get(0.0, tk.END).split("\n")[0].strip()
        page_range = self.page_range.get(0.0, tk.END).split("\n")[0].strip()
        save_with_year = self.CheckVar2.get()
        confirm_message = "开始下载吗？\n\n保存目录:\n{}\n\n关键词: {}\n页码范围: {}".format(save_dir, keywords, page_range)
        if show_begin_download(confirm_message):
            is_valid = check_value_valid(mode=2, save_dir=save_dir, keyword=keywords, page=page_range)
            page_is_valid, page_range = check_page_valid(page_range)
            if not page_is_valid:
                return
            if not is_valid:
                return
            # 配置存储文件夹
            import os
            if not os.path.exists(save_dir):
                os.mkdir(save_dir)
            utils.log_message("=" * 60)
            utils.log_message("准备开始下载，保存目录: {}".format(save_dir))
            utils.log_message("关键词: {} | 页码范围: {}".format(keywords, page_range))
            utils.reset_progress(status="正在查询 IEEE Xplore...")
            status, paper_info = organize_info_by_query(keywords, page_range, save_dir, save_with_year)
            if not status:
                utils.finish_progress("在线查询失败")
                utils.log_message("URL解析失败...")
                return

            if self.all_downloaded(paper_info):
                info = "{}篇论文已存在，无需下载!".format(len(paper_info))
                utils.finish_progress(info)
                utils.log_message(info)
                return
            # 下载论文
            succeed, paper_downloaded, already_exist, failed_papers = downLoad_paper(paper_info, show_bar=True)
            if succeed:
                info = "成功下载{}篇论文!".format(paper_downloaded + already_exist)
                utils.log_message(info)
            else:
                fail_count = len(failed_papers)
                utils.log_message("下载完成，但有{}篇失败。成功下载{}篇，已存在{}篇。".format(
                    fail_count, paper_downloaded, already_exist
                ))

    def begin_download_2(self):
        try:
            _thread.start_new_thread(self.download_2_thread, ())
        except:
            show_fail_window("Error: 无法启动线程")

    def close(self, *arg):
        utils.log_message("退出程序")
        utils.set_logger(None)
        self.root.destroy()


if __name__ == "__main__":
    utils._init()
    utils.set_value("progress_bar_num", 0)
    app = App()
    app.root.mainloop()
