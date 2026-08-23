import sys, types
_m = types.ModuleType("resource")
_m.RLIMIT_AS = 9
_m.RLIM_INFINITY = -1
_m.getrlimit = lambda w: (_m.RLIM_INFINITY, _m.RLIM_INFINITY)
_m.setrlimit = lambda w, l: None
sys.modules.setdefault("resource", _m)
