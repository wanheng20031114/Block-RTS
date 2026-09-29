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

地图扩大到 **256×144 米**，面积为初版的 2.4 倍。西侧基地、八处永久金矿、东侧十三座敌方建筑分布在多层雪山环抱的谷地中；134 段外围山脊、10 处内部雪台和 483 棵雪松分隔南、中、北三条路线。丘陵具有实际高度与碰撞，军队沿低处河谷行军，基地附近保留成片建造空间。

蜿蜒冰河纵贯南北，带积雪岸坡、蓝色冰壳、裂纹和未封冻水面。**只有中央桥梁、北侧冰面和南侧冰面三处可以过河**；其他河段同时排除寻路和实际移动，也不能建造。三处渡口都保留宽阔通路供战象、重炮和编队通过。小地图在已探索区域显示河线和渡口。

相机正对东西方向，保持玩家基地在画面左侧、敌军来自右侧，并扩大缩放范围。出生位置改由地图内的 `StartingUnits` 原生标记布置，不再在控制器中写死旧地图坐标。

地形、碰撞、矿点、建筑和增援标记保存为原生 `.tscn`；原生 `GPUParticles3D` 表现飘雪，树林使用分块的原生 `MultiMeshInstance3D` 批量显示。导航源包含 19,826 个连通的一米网格，与 `ConstructionNavigation` 的动态施工占地契约一致。每个完整网格与障碍轮廓保持至少 1.15 米净空，避免大型单位沿格角行走时擦入水墙、树干或岩壁。河道水面、岸坡、物理阻挡和导航边界使用相同的曲线分段；地面沿河岸切开，避免重复铺面。几何与着色器直接适配项目的 3D 低多边形风格，没有新增栅格图像素材。

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
| `tools/snowfield_river.py` | 河岸、冰面、桥梁及其物理/导航边界 |
| `assets/defense/snowfield_minimap.gdshader` | 与地图共用河道曲线的小地图 |
| `tools/build_defense_audio.py` | 确定性重建原创钟声及来源元数据 |

`wave_started(index)`、`wave_cleared(index)` 信号和独立关卡 Resource 为后续波间选择、遗物、强化与随机事件提供接入点。当前没有 Rogue 奖励选择或局外成长系统。单人防卫数据不参与联机内容指纹。

## 验证

Godot 4.6.3，Windows，Forward+。

- `tests/defense_mode_test.gd`：57 项通过；真实经济与建造、6 处大体型出兵口和整条导航路线、暂停、清波倒计时、削弱与边界增援、末波待出兵检查、原始基地失败判定。
- `tests/defense_terrain_test.gd`：50 项通过；开放水域阻挡移动和建造、三处渡口双向大型碰撞体净空及真实战象行军、跨河谷寻路、内部高地/树林碰撞、八矿全部 48 个采矿位置。原生路径查询使用实际单位的搜索配置，并等待初始建筑占地发布。
- `tests/defense_battle_probe.gd`：首波全程实际行军和交战；敌军抵达西侧后，向初始六名军事单位下达正常攻击移动命令，在约 79 秒模拟时间内清除首波，大本营保持 3000 生命。侧翼敌军可能超出静止守军的自动索敌范围，需要玩家调兵。测试没有传送单位、修改伤害或增添守军；完整十波难度仍需试玩调校。
- `tests/defense_visual_review.gd`：大厅入口、实际开局、警钟提示，以及关闭迷雾用于美术检查的地图总览、两侧基地、冰河与北侧冰面细节；Forward+ 渲染无着色器错误。
- 本次地形改版记录保存在本机 `artifacts/defense_terrain/`，内容清单检查通过。首版大厅 UI 回归 228 项通过，历史记录保存在 `artifacts/defense/`。
- 原有 `hud_skirmish_display_test.gd` 为 151 项中的 147 项通过。四个失败分别是两项角色文案精确匹配、旧版建造按钮数量、旧版扩农民帮助说明；以修改前 HEAD 的 game/HUD/场景副本运行，得到完全相同的四项失败。本次未修改这些已有过期断言。

官方参考：[GPUParticles3D](https://docs.godotengine.org/en/stable/classes/class_gpuparticles3d.html)、[ParticleProcessMaterial](https://docs.godotengine.org/en/stable/classes/class_particleprocessmaterial.html)、[NavigationRegion3D](https://docs.godotengine.org/en/stable/classes/class_navigationregion3d.html)、[MultiMesh](https://docs.godotengine.org/en/stable/classes/class_multimesh.html)、[ArrayMesh](https://docs.godotengine.org/en/stable/classes/class_arraymesh.html)、[ConvexPolygonShape3D](https://docs.godotengine.org/en/stable/classes/class_convexpolygonshape3d.html)。
