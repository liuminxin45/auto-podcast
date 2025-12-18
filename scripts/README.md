# 环境配置管理脚本

这个目录包含用于管理 `.env*` 配置文件的实用脚本。

## 脚本列表

### 1. `merge_env.py` - 合并配置文件

将所有 `.env*` 文件合并成一个备份文件，方便迁移或备份。

**用法：**

```bash
# 合并所有 .env* 文件到 .env.backup
python scripts/merge_env.py

# 指定输出文件
python scripts/merge_env.py -o my-backup.env

# 预览合并结果（不写入文件）
python scripts/merge_env.py --dry-run

# 指定搜索目录
python scripts/merge_env.py --root /path/to/project
```

**功能：**
- 自动查找所有 `.env` 和 `.env.*` 文件（排除 `.env.example`、`.env.backup` 等）
- 在合并文件中添加源文件标记，方便后续拆分
- 添加时间戳和文件列表注释

### 2. `split_env.py` - 拆分配置文件

将合并的备份文件拆分回独立的 `.env*` 文件。

**用法：**

```bash
# 从备份恢复所有配置文件
python scripts/split_env.py .env.backup

# 指定输出目录
python scripts/split_env.py .env.backup --output-dir /path/to/restore

# 预览拆分结果（不写入文件）
python scripts/split_env.py .env.backup --dry-run
```

**功能：**
- 解析合并文件中的源文件标记
- 自动恢复到原始文件名
- 支持预览模式

## 使用场景

### 场景 1：备份所有配置
```bash
# 创建备份
python scripts/merge_env.py -o backups/env-$(date +%Y%m%d).backup

# 提交到私有仓库或加密存储
```

### 场景 2：迁移到新机器
```bash
# 在旧机器上
python scripts/merge_env.py -o env-export.txt

# 复制 env-export.txt 到新机器

# 在新机器上
cd /path/to/new/project
python scripts/split_env.py /path/to/env-export.txt
```

### 场景 3：快速切换配置组
```bash
# 保存当前配置
python scripts/merge_env.py -o .env.backup.dev

# 切换到生产配置
python scripts/split_env.py .env.backup.prod

# 恢复开发配置
python scripts/split_env.py .env.backup.dev
```

## 注意事项

1. **安全性**：合并后的文件包含所有 API Key，请妥善保管
2. **版本控制**：`.env.backup` 已在 `.gitignore` 中排除，不会被提交
3. **文件覆盖**：拆分时会覆盖现有的 `.env*` 文件，请先备份
4. **编码**：所有脚本使用 UTF-8 编码，确保中文注释正常显示

## 示例输出

### 合并输出示例
```
Found 4 .env file(s):
  - .env
  - .env.podcast
  - .env.tts
  - .env.voiceclone_http

✓ Successfully merged 4 file(s) into: .env.backup
  Total size: 3456 bytes
```

### 拆分输出示例
```
Found 4 file(s) to restore:
  - .env (45 lines)
  - .env.podcast (12 lines)
  - .env.tts (38 lines)
  - .env.voiceclone_http (28 lines)

✓ Restored: .env
✓ Restored: .env.podcast
✓ Restored: .env.tts
✓ Restored: .env.voiceclone_http

✓ Successfully restored 4/4 file(s)
```
