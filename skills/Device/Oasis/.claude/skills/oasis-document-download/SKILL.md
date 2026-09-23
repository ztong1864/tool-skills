---
name: oasis-document-download
description: 访问 Oasis 绿洲远程文档 API，查询目录内容并把目标文件下载到本地。当用户要“查看远程目录里有什么文件、先列一下目录、下载某个远程文档、把多个远程文件批量拉到本地”时调用本技能；不要把它误当成 Oasis 实验执行接口使用。
---

# oasis-document-download
用于查询远程目录、读取 `download_url`，并把目标文件下载到本地。

- 可以列目录
- 可以下载单个文件
- 可以批量下载同一目录或不同目录下的多个文件

## 直接调用

```bash
# 查看根目录
python skills/oasis-document-download/scripts/call.py

# 查看某个目录
python skills/oasis-document-download/scripts/call.py \
  --folder-path folder_dir

# 只输出 items 数组
python skills/oasis-document-download/scripts/call.py \
  --folder-path folder_dir \
  --only-data

# 检查服务是否可用
python skills/oasis-document-download/scripts/call.py --check-service

# 下载单个文件
python skills/oasis-document-download/scripts/call.py \
  --download-path file_name.txt

# 批量下载同一目录或不同目录下的多个文件路径
python skills/oasis-document-download/scripts/call.py \
  --download-paths folder_a/file_a.txt folder_b/file_b.txt folder_c/file_c.txt

# 批量下载多个 download_url
python skills/oasis-document-download/scripts/call.py \
  --download-urls /download/folder_a/file_a.txt /download/folder_b/file_b.txt

# 批量下载某个目录下的所有文件
python skills/oasis-document-download/scripts/call.py \
  --folder-path folder_dir \
  --download-folder

# 递归批量下载目录及其子目录下的所有文件
python skills/oasis-document-download/scripts/call.py \
  --folder-path folder_dir \
  --download-folder \
  --recursive

# 指定输出目录
python skills/oasis-document-download/scripts/call.py \
  --download-urls /download/folder_a/file_a.txt /download/folder_b/file_b.txt \
  --output-dir outputs/oasis-document-download

# 输出完整 JSON
python skills/oasis-document-download/scripts/call.py \
  --folder-path folder_dir \
  --json-output
```

通常只需要传递业务参数，例如 `--folder-path`、`--download-path`、`--download-paths` 或 `--download-urls`。脚本默认会直接访问 API；只有在明确需要改回“通过 SSH 在远端执行 curl”时，才追加 `--use-ssh`。如还需要切换 SSH 主机、账号、密码、端口或超时，再追加：

```bash
--ssh-host <IP> --ssh-user <用户名> --ssh-password <密码> --ssh-port <端口> --ssh-timeout <秒数>
```

## 输入规则

- `--folder-path`、`--download-path` 和 `--download-paths` 要传远程 API 返回的相对路径
- `--download-urls` 要传 `/download/...` 这种格式；也可以直接传完整下载 URL
- 路径分隔符统一使用 `/`
- 优先复用 `/list` 返回里的 `path`、`download_url`、`list_url`

## 推荐工作顺序

1. 先列目录，确认目标文件或子目录存在。
2. 如果要批量下载多个离散文件，优先收集 `download_url` 组成列表。
3. 再用 `--download-urls` 批量下载。
4. 如果要整批拉取某个目录下的所有文件，改用 `--download-folder`。

## 返回结构

### 检查服务

```json
{
  "message": "File API is running",
  "download": "/download/{relative_file_path}",
  "list": "/list/{relative_folder_path}"
}
```

### 列目录

```json
{
  "current_path": "",
  "base_dir": "C:\\Users\\MolDev\\Downloads",
  "items": [
    {
      "name": "file_name.txt",
      "type": "file",
      "path": "file_name.txt",
      "download_url": "/download/file_name.txt",
      "list_url": null
    }
  ]
}
```

重点字段：

- `items`：当前目录下的文件和子目录
- `name`：显示名称
- `type`：`file` 或 `folder`
- `path`：相对路径
- `download_url`：下载这个文件时优先使用的路径
- `list_url`：进入子目录时可参考的路径

## 下载行为

- 默认下载到 `outputs/oasis-document-download/`
- 单文件下载可以用 `--output` 指定单个本地文件路径
- 多文件下载和目录下载统一用 `--output-dir`
- 已存在同名文件时，只有加 `--overwrite` 才覆盖
- `--download-folder` 会批量下载 `--folder-path` 下的所有文件
- `--recursive` 只在 `--download-folder` 场景下生效

## 常见错误

- 把目录路径传给 `--download-path`
- 把文件路径传给 `--folder-path`
- 同时传 `--download-path`、`--download-paths`、`--download-urls` 或 `--download-folder`
- 多文件下载时误用 `--output`
- 没先 `list` 就手写不存在的路径
