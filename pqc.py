"""Root backward-compatible shim for core.crypto.pqc"""
from core.crypto.pqc import *
from core.crypto.pqc import __all__

if __name__ == "__main__":
    from core.crypto.pqc import main
    main()
