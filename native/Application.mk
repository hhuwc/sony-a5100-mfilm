APP_ABI := armeabi-v7a
APP_PLATFORM := android-14
NDK_TOOLCHAIN_VERSION := 4.9
APP_OPTIM := release
# GCC 4.9 records its working directory in DWARF. The linker includes that
# data in the build ID even though the APK contains the stripped library.
NDK_DEBUG_ROOT := $(abspath $(NDK_ROOT))
APP_CFLAGS := -gno-record-gcc-switches -fdebug-prefix-map=$(NDK_PROJECT_PATH)=. -fdebug-prefix-map=$(subst /,\,$(NDK_PROJECT_PATH))=.
APP_CFLAGS += -fdebug-prefix-map=$(NDK_DEBUG_ROOT)=ndk -fdebug-prefix-map=$(subst /,\,$(NDK_DEBUG_ROOT))=ndk
