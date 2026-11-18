# polaris 内核编译（修复 DSI PLL 锁不上）

小米 MIX 2S（polaris）在 postmarketOS 上黑屏，根因是内核 DSI PHY 驱动的缺陷：

```
msm_dsi_phy ae94400.phy: dsi_pll_10nm_vco_prepare: DSI PLL(0) lock failed, status=0x00000000
```

`dsi_pll_enable_pll_bias()` 启动 PLL 时只置了 `REG_DSI_10nm_PHY_CMN_CTRL_0` 的 `BIT(5)`
（PLL bias），没有置 `BIT(6)`（digital top 上电）。时钟框架在 probe 阶段按设备树
`assigned-clock-parents` 提前调用 `vco_prepare`，此时 PHY 还没 enable，digital top 仍处于
掉电状态，PLL 无法锁定。

本仓库把 `BIT(5)` 改为 `BIT(6) | BIT(5)`，让 digital top 与 PLL bias 一起上电。
正常上电路径不受影响（`dsi_10nm_phy_enable()` 本来就会写 `0x7f`）。

上游参考：Luca Weiss / Dmitry Baryshkov，dri-devel 2026-09，
"drm/msm/dsi/phy: power up the digital top before starting the 7nm PLL"。

## 文件

| 文件 | 作用 |
|---|---|
| `.github/workflows/build.yml` | GitHub Actions 工作流：下载 7.1-rc1 源码 → 打补丁 → 编译 arm64 Image → 上传产物 |
| `config.txt` | 从设备上运行中的 `vmlinuz` 提取的真实内核配置（`IKCFG_ST` 段） |
| `patch_dsi.py` | 打补丁脚本，会校验目标行出现次数必须为 1，防止改错 |

## 用法

1. 在 GitHub 建一个空仓库（Private 也行）。
2. 把本目录所有文件（含 `.github/`）推上去。
3. 仓库页面 → **Actions** → 左侧 "Build polaris kernel (DSI PLL fix)" → **Run workflow**。
4. 等 20~30 分钟。
5. 在运行结果页底部下载 `polaris-Image-7.1-rc1` 压缩包，里面是 `Image`。

## 拿到 Image 之后

用 adb 把它推到 ESP 分区替换原来的 `Image`（建议先备份原文件）：

```
adb push Image /data/local/tmp/Image
adb shell su -c 'mkdir -p /mnt/e; mount -t vfat /dev/block/by-name/mindowsesp /mnt/e'
adb shell su -c 'cp /mnt/e/Image /data/local/tmp/Image.bak'
adb shell su -c 'cp /data/local/tmp/Image /mnt/e/Image; sync; umount /mnt/e'
```

然后重启，在菜单选 postmarketOS。屏幕能亮即说明修复有效。

## 备注

- 关掉了 `DEBUG_INFO` / `DEBUG_INFO_BTF` 以缩短编译时间，不影响任何功能。
- 原内核用 Clang 编译，这里用 gcc（`olddefconfig` 会自动切换 `CC_IS_*` 选项）。
- 若 `patch_dsi.py` 报 "expected exactly 1 occurrence"，说明源码版本变了，需要重新核对目标行。
