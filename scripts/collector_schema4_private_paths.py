"""Schema-4 path identities, captured once and carried across fresh SSH processes.

Prepended with the existing no-follow directory checker and upload helper.
The host key, fixed paths, account, owners and modes identify the deployment
target. Device/inode pairs bind that target for this execution, not forever.
"""

_unbound_checked_fd = checked_fd
PRIVATE_PATH_IDENTITY = None


def private_path_identity(value):
    paths = (BASE, *TARGETS)
    need(type(value) is dict and set(value) == set(paths), "PRIVATE_PATH_IDENTITY_REQUIRED")
    for pair in value.values():
        need(type(pair) is list and len(pair) == 2
             and all(type(number) is int for number in pair)
             and pair[0] >= 0 and pair[1] > 0, "PRIVATE_PATH_IDENTITY_INVALID")
    return {path: list(value[path]) for path in paths}


def checked_fd(api, path):
    need(PRIVATE_PATH_IDENTITY is not None, "PRIVATE_PATH_IDENTITY_REQUIRED")
    fd = _unbound_checked_fd(api, path, base_identity=tuple(PRIVATE_PATH_IDENTITY[BASE]))
    try:
        actual = api.fstat(fd)
        need([actual.st_dev, actual.st_ino] == PRIVATE_PATH_IDENTITY[path], "PRIVATE_ROOT_REPLACED")
        return fd
    except BaseException:
        api.close(fd)
        raise


def schema4_guard():
    identity(os)
    for path in TARGETS:
        inspect(os, path)
    need(all(not inside(ROOT, path) and not inside(path, ROOT) for path in PUBLIC), "PUBLIC_ROOT_OVERLAP")


def bind_private_paths(data, *, capture=False):
    global PRIVATE_PATH_IDENTITY
    if capture:
        need(data.get("action") == "prepare" and "private_path_identity" not in data
             and PRIVATE_PATH_IDENTITY is None, "PRIVATE_PATH_IDENTITY_RECAPTURE")
        measured = {}
        for path in (BASE, *TARGETS):
            # The existing checker still verifies fixed names, no-follow opens,
            # stat/open races, canonical paths, owners and modes. Once the base
            # has been measured, every remaining traversal must match it.
            base = tuple(measured[BASE]) if BASE in measured else None
            fd = _unbound_checked_fd(os, path, base_identity=base)
            try:
                actual = os.fstat(fd)
                measured[path] = [actual.st_dev, actual.st_ino]
            finally:
                os.close(fd)
    else:
        measured = data.get("private_path_identity")
    measured = private_path_identity(measured)
    need(PRIVATE_PATH_IDENTITY is None or PRIVATE_PATH_IDENTITY == measured,
         "PRIVATE_PATH_IDENTITY_REBIND")
    PRIVATE_PATH_IDENTITY = measured
    # A complete second pass proves stability before any lock or stage write.
    schema4_guard()
    return private_path_identity(PRIVATE_PATH_IDENTITY)


guard = schema4_guard
