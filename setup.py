from __future__ import print_function
import sys
if sys.version_info[0] < 3:
    print("Python 3.x is required to proceed")
    exit(1)


import argparse
import configparser
import inspect
import os
import os.path
import shutil
import subprocess
import zipfile


DIR_HERE = os.path.normpath(os.path.abspath(os.path.dirname(__file__)))
DIR_OBJ = os.path.join(DIR_HERE, 'obj')
MODULES_CATALOG_FILE = os.path.join(DIR_HERE, 'catalog.ini')
BUILD_SPEC_FNAME = 'build.spec'
ABI_ALL = ['armeabi','armeabi-v7a','armeabi-v7a-hard','x86','mips','arm64-v8a','x86_64','mips64']

TAG_INI_CONF_MAIN = 'CONFIG'
TAG_INI_MODULES = 'PACKAGES'
TAG_INI_HOME_DIR = 'HOME_DIR'
TAG_INI_REQUIREMENTS = 'REQUIREMENTS'

TAG_BUILDSPEC_GRAMMAR_KEY_MODULES = 'MODULES'
TAG_BUILDSPEC_GRAMMAR_KEYS_ALL = [
    TAG_BUILDSPEC_GRAMMAR_KEY_MODULES,
]

TAG_BUILDSPEC_MOD_TYPE = 'module-type'
TAG_BUILDSPEC_TARGET_TYPE = 'target-type'
TAG_BUILDSPEC_TARGET_DIR  = 'target-dir'
TAG_BUILDSPEC_TARGET_NAME = 'target-name'
TAG_BUILDSPEC_ZIP_SPEC = 'zip-spec'
TAG_BUILDSPEC_HOME_DIR = 'home-dir'
TAG_BUILDSPEC_ZIP_PREFIX = 'prefix'
TAG_BUILDSPEC_ZIP_EXPLICIT = 'explicit'
TAG_BUILDSPEC_NDK_NAME = 'ndk-name'

TAG_BUILDSPEC_MOD_TYPE_PYZIP = 'pyzip'
TAG_BUILDSPEC_MOD_TYPE_NDK_SO = 'ndk-so'
TAG_BUILDSPEC_SUPPORTED_BUILD_TYPES = [TAG_BUILDSPEC_MOD_TYPE_PYZIP, TAG_BUILDSPEC_MOD_TYPE_NDK_SO]
TAG_BUILDSPEC_TARGET_TYPE_FILE = 'file'
TAG_BUILDSPEC_TARGET_TYPE_PYMOD_SO = 'python-so-module'
TAG_BUILDSPEC_SUPPORTED_TARGET_TYPES = [TAG_BUILDSPEC_TARGET_TYPE_FILE, TAG_BUILDSPEC_TARGET_TYPE_PYMOD_SO]
TAG_BUILDSPEC_SUPPORTED_TARGET_DIRECTORIES = ['site-packages']


def eval_ndk_dir():
    ndk_dir = None
    python_exe_dir = os.path.normpath(os.path.dirname(sys.executable))
    if len(python_exe_dir.split(os.path.sep)) >= 5:
        ndk_dir_variant = os.path.normpath(os.path.join(python_exe_dir, '../../../..'))
        python_for_android = 'sources/python/{}.{}/shared'.format(sys.version_info[0], sys.version_info[1])
        python_dir_for_android = os.path.normpath(os.path.join(ndk_dir_variant, python_for_android))
        if not os.path.isdir(python_dir_for_android):
            print("Directory not found '{}'.".format(python_dir_for_android))
        else:
            ndk_dir = ndk_dir_variant
    if ndk_dir is None:
        print("Cannot eval NDK root using '{}' as landmark.".format(python_exe_dir))
        print("Please use prebuilt python executable distributed with NDK to launch this script.")
        exit(126)
    print("::: resolved NDK location: '{}'.".format(ndk_dir))
    return ndk_dir


