# Windows 发布维护

随包的 `START_HERE.txt` 来自 [玩家指南](windows-readme.txt)，只保留玩法、操作和故障反馈说明。构建与联机维护说明集中在本文。

## 版本与联机内容

发行版本以 `scripts/network/network_protocol.gd` 的 `RELEASE_ID` 为准；Windows 导出预设中的 `application/file_version` 和 `application/product_version` 应与之同步，末尾补 `.0`。玩家指南不重复写死版本号，避免更新时遗漏。

网络协议 `VERSION`、网络构建标识 `BUILD_ID` 与发行版本不同。联机要求客户端和中继的协议、构建标识及内容指纹匹配；仅发行版本相同不代表修改过的兵种、建筑或地图仍兼容。资源描述也包含在当前内容清单校验中，修改后应重新生成清单。重新打包客户端并不会自动更新线上中继。

## 重新打包

在项目根目录运行 `tools/build_windows.ps1`。脚本会根据当前文件生成内容清单、导出游戏、校验包内内容，并将玩家指南、字体许可和诊断工具一并放入 ZIP。使用 `-VersionedOutput` 时，版本必须与导出预设一致。

直接使用 Godot 编辑器导出前，先运行 `python tools/build_content_manifest.py`。导出后用 `python tools/build_content_manifest.py --check` 检查文件是否仍匹配；校验实际安装包可使用 `tests/network_release_runner.py` 的 `--catalogue-only` 选项。

发布前检查以下内容：

- EXE、PCK 来自同一次完整发布；更新启动器版本时需要完整导出。
- `START_HERE.txt`、`FONT_LICENSE.txt`、`collect_diagnostics.ps1` 与 `COLLECT_DIAGNOSTICS.cmd` 随包提供。
- 房间服务器采用与测试客户端一致的协议、构建标识和内容清单。
- 用待发布安装包验证启动、中文显示、对战入口和联机版本检查。

## 运行与诊断

项目使用 Forward+ Vulkan 渲染；单位数量、粒子和场景复杂度都会影响 CPU/GPU 负担。性能结论应以目标设备实测为准。

`COLLECT_DIAGNOSTICS.cmd` 在本机文档目录的“Block-RTS-诊断”文件夹生成 ZIP，不自动上传。内容包括日志、相关 Windows 错误、系统与显卡信息以及 EXE/PCK 校验值。排查联机不匹配时，同时核对客户端、服务器的协议和内容清单。

远征存档路径为 `user://rogue_run.json`，由 Godot 映射到本机用户数据目录。存档保存节点结算后的状态，不保存战斗现场。

本产品源码与发布入口：[Block-RTS](https://github.com/wanheng20031114/Block-RTS)。独立用户数据目录为 `Godot/app_userdata/Block-RTS`；首次运行从原「积木争霸」复制设置、大厅偏好及远征检查点，目标已有文件时不覆盖，旧产品数据不修改。
