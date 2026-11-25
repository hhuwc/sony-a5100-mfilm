LOCAL_PATH := $(call my-dir)
include $(CLEAR_VARS)
LOCAL_MODULE := filmos
LOCAL_C_INCLUDES := $(LOCAL_PATH) $(LOCAL_PATH)/../build/filmos
FOS_FILES := gfx film ui shelf pages hud print dark dev lab looks jpeg
LOCAL_SRC_FILES := port.c display.c arw.c batch.c read_ahead.c editions.c master_prints.c capture_record.c finder_hud.c verification.c $(foreach f,$(FOS_FILES),../build/filmos/fos_$(f).c)
LOCAL_CFLAGS := -std=gnu99 -O2 -mtune=cortex-a5 -fno-math-errno -fno-strict-aliasing -Wno-unused-function -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0
LOCAL_ARM_MODE := arm
LOCAL_LDLIBS := -lm -llog -ljnigraphics -landroid
LOCAL_LDFLAGS := -Wl,--hash-style=sysv
include $(BUILD_SHARED_LIBRARY)

include $(CLEAR_VARS)
LOCAL_MODULE := mfilm_devtest
LOCAL_SRC_FILES := ../tests/develop.c
LOCAL_C_INCLUDES := $(LOCAL_PATH)/../build/filmos
LOCAL_CFLAGS := -std=gnu99
LOCAL_SHARED_LIBRARIES := filmos
include $(BUILD_EXECUTABLE)