def load_ini_config(path):
    config = configparser.RawConfigParser()
    config.read(path)
    return config


def get_ini_conf_strings(config, section, option):
    return config.get(section, option).split()


def get_ini_conf_string1(config, section, option):
    return config.get(section, option).strip()


def get_ini_conf_strings_optional(config, section, option):
    if not config.has_option(section, option):
        return []
    return get_ini_conf_strings(config, section, option)


class PackageInfo:
    def __init__(self, pkgname, home_dir, requirements):
        self.pkgname = pkgname
        self.home_dir = home_dir
        self.requirements = requirements


def load_packages_catalog():
    if not os.path.isfile(MODULES_CATALOG_FILE):
        print("File with modules catalog not found: '{}'.".format(MODULES_CATALOG_FILE))
        exit(126)
    home_dirs_prefix = os.path.dirname(MODULES_CATALOG_FILE)
    config = load_ini_config(MODULES_CATALOG_FILE)
    pkg_names = get_ini_conf_strings(config, TAG_INI_CONF_MAIN, TAG_INI_MODULES)
    packages = {}
    for pkg in pkg_names:
        home_dir_ref = get_ini_conf_string1(config, pkg, TAG_INI_HOME_DIR)
        home_dir = os.path.normpath(os.path.join(home_dirs_prefix, home_dir_ref))
        requirements = get_ini_conf_strings_optional(config, pkg, TAG_INI_REQUIREMENTS)
        packages[pkg] = PackageInfo(pkg, home_dir, requirements)
    print("::: loaded information about {} packages from '{}'.".format(len(packages), MODULES_CATALOG_FILE))
    return packages


class BuildSystemException(Exception):
    def __init__(self, text, exit_code=None, frame=1):
        if exit_code is None:
            frame_info = inspect.stack()[frame]
            msg = '[{}({})] {}'.format(os.path.basename(frame_info[1]), frame_info[2], text)
        else:
            msg = text
        Exception.__init__(self, msg)
        self.exit_code = 126
        if exit_code is not None:
            self.exit_code = exit_code

    def to_exit_code(self):
        return self.exit_code


def load_build_spec(fname):
    grammar_tokens = {}
    for k in TAG_BUILDSPEC_GRAMMAR_KEYS_ALL:
        grammar_tokens[k] = None
    with open(fname, mode='rt') as file:
        source = file.read()
        try:
            ast = compile(source, fname, 'exec')
            global_vars = {}
            local_vars = {}
            exec(ast, global_vars, local_vars)
            for var_name in local_vars.keys():
                if var_name in TAG_BUILDSPEC_GRAMMAR_KEYS_ALL:
                    grammar_tokens[var_name] = local_vars[var_name]
        except SyntaxError as syntax:
            raise BuildSystemException("Invalid syntax: file: '{}', line: {}, offset: {}.".format(fname, syntax.lineno, syntax.offset))
    return grammar_tokens


