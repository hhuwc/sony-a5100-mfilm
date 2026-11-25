# M-Film for Sony ILCE-5100

以 HNGSeries 的 EOS M 2.0.2 版 M-Film 0.2.4 为基准。原版提交为 `84370e411ae8e106e8a4df5f094150a162707bcb`。安卓进程直接运行原版 720 × 480 C 画布、页面状态机、胶卷和暗房代码。ARW 入口读取 ILCE-5100 的 12 位 Sony ARW2，支持本次验证的 6048 × 4024 RGGB 布局。真机测试条件和目前的覆盖范围见 [验证记录](../validation/REPORT.md)。

## 安装和操作

固件 **3.10**、Android 2.3.7、API 10、armeabi-v7a 已覆盖安装并启动 [port19 签名 APK](dist/M-Film-0.2.4-ILCE5100-port19.apk)，机身回读的 APK 与发布文件逐字节一致。软件包名为 `org.mfilm.sony`。

port19 包含写卡与暗房恢复、取景测光、镜头读数和实体键修正，装卷时还会应用胶卷的白平衡微调和预览风格。结束胶卷时，左右选择操作，中间 OK 确认，MENU 取消。删除前的最后一页默认选中 Keep。port19 真机已打开胶卷架和取景器，Superia 400 已读回胶卷参数。实拍新文件、关闭触控后断开调试拍完一卷仍待验证。[port19 签名 APK](dist/M-Film-0.2.4-ILCE5100-port19.apk) · [校验和](dist/M-Film-0.2.4-ILCE5100-port19.apk.sha256) · [验证记录](../validation/REPORT.md)

在 Windows 命令行，把 CAMERA_IP 换为 Tweak → Developer 显示的地址。打开 Enable Wifi 和 Enable ADB，在相同局域网运行下列命令。

```powershell
adb connect CAMERA_IP:5555
adb -s CAMERA_IP:5555 install --no-streaming -r .\sony-port\dist\M-Film-0.2.4-ILCE5100-port19.apk
```

