# 雪原防卫 · 霜原守望

大厅选择「雪原防卫 · 守住十波敌袭」。也可通过 `-- --defense` 直接进入。首版为独立单人防卫战，采用现有 RTS 指挥、建造、经济与升级系统。

## 战斗规则

- 西侧初始大本营是必须保护的目标。它被摧毁即失败，同一物理帧发生的基地毁灭优先于清波胜利。
- 清除第十波全部敌人、且待出兵队列为空时获胜，不要求摧毁东侧建筑。
- 初始拥有大本营、兵营、箭塔、6 农民、4 剑士、2 弓箭手和 520 金币。
- 开局准备 120 秒，每波清完后整备 45 秒。每波开始播放原创双击城防钟，HUD 显示波次、名称和剩余敌军（包含待到达增援）。暂停同步冻结倒计时、战斗和警钟。
- 每波清完获得 100～300 金币补给。人口、采矿速度、造价、招募时间和科技沿用普通 RTS。
- 敌军从现存兵营和工厂出发。摧毁六处生产建筑会按比例削弱后续波次，最多减少 50%；剩余兵力由东侧边界增援，因此仍需守完十波。当前波已排队的敌人不会凭空消失。
- 单个出口拥挤时保留排队单位，轮转尝试其他兵种；持续阻塞 8 秒后由东侧预设增援点入场，避免堵门让波次永久停滞。
- 敌方不运行遭遇战 Bot，不会另行发展经济或产生计划外波次。堡垒和炮塔仍会正常防守，玩家可以主动反攻。

## 地图

160×96 米的开阔雪原，西侧基地、六处永久金矿、东侧十三座敌方建筑。三条宽路线贯穿战场，周围的雪山、雪松和冰川岩石构成地形边界；两处冻结水面可以通行。相机正对东西方向，保持玩家基地在画面左侧、敌军来自右侧。

地形、碰撞、矿点、建筑和增援标记保存为原生 `.tscn`；原生 `GPUParticles3D` 表现飘雪。导航源保持一米网格，与 `ConstructionNavigation` 的动态施工占地契约一致。几何与着色器直接适配项目的 3D 低多边形风格，没有新增栅格图像素材。

## 数据和后续 Rogue 扩展

| 文件 | 用途 |
| --- | --- |
| `data/defense/ten_waves.tres` | 十波兵种组合、清波补给、准备时间与削弱比例 |
| `scripts/defense/defense_wave_definition.gd` | 单波 Resource，按兵种交错排列出兵 |
| `scripts/defense/defense_scenario_definition.gd` | 关卡规则 Resource |
| `scripts/defense/defense_battle.gd` | 波次调度与初始大本营胜负规则 |
| `scenes/defense/battle.tscn` | 继承主战场，配置冷色环境、相机和警钟 |
| `scenes/defense/snowfield_map.tscn` | 可编辑雪地图及布局标记 |
| `tools/build_snowfield_map.py` | 确定性重建地形、材质和导航，覆盖对应生成资产 |
| `tools/build_defense_audio.py` | 确定性重建原创钟声及来源元数据 |

`wave_started(index)`、`wave_cleared(index)` 信号和独立关卡 Resource 为后续波间选择、遗物、强化与随机事件提供接入点。当前没有 Rogue 奖励选择或局外成长系统。单人防卫数据不参与联机内容指纹。

## 验证

Godot 4.6.3，Windows，Forward+。

- `tests/defense_mode_test.gd`：57 项通过；真实经济与建造、6 处大体型出兵口和整条导航路线、暂停、清波倒计时、削弱与边界增援、末波待出兵检查、原始基地失败判定。
- `tests/defense_battle_probe.gd`：首波全程实际行军和交战；初始守军在约 50 秒战斗时间内清除首波，大本营保持 3000 生命。仅是首波冒烟验证，完整十波难度仍需试玩调校。
- `tests/defense_visual_review.gd`：大厅入口、实际开局、警钟提示，以及关闭迷雾用于美术检查的地图总览和两侧基地截图。
- 原有大厅 UI 回归 228 项通过，内容清单检查通过；检查记录保存在本机 `artifacts/defense/`。
- 原有 `hud_skirmish_display_test.gd` 为 151 项中的 147 项通过。四个失败分别是两项角色文案精确匹配、旧版建造按钮数量、旧版扩农民帮助说明；以修改前 HEAD 的 game/HUD/场景副本运行，得到完全相同的四项失败。本次未修改这些已有过期断言。

官方参考：[GPUParticles3D](https://docs.godotengine.org/en/stable/classes/class_gpuparticles3d.html)、[ParticleProcessMaterial](https://docs.godotengine.org/en/stable/classes/class_particleprocessmaterial.html)、[NavigationRegion3D](https://docs.godotengine.org/en/stable/classes/class_navigationregion3d.html)、[PrimitiveMesh](https://docs.godotengine.org/en/stable/classes/class_primitivemesh.html)。