def validate_module_spec(mod_name, build_spec_file, mod_info):
    mod_type = mod_info.get(TAG_BUILDSPEC_MOD_TYPE)
    mod_target_type = mod_info.get(TAG_BUILDSPEC_TARGET_TYPE)
    mod_target_dir = mod_info.get(TAG_BUILDSPEC_TARGET_DIR)
    mod_target_name = mod_info.get(TAG_BUILDSPEC_TARGET_NAME)

    if not isinstance(mod_type, str) or not mod_type:
        raise BuildSystemException(
            "Got malformed build specification '{}' - token '{}' is missed or malformed for module '{}'.".format(
                build_spec_file, TAG_BUILDSPEC_MOD_TYPE, mod_name))
    if mod_type not in TAG_BUILDSPEC_SUPPORTED_BUILD_TYPES:
        raise BuildSystemException(
            "Got malformed build specification '{}' - module '{}' - module type '{}' is unknown.".format(
                build_spec_file, mod_name, mod_type))

    if not isinstance(mod_target_type, str) or not mod_target_type:
        raise BuildSystemException(
            "Got malformed build specification '{}' - token '{}' is missed or malformed for module '{}'.".format(
                build_spec_file, TAG_BUILDSPEC_TARGET_TYPE, mod_name))
    if mod_target_type not in TAG_BUILDSPEC_SUPPORTED_TARGET_TYPES:
        raise BuildSystemException(
            "Got malformed build specification '{}' - module '{}' - module target type '{}' is unknown.".format(
                build_spec_file, mod_name, mod_target_type))

    if not isinstance(mod_target_dir, str) or mod_target_dir not in TAG_BUILDSPEC_SUPPORTED_TARGET_DIRECTORIES:
        raise BuildSystemException(
            "Got malformed build specification '{}' - token '{}' is missed or malformed for module '{}'.".format(
                build_spec_file, TAG_BUILDSPEC_TARGET_DIR, mod_name))

    if not isinstance(mod_target_name, str) or not mod_target_name:
        raise BuildSystemException(
            "Got malformed build specification '{}' - token '{}' is missed or malformed for module '{}'.".format(
                build_spec_file, TAG_BUILDSPEC_TARGET_NAME, mod_name))

    if mod_type == TAG_BUILDSPEC_MOD_TYPE_PYZIP:
        if len(mod_target_name) < 5 or not mod_target_name.endswith(".zip"):
            raise BuildSystemException(
                "Got malformed build specification '{}' - module '{}' - invalid target name '{}'.".format(
                    build_spec_file, mod_name, mod_target_name))
        zip_spec = mod_info.get(TAG_BUILDSPEC_ZIP_SPEC)
        if not isinstance(zip_spec, list) or not zip_spec:
            raise BuildSystemException(
                "Got malformed build specification '{}' - token '{}' is missed or malformed for module '{}'.".format(
                    build_spec_file, TAG_BUILDSPEC_ZIP_SPEC, mod_name))
        for zip_spec_part in zip_spec:
            if not isinstance(zip_spec_part, dict) or not zip_spec_part:
                raise BuildSystemException(
                    "Got malformed build specification '{}' - token '{}' is malformed for module '{}'.".format(
                        build_spec_file, TAG_BUILDSPEC_ZIP_SPEC, mod_name))
            xpl = zip_spec_part.get(TAG_BUILDSPEC_ZIP_EXPLICIT)
            if xpl is not None:
                zip_xpl_good = True
                if not isinstance(xpl, list) or not xpl:
                    zip_xpl_good = False
                if zip_xpl_good:
                    for xpl_part in xpl:
                        if not isinstance(xpl_part, str) or not xpl_part:
                            zip_xpl_good = False
                            break
                if not zip_xpl_good:
                    raise BuildSystemException(
                        "Got malformed build specification '{}' - in token '{}', subtoken '{}' is malformed for module '{}'.".format(
                            build_spec_file, TAG_BUILDSPEC_ZIP_SPEC, TAG_BUILDSPEC_ZIP_EXPLICIT, mod_name))

    elif mod_type == TAG_BUILDSPEC_MOD_TYPE_NDK_SO:
        ndk_name = mod_info.get(TAG_BUILDSPEC_NDK_NAME)
        if not isinstance(ndk_name, str) or not ndk_name:
            raise BuildSystemException(
                "Got malformed build specification '{}' - token '{}' is missed or malformed for module '{}'.".format(
                    build_spec_file, TAG_BUILDSPEC_NDK_NAME, mod_name))



def check_file_object(file_name):
    if not os.path.isfile(file_name):
        raise BuildSystemException("'{}' - file not found.".format(file_name))


def check_dir_object(dir_name):
    if not os.path.isdir(dir_name):
        raise BuildSystemException("'{}' - directory not found.".format(dir_name))


