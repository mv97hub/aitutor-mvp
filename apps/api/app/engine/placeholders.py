"""Fixed placeholder objects for layers 5, 6, and 7.

Nothing in these layers is inferred. The assembler always receives them.
"""

from app.engine.types import Layer5Affect, Layer6Metacognition, Layer7Memory


def affect_layer() -> Layer5Affect:
    return Layer5Affect(praise="growth-mindset-only")


def metacognition_layer() -> Layer6Metacognition:
    return Layer6Metacognition(self_explanation="one-line")


def memory_layer() -> Layer7Memory:
    return Layer7Memory(schedule="none")
