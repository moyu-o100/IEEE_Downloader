# Modification Log

本文档记录当前项目相对原始仓库的主要修改，方便后续回顾、继续开发和排查问题。

原始项目：
- `yongcaoplus/IEEE_downloader`
- 原仓库链接：<https://github.com/yongcaoplus/IEEE_downloader>

修改时间范围：
- 本轮主要修改集中在 `2026-04-02`

## 1. 初始可运行性修复

目标：
- 先让 `main.py` 和 `main_ui.py` 在当前环境下能正常启动和执行

修改内容：
- 新增 `requirements.txt`
  - 明确项目依赖：`requests`、`tqdm`、`Pillow`
- 修复 `main.py`
  - 统一创建保存目录
  - 修正 `txt` 模式下 `organize_info_by_txt()` 的调用参数
  - 在查询失败或文件不存在时给出明确退出信息
- 修复 `utils.py`
  - 给全局状态字典增加默认初始化，避免部分流程未初始化时报错

涉及文件：
- `requirements.txt`
- `main.py`
- `utils.py`

## 2. IEEE 在线请求兼容修复

问题背景：
- 原始代码使用旧请求头和旧 cookie 获取方式，在当前 IEEE Xplore 上容易遇到 `HTTP 418` 或返回拦截页

修改内容：
- 重写 `download_paper_by_pageURL.py` 中的 IEEE 会话建立方式
  - 使用浏览器风格请求头
  - 使用 `requests.Session()` 先访问首页获取有效会话
  - 再调用 `/rest/search` 搜索接口
- 对搜索请求增加异常处理
- 在线查询逻辑失败时返回明确失败状态而不是继续误判

涉及文件：
- `download_paper_by_pageURL.py`

## 3. 下载阶段改造

问题背景：
- 原始项目可能把 IEEE 的拦截 HTML 页面保存成 `.pdf`
- 原始项目对“已下载”的判断只看文件是否存在，不判断文件内容是否为真实 PDF

修改内容：
- 在 `utils.py` 中新增 PDF 有效性判断
  - 通过文件头 `%PDF-` 检查是否为真实 PDF
- 下载前如果发现目标文件已存在：
  - 若为真实 PDF，则视为已下载
  - 若不是 PDF，则删除后重新下载
- 下载请求改为带会话和 `Referer`
- 增加下载失败重试
- 增加定期刷新会话，减少大批量下载中段被 IEEE 拦截的概率
- 下载完成时返回失败列表，供 UI 给出更明确反馈

涉及文件：
- `utils.py`

## 4. `txt` 解析能力增强

目标：
- 不再只支持旧版 `URL.txt`
- 支持 IEEE 导出的 `Citation Plain Text`

修改内容：
- `download_paper_by_URLfile.py` 现在同时支持两类输入：
  - 旧版带 `URL: ... arnumber=...` 的文本
  - `IEEE Xplore Citation Plain Text Download ... .txt`
- 对旧版 `URL.txt`
  - 直接提取 `arnumber`
- 对 Citation Plain Text
  - 先提取标题
  - 优先提取 DOI
  - 用 DOI 到 IEEE 搜索接口查 `articleNumber`
  - 若 DOI 没命中，再回退为标题搜索
- 支持多编码读取文本
  - `utf-8-sig`
  - `utf-8`
  - `gb18030`

涉及文件：
- `download_paper_by_URLfile.py`

## 5. 路径兼容修复

问题背景：
- 从资源管理器复制路径时，路径前面可能带不可见 Unicode 控制字符，例如 `U+202A`
- 原始程序会把这种路径误判为不存在

修改内容：
- 在 `utils.py` 中新增 `clean_input_path()`
  - 统一清理隐藏字符、引号和多余空白
- 在 `main_ui.py` 和 `download_paper_by_URLfile.py` 中统一使用该方法

涉及文件：
- `utils.py`
- `main_ui.py`
- `download_paper_by_URLfile.py`

## 6. UI 兼容与交互改造

目标：
- 提升可用性
- 避免新版 `Pillow` 和当前 UI 行为带来的问题

