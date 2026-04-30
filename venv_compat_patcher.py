"""
Monkey patch for Python 3.9 compatibility with CrewAI.
"""

import sys
import typing

if sys.version_info < (3, 10):
    # Python 3.9 doesn't support `type1 | type2` syntax
    # CrewAI 0.5.0 uses this syntax, so we need to patch typing
    
    # First, try to import typing_extensions which has better support
    try:
        import typing_extensions
        sys.modules['typing'] = typing_extensions
    except ImportError:
        # If not available, create a workaround
        class UnionType:
            def __init__(self, lhs, rhs):
                self.lhs = lhs
                self.rhs = rhs
                self.__class_name__ = "UnionType"
            
            def __or__(self, other):
                return UnionType(self, other)
            
            __ror__ = __or__
            
            def __repr__(self):
                return f"Union[{self.lhs}, {self.rhs}]"
            
            def __getitem__(self, key):
                return typing._GenericAlias(self, key)
            
            def __hash__(self):
                return hash((type(self), self.lhs, self.rhs))
            
            def __eq__(self, other):
                return isinstance(other, UnionType) and (self.lhs, self.rhs) == (other.lhs, other.rhs)
        
        # Patch typing module
        typing.Union = type('Union', (), {
            '__or__': lambda self, other: UnionType(self, other)
        })
        
        print("✓ Applied Python 3.9 compatibility patch for CrewAI")
        
        # Now try to import again
        try:
            from crewai import Agent, Crew, LLM, Task
            print("✓ CrewAI imports successful after patch")
        except ImportError as e:
            print(f"✗ CrewAI import failed even after patch: {e}")
            sys.exit(1)
