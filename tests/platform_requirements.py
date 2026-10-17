"""Explicit test eligibility metadata, never a default unittest skip.

Only the named public-portable lane interprets these annotations. Ordinary
unittest discovery and the complete Linux public lane execute the real bodies.
"""


def requires_linux(reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('a concrete Linux capability requirement is mandatory')

    def annotate(target):
        target.__irisx_linux_requirement__ = reason
        return target
    return annotate


def linux_requirement(test):
    method = getattr(test, test._testMethodName)
    return (getattr(method, '__irisx_linux_requirement__', None) or
            getattr(type(test), '__irisx_linux_requirement__', None))
