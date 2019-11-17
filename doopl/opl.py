# --------------------------------------------------------------------------
# Source file provided under Apache License, Version 2.0, January 2004,
# http://www.apache.org/licenses/
# (c) Copyright IBM Corp. 2018
# --------------------------------------------------------------------------

try:
    from doopl.internal.opl1290.opl import *
except:
    try:
        from doopl.internal.opl1280.opl import *
    except Exception as u:
        import traceback
        traceback.print_exc()
        raise ImportError('Could not import OPL wrappers. Make sure than OPL bin directory is in the PATH')

class OplRuntimeException(Exception):
    '''The exception thrown by doopl methods when an error occurs
    '''
    pass