def enum_all_files(dname, prefix, catalog):
    subdirs = [(dname, prefix)]
    while subdirs:
        idx = len(subdirs) - 1
        subdir_path, subdir_archname = subdirs[idx]
        del subdirs[idx]
        for item in sorted(os.listdir(subdir_path)):
            if item in ['__pycache__'] or item.endswith('.pyc'):
                continue
            item_path = os.path.join(subdir_path, item)
            if subdir_archname:
                item_arcname = '/'.join([subdir_archname, item])
            else:
                item_arcname = item
            if os.path.isdir(item_path):
                subdirs.append((item_path, item_arcname))
            else:
                mt = os.path.getmtime(item_path)
                catalog.append((item_path, item_arcname, mt))


def enum_all_files_explicit(home_dir, prefix, xpl, catalog):
    for item in xpl:
        item_path = os.path.normpath(os.path.join(home_dir, item))
        check_file_object(item_path)
        mt = os.path.getmtime(item_path)
        location_and_name = item.rsplit('/', 1)
        if len(location_and_name) == 2:
            location, name = location_and_name[0], location_and_name[1]
        else:
            location, name = '', item
        if prefix:
            if location:
                location = '/'.join([prefix, location])
            else:
                location = prefix
        if location:
            item_arcname = '/'.join([location, name])
        else:
            item_arcname = name
        catalog.append((item_path, item_arcname, mt))


def load_zip_module_catalog(mod_name, mod_home_dir, mod_info, catalog):
    for zip_spec_part in mod_info[TAG_BUILDSPEC_ZIP_SPEC]:
        location = mod_home_dir
        location_subdir = zip_spec_part.get(TAG_BUILDSPEC_HOME_DIR)
        if isinstance(location_subdir, str) and location_subdir:
            location = os.path.normpath(os.path.join(mod_home_dir, location_subdir))
        check_dir_object(location)
        prefix = zip_spec_part.get(TAG_BUILDSPEC_ZIP_PREFIX, '')
        xpl = zip_spec_part.get(TAG_BUILDSPEC_ZIP_EXPLICIT)
        if xpl is None:
            enum_all_files(location, prefix, catalog)
        else:
            enum_all_files_explicit(location, prefix, xpl, catalog)


def zip_rebuild_required(zipfilename, catalog, extra_depends):
    if not os.path.exists(zipfilename):
        return True
    zip_mtime = os.path.getmtime(zipfilename)
    for dep in extra_depends:
        if zip_mtime < os.path.getmtime(dep):
            return True
    for entry in catalog:
        mt = entry[2]
        if zip_mtime < mt:
            return True
    return False


def build_zip_module(mod_name, pkg_info, mod_info, ndk_dir, abis):
    print("-------- BUILD ---------- '{}' ".format(mod_name))
    mod_obj_dir = os.path.join(DIR_OBJ, mod_name)
    if not os.path.isdir(mod_obj_dir):
        os.makedirs(mod_obj_dir)
    zipfilename = mod_info[TAG_BUILDSPEC_TARGET_NAME]
    zipfilepath = os.path.join(mod_obj_dir, zipfilename)
    catalog = []
    load_zip_module_catalog(mod_name, pkg_info.home_dir, mod_info, catalog)
    extra_depends = [ os.path.join(pkg_info.home_dir, BUILD_SPEC_FNAME) ]
    if not zip_rebuild_required(zipfilepath, catalog, extra_depends):
        print("::: python zip package '{}' is up-to-date.".format(zipfilepath))
        return
    print("::: compiling python zip package '{}' ...".format(zipfilepath))
    with zipfile.ZipFile(zipfilepath, "w", zipfile.ZIP_DEFLATED) as fzip:
        for entry in catalog:
            fname, arcname = entry[0], entry[1]
            fzip.write(fname, arcname)
            print("::: {} >>> {}/{}".format(fname, zipfilename, arcname))


