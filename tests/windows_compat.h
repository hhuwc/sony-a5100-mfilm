#ifdef _MSC_VER
#include <intrin.h>
#define __attribute__(x)
#define __builtin_expect(x,v) (x)
static inline int __builtin_clz(unsigned v){unsigned long n;_BitScanReverse(&n,v);return 31-(int)n;}
#endif

