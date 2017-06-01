MODULES = {
    'cryptography':
    {
        'module-type'   : 'pyzip',
        'zip-spec'      : [{'home-dir': 'cryptography', 'prefix': 'cryptography'}],
        'target-type'   : 'file',
        'target-dir'    : 'site-packages',
        'target-name'   : 'cryptography.zip',
    },
    'cryptography-openssl':
    {
        'module-type'   : 'ndk-so',
        'home-dir'      : 'openssl',
        'ndk-name'      : '_cryptography_openssl',
        'target-type'   : 'python-so-module',
        'target-dir'    : 'site-packages',
        'target-name'   : '_cryptography_openssl',
    },
    'cryptography-constant-time':
    {
        'module-type'   : 'ndk-so',
        'home-dir'      : 'constant_time',
        'ndk-name'      : '_cryptography_constant_time',
        'target-type'   : 'python-so-module',
        'target-dir'    : 'site-packages',
        'target-name'   : '_cryptography_constant_time',
    },
    'cryptography-padding':
    {
        'module-type'   : 'ndk-so',
        'home-dir'      : 'padding',
        'ndk-name'      : '_cryptography_padding',
        'target-type'   : 'python-so-module',
        'target-dir'    : 'site-packages',
        'target-name'   : '_cryptography_padding',
    },
}