def build_ndk_module(mod_name, pkg_info, mod_info, ndk_dir, abis):
    print("-------- BUILD ---------- '{}' ".format(mod_name))
    if sys.platform == 'win32':
        ndk_executor = os.path.normpath(os.path.join(ndk_dir, 'build/ndk-build.cmd'))
    else:
        ndk_executor = os.path.normpath(os.path.join(ndk_dir, 'build/ndk-build'))
    check_file_object(ndk_executor)
    mod_obj_dir = os.path.join(DIR_OBJ, mod_name)
    if not os.path.isdir(mod_obj_dir):
        os.makedirs(mod_obj_dir)
    location = pkg_info.home_dir
    location_subdir = mod_info.get(TAG_BUILDSPEC_HOME_DIR)
    if isinstance(location_subdir, str) and location_subdir:
        location = os.path.normpath(os.path.join(pkg_info.home_dir, location_subdir))
    check_dir_object(location)
    build_script = os.path.join(location, 'Android.mk')
    check_file_object(build_script)
    build_argv = [ndk_executor, '-C', location, 'V=1',
       'APP_ABI={}'.format(','.join(abis)),
       'APP_BUILD_SCRIPT={}'.format(build_script),
       'NDK_PROJECT_PATH={}'.format(mod_obj_dir)
    ]
    print("::: exec ::: {}".format(build_argv))
    exit_code = subprocess.call(build_argv)
    if exit_code == 0:
        print("::: done ::: [{}]".format(' '.join(build_argv)))
    else:
        raise BuildSystemException("Command completed with non-zero exit code: {}".format(build_argv), exit_code=exit_code)


def install_python_module(mod_name, pkg_info, mod_info, ndk_dir, abis):
    print("-------- INSTALL -------- '{}' ".format(mod_name))
    python_for_android = 'sources/python/{}.{}/shared'.format(sys.version_info[0], sys.version_info[1])
    python_dir_for_android = os.path.normpath(os.path.join(ndk_dir, python_for_android))
    mod_obj_dir = os.path.join(DIR_OBJ, mod_name)
    mod_type = mod_info[TAG_BUILDSPEC_MOD_TYPE]

    for abi in abis:
        mod_file_src = None
        if mod_type == TAG_BUILDSPEC_MOD_TYPE_PYZIP:
            mod_file_src = os.path.join(mod_obj_dir, mod_info[TAG_BUILDSPEC_TARGET_NAME])
        elif mod_type == TAG_BUILDSPEC_MOD_TYPE_NDK_SO:
            mod_obj_dir_abi = os.path.normpath(os.path.join(mod_obj_dir, 'obj/local/{}'.format(abi)))
            check_dir_object(mod_obj_dir_abi)
            mod_file = 'lib{}.so'.format(mod_info[TAG_BUILDSPEC_NDK_NAME])
            mod_file_src = os.path.join(mod_obj_dir_abi, mod_file)
        else:
            raise BuildSystemException(
                "Module type '{}' is unknown for install.".format(mod_type))

        check_file_object(mod_file_src)

        target_dir = os.path.normpath(os.path.join(python_dir_for_android, abi, mod_info[TAG_BUILDSPEC_TARGET_DIR]))
        check_dir_object(target_dir)
        target_file_name = None
        target_file_type = mod_info[TAG_BUILDSPEC_TARGET_TYPE]
        if target_file_type == TAG_BUILDSPEC_TARGET_TYPE_FILE:
            target_file_name = mod_info[TAG_BUILDSPEC_TARGET_NAME]
        elif target_file_type == TAG_BUILDSPEC_TARGET_TYPE_PYMOD_SO:
            target_file_name = '{}.so'.format(mod_info[TAG_BUILDSPEC_TARGET_NAME])
        else:
            raise BuildSystemException(
                "Module target type '{}' is unknown for install.".format(target_file_type))
        target_file_path = os.path.normpath(os.path.join(target_dir, target_file_name))

        print("::: {} >>> {}".format(mod_file_src, target_file_path))
        if os.path.exists(target_file_path):
            os.remove(target_file_path)
        shutil.copyfile(mod_file_src, target_file_path)


