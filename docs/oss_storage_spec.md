# 规格：对象存储（S3 兼容 OSS）可选配置

## Objective（目标）

解决"本机上传图片无公网、他人运行代码看到碎裂图片"的问题：

- 在后台「门户设置」新增「对象存储（OSS）」配置面板，允许配置符合 **Amazon S3 规范**的三方对象存储（阿里云 OSS、腾讯云 COS、MinIO、AWS S3 等）。
- **未配置（endpoint 留空）**：维持现有逻辑，上传保存到本地 `uploads/`，URL 为 `BASE_URL/static/...`。
- **已配置**：新上传的文件写入 OSS，返回 OSS 可公网访问的 URL（假设 bucket 为公开读），文稿封面/正文引用不再依赖运行机器的本地文件。
- 存量本地图片不受影响（不迁移）；`upload-by-url` 链接下载同样走配置的存储。

## 存储配置（system_settings 新增一条）

| config_key | value_type | 默认值 | 说明 |
| --- | --- | --- | --- |
| oss_config | json | null | endpoint 为空 = 本地模式；非空 = S3 兼容对象存储 |

配置字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| endpoint | 是（启用 OSS 时） | 服务地址，如 `https://oss-cn-hangzhou.aliyuncs.com`、`http://192.168.1.10:9000` |
| bucket | 是 | 存储桶名称（bucket 需允许公开读） |
| region | 否 | 区域，默认 `us-east-1`（MinIO 等自建可随意） |
| access_key | 是 | Access Key |
| secret_key | 是 | Secret Key（回显脱敏，保存时 `****` 表示保留原值） |
| path_prefix | 否 | 对象前缀，如 `articles/`，不填则存 bucket 根 |
| public_base_url | 否 | 公开访问前缀；不填则按 `endpoint/bucket/key`（路径风格）拼接，填了则用它替换 endpoint（兼容虚拟主机风格/CDN） |

## 接口契约

### 1. 读取 OSS 配置（管理员）

`GET /api/portal/oss-config` → `{ "configured": true, "config": { endpoint, bucket, region, access_key, path_prefix, public_base_url, secret_key: "****" } }`

secret_key 脱敏返回：已设置显示 `****`，未设置显示空。

### 2. 保存 OSS 配置（管理员）

`PUT /api/portal/oss-config`，body 同配置字段。`secret_key` 传 `****` 或空时保留原值（编辑场景）。endpoint 留空即关闭 OSS 回本地模式。

### 3. 上传接口（复用现有）

`POST /api/resources/upload`、`POST /api/resources/upload-by-url` 行为变化：

- 未配置 OSS：原逻辑不变。
- 已配置：文件上传到 OSS（key = `[path_prefix]YYYYMMDD_uuid.ext`），`Resource.storage='oss'`、`url` 为公网地址；**OSS 上传失败时明确报错，不回退本地**（避免同一批图片分散两地）。

## 数据模型变更

`resources` 表新增 `storage` 字段（`local` / `oss`，默认 `local`），用于删除资源时区分物理位置：

- `local`：删除 `uploads/` 本地文件（现有逻辑）。
- `oss`：调用 OSS `delete_object` 删除对象；若 OSS 配置已被清空，跳过并提示。

老库由 `ensure_schema_compat` 幂等补列；新库由模型自动建。

## 后端实现要点

- 新增 `backend/app/services/oss_service.py`：读配置、懒加载 boto3 客户端（未配置时不 import）、`upload_bytes` / `delete_object`、URL 拼接。
- `requirements.txt` 新增 `boto3`。
- `resources.py` 的 upload / upload-by-url / delete 按 `storage` 分流。

## 前端设计（门户设置页）

在「注册开放配置」之后新增 panel「对象存储（OSS）」：

- 顶部说明：endpoint 留空 = 上传到本地服务器；配置后新上传文件写入 S3 兼容存储（bucket 需公开读）。
- 字段：endpoint、bucket、region、access_key、secret_key（`show-password`）、path_prefix、public_base_url + 保存按钮。
- 保存成功后提示；`secret_key` 显示 `****`（已设置）。

## 成功标准

1. 未配置时上传、链接下载、删除全部维持本地逻辑（回归验证）。
2. 配置保存/读取正常，secret_key 脱敏。
3. 配置后上传走 OSS 分支：无效 endpoint 时报清晰中文错误；有效时返回公网 URL（用 botocore Stubber 验证调用与 URL 拼接逻辑）。
4. 删除 OSS 资源时调用 delete_object（Stubber 验证），删除本地资源时不动 OSS。
5. 冒烟测试覆盖：配置读写、未配置上传回归；前端构建通过；浏览器审核门户设置页 OSS 面板。

## 边界

- Always：secret_key 不落日志、接口回显脱敏；上传文件类型/大小校验保持现有；中文注释。
- Ask first：存量本地文件自动迁移到 OSS、私有 bucket + 预签名 URL、CDN 刷新等。
- Never：把 secret_key 明文回显给前端；OSS 上传失败静默回退本地。

## 存量内网 URL 迁移

早期 MinIO endpoint 使用内网地址时，已入库的封面/正文/资源 URL 都是内网前缀，
公网访问图片会失败。可使用一次性脚本修复（先 dry-run 再看数量）：

```bash
cd backend
# 只统计，不写库
python fix_oss_public_urls.py --new-prefix http://wgfb.89cyx.cc:9000 --dry-run
# 正式替换，并同时把 OSS public_base_url 改为含 bucket 的公网地址
python fix_oss_public_urls.py \
  --new-prefix http://wgfb.89cyx.cc:9000 \
  --set-public-base http://wgfb.89cyx.cc:9000/wgfb
```

说明：
- `--new-prefix` 只到协议+域名[:端口]，不含 bucket；脚本会把
  `http://192.168.14.216:9000/wgfb/xxx.jpg` 替换为 `http://wgfb.89cyx.cc:9000/wgfb/xxx.jpg`。
- `--set-public-base` 会更新 OSS 配置，确保**之后新上传**的图片也生成公网 URL。
- 替换范围：`articles.cover_url`、`articles.content`、`resources.url`、
  `portal_modules.content`（JSON 内图片地址）。

### MinIO 内网穿透

MinIO 使用内网地址且服务器无公网时，需要在公网机 `38.22.95.20` 上额外做 9000 端口穿透：

```ini
[minio_tcp]
type = tcp
# frpc 跑在 MinIO 机器上时填 127.0.0.1；否则填 192.168.14.216
local_ip = 127.0.0.1
local_port = 9000
remote_port = 9000
```

同时放行公网机防火墙 9000 端口，并确保 `wgfb` bucket 允许公开读，
然后执行上面的 `fix_oss_public_urls.py` 迁移即可。

排查要点：
- frpc 若不在 MinIO 机器上运行，`local_ip` 要填 `192.168.14.216`，不能是 `127.0.0.1`。
- MinIO console 启动参数用 `--console-address ":9001"`（监听所有网卡），不要只绑 `127.0.0.1`。
- 公网机 `38.22.95.20` 需要放行 9000/9001 端口（firewall/iptables + 云安全组）。
- 在公网机执行 `curl http://127.0.0.1:9001/` 可验证 frp 转发链路是否正常。
