"""Root backward-compatible shim for core.intelligence.processor"""
from core.intelligence.processor import *
from core.intelligence.processor import __all__

if __name__ == "__main__":
    from core.intelligence.processor import main
    main()