def process_package(pkg, pkg_catalog, builders, ndk_dir, abis, seen_packages, do_build, do_install):
    print("::: processing package '{}' ...".format(pkg))
    if pkg not in pkg_catalog:
        raise BuildSystemException("Got unknown package name '{}'.".format(pkg))
    pkg_info = pkg_catalog[pkg]
    build_spec_file = os.path.join(pkg_info.home_dir, BUILD_SPEC_FNAME)
    if not os.path.isfile(build_spec_file):
        raise BuildSystemException("Cannot find file with build specification '{}' while processing package '{}'.".format(build_spec_file, pkg))
    build_spec = load_build_spec(build_spec_file)
    modules = build_spec[TAG_BUILDSPEC_GRAMMAR_KEY_MODULES]
    if pkg not in seen_packages:
        seen_packages.append((pkg, modules))
    if not isinstance(modules, dict) or not modules:
        raise BuildSystemException("Got malformed build specification '{}' - token '{}' must be a non-empty dict.".format(build_spec_file, TAG_BUILDSPEC_GRAMMAR_KEY_MODULES))
    mod_names = [x for x in sorted(modules.keys()) ]
    for mod_name in mod_names:
        if not isinstance(modules[mod_name], dict):
            raise BuildSystemException("Got malformed build specification '{}' - module info '{}' must be a dict.".format(build_spec_file, mod_name))
        validate_module_spec(mod_name, build_spec_file, modules[mod_name])

    for required_pkg_name in pkg_info.requirements:
        print("::: package '{}' is required due to '{}'".format(required_pkg_name, pkg))
        process_package(required_pkg_name, pkg_catalog, builders, ndk_dir, abis, seen_packages, do_build, False)

    print("::: got {} module(s) for package '{}': '{}'".format(len(mod_names), pkg, ", ".join(mod_names)))
    for mod_name in mod_names:
        print("::: processing module '{}' from package '{}' ...".format(mod_name, pkg))
        if do_build:
            mod_type = modules[mod_name][TAG_BUILDSPEC_MOD_TYPE]
            build_function = builders.get(mod_type)
            if build_function is None:
                raise BuildSystemException(
                    "Module type '{}' is unknown for build, got from '{}'.".format(mod_type, build_spec_file))
            build_function(mod_name, pkg_info, modules[mod_name], ndk_dir, abis)

        if do_install:
            for required_pkg_name, requred_pkg_modules in seen_packages:
                if required_pkg_name == pkg:
                    continue
                for required_mod_name in sorted(requred_pkg_modules.keys()):
                    install_python_module(required_mod_name, pkg_info, requred_pkg_modules[required_mod_name], ndk_dir, abis)

            install_python_module(mod_name, pkg_info, modules[mod_name], ndk_dir, abis)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pkg', nargs=1)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--abi', nargs='*', choices=ABI_ALL)

    args = parser.parse_args()

    abis = args.abi[:] if args.abi is not None else ABI_ALL[:]
    ndk_dir = eval_ndk_dir()
    pkg_catalog = load_packages_catalog()

    builders = {
        TAG_BUILDSPEC_MOD_TYPE_PYZIP: build_zip_module,
        TAG_BUILDSPEC_MOD_TYPE_NDK_SO: build_ndk_module,
    }

    try:

        seen_packages = []
        process_package(args.pkg[0], pkg_catalog, builders, ndk_dir, abis, seen_packages, args.build, args.install)
        print("-------- DONE -----------")

    except BuildSystemException as exc:
        exit_code = exc.to_exit_code()
        print("ERROR({}): {}".format(exit_code, exc))
        exit(exit_code)