修改内容：
- 修复 `Pillow` 新版本兼容性
  - 将 `Image.ANTIALIAS` 改为兼容新版的 `Resampling.LANCZOS`
- 改进“已下载”判断
  - 只有真实 PDF 才算已下载
- 增加文件选择按钮
  - 选择 `txt` 文件
- 增加目录选择按钮
  - 选择论文保存目录
- 增加滚动日志框
  - 解析进度
  - 下载进度
  - 成功 / 失败摘要
- 将原本的结果弹窗改为日志输出
  - 当前 UI 已改为无弹窗模式，主要状态都写入日志

涉及文件：
- `main_ui.py`

## 7. 解析性能优化

问题背景：
- Citation Plain Text 并不直接包含 IEEE 下载链接
- 原始增强版实现采用逐条联网解析 `doi/title -> articleNumber`
- 首次大批量解析速度偏慢

修改内容：
- 在 `download_paper_by_URLfile.py` 中加入本地解析缓存
  - 缓存位置：`.cache/ieee_lookup_cache.json`
  - 缓存键：
    - `doi:*`
    - `title:*`
- 增加 Citation 解析并发
  - 当前最大并发数：`6`
  - 仅对未命中缓存的条目发起并发查询
- 仍然保持输出顺序与输入顺序一致

效果：
- 第一次解析仍需联网补全 `articleNumber`
- 第二次解析相同或高度重合的文件时，速度显著提升

涉及文件：
- `download_paper_by_URLfile.py`
- `.gitignore`
- `README.md`

## 8. 内存和资源释放改进

问题背景：
- UI 日志框如果无限追加，长时间运行会使 Python 进程内存持续增长
- 若 `requests.Session` 不显式关闭，连接资源可能保留过久
- 图片文件句柄也应尽量及时释放

修改内容：
- 为日志框设置行数上限
  - 当前最多保留 `1000` 行
- 在下载和在线查询流程中显式关闭 `requests.Session`
- 图片加载改为 `with Image.open(...).copy()` 形式，及时释放句柄

涉及文件：
- `main_ui.py`
- `utils.py`
- `download_paper_by_pageURL.py`

## 9. 仓库整理

目标：
- 避免把下载结果、缓存和本地环境推送到仓库
- 让项目说明与当前功能一致

修改内容：
- 新增 `.gitignore`
  - 忽略 PDF
  - 忽略 `save/` 及其他下载目录
  - 忽略 `__pycache__/`
  - 忽略 `.venv/`、`venv/`、`env/`
  - 忽略 `.cache/`
  - 忽略测试样本文件
- 重写 `README.md`
  - 更新功能说明
  - 记录当前 UI 能力
  - 增加项目虚拟环境使用说明
  - 保留对原仓库的 Acknowledgement

涉及文件：
- `.gitignore`
- `README.md`

## 10. 额外文档

新增内容：
- `future_feature_notes.txt`
  - 记录后续功能想法
  - 包括 arXiv 支持、元信息提取、导出格式、更多数据源、UI 改进等

涉及文件：
- `future_feature_notes.txt`

## 11. 已完成的主要验证

完成过的验证包括：
- `main.py` 可运行
- `main_ui.py` 可运行
- IEEE 在线搜索下载链路可运行
- `Citation Plain Text` 输入可解析
- UI 的方法 1 和方法 2 都可走通
- 100 篇批量下载在会话刷新和重试后可完成
- 3 篇小样本验证了：
  - 文件选择按钮
  - 文件夹选择按钮
  - 日志框输出
  - 无弹窗模式
  - 缓存命中加速
- `python -m py_compile ...` 已用于静态校验主要 Python 文件

## 12. 当前状态摘要

相对原始项目，当前版本已经具备：
- 更稳的 IEEE 会话处理
- 更可靠的 PDF 有效性判断
- 同时支持 `URL.txt` 和 `Citation Plain Text`
- 更友好的 UI 文件/目录选择
- 无弹窗日志模式
- 下载重试和会话刷新
- Citation 解析缓存和并发优化
- 更完整的仓库清理规则和说明文档

