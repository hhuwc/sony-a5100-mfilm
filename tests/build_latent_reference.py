"""Build Latent's own fltool for the same 32-bit camera, with its bundled JPEG codec."""
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[2]
out=root/"sony-port/build/latent-reference"
out.mkdir(exist_ok=True)
latent=root/"latent"
spec=(latent/"tools/libjpeg-sources.sh").read_text()
names=re.search(r'LIBJPEG_SOURCES="([^"]+)"',spec).group(1).split()
codec="../../../latent/vendor/libjpeg-turbo-2.1.5.1"
sources=["../../../latent/tools/fltool.c","../../../latent/jni/filmcore.c"]
sources.extend(f"{codec}/{n}.c" for n in names)
(out/"Android.mk").write_text("\n".join([
    "LOCAL_PATH := $(call my-dir)","include $(CLEAR_VARS)","LOCAL_MODULE := latent_reference",
    "LOCAL_SRC_FILES := "+" ".join(sources),
    "LOCAL_C_INCLUDES := $(LOCAL_PATH)/../../../latent/jni $(LOCAL_PATH)/../../../latent/jni/turbo $(LOCAL_PATH)/"+codec,
    "LOCAL_ARM_MODE := arm","LOCAL_CFLAGS := -std=gnu99 -O3 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0",
    "LOCAL_LDFLAGS := -Wl,--hash-style=sysv","LOCAL_LDLIBS := -lm","include $(BUILD_EXECUTABLE)",""
]), encoding="ascii")
subprocess.run([str(root/"toolchain/android-ndk-r16b/ndk-build.cmd"),
    "NDK_PROJECT_PATH="+out.as_posix(),"APP_BUILD_SCRIPT=Android.mk",
    "NDK_APPLICATION_MK="+(root/"sony-port/native/Application.mk").as_posix(),"-j6"],cwd=out,check=True)
