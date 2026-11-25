# α5100 成片放大检查

2026-11-25。稳定基线为 port19，提交 `f041652`。研究分支为 `research/image-quality`。本次使用机身卡上的实际成片、对应 ARW、同一次快门的索尼 JPEG，以及同一张 ARW 的桌面参考。实拍照片只保存在这台电脑。

## 卡上实际交付的尺寸

卷 003 使用 Superia 400。DCIM/NOV1125 里的 DSC01122 至 DSC01126 五张胶片 JPEG 全部是 720 × 480。佳能 0.2.4 将初始 print_size 设为 1，即 Medium。索尼 port19 的状态初始化省略了 FS_SIZE，新装时 C 将它初始化为 0，即 Small。已有卷实际使用 Small 的原因还可能包括用户手动选择。研究分支补齐初始值，已有偏好依旧从卡上读取。

| 档位 | 这台 α5100 的横幅输出 | 相对 S 的像素数 | 已有机身单张耗时 | 已有机身峰值 RSS |
| --- | --- | ---: | ---: | ---: |
| S | 720 × 480 | 1.0 倍 | 8.99 s | 9,036 KiB |
| M | 2008 × 1341 | 7.8 倍 | 16.47 s | 25,016 KiB |
| L | 3012 × 2012 | 17.5 倍 | 25.36 s | 44,532 KiB |

耗时来自固件 3.10，上一次在机身以 DSC01126.ARW、Superia 400、CPU 3、双线程预读实测。每档一次，卡缓存未重置。研究分支沿用此显影算法。另一次同一输入、Velvia 50 的前台条件测试，在 CPU 3 上预读将平均单张时间从 19.68 s 降到 16.46 s。放大回看与显影是两段不同的工作。[三档原始记录](../../validation/port11-print-sizes.txt) · [内存记录](../../validation/port11-sizes/results.txt) · [预读对照](../../validation/port14-latency/results.txt)

## 同一快门的细节

卷 004 第一张 DSC01127 是 Ektar 100，唯卓仕 28mm，f/4.5、1/500 s、ISO 100、+0.7 EV。其 ARW 和机身 JPEG 都记录了 Landscape、5500 K、白平衡微调 0/0、对比度 +1、饱和度 +2、锐度 0。检查器现能将 ExifTool 的 `+1` 与整数 1 正确比较。当天的三档胶片输出均在电脑上用移植版 C 暗房从这张 ARW 独立显影。

对照图上排是同一视野，下排是同一扇窗与晾衣架。S 放大后细窗框和支架融在一起；M 已经分出斜撑，L 的窗框边缘和支架线条更清楚。机身 JPEG 另有索尼自己的锐化和色调。LibRaw 参考使用 AHD、拍摄白平衡、sRGB、关闭自动增亮，以便单独查看 RAW 中的结构；它的亮度不用于给胶片效果评分。额外的三种胶卷对照固定为 M 尺寸和同一曝光。[尺寸与窗框局部](../build/image-quality/figures/daylight-comparison.jpg) · [三款配方](../build/image-quality/figures/daylight-stocks.jpg) · [像素取样数据](../build/image-quality/figures/daylight-metrics.json)

提高尺寸对这张片子的颜色影响很小。统一缩放到 720 × 480 后，同一片天空的平均 RGB，S 是 165/186/209，M 和 L 也都是 165/186/209。室内卷还有拍摄时的因素：第 1–3 张都是 1/4 s，第 5 张是 1/13 s，第 3 张的索尼原始 JPEG 中也能看见重影。[室内拍摄记录](../../validation/port10-focus-latest.txt) · [第 3 张原片局部](../../validation/DSC01124-100pct.jpg)

已从卷 003 的第 1、2、5 张原始 ARW 生成同配方、同帧号的 S/M/L 副本。三张桌面 S 与卡上对应成片解码后的 RGB 均逐像素一致。第 3 张 ARW 在传输途中 Wi-Fi ADB 断线，第 4 张未传完这一轮的取片流程；两张都未用于高分辨率重洗。卡上的五张 JPEG 均已取回。卷 004 的第一张也已有三档输出。黑白、肤色或镜头分辨率的普遍结论需要更多场景。[卷 003 的 Large 副本](../build/image-quality/roll003/L/) · [卷 004 的 Large 副本](../build/image-quality/roll004/L/)

## W/T 回看

打开 S 成片后，T 会放大 720 × 480 的预览，继续推到 4× 仍只有原预览的细节。研究包在小地图的倍率前标明 Preview。M/L 会从配套 ZOM 读取显影时生成的高分辨率索引图，末级缩放可逐像素查看。JPEG 保留独立的全彩输出。

原实现为一次缩放预留整个视口的源行。研究分支改成每次连续读取 8 行输出对应的源数据。以横幅 L 及可用的最大采样步长 2 计算，读图缓冲从 2,891,520 字节降为 48,192 字节。两种方式顺序读取的文件总字节数相同。桌面检查覆盖 116 个窗口，包括四种采样步长、横竖幅、边缘、非整批末行及截短文件。该数字仅指这一项缓冲分配，机身整进程峰值及拨杆到刷新耗时待复测。

## 佳能用户与其他 RAW 软件的经验

- EOS M 用户反馈过直幅明显比横幅软。原作者在同一讨论中核实，当时的直幅成片只有 320 × 480。此次 α5100 楼房是横幅，单用 720 × 480 也重现了放大后细节丢失。现有 α5100 直幅 M 样片已验证为 1341 × 2008。[佳能用户讨论 #6](https://github.com/HNGSeries/mfilm-canon-film-simulation/issues/6) · [α5100 直幅测试](../../validation/portrait-target/README.md)
- 一位佳能使用者实拍了 Ektar、Portra、Gold 等，并尽量固定场景来比较配方。我们沿用同景比较，进一步固定同一份 RAW、帧号和输出尺寸。[佳能实拍与对照](https://note.com/maximum_aperture/n/n3c4ab9b89e3d)
- PIXLS.US 的索尼 A6000 用户固定输入比较两种颜色配置，评论者对更鲜艳的版本意见并不一致。此处只借用对比方法。α5100 的测试保留原配方，独立渲染一份 LibRaw 参考来检查窗框等结构。[索尼用户的 RAW 对比](https://discuss.pixls.us/t/comparing-darktable-and-capture-one-input-color-profile-for-sony-a6000/9485)

## 复测

先按项目 README 准备依赖，运行 `python tests/build_menu_scene.py`。用 `tests/reprint_real_roll.py` 读取复制到电脑的卷清单和 ARW，在独立临时卡中运行 S/M/L 三次；输出保持原帧号。可用 `--frames 1 2 5` 指定已有原片。尺寸、配方实验和机身文件分目录存放。

```powershell
python tests/reprint_real_roll.py build/image-quality/capture/ROLL_003.TXT build/image-quality/roll003 --raw-dir build --frames 1 2 5
python tests/reprint_real_roll.py build/image-quality/capture/ROLL_004.TXT build/image-quality/roll004
python tests/print_quality_comparison.py build/image-quality/capture/DSC01127.ARW build/image-quality/capture/DSC01127.JPG build/image-quality/roll004 build/image-quality/figures
```
