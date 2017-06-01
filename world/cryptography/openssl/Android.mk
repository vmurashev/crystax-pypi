LOCAL_PATH := $(call my-dir)
include $(CLEAR_VARS)
LOCAL_MODULE := _cryptography_openssl
LOCAL_SRC_FILES := _cryptography_openssl.c
LOCAL_STATIC_LIBRARIES := python_shared openssl_static opencrypto_static
include $(BUILD_SHARED_LIBRARY)
$(call import-module,python/3.5)
$(call import-module,openssl/1.0.2h)
