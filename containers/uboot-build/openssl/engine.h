/* Shim for Fedora 44 (OpenSSL 3.5) which dropped <openssl/engine.h>
 * while libcrypto still exports the ENGINE API. U-Boot's host tools
 * (mkimage/fdt_add_pubkey) reference these declarations; per the sirius
 * port notes the tools are never used to sign anything here. */
#ifndef OSSL_ENGINE_SHIM_H
#define OSSL_ENGINE_SHIM_H

#include <openssl/ossl_typ.h>

typedef struct engine_st ENGINE;
typedef struct ui_method_st UI_METHOD;

ENGINE *ENGINE_by_id(const char *id);
int ENGINE_init(ENGINE *e);
int ENGINE_finish(ENGINE *e);
int ENGINE_free(ENGINE *e);
int ENGINE_set_default_RSA(ENGINE *e);
int ENGINE_ctrl_cmd_string(ENGINE *e, const char *cmd_name, const void *arg);
EVP_PKEY *ENGINE_load_private_key(ENGINE *e, const char *key_id,
                                  UI_METHOD *ui_method, void *callback_data);

#endif
