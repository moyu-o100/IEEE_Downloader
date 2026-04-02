# IEEE Downloader

在具备 IEEE Xplore 下载权限的网络环境下，批量解析论文列表并下载 PDF。

当前版本在原项目基础上补了这些内容：

- 支持两种 `txt` 输入格式：
  - 旧版带 `URL: ... arnumber=...` 的导出格式
  - `IEEE Xplore Citation Plain Text` 引文格式
- 自动兼容从资源管理器复制路径时可能带的隐藏字符
- Citation 解析结果会本地缓存，重复解析更快
- UI 增加：
  - 选择保存文件夹按钮
  - 选择 `txt` 文件按钮
  - 内置滚动日志框
  - 无弹窗运行，状态统一写入日志
- 下载时会校验是否为真实 PDF，并在被 IEEE 临时拦截时自动重试

## 环境要求

- Python 3.10+
- 当前网络已经具备 IEEE Xplore 文献下载权限

安装依赖：

```bash
python -m pip install -r requirements.txt
```

可选：如果你希望依赖只安装在当前项目，而不是全局 Python，建议使用虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell 激活：

```bash
.\.venv\Scripts\Activate.ps1
```

激活后安装依赖：

```bash
python -m pip install -U pip
python -m pip install -r requirements.txt
```

如果不想手动激活，也可以直接使用项目环境里的 Python：

```bash
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main_ui.py
```

## 运行方式

启动图形界面：

```bash
python main_ui.py
```

或运行脚本入口：

```bash
python main.py
```

## 使用说明

### 方法 1：使用 URL/Citation txt 文件

适用于：

- 旧版 `URL.txt`
- `IEEE Xplore Citation Plain Text Download ... .txt`

流程：

1. 在 UI 中选择论文保存文件夹。
2. 选择导出的 `txt` 文件。
3. 点击开始下载。
4. 在底部日志框查看解析进度和下载进度。

解析逻辑：

- 如果 `txt` 里直接包含 `arnumber=...`，就直接提取 `articleNumber`
- 如果是 Citation Plain Text，则优先用 DOI 去 IEEE 搜索接口查 `articleNumber`
- 找到 `articleNumber` 后，统一拼接 PDF 下载地址

### 方法 2：在线查询

输入关键词和页码范围后，程序会访问 IEEE Xplore 搜索接口并批量下载结果论文。

页码范围支持：

- `2`
- `2,3,5`
- `2-5`

## 文件忽略规则

仓库默认不会上传以下内容：

- `save/` 及其他下载输出目录
- 所有 `pdf`
- `__pycache__`
- `.cache/` 本地解析缓存
- 本地测试样本文件

## Acknowledgement

本项目基于原仓库修改：

- [yongcaoplus/IEEE_downloader](https://github.com/yongcaoplus/IEEE_downloader)
