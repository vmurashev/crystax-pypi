#if defined(__ARM_ARCH_5TE__)
#include "ffitarget_armeabi.h"
#elif defined(__ARM_ARCH_7A__) && !defined(__ARM_PCS_VFP)
#include "ffitarget_armeabi_v7a.h"
#elif defined(__ARM_ARCH_7A__) && defined(__ARM_PCS_VFP)
#include "ffitarget_armeabi_v7a_hard.h"
#elif defined(__aarch64__)
#include "ffitarget_arm64_v8a.h"
#elif defined(__i386__)
#include "ffitarget_x86.h"
#elif defined(__x86_64__)
#include "ffitarget_x86_64.h"
#elif defined(__mips__) && !defined(__mips64)
#include "ffitarget_mips.h"
#elif defined(__mips__) && defined(__mips64)
#include "ffitarget_mips64.h"
#else
#error "Unsupported ABI"
#endif