在机身应用程序列表启动 **MFilm**，图标是金色光圈中的 M。Wi-Fi 调试中断后，应用仍可从 APK 读取胶卷资源，向存储卡写入照片和卷记录。USB 安装可在机身选择 MTP，用 Sony-PMCA-RE 的 Install app 选择本地 APK，等安装器确认完成后断线。电脑以大容量存储模式读卡时可取回结果。此项目在这台机器上走通的安装通道为 Wi-Fi ADB。[PMCA 安装器](https://github.com/ma1co/Sony-PMCA-RE#installing-android-apps) · [Tweak 的 ADB 说明](https://github.com/ma1co/OpenMemories-Tweak#adb)

四个方向键移动当前焦点、候选项或放大区域，中间 OK 执行选中项。MENU 短按返回上一级或取消弹窗。图片缩放和取景放大只用快门旁的 W/T 拨杆，每拨一次回中后可以再拨。实体 ▶ 进入回看，在胶卷架查看当前胶卷的示例图，在取景或 Home 查看成片。机背 ? 执行当前页标出的辅助操作。

研究分支 port20 增加了长按 MENU 满 2 秒退出。短按在松手时返回，长按触发一次退出。快门写卡时等照片入卷，暗房工作时等当前任务关闭文件。这个手势已通过桌面按键测试，实体 MENU 的按住时序仍待真机验证。

如果希望放大检查细节，在 Settings → Print size 选 Large，用 Darkroom → Recipe 选择原胶卷重洗已结束的卷。α5100 横幅的 Large 是 3012 × 2012，Medium 是 2008 × 1341。port20 首次启动的默认值为 Medium，已有机身设置会继续使用。Small 只有 720 × 480，在相机上用 T 放大时，port20 会标出 Preview。[成片和性能调研](research/print-detail.md)

状态栏和按键名使用 15 px Barlow Bold，底栏及小字正文使用 18 px Barlow SemiBold，字号以 720 × 480 设计画布为准。标准构建直接打包项目内的小字号字库。用 Python 3.12、Pillow 13.0.0 运行 `python sony-port/fonts.py` 可从锁定版本的原版 Barlow 字体重新生成它。

| 屏幕 | 方向键 | 中间 OK、MENU 和其他实体键 |
|---|---|---|
| 胶卷架 | 左右选胶卷。上移到顶部分类后左右换分类，下移回胶卷。由胶卷按下移到底部操作栏，左右移动高亮。 | OK 装卷或执行高亮操作。? 切换待装卷的 36、24、12 张，▶ 看样片。进行中的卷须确认换卷。 |
| 样片、换卷弹窗 | 样片左右换片，下移到操作栏。弹窗用左右移动高亮。 | OK 执行选项；MENU 取消或返回胶卷架。 |
| 取景 | 左右移动底部 Home、Film、Darkroom、Prints 的焦点。使用取景放大时方向键移动放大区域。 | OK 打开选中项，手动过片时可选择 Wind。快门半按对焦、全按拍摄。▶ 打开成片，MENU 返回最近的菜单。要退出，在 Settings 选择 Exit to camera。 |
| Home、Roll | 上下选行或移动到底部操作栏。结束卷弹窗内左右移动高亮。 | OK 才会进入项目、确认结束或冲洗。MENU 返回或取消。 |
| 暗房 | 上下选卷，右移到操作栏，左右定位 Recipe、Delete、Develop 等当前可用操作。Recipe 窗口内左右选胶片。 | OK 开始用选定的配方另洗一版。MENU 取消。删除经过确认，ARW 保留。 |
| 冲洗 | 暂停确认框内左右移动高亮。下移可聚焦底部操作。 | ? 调暗；MENU 发起停止确认，MENU 再按取消；完成后 OK 或 ▶ 查看成片。 |
| 接触印样、单张成片 | 接触印样内上下左右移动照片光标；单张未放大时左右翻帧；放大后四向平移。 | OK 打开选中的照片。T 放大，W 缩小；单张全图再推 W 回到印样。小尺寸输出可用 2×、4× 显示放大，大尺寸优先读取高分辨率文件。MENU 返回。 |
| 设置 | 上下选择设置行；进入数值选择后左右移动候选位置。 | OK 进入、切换开关或应用候选值。MENU 取消待选值或返回上级。 |

### 同一张底片换配方

在 Darkroom 选中已结束的卷，按右进入底栏，选 **Recipe** 并按 OK。左右选配方，按 OK 冲洗整卷。完成后按 OK 打开这次冲洗的接触印样，再按 OK 看单张，推 T 看细节。

从 Prints 重新进入时，默认显示原版印样。要查看另一版，在印样最后一排按下进入底栏，左右选 **Version**，按 OK 在原版和已完成的版本间轮换。信息栏显示卷号、版本号和胶片名称。如果只有再洗版本，打开时显示最新的一版。

每次再洗独立保存在卡的 `MFILM/PRINTS/Rnnn/Pxxxxxxx/`。每帧有 JPEG 和预览 BMP，中、大尺寸另有 ZOM 放大文件，整卷有一张 SHEET.BMP。冲洗完成后整版才会出现在 Prints。若正在写卡时断电，未完成的 T 开头目录可能留在卡上。旧版生成的 `RnnnLxx` 目录仅含 JPEG，可在电脑上打开。升级前若旧版已覆盖预览，可用原 ARW 选回原配方重新冲洗。

成片 JPEG 记录 SONY、ILCE-5100、胶片配方，以及原始 ARW 里的拍摄时间和光圈。原片缺少某个字段时使用卷记录里的值。port14 起在机身已有的卷上再洗也能使用原片中的时间。

定焦镜头使用索尼取景放大辅助对焦，W 逐级退回全图。拍摄前程序退出取景放大，ARW 使用原始画幅。电动镜头的实际焦距变化需装上支持电动变焦的镜头核验。

使用自动对焦镜头时，半按显示机身的 AF 模式、对焦区域和对焦结果。机身提供曝光读数时同时显示快门速度。按住全按等候合焦就会拍摄一张，合焦前松开全按会取消这次待拍。显示 No focus 时松开再半按。程序沿用机身的 AF 区域。使用 Wide 时机身可在画面多处选择主体。手动对焦模式可直接全按拍摄，保留原版装饰性对焦屏。

固件 3.10 的实体 ▶ 键经 Sony 前台应用按键注册后可留在 M-Film。胶卷示例和实际拍摄成片在不同页面。[机身样片页](../validation/port4-physical-play-sample.png) · [实体键日志](../validation/port4-play.log)

原图留在 DCIM 的索尼照片文件夹。卷清单写在相应文件夹的 ROLL_nnn.TXT。小尺寸全彩 JPEG 和接触印样是独立文件，索尼的原生回放是否为新增 JPEG 建立索引须另行验证。通过 M-Film 自带的 Prints 页面查看预览。应用记录在卡上 MFILM/CAMERA.LOG 和 MFILM/FILMOS.LOG。在卡上 MFILM 目录创建空文件 TEST.ON，可在启动后记录实体键扫描码及页面画布到 VERIFY。截屏和磁盘日志会影响性能。

### 装卷时的机身设置

胶卷决定拍摄 ISO、色温和白平衡微调。port19 按 EOS M 原版的整档步进设置 ISO，胶卷架仍显示胶卷盒标称值。Portra 160 和 FP4 Plus 125 在这条拍摄路径上使用 ISO 200，Velvia 50 使用 ISO 100。机身曝光补偿和 AF 区域沿用拍摄者的设置。

取景和机身 JPEG 依胶卷选择索尼 Standard、Landscape 或 B&W，随后按机身公布的范围调整对比度、饱和度与锐度。黑白风格跳过饱和度。佳能锐度 3 映射到索尼 0，色调没有直接对应项。色表、颗粒和暗房 JPEG 由原版 C 暗房生成。正常释放相机或退卷时，应用尝试恢复本次自己改过的白平衡微调；意外断电后的机身设置仍待实测。

用固件 3.10 的真实卷清单、同一快门的 ARW 和相机 JPEG 可核对装卷效果。先按下文构建桌面菜单测试程序，再运行以下命令。第二条需要 ExifTool，会写出逐项差异，返回 0 表示原片和 JPEG 均与所选配方的预期字段相符。

```powershell
python sony-port/tests/stock_settings.py sony-port/dist/M-Film-0.2.4-ILCE5100-port19.apk validation/my-stock
python sony-port/tests/verify_stock_capture.py validation/my-stock/stocks.tsv C:\photos\ROLL_003.TXT C:\photos\DSC01126.ARW C:\photos\DSC01126.JPG validation/my-stock/capture.json
```

## 从源码构建

Windows x64，Git、Python 3.12。保持 sony-port 和各上游仓库为同级目录。NDK r16b 的构建工作目录应无空格。使用 Android Studio 打开 sony-port 目录编辑，也可在终端构建。Gradle 入口 cameraApk 调用同一个 Python 构建脚本。当前电脑实际执行的是以下命令。

```powershell
python .\sony-port\setup.py
python .\sony-port\build.py
```

当前源码构建到 `sony-port/dist/M-Film-0.2.4-ILCE5100-port19.apk`。将源码压缩包解压到新目录的 `sony-port` 子目录后，也可按上述命令构建。若需以原签名更新已安装的应用，用 `build.py --signing-dir 路径` 指向这台开发电脑备份的签名目录。首次在空目录构建会生成独立密钥。源码压缩包只包含可分发的项目文件。

Windows 桌面按键回归使用 Zig 0.13.0 编译项目中的 C 菜单。准备好上游源码和资源后，在项目根目录执行以下命令。`--raw` 接受 α5100 的 ARW，会在临时目录的独立副本上冲洗、回看、W/T 放大、取消和删除测试卷。省略 `--raw` 可运行使用模拟卡的子集。测试所用虚拟时钟仅用于驱动动画。

```powershell
python -m pip install --target sony-port/build/host-cc ziglang==0.13.0
python sony-port/tests/build_menu_scene.py
python sony-port/tests/menu_navigation.py sony-port/build/key-results --raw C:/Photos/example.ARW
```

也可在 `sony-port` 目录运行 `.\gradlew.bat cameraApk`。Wrapper 固定 Gradle 8.13 和发行包 SHA-256。Gradle 可使用 JDK 17，构建相机 APK 的子进程仍使用项目固定的 JDK 11。

打包时在新的临时目录编译 Java，APK 条目使用固定顺序和时间戳。在同一台开发机复用同一密钥构建两次，port14 的两份 APK 和从机身取回的 APK 三者 SHA-256 相同。不同电脑的对照仍待验证。[port14 构建与机身文件校验](../validation/port14-metadata/installed.txt)

setup.py 固定参考仓库提交、Temurin JDK 11.0.25+9、SDK Platform 28 r06、Build Tools 30.0.3 和 NDK r16b，并校验下载的压缩包。平台压缩包名中的 android-9 是 Android 9 / API 28，Build Tools 中的 android-11 是工具归档目录。build.py 生成 JNI 库、DEX 035 和 v1 签名 APK，执行 API 检查和验签。首次构建会生成本地密钥。离线备份 .signing 整个目录；在另一台电脑重新生成密钥会产生不同签名。发布文件校验和见 [SHA256SUMS.txt](dist/SHA256SUMS.txt)。

prepare.py 在 build/filmos 生成索尼版 C 源码，不改参考仓库。编译模式为 GNU99 与 GCC 4.9，原版用到 designated initializers、GCC attributes、分支预测和位计数内建函数。端口用到 GNU typeof。log2f 通过本机支持的 logf 实现。r16b 的 android-14 头文件配合 API 10 manifest，ABI 兼容性另外用真机系统库和 JNI 探针验证。探针可用 `adb shell am start -W -n org.mfilm.sony/.Probe` 启动。主界面是 `org.mfilm.sony/.FilmOS`。

换配方与回看的回归测试在机身上运行独立进程，使用原版脚本输入和移植后的 C 页面。以下命令在项目根目录运行，将现有 ARW 复制进随机命名的测试卷，保存在 `MFILM/VERIFY/`。脚本使用 Python 和 Pillow。从输出首行取得八字符测试目录名，可在下一条命令中替换 TEST_DIR。

```powershell
python sony-port/tests/build_darkroom_scene.py
python sony-port/tests/reprint_scene.py CAMERA_IP:5555 /mnt/sdcard/DCIM/100MSDCF/DSC01126.ARW validation/my-reprint
python sony-port/tests/darkroom_latency.py CAMERA_IP:5555 TEST_DIR validation/my-latency
python sony-port/tests/footer_render.py CAMERA_IP:5555 TEST_DIR validation/my-footer
python sony-port/tests/roll_development.py CAMERA_IP:5555 TEST_DIR 12 validation/my-roll12
```

要重现较早的底栏整屏重绘与按键调度方式，先给 `build_darkroom_scene.py` 加 `--port12-controls`，再把同一选项传给 `darkroom_latency.py`。速度测试报告中列明了机身 CPU 限制、样本数、计时起止和最长延迟。

Windows 桌面整卷回归可运行 `sony-port\tests\desktop_roll.cmd 原片绝对路径 新输出目录 36`。它在同一进程中给同一份原片分配 36 个帧号，分别冲洗，最后生成整卷接触印样。机身测试脚本接受 12、24 或 36 张；运行记录写在独立测试目录中，网络恢复后可用 `--collect 测试目录名` 继续取回结果。

桌面参考冲洗需要 Visual Studio C++ Build Tools。给出 ARW 和输出前缀的绝对路径，最后一个数是胶片索引（0 为 Portra 400）。参考工具和 APK 使用相同的 C 解码及冲洗代码。独立传感器参考使用 rawpy / LibRaw。

```cmd
sony-port\tests\reference.cmd C:\work\validation\camera.ARW C:\work\validation\portra-reference 0
```

参考工具可在胶卷索引后增加 S、M 或 L 来选择输出尺寸。用下面的命令复核三档机内输出，替换机身地址和卡上的真实 ARW。测试将 JPEG、预览和放大文件写到相机卡的 MFILM/VERIFY 并取回 JPEG。第四个参数指定电脑上的结果目录。

```powershell
python sony-port/tests/print_sizes.py CAMERA_IP:5555 /mnt/sdcard/DCIM/100MSDCF/DSC01126.ARW 4 validation/port11-sizes
```

## 写卡恢复验证

首次冲洗中途退出后，重新进入 Darkroom，选中同一卷并再次选择 Develop。已完成的帧沿用原尺寸，缺少输出的帧按这次选择的尺寸补洗。如果只缺整卷接触印样，暗房只重建这张印样。写入失败时终页显示 INCOMPLETE。单张放大文件用于 M 和 L 输出。

使用本机拍摄的 ARW，在 Windows 上复现中断与重新冲洗，可执行以下命令。测试需要 Zig 0.13 和 Pillow，输入照片会先复制到临时卡目录。

```powershell
python sony-port/tests/build_menu_scene.py --zig C:\tools\zig\zig.exe
python sony-port/tests/darkroom_restart.py C:\photos\DSC01126.ARW validation/my-restart
```

取景 HUD 的桌面对照可运行 `sony-port\tests\finder_hud.cmd`。默认输出到 `sony-port/build/finder-tests`。可用 `--background 图片绝对路径 --output 目录绝对路径` 指定同一张取景底图和输出目录。测试分别编译原版与移植版 C 绘制代码，核对四种样式的覆盖位置和亮红指示灯。[四种取景器的对照图](../validation/port16-finder/comparison.jpg)

写卡恢复测试使用 Windows x64、Visual Studio C++ Build Tools 和项目固定的 JDK。项目根目录执行 `sony-port\tests\capture_record.cmd`，测试只写本地临时目录。用 `python sony-port/tests/check_camera_apk.py sony-port/dist/M-Film-0.2.4-ILCE5100-port15.apk` 可在本工作区对照此前取回的相机系统库复核原生依赖。在机身运行三档输出脚本时，可用 `--apk` 指定与测试库配套的签名包。

## 上游项目与许可

Film OS 和机内冲洗来自 HNGSeries / M-Film，新增 Sony 端口按 GPL-2.0 提供。字体 Barlow 来自 Jeremy Tribby，使用 SIL OFL。色表沿用原版发布包，涉及 Pat David 和 Andrea Volpato 的 CC BY-SA 4.0 内容，原始归属、许可和转换细节见上游说明。Sony ARW2 行格式、色彩矩阵和 SR2 元数据读取参考 LibRaw 0.21.4。卡上照片只用于本地验证。[M-Film](https://github.com/HNGSeries/mfilm-canon-film-simulation/tree/v0.2.4) · [原版第三方说明](https://github.com/HNGSeries/mfilm-canon-film-simulation/blob/v0.2.4/THIRD_PARTY.md) · [LibRaw](https://github.com/LibRaw/LibRaw/tree/0.21.4)

