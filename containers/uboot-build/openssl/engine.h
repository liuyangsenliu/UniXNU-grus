/* Shim for Fedora 44 (OpenSSL 3.5) which dropped <openssl/engine.h>
 * while libcrypto still exports the ENGINE API. U-Boot host tools only
 * include the header; per the sirios port notes a declaration-only
 * header is sufficient (the tools are never used to sign anything). */
#ifndef OSSL_ENGINE_SHIM_H
#define OSSL_ENGINE_SHIM_H

typedef struct engine_st ENGINE;
typedef struct ui_method_st UI_METHOD;

#endif
