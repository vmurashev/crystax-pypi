LOCAL_PATH := $(call my-dir)
include $(CLEAR_VARS)
LOCAL_MODULE := _cffi_backend
LOCAL_C_INCLUDES := $(LOCAL_PATH)/../../libffi/include

LOCAL_SRC_FILES := \
  src/_cffi_backend.c \
  ../../libffi/src/prep_cif.c \
  ../../libffi/src/types.c

ifeq ($(TARGET_ARCH_ABI),arm64-v8a)
    LOCAL_SRC_FILES += \
        ../../libffi/src/aarch64/ffi.c \
        ../../libffi/src/aarch64/sysv.S
else ifeq ($(TARGET_ARCH_ABI),armeabi)
    LOCAL_SRC_FILES += \
        ../../libffi/src/arm/ffi.c \
        ../../libffi/src/arm/sysv.S
else ifeq ($(TARGET_ARCH_ABI),armeabi-v7a)
    LOCAL_SRC_FILES += \
        ../../libffi/src/arm/ffi.c \
        ../../libffi/src/arm/sysv.S
else ifeq ($(TARGET_ARCH_ABI),armeabi-v7a-hard)
    LOCAL_SRC_FILES += \
        ../../libffi/src/arm/ffi.c \
        ../../libffi/src/arm/sysv.S
else ifeq ($(TARGET_ARCH_ABI),mips)
    LOCAL_SRC_FILES += \
        ../../libffi/src/mips/ffi.c \
        ../../libffi/src/mips/o32.S
else ifeq ($(TARGET_ARCH_ABI),mips64)
    LOCAL_SRC_FILES += \
        ../../libffi/src/mips/ffi.c \
        ../../libffi/src/mips/o32.S \
        ../../libffi/src/mips/n32.S
else ifeq ($(TARGET_ARCH_ABI),x86)
    LOCAL_SRC_FILES += \
        ../../libffi/src/x86/ffi.c \
        ../../libffi/src/x86/sysv.S \
        ../../libffi/src/x86/win32.S
else ifeq ($(TARGET_ARCH_ABI),x86_64)
    LOCAL_SRC_FILES += \
        ../../libffi/src/x86/ffi64.c \
        ../../libffi/src/x86/unix64.S
else
  $(error Not a supported TARGET_ARCH_ABI: $(TARGET_ARCH_ABI))
endif


LOCAL_STATIC_LIBRARIES := python_shared
include $(BUILD_SHARED_LIBRARY)
$(call import-module,python/3.5)
