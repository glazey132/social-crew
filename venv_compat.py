"""
Python 3.9 compatibility shim to fix crewai union type issues.
Monkey-patch to add | operator support for types.
"""
import sys
import types
import builtins

# For Python 3.9, we need to manually set __class_getitem__ for TypeUnion
# This allows the | operator to work with types like "str | None"

if sys.version_info < (3, 10):
    import typing
    from typing import _GenericAlias
    
    class UnionType:
        """Minimal UnionType for Python 3.9"""
        def __init__(self, lhs, rhs):
            self.lhs = lhs
            self.rhs = rhs
            self.origin = type(None)
            self.args = (lhs, rhs)
        
        def __or__(self, other):
            return UnionType(self, other)
        
        __ror__ = __or__
        
        def __repr__(self):
            return f"{self.lhs} | {self.rhs}"
        
        def __getitem__(self, key):
            return _GenericAlias(self, key)
        
        def __hash__(self):
            return hash((type(self), self.lhs, self.rhs))
        
        def __eq__(self, other):
            return isinstance(other, UnionType) and (self.lhs, self.rhs) == (other.lhs, other.rhs)
    
    # Monkey-patch the sys module
    sys.intern = sys.intern
    
    # Make UnionType work with typing module
    if not hasattr(typing, '_SpecialForm'):
        typing._SpecialForm = type
    
    # Install the union operator
    UnionType.__init__(builtins, object)
    
    # Patch typing to use UnionType
    def _make_union_type(lhs, rhs):
        return UnionType(lhs, rhs)
    
    # Add to typing namespace
    typing.Union.__or__ = lambda self, other: UnionType(self, other)

print("✓ Python 3.9 compatibility shim loaded")
