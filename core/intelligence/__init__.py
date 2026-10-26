"""
Neural Intelligence, Heuristics & Game Theoretic Solvers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Multi-model inference routing, CFR+ equilibrium solver, opponent profiling,
and FAISS-backed memory store.
"""

from .processor import AIProcessor, AnalysisResult
from .router import AIRouter
from .dossier import DossierManager
from .equity import calculate_equity_fast, range_vs_range, multi_way_equity
from .nash import Player as NashPlayer, train as train_nash
from .engine import PokerGame, HandEvaluator, Card, Deck
from .vector_store.faiss_store import HandVectorStore

__all__ = [
    "AIProcessor",
    "AnalysisResult",
    "AIRouter",
    "DossierManager",
    "calculate_equity_fast",
    "range_vs_range",
    "multi_way_equity",
    "NashPlayer",
    "train_nash",
    "PokerGame",
    "HandEvaluator",
    "Card",
    "Deck",
    "HandVectorStore",
]
