LOCAL_PATH := $(call my-dir)
include $(CLEAR_VARS)
LOCAL_MODULE := _cryptography_constant_time
LOCAL_SRC_FILES := _cryptography_constant_time.c
LOCAL_STATIC_LIBRARIES := python_shared
include $(BUILD_SHARED_LIBRARY)
$(call import-module,python/3.5)
