# 用户数据迁移记录

## 迁移日期
2026-01-31

## 迁移说明

为了简化项目结构，将所有历史用户的数据整合到单一用户 `qingshui` 下。

## 迁移操作

### 源用户（已删除）
- `12afc526-fcc4-49ea-884e-61c44d130d14` - 8 个项目
- `bd589dd2-30e4-4d06-9a05-97d7cfe4e4e7` - 1 个项目  
- `d4d9f53b-5800-42ca-bb5a-42062ae5b67b` - 无项目数据

### 目标用户
- `qingshui` (ID: `04383daf-2b3c-497d-941f-1deefe31fbf0`)
- 账号：qingshui / qingshui123

## 迁移后的数据统计

| 数据类型 | 数量 |
|---------|------|
| 项目 (projects) | 9 个 |
| 角色 (characters) | 36 个 |
| 场景 (scenes) | 18 个 |
| 道具 (props) | 11 个 |
| 首帧 (frames) | 40 个 |
| 视频 (videos) | 171 个 |
| 图库 (gallery) | 140 个 |
| 图片工作室 (studio) | 53 个 |
| 视频工作室 (video_studio) | 95 个 |
| 音频 (audio) | 2 个 |
| 视频库 (video_library) | 33 个 |
| 风格 (styles) | 10 个 |

## 备份位置

旧用户数据已备份至：
```
/tmp/old-users-backup-20260131-144958.tar.gz
```

## 恢复方法

如需恢复旧用户数据：
```bash
cd /Users/zane/Project/Miemie-studio/backend/data
tar -xzf /tmp/old-users-backup-*.tar.gz
```

## 注意事项

1. 所有历史项目现在归属于 `qingshui` 用户
2. 原用户目录已删除，仅保留备份
3. 如需访问历史数据，请使用 `qingshui` 账号登录
4. 备份文件建议保留至少 30 天后再删除